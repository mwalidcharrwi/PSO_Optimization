"""SABRE-style SWAP routing (Li, Ding & Xie, ASPLOS 2019) and bidirectional
layout search, parameterised so that the swarm can tune the router.
"""
from __future__ import annotations

import random

from ..circuit import Circuit, Gate
from .devices import CouplingMap


def _dag(circ: Circuit):
    m = len(circ.gates)
    pred = [0] * m
    succ = [[] for _ in range(m)]
    last = [-1] * circ.n_qubits
    for i, g in enumerate(circ.gates):
        ps = set()
        for q in g.qubits:
            if last[q] >= 0:
                ps.add(last[q])
            last[q] = i
        pred[i] = len(ps)
        for p in ps:
            succ[p].append(i)
    return pred, succ


def sabre_route(circ: Circuit, cmap: CouplingMap, layout, ext_size: int = 20, weight: float = 0.5,
                decay_delta: float = 0.001, seed: int = 0, emit: bool = True):
    """Route ``circ`` (gates on <= 2 qubits) onto ``cmap``.

    ``layout[l]`` is the physical qubit of logical qubit ``l``.  Returns
    ``(physical circuit, final layout, n_swaps)``; the physical circuit uses
    ``swap`` gates for inserted SWAPs.
    """
    gates = circ.gates
    n_phys = cmap.n
    pred, succ = _dag(circ)
    l2p = list(layout)
    p2l = [-1] * n_phys
    for l, p in enumerate(l2p):
        p2l[p] = l
    dist = cmap.dist
    adj = cmap.adj
    front = [i for i in range(len(gates)) if pred[i] == 0]
    out: list[Gate] = []
    decay = [1.0] * n_phys
    rng = random.Random(seed)
    n_swaps = 0
    since_progress = 0
    since_reset = 0
    while front:
        exe = [i for i in front
               if len(gates[i].qubits) == 1 or l2p[gates[i].qubits[1]] in adj[l2p[gates[i].qubits[0]]]]
        if exe:
            exe_set = set(exe)
            newf = [i for i in front if i not in exe_set]
            for i in exe:
                g = gates[i]
                if emit:
                    out.append(Gate(g.name, tuple(l2p[q] for q in g.qubits), g.params, g.tag))
                for s in succ[i]:
                    pred[s] -= 1
                    if pred[s] == 0:
                        newf.append(s)
            front = newf
            decay = [1.0] * n_phys
            since_progress = since_reset = 0
            continue
        fq = [(gates[i].qubits[0], gates[i].qubits[1]) for i in front]
        if since_progress > 5 * n_phys:  # release valve: walk the first gate along a shortest path
            a, b = l2p[fq[0][0]], l2p[fq[0][1]]
            while b not in adj[a]:
                nxt = min(adj[a], key=lambda v: dist[v, b])
                _apply_swap(a, nxt, l2p, p2l, out, emit)
                n_swaps += 1
                a = nxt
            since_progress = 0
            continue
        # extended (look-ahead) set
        ext = []
        if ext_size > 0 and weight > 0:
            seen = set(front)
            queue = list(front)
            k = 0
            while queue and len(ext) < ext_size:
                i = queue.pop(0)
                for s in succ[i]:
                    if s not in seen:
                        seen.add(s)
                        queue.append(s)
                        if len(gates[s].qubits) == 2:
                            ext.append((gates[s].qubits[0], gates[s].qubits[1]))
                            if len(ext) >= ext_size:
                                break
                k += 1
        cands = set()
        for (u, v) in fq:
            for l in (u, v):
                p = l2p[l]
                for nb in adj[p]:
                    cands.add((p, nb) if p < nb else (nb, p))
        best, best_s = None, None
        nf, ne = len(fq), max(1, len(ext))
        for (a, b) in sorted(cands):
            def pos(l, a=a, b=b):
                p = l2p[l]
                return b if p == a else (a if p == b else p)
            hf = sum(dist[pos(u), pos(v)] for (u, v) in fq) / nf
            he = sum(dist[pos(u), pos(v)] for (u, v) in ext) / ne if ext else 0.0
            s = max(decay[a], decay[b]) * (hf + weight * he)
            if best_s is None or s < best_s - 1e-12 or (abs(s - best_s) <= 1e-12 and rng.random() < 0.5):
                best, best_s = (a, b), s
        a, b = best
        _apply_swap(a, b, l2p, p2l, out, emit)
        n_swaps += 1
        since_progress += 1
        decay[a] += decay_delta
        decay[b] += decay_delta
        since_reset += 1
        if since_reset >= 5:
            decay = [1.0] * n_phys
            since_reset = 0
    return Circuit(n_phys, out, circ.name, circ.meta), l2p, n_swaps


def _apply_swap(a, b, l2p, p2l, out, emit):
    la, lb = p2l[a], p2l[b]
    p2l[a], p2l[b] = lb, la
    if la >= 0:
        l2p[la] = b
    if lb >= 0:
        l2p[lb] = a
    if emit:
        out.append(Gate("swap", (a, b), (), ("swap",)))


def reverse_circuit(circ: Circuit) -> Circuit:
    return Circuit(circ.n_qubits, list(reversed(circ.gates)), circ.name)


def bidirectional_layout(circ: Circuit, cmap: CouplingMap, trials: int = 4, iterations: int = 3,
                         seed: int = 0, **params):
    """SabreLayout: forward/backward routing passes refine a random layout;
    the best of ``trials`` restarts (by SWAP count) is returned."""
    sw, layout = layout_candidates(circ, cmap, trials, iterations, seed, **params)[0]
    return layout, sw


def layout_candidates(circ: Circuit, cmap: CouplingMap, trials: int = 4, iterations: int = 3,
                      seed: int = 0, **params) -> list[tuple[int, list[int]]]:
    """All SabreLayout trial results as (n_swaps, layout), best first."""
    rng = random.Random(seed)
    n = circ.n_qubits
    rev = reverse_circuit(circ)
    res = []
    for t in range(trials):
        layout = list(range(n)) if t == 0 else rng.sample(range(cmap.n), n)
        for _ in range(iterations):
            _, fin, _ = sabre_route(circ, cmap, layout, seed=seed + t, emit=False, **params)
            _, layout, _ = sabre_route(rev, cmap, fin, seed=seed + t, emit=False, **params)
        _, _, sw = sabre_route(circ, cmap, layout, seed=seed + t, emit=False, **params)
        res.append((sw, list(layout)))
    res.sort(key=lambda r: r[0])
    return res


def lower_swaps(circ: Circuit) -> Circuit:
    """Replace SWAPs by 3 CNOTs, orienting each SWAP so that one of its CNOTs
    can cancel against an adjacent CNOT on the same pair."""
    gates = circ.gates
    n = circ.n_qubits
    last_on = [-1] * n
    prev_of = {}
    for i, g in enumerate(gates):
        if g.name == "swap":
            a, b = g.qubits
            pa, pb = last_on[a], last_on[b]
            prev_of[i] = pa if pa == pb else -1
        for q in g.qubits:
            last_on[q] = i
    nxt_on = [-1] * n
    next_of = {}
    for i in range(len(gates) - 1, -1, -1):
        g = gates[i]
        if g.name == "swap":
            a, b = g.qubits
            na, nb = nxt_on[a], nxt_on[b]
            next_of[i] = na if na == nb else -1
        for q in g.qubits:
            nxt_on[q] = i
    out = []
    for i, g in enumerate(gates):
        if g.name != "swap":
            out.append(g)
            continue
        a, b = g.qubits
        first = (a, b)
        p = prev_of.get(i, -1)
        nx = next_of.get(i, -1)
        if p >= 0 and gates[p].name == "cx":
            first = gates[p].qubits  # cancels with the preceding CNOT
        elif nx >= 0 and gates[nx].name == "cx":
            c, t = gates[nx].qubits  # last CNOT of the SWAP equals the next one
            first = (c, t)
        c, t = first
        tag = g.tag
        out.extend([Gate("cx", (c, t), (), tag), Gate("cx", (t, c), (), tag), Gate("cx", (c, t), (), tag)])
    return Circuit(n, out, circ.name, circ.meta)
