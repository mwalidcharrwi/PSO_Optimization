"""Hadamard gate reduction (Nam, Ross, Su, Childs & Maslov 2018, Fig. 4).

Rules (S = rz(pi/2), verified numerically in the test-suite):

1. H S H            ->  S^dag H S^dag           (and the mirrored S^dag rule)
2. (H x H) CX(a,b) (H x H) -> CX(b,a)
3. on the target b of CX(a,b):  H S CX S^dag H  ->  S^dag CX S
                                H S^dag CX S H  ->  S CX S^dag

Fewer Hadamards mean fewer path variables, i.e. more phase-folding
opportunities.
"""
from __future__ import annotations

import math

from ..circuit import Circuit, Gate, norm_angle

_HALF = math.pi / 2


def _quarter_sign(g: Gate) -> int:
    """+1 for rz(pi/2), -1 for rz(-pi/2), 0 otherwise."""
    if g.name != "rz":
        return 0
    t = norm_angle(g.params[0])
    if abs(t - _HALF) < 1e-9:
        return 1
    if abs(t + _HALF) < 1e-9:
        return -1
    return 0


def hadamard_reduce_pass(circ: Circuit) -> tuple[Circuit, bool]:
    gates = list(circ.gates)
    m = len(gates)
    n = circ.n_qubits
    alive = [True] * m
    # doubly-linked per-wire neighbours (by index), rebuilt once per pass
    prev = [dict() for _ in range(m)]
    nxt = [dict() for _ in range(m)]
    last = [-1] * n
    for i, g in enumerate(gates):
        for q in g.qubits:
            if last[q] >= 0:
                nxt[last[q]][q] = i
                prev[i][q] = last[q]
            last[q] = i
    touched = [False] * m
    changed = False

    def nb(i, q, d):
        return (nxt if d > 0 else prev)[i].get(q, -1)

    for i in range(m):
        g = gates[i]
        if not alive[i] or touched[i]:
            continue
        if g.name == "cx":
            a, b = g.qubits
            pa, pb, na, nb_ = nb(i, a, -1), nb(i, b, -1), nb(i, a, 1), nb(i, b, 1)
            idx = [pa, pb, na, nb_]
            if min(idx) >= 0 and all(gates[j].name == "h" and not touched[j] for j in idx):
                for j in idx:
                    alive[j] = False
                    touched[j] = True
                gates[i] = Gate("cx", (b, a), (), g.tag)
                touched[i] = True
                changed = True
                continue
            # rule 3 on the target wire
            s1, s2 = pb, nb_
            if s1 >= 0 and s2 >= 0:
                k1, k2 = _quarter_sign(gates[s1]), _quarter_sign(gates[s2])
                if k1 != 0 and k2 == -k1:
                    h1, h2 = nb(s1, b, -1), nb(s2, b, 1)
                    if (h1 >= 0 and h2 >= 0 and gates[h1].name == "h" and gates[h2].name == "h"
                            and not any(touched[j] for j in (s1, s2, h1, h2))):
                        alive[h1] = alive[h2] = False
                        gates[s1] = Gate("rz", (b,), (-k1 * _HALF,), gates[s1].tag)
                        gates[s2] = Gate("rz", (b,), (k1 * _HALF,), gates[s2].tag)
                        for j in (s1, s2, i, h1, h2):
                            touched[j] = True
                        changed = True
                        continue
        elif g.name == "h":
            q = g.qubits[0]
            j = nb(i, q, 1)
            if j >= 0 and not touched[j]:
                k = _quarter_sign(gates[j])
                if k:
                    h2 = nb(j, q, 1)
                    if h2 >= 0 and gates[h2].name == "h" and not touched[h2]:
                        gates[i] = Gate("rz", (q,), (-k * _HALF,), g.tag)
                        gates[j] = Gate("h", (q,), (), gates[j].tag)
                        gates[h2] = Gate("rz", (q,), (-k * _HALF,), gates[h2].tag)
                        for x in (i, j, h2):
                            touched[x] = True
                        changed = True
    if not changed:
        return circ, False
    return Circuit(n, [g for g, a in zip(gates, alive) if a], circ.name, circ.meta), True


def hadamard_reduce(circ: Circuit, max_iter: int = 20) -> Circuit:
    for _ in range(max_iter):
        circ, ch = hadamard_reduce_pass(circ)
        if not ch:
            break
    return circ
