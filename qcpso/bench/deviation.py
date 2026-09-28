"""Numerical deviation between an input circuit and an optimised output.

For <= 20 used qubits: random-state test with a common global phase,
    err = || A psi - e^{i phi} B psi ||_F / sqrt(#states)
(the same quantity :func:`qcpso.sim.equivalent` compares with 1e-6), and,
for <= 11 qubits, the exact normalised unitary distance
    || U_A - e^{i phi} U_B ||_F / sqrt(2^n).

    python -m qcpso.bench.deviation input.qasm output.qasm [more outputs...]
"""
from __future__ import annotations

import sys

import numpy as np

from ..circuit import Circuit, Gate
from ..io import load
from ..sim import statevector


def _compact(c: Circuit, used):
    idx = {q: i for i, q in enumerate(used)}
    return Circuit(len(used), [Gate(g.name, tuple(idx[q] for q in g.qubits), g.params) for g in c.gates])


def deviation(a: Circuit, b: Circuit, n_states: int = 2, seed: int = 1234) -> dict:
    used = sorted(a.used_qubits() | b.used_qubits())
    if len(used) > 20:
        return {"used_qubits": len(used), "state_err": None}
    A, B = _compact(a, used), _compact(b, used)
    n = len(used)
    rng = np.random.default_rng(seed)
    psi = rng.normal(size=(2 ** n, n_states)) + 1j * rng.normal(size=(2 ** n, n_states))
    psi /= np.linalg.norm(psi, axis=0, keepdims=True)
    x, y = statevector(A, psi), statevector(B, psi)
    inner = np.sum(np.conj(y) * x)
    ph = inner / abs(inner)
    out = {"used_qubits": n, "state_err": float(np.linalg.norm(x - ph * y) / np.sqrt(n_states))}
    if n <= 11:
        from ..sim import unitary
        U, V = unitary(A), unitary(B)
        inner = np.vdot(V, U)
        out["unitary_err"] = float(np.linalg.norm(U - inner / abs(inner) * V) / np.sqrt(2 ** n))
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    a = load(argv[0])
    for p in argv[1:]:
        b = load(p)
        if b.n_qubits < a.n_qubits:
            b = Circuit(a.n_qubits, b.gates)
        print(p, deviation(a, b), flush=True)


if __name__ == "__main__":  # pragma: no cover
    main()
