"""Fuse maximal runs of single-qubit gates into one gate (rz if diagonal,
x if a bit flip, u3 otherwise; identities are dropped)."""
from __future__ import annotations

import cmath

import numpy as np

from ..circuit import Circuit, Gate, norm_angle
from ..linalg import is_identity_up_to_phase, u3_params


def _fused(mats: list[np.ndarray], q: int, tag) -> Gate | None:
    u = np.eye(2, dtype=complex)
    for m in mats:
        u = m @ u
    if is_identity_up_to_phase(u, 1e-10):
        return None
    if abs(u[0, 1]) < 1e-10 and abs(u[1, 0]) < 1e-10:
        return Gate("rz", (q,), (norm_angle(cmath.phase(u[1, 1]) - cmath.phase(u[0, 0])),), tag)
    th, ph, la = u3_params(u)
    return Gate("u3", (q,), (th, ph, la), tag)


def fuse_1q(circ: Circuit) -> tuple[Circuit, bool]:
    gates = circ.gates
    n = circ.n_qubits
    runs: list[list[int]] = [[] for _ in range(n)]
    out_at: dict[int, Gate | None] = {}
    drop: set[int] = set()
    changed = False

    def flush(q):
        nonlocal changed
        r = runs[q]
        if not r:
            return
        runs[q] = []
        if len(r) == 1 and gates[r[0]].name in ("rz", "u3", "x", "h"):
            return
        new = _fused([gates[i].matrix() for i in r], q, gates[r[0]].tag)
        drop.update(r)
        out_at[r[-1]] = new
        changed = True

    for i, g in enumerate(gates):
        if len(g.qubits) == 1:
            runs[g.qubits[0]].append(i)
        else:
            for q in g.qubits:
                flush(q)
    for q in range(n):
        flush(q)
    if not changed:
        return circ, False
    out = []
    for i, g in enumerate(gates):
        if i in out_at:
            if out_at[i] is not None:
                out.append(out_at[i])
        elif i not in drop:
            out.append(g)
    return Circuit(n, out, circ.name, circ.meta), True
