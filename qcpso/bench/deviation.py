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


def _to_qiskit(c: Circuit):
    """IR -> Qiskit circuit with *reversed* qubit order, so that Qiskit's
    little-endian statevector equals the IR's big-endian one."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import ECRGate
    n = c.n_qubits
    qc = QuantumCircuit(n)
    r = lambda q: n - 1 - q  # noqa: E731
    for g in c.gates:
        q = [r(x) for x in g.qubits]
        if g.name == "ecr":
            qc.append(ECRGate(), q)
        elif g.name == "cx":
            qc.cx(*q)
        elif g.name == "rz":
            qc.rz(g.params[0], q[0])
        elif g.name == "sx":
            qc.sx(q[0])
        elif g.name == "x":
            qc.x(q[0])
        elif g.name == "h":
            qc.h(q[0])
        elif g.name in ("u3", "u"):
            qc.u(*g.params, q[0])
        else:
            qc.unitary(g.matrix(), q[::-1] if len(q) > 1 else q)
    return qc


def _evolve_aer(c: Circuit, psi: np.ndarray) -> np.ndarray:
    from qiskit_aer import AerSimulator
    sim = AerSimulator(method="statevector", max_parallel_threads=1)
    out = []
    body = _to_qiskit(c)
    for k in range(psi.shape[1]):
        from qiskit import QuantumCircuit
        qc = QuantumCircuit(c.n_qubits)
        qc.set_statevector(psi[:, k])
        qc.compose(body, inplace=True)
        qc.save_statevector()
        res = sim.run(qc).result()
        out.append(np.asarray(res.get_statevector()))
    return np.stack(out, axis=1)


def deviation(a: Circuit, b: Circuit, n_states: int = 2, seed: int = 1234, _cache: dict = {}) -> dict:
    used = sorted(a.used_qubits() | b.used_qubits())
    if len(used) > 20:
        return {"used_qubits": len(used), "state_err": None}
    A, B = _compact(a, used), _compact(b, used)
    n = len(used)
    rng = np.random.default_rng(seed)
    psi = rng.normal(size=(2 ** n, n_states)) + 1j * rng.normal(size=(2 ** n, n_states))
    psi /= np.linalg.norm(psi, axis=0, keepdims=True)
    try:
        import qiskit_aer  # noqa: F401
        use_aer = n >= 14
    except ImportError:  # pragma: no cover
        use_aer = False
    evolve = _evolve_aer if use_aer else statevector
    key = (hash(tuple((g.name, g.qubits, g.params) for g in a.gates)), n, seed, n_states, use_aer)
    if key not in _cache:  # the input's evolved states are reused for all outputs
        _cache.clear()
        _cache[key] = evolve(A, psi)
    x, y = _cache[key], evolve(B, psi)
    inner = np.sum(np.conj(y) * x)
    ph = inner / abs(inner)
    out = {"used_qubits": n, "state_err": float(np.linalg.norm(x - ph * y) / np.sqrt(n_states))}
    if n <= 8 and len(a.gates) + len(b.gates) < 50000:
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
