"""Dense simulation and equivalence checking (up to a global phase)."""
from __future__ import annotations

import numpy as np

from .circuit import Circuit, Gate

MAX_UNITARY_QUBITS = 11
MAX_STATEVECTOR_QUBITS = 24


def _apply(state: np.ndarray, gate: Gate, n: int) -> np.ndarray:
    """Apply ``gate`` to a tensor of shape (2,)*n + batch."""
    k = len(gate.qubits)
    m = gate.matrix().reshape((2,) * (2 * k))
    axes = list(gate.qubits)
    out = np.tensordot(m, state, axes=(list(range(k, 2 * k)), axes))
    # tensordot puts the k output axes first: move them back into place
    return np.moveaxis(out, list(range(k)), axes)


def statevector(circ: Circuit, init: np.ndarray | None = None) -> np.ndarray:
    n = circ.n_qubits
    if init is None:
        init = np.zeros(2 ** n, dtype=complex)
        init[0] = 1.0
    st = np.asarray(init, dtype=complex).reshape((2,) * n + init.shape[1:])
    for g in circ.gates:
        st = _apply(st, g, n)
    return st.reshape((2 ** n,) + init.shape[1:])


def unitary(circ: Circuit) -> np.ndarray:
    n = circ.n_qubits
    if n > MAX_UNITARY_QUBITS:
        raise ValueError(f"unitary of {n} qubits is too large")
    return statevector(circ, np.eye(2 ** n, dtype=complex))


def equal_up_to_phase(a: np.ndarray, b: np.ndarray, tol: float = 1e-7) -> bool:
    """True iff a = e^{i phi} b (Frobenius-normalised tolerance)."""
    inner = np.vdot(b, a)
    if abs(inner) < 1e-14:
        return False
    phase = inner / abs(inner)
    return bool(np.linalg.norm(a - phase * b) / np.sqrt(a.shape[0]) < tol)


def equivalent(c1: Circuit, c2: Circuit, tol: float = 1e-6, n_states: int = 2, seed: int = 1234,
               method: str = "auto") -> bool | None:
    """Check ``c1`` == ``c2`` up to global phase.

    Uses full unitaries for small circuits and random-state tests (with a
    shared phase requirement) otherwise.  Returns ``None`` when the circuit
    is too large to be checked.
    """
    n = max(c1.n_qubits, c2.n_qubits)
    if c1.n_qubits != c2.n_qubits:
        c1 = Circuit(n, c1.gates)
        c2 = Circuit(n, c2.gates)
    if method == "auto":
        method = "unitary" if n <= 8 else "state"
    if method == "unitary":
        return equal_up_to_phase(unitary(c1), unitary(c2), tol)
    if n > MAX_STATEVECTOR_QUBITS:
        return None
    rng = np.random.default_rng(seed)
    dim = 2 ** n
    psi = rng.normal(size=(dim, n_states)) + 1j * rng.normal(size=(dim, n_states))
    psi /= np.linalg.norm(psi, axis=0, keepdims=True)
    a = statevector(c1, psi)
    b = statevector(c2, psi)
    # one common global phase must explain every column
    inner = np.sum(np.conj(b) * a)
    if abs(inner) < 1e-12:
        return False
    phase = inner / abs(inner)
    err = np.linalg.norm(a - phase * b) / np.sqrt(n_states)
    return bool(err < tol)
