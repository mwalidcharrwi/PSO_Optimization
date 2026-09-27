"""Lowering to the base gate set {h, x, rz, cx} with *decomposition variants*.

Many gates have several equally-valid decompositions.  Classical compilers
fix one of them; HyPSO-QCO exposes the choice to the swarm.  Each
multi-variant gate instance ("variant site") has a small tuple of categorical
*factors*:

* ``ccz`` / ``ccx``  -> (network, polarity, T-placement)
      network   : one of the minimal CNOT parity networks enumerated by BFS
                  (108 six-CNOT networks for all-to-all connectivity, plus
                  12 eight-CNOT nearest-neighbour networks in hardware mode)
      polarity  : CCZ is self-inverse, so every T can be swapped with T-dagger
      placement : each T is placed at the first / last time its parity appears
* ``cz``  -> (which qubit carries the H pair,)
* ``swap``-> (CNOT orientation,)
* ``cp``/``cu1``/``crz`` -> (accumulator qubit, placement)
* ``rzz``/``rxx``/``rzx`` -> (accumulator qubit,)
* ``cswap`` -> (orientation,)   (+ the inner Toffoli is its own site)

Provenance: every emitted gate is tagged with a *key path* (tuple of ints),
the first element being the index of the gate in the input circuit.  The
choice callback receives the key path of the site and returns the chosen
factor tuple, which is how particles of the swarm steer the lowering.
"""
from __future__ import annotations

import math
from collections import deque
from functools import lru_cache
from typing import Callable

import numpy as np

from .circuit import PI, Circuit, Gate, is_zero_angle
from .linalg import zyz_angles

ChoiceFn = Callable[[tuple, tuple], tuple]

BASE_GATES = frozenset({"h", "x", "rz", "cx"})


# --------------------------------------------------------------------------- #
# CCZ parity networks (enumerated once by breadth-first search)
# --------------------------------------------------------------------------- #
# phase polynomial of CCZ on (a,b,c) with T = rz(pi/4):
#   pi*abc = pi/4 * (a + b + c - a^b - a^c - b^c + a^b^c)
_CCZ_SIGNS = {1: 1, 2: 1, 4: 1, 3: -1, 5: -1, 6: -1, 7: 1}
_NEED = {3: 0, 5: 1, 6: 2, 7: 3}
# Nielsen & Chuang's textbook network (wires a=0, b=1, c=2) -- used as default
_NC_NETWORK = ((1, 2), (0, 2), (1, 2), (0, 2), (0, 1), (0, 1))


def _enumerate_networks(moves: tuple) -> list[tuple]:
    start = ((1, 2, 4), 0)
    dist = {start: 0}
    parents: dict = {start: []}
    q = deque([start])
    goals, best = [], None
    while q:
        s = q.popleft()
        d = dist[s]
        if best is not None and d >= best:
            continue
        st, mask = s
        for (c, t) in moves:
            ns = list(st)
            ns[t] ^= ns[c]
            ns = tuple(ns)
            m = mask | (1 << _NEED[ns[t]]) if ns[t] in _NEED else mask
            n2 = (ns, m)
            if n2 not in dist:
                dist[n2] = d + 1
                parents[n2] = [(s, (c, t))]
                q.append(n2)
                if ns == (1, 2, 4) and m == 15:
                    best = d + 1
                    goals.append(n2)
            elif dist[n2] == d + 1:
                parents[n2].append((s, (c, t)))
    paths: list[tuple] = []

    def back(s, acc):
        if s == start:
            paths.append(tuple(reversed(acc)))
            return
        for p, mv in parents[s]:
            back(p, acc + [mv])

    for g in goals:
        back(g, [])
    return sorted(set(paths))


@lru_cache(maxsize=None)
def ccz_networks(topology: str = "full") -> tuple:
    """Minimal CNOT networks visiting all 7 parities of CCZ.

    ``topology``: ``"full"`` or ``"line0"``/``"line1"``/``"line2"`` (the index
    of the middle qubit of a nearest-neighbour line).
    """
    if topology == "full":
        moves = tuple((c, t) for c in range(3) for t in range(3) if c != t)
        nets = _enumerate_networks(moves)
        nets.remove(_NC_NETWORK)
        return tuple([_NC_NETWORK] + nets)
    m = int(topology[-1])
    o = [x for x in range(3) if x != m]
    moves = ((m, o[0]), (o[0], m), (m, o[1]), (o[1], m))
    return tuple(_enumerate_networks(moves))


@lru_cache(maxsize=None)
def ccz_template(network: tuple, polarity: int, placement: int) -> tuple:
    """Return the CCZ circuit on abstract wires 0,1,2 as a tuple of
    ('cx', c, t) / ('rz', w, sign, parity) instructions."""
    L = len(network)
    states = [(1, 2, 4)]
    for (c, t) in network:
        st = list(states[-1])
        st[t] ^= st[c]
        states.append(tuple(st))
    where: dict[int, tuple[int, int]] = {}
    times = range(L + 1) if placement == 0 else range(L, -1, -1)
    for tm in times:
        for w in range(3):
            p = states[tm][w]
            if p in _CCZ_SIGNS and p not in where:
                where[p] = (tm, w)
    assert len(where) == 7, "network does not realise every CCZ parity"
    sgn = 1 if polarity == 0 else -1
    by_time: dict[int, list] = {}
    for p, (tm, w) in where.items():
        by_time.setdefault(tm, []).append(("rz", w, sgn * _CCZ_SIGNS[p], p))
    out = []
    for tm in range(L + 1):
        out.extend(sorted(by_time.get(tm, [])))
        if tm < L:
            out.append(("cx",) + tuple(network[tm]))
    return tuple(out)


# --------------------------------------------------------------------------- #
# Lowering
# --------------------------------------------------------------------------- #
class Lowerer:
    """Lower arbitrary circuits into {h, x, rz, cx} with steerable variants.

    Parameters
    ----------
    topology_variants : bool
        Also offer nearest-neighbour (line) CCZ networks (hardware mode).
    max_networks : int | None
        Optionally cap the number of all-to-all CCZ networks exposed.
    """

    def __init__(self, topology_variants: bool = False, max_networks: int | None = None):
        self.topology_variants = topology_variants
        nets = list(ccz_networks("full"))
        if max_networks is not None:
            nets = nets[:max_networks]
        if topology_variants:
            for m in range(3):
                nets.extend(ccz_networks(f"line{m}"))
        self.networks = tuple(nets)

    # ------------------------------------------------------------------ #
    def variant_sizes(self, gate: Gate) -> tuple:
        n = gate.name
        if n in ("ccz", "ccx"):
            return (len(self.networks), 2, 2)
        if n in ("cz", "swap", "rzz", "cswap"):
            return (2,)
        if n in ("cp", "cu1", "crz"):
            return (2, 2)
        return ()

    def lower(self, circ: Circuit, choice: ChoiceFn | None = None) -> Circuit:
        out: list[Gate] = []
        n = circ.n_qubits
        for i, g in enumerate(circ.gates):
            self._lower(g, (i,), out, choice, n)
        res = Circuit(n, out, name=circ.name, meta=circ.meta)
        return res

    def sites(self, circ: Circuit) -> list[tuple[tuple, tuple]]:
        """All variant sites (key path, factor sizes) reached by the default lowering."""
        found: list[tuple[tuple, tuple]] = []

        def rec(key, sizes):
            found.append((key, sizes))
            return tuple(0 for _ in sizes)

        self.lower(circ, rec)
        return found

    # ------------------------------------------------------------------ #
    def _choose(self, g: Gate, key: tuple, choice: ChoiceFn | None) -> tuple:
        sizes = self.variant_sizes(g)
        if not sizes:
            return ()
        if choice is None:
            return tuple(0 for _ in sizes)
        v = tuple(choice(key, sizes))
        v = v + (0,) * (len(sizes) - len(v))
        return tuple(int(x) % s for x, s in zip(v, sizes))

    def _lower(self, g: Gate, key: tuple, out: list, choice, n: int):
        name, qs, ps = g.name, g.qubits, g.params
        v = self._choose(g, key, choice)
        sub: list[Gate] | None = None

        # ---------------- base gates ----------------
        if name in ("h", "x", "cx"):
            out.append(Gate(name, qs, (), key))
            return
        if name == "rz":
            if not is_zero_angle(ps[0]):
                out.append(Gate("rz", qs, (ps[0],), key))
            return
        if name == "id":
            return
        # ---------------- one-qubit ----------------
        rz_ang = {"z": PI, "s": PI / 2, "sdg": -PI / 2, "t": PI / 4, "tdg": -PI / 4}
        if name in rz_ang:
            sub = [Gate("rz", qs, (rz_ang[name],))]
        elif name in ("p", "u1"):
            sub = [Gate("rz", qs, ps)]
        elif name == "y":
            sub = [Gate("rz", qs, (PI,)), Gate("x", qs)]
        elif name == "rx":
            sub = [Gate("h", qs), Gate("rz", qs, ps), Gate("h", qs)]
        elif name == "ry":
            sub = _ry_gates(qs[0], ps[0])
        elif name == "sx":
            sub = [Gate("h", qs), Gate("rz", qs, (PI / 2,)), Gate("h", qs)]
        elif name == "sxdg":
            sub = [Gate("h", qs), Gate("rz", qs, (-PI / 2,)), Gate("h", qs)]
        elif name in ("u3", "u"):
            sub = _u3_gates(qs[0], *ps)
        elif name == "u2":
            sub = _u3_gates(qs[0], PI / 2, ps[0], ps[1])
        elif name == "unitary" and len(qs) == 1:
            _, b, c, d = zyz_angles(ps[0])
            sub = _u3_gates(qs[0], c, b, d)
        # ---------------- two-qubit ----------------
        elif name == "cz":
            a, b = qs if v[0] == 0 else qs[::-1]
            sub = [Gate("h", (b,), (), ("h", 0)), Gate("cx", (a, b), (), ("c", 0)), Gate("h", (b,), (), ("h", 1))]
        elif name == "swap":
            a, b = qs if v[0] == 0 else qs[::-1]
            sub = [Gate("cx", (a, b)), Gate("cx", (b, a)), Gate("cx", (a, b))]
        elif name == "dcx":
            sub = [Gate("cx", qs), Gate("cx", qs[::-1])]
        elif name == "cy":
            a, b = qs
            sub = [Gate("rz", (b,), (-PI / 2,)), Gate("cx", (a, b)), Gate("rz", (b,), (PI / 2,))]
        elif name in ("cp", "cu1", "crz"):
            a, b = qs
            lam = ps[0]
            if name == "crz":  # phase: lam/2*b - lam/2*(a^b)
                singles = [Gate("rz", (b,), (lam / 2,), ("s", 1))]
            else:  # phase: lam/2*a + lam/2*b - lam/2*(a^b)
                singles = [Gate("rz", (a,), (lam / 2,), ("s", 0)), Gate("rz", (b,), (lam / 2,), ("s", 1))]
            ctl, acc = (a, b) if v[0] == 0 else (b, a)
            core = [Gate("cx", (ctl, acc), (), ("c", 0)), Gate("rz", (acc,), (-lam / 2,), ("pp",)),
                    Gate("cx", (ctl, acc), (), ("c", 1))]
            sub = singles + core if v[1] == 0 else core + singles
        elif name == "rzz":
            ctl, acc = qs if v[0] == 0 else qs[::-1]
            sub = [Gate("cx", (ctl, acc), (), ("c", 0)), Gate("rz", (acc,), ps, ("pp",)),
                   Gate("cx", (ctl, acc), (), ("c", 1))]
        elif name == "rxx":
            a, b = qs
            sub = [Gate("h", (a,)), Gate("h", (b,)), Gate("rzz", qs, ps), Gate("h", (a,)), Gate("h", (b,))]
        elif name == "rzx":
            a, b = qs
            sub = [Gate("h", (b,)), Gate("rzz", qs, ps), Gate("h", (b,))]
        elif name == "ryy":
            a, b = qs
            pre = [Gate("rx", (a,), (PI / 2,)), Gate("rx", (b,), (PI / 2,))]
            post = [Gate("rx", (a,), (-PI / 2,)), Gate("rx", (b,), (-PI / 2,))]
            sub = pre + [Gate("rzz", qs, ps)] + post
        elif name == "iswap":
            sub = [Gate("rxx", qs, (-PI / 2,)), Gate("ryy", qs, (-PI / 2,))]
        elif name in ("ch", "csx", "crx", "cry", "cu3", "cu") or (name == "mcu" and len(qs) == 2):
            sub = _controlled_1q_gates(qs[0], qs[1], _target_matrix(g))
        elif name == "unitary" and len(qs) == 2:
            from .passes.kak import synthesize_2q
            sub = synthesize_2q(ps[0], qs[0], qs[1])
        # ---------------- three-qubit and larger ----------------
        elif name == "ccz":
            sub = self._ccz_gates(qs, v)
        elif name == "ccx":
            a, b, c = qs
            sub = [Gate("h", (c,), (), ("h", 0))] + self._ccz_gates(qs, v) + [Gate("h", (c,), (), ("h", 1))]
        elif name == "cswap":
            c, a, b = qs
            if v[0] == 0:
                sub = [Gate("cx", (b, a)), Gate("ccx", (c, a, b)), Gate("cx", (b, a))]
            else:
                sub = [Gate("cx", (a, b)), Gate("ccx", (c, b, a)), Gate("cx", (a, b))]
        elif name == "mcx":
            sub = mcx_gates(list(qs[:-1]), qs[-1], [q for q in range(n) if q not in qs])
        elif name == "mcz":
            t = qs[-1]
            sub = [Gate("h", (t,)), Gate("mcx", qs), Gate("h", (t,))]
        elif name == "mcu":
            sub = mcu_gates(list(qs[:-1]), qs[-1], np.asarray(ps[0], dtype=complex),
                            [q for q in range(n) if q not in qs])
        if sub is None:
            raise ValueError(f"cannot lower gate {g!r}")
        for j, s in enumerate(sub):
            sk = key + (s.tag if s.tag is not None else (j,))
            if s.name in BASE_GATES:
                if s.name == "rz" and is_zero_angle(s.params[0]):
                    continue
                out.append(Gate(s.name, s.qubits, s.params, sk))
            else:
                self._lower(s, sk, out, choice, n)

    def _ccz_gates(self, qs, v) -> list[Gate]:
        net = self.networks[v[0]]
        tpl = ccz_template(net, v[1], v[2])
        res = []
        ncx = 0
        for ins in tpl:
            if ins[0] == "cx":
                res.append(Gate("cx", (qs[ins[1]], qs[ins[2]]), (), ("c", ncx)))
                ncx += 1
            else:
                # semantic provenance: the parity term, identical in every variant
                res.append(Gate("rz", (qs[ins[1]],), (ins[2] * PI / 4,), ("p", ins[3])))
        return res


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _ry_gates(q: int, theta: float) -> list[Gate]:
    # Ry(t) = S Rx(t) S^dag  (circuit order: sdg, h, rz(t), h, s)
    return [Gate("rz", (q,), (-PI / 2,)), Gate("h", (q,)), Gate("rz", (q,), (theta,)),
            Gate("h", (q,)), Gate("rz", (q,), (PI / 2,))]


def _u3_gates(q: int, theta: float, phi: float, lam: float) -> list[Gate]:
    # U3 = Rz(phi) Ry(theta) Rz(lam)   (up to global phase)
    if is_zero_angle(theta):
        return [Gate("rz", (q,), (phi + lam,))]
    return [Gate("rz", (q,), (lam - PI / 2,)), Gate("h", (q,)), Gate("rz", (q,), (theta,)),
            Gate("h", (q,)), Gate("rz", (q,), (phi + PI / 2,))]


def _target_matrix(g: Gate) -> np.ndarray:
    """The single-qubit unitary applied to the target of a controlled gate."""
    if g.name == "mcu":
        return np.asarray(g.params[0], dtype=complex)
    return g.matrix()[2:, 2:]


def _controlled_1q_gates(c: int, t: int, u: np.ndarray) -> list[Gate]:
    """Controlled-U via the A X B X C construction (Barenco et al. 1995)."""
    alpha, beta, gamma, delta = zyz_angles(u)
    gates = [Gate("rz", (t,), ((delta - beta) / 2,)),  # C
             Gate("cx", (c, t))]
    gates += [Gate("rz", (t,), (-(delta + beta) / 2,))] + _ry_gates(t, -gamma / 2)  # B
    gates += [Gate("cx", (c, t))]
    gates += _ry_gates(t, gamma / 2) + [Gate("rz", (t,), (beta,))]  # A
    gates += [Gate("rz", (c,), (alpha,))]  # phase on control (p(alpha) ~ rz(alpha))
    return gates


def mcx_gates(ctrls: list[int], t: int, free: list[int]) -> list[Gate]:
    """Multi-controlled X using Toffolis and *dirty* (borrowed) ancillas."""
    k = len(ctrls)
    if k == 0:
        return [Gate("x", (t,))]
    if k == 1:
        return [Gate("cx", (ctrls[0], t))]
    if k == 2:
        return [Gate("ccx", (ctrls[0], ctrls[1], t))]
    if len(free) >= k - 2:  # Barenco et al. Lemma 7.2: 4(k-2) Toffolis
        a = free[: k - 2]
        c = ctrls
        top = Gate("ccx", (c[k - 1], a[k - 3], t))
        down = [Gate("ccx", (c[j + 1], a[j - 1], a[j])) for j in range(k - 3, 0, -1)]
        base = Gate("ccx", (c[0], c[1], a[0]))
        up = [Gate("ccx", (c[j + 1], a[j - 1], a[j])) for j in range(1, k - 2)]
        seq = [top] + down + [base] + up
        return seq + seq
    if free:  # split with one borrowed qubit (Barenco et al. Lemma 7.3)
        anc = free[0]
        m1 = (k + 1) // 2
        c1, c2 = ctrls[:m1], ctrls[m1:]
        f1 = [q for q in free[1:]] + c2 + [t]
        f2 = [q for q in free[1:]] + c1
        g1 = mcx_gates(c1, anc, f1)
        g2 = mcx_gates(c2 + [anc], t, f2)
        return g1 + g2 + g1 + g2
    # no ancilla at all: C^k X = C^k(U=X) via square-root recursion
    return mcu_gates(ctrls, t, np.array([[0, 1], [1, 0]], dtype=complex), [])


def _sqrtm_2x2(u: np.ndarray) -> np.ndarray:
    w, vecs = np.linalg.eig(u)
    return vecs @ np.diag(np.sqrt(w)) @ np.linalg.inv(vecs)


def mcu_gates(ctrls: list[int], t: int, u: np.ndarray, free: list[int]) -> list[Gate]:
    """Multi-controlled single-qubit U (Barenco et al. Lemma 7.5 recursion)."""
    k = len(ctrls)
    if k == 0:
        return [Gate("unitary", (t,), (u,))]
    if k == 1:
        return _controlled_1q_gates(ctrls[0], t, u)
    if np.allclose(u, [[0, 1], [1, 0]]) and free:
        return mcx_gates(ctrls, t, free)
    v = _sqrtm_2x2(u)
    vd = v.conj().T
    last, rest = ctrls[-1], ctrls[:-1]
    fx = free + [t]
    return (_controlled_1q_gates(last, t, v)
            + mcx_gates(rest, last, fx)
            + _controlled_1q_gates(last, t, vd)
            + mcx_gates(rest, last, fx)
            + mcu_gates(rest, t, v, free + [last]))


def lower(circ: Circuit, choice: ChoiceFn | None = None, **kw) -> Circuit:
    """Convenience: lower with default (or given) variant choices."""
    return Lowerer(**kw).lower(circ, choice)


def angle_is_trivial(theta: float) -> bool:
    return is_zero_angle(theta)


__all__ = ["Lowerer", "lower", "ccz_networks", "ccz_template", "mcx_gates", "mcu_gates", "BASE_GATES"]


def _selftest():  # pragma: no cover - handy for debugging
    from .sim import equivalent
    c = Circuit(3).append("ccx", (0, 1, 2))
    low = Lowerer()
    for net in range(len(low.networks)):
        for pol in range(2):
            for pl in range(2):
                d = low.lower(c, lambda k, s: (net, pol, pl))
                assert equivalent(c, d), (net, pol, pl)
    return True


if __name__ == "__main__":  # pragma: no cover
    print(_selftest(), math.pi)
