"""Equivalence check for mapped circuits (initial/final layouts, |0> ancillas)."""
from __future__ import annotations

import numpy as np

from ..circuit import Circuit, Gate
from ..sim import statevector

MAX_QUBITS = 22


def mapped_equivalent(logical: Circuit, physical: Circuit, init_layout, final_layout, seed: int = 11,
                      tol: float = 1e-6) -> bool | None:
    n_log = logical.n_qubits
    used = sorted(set(init_layout) | set(final_layout) | physical.used_qubits())
    if len(used) > MAX_QUBITS or n_log > MAX_QUBITS:
        return None
    idx = {p: i for i, p in enumerate(used)}
    n = len(used)
    phys = Circuit(n, [Gate(g.name, tuple(idx[q] for q in g.qubits), g.params) for g in physical.gates])
    rng = np.random.default_rng(seed)
    psi = rng.normal(size=2 ** n_log) + 1j * rng.normal(size=2 ** n_log)
    psi /= np.linalg.norm(psi)

    def embed(state, layout):
        t = state.reshape((2,) * n_log)
        # logical axes first, ancillas fixed to |0>
        sl = tuple([slice(None)] * n_log + [0] * (n - n_log))
        tmp = np.zeros((2,) * n_log + (2,) * (n - n_log), dtype=complex)
        tmp[sl] = t
        dest = [idx[p] for p in layout]
        others = [i for i in range(n) if i not in dest]
        full = np.moveaxis(tmp, list(range(n)), dest + others)
        return full.reshape(-1)

    start = embed(psi, init_layout)
    out = statevector(phys, start)
    expect = embed(statevector(logical, psi), final_layout)
    inner = np.vdot(expect, out)
    if abs(inner) < 1e-9:
        return False
    return bool(np.linalg.norm(out - inner / abs(inner) * expect) < tol)
