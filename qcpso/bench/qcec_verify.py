"""Large-circuit equivalence checking with MQT QCEC (optional dependency).

Statevector simulation is limited to ~20-24 qubits; QCEC (decision diagrams,
ZX-calculus and simulation) can verify compiled circuits on many more qubits.
"""
from __future__ import annotations

from ..circuit import Circuit


def to_qiskit(circ: Circuit, used_only: bool = True):
    qubits = sorted(circ.used_qubits()) if used_only else list(range(circ.n_qubits))
    return _build(circ, {q: i for i, q in enumerate(qubits)}, len(qubits))


def _build(circ: Circuit, idx: dict, n: int):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(n)
    for g in circ.gates:
        qs = [idx[q] for q in g.qubits]
        name = g.name
        if name in ("u3", "u"):
            qc.u(*g.params, qs[0])
        elif name in ("rz", "rx", "ry", "p"):
            getattr(qc, name)(g.params[0], qs[0])
        elif name in ("sx", "x", "h", "s", "sdg", "t", "tdg", "z", "y"):
            getattr(qc, name)(qs[0])
        elif name in ("cx", "cz", "swap", "ecr"):
            getattr(qc, name)(*qs)
        else:
            raise ValueError(f"to_qiskit: unsupported gate {name}")
    return qc


def qcec_equivalent(a: Circuit, b: Circuit, timeout: float = 600.0, max_sims: int = 16) -> str:
    """QCEC verdict: "equivalent", "probably_equivalent" (random-stimuli
    simulation only), "not_equivalent" or "unknown".  The ZX checker is
    disabled because floating-point rotation angles make it unreliable."""
    try:
        from mqt import qcec
    except ImportError:
        return "unknown"
    qubits = sorted(a.used_qubits() | b.used_qubits())
    idx = {q: i for i, q in enumerate(qubits)}
    qa, qb = _build(a, idx, len(qubits)), _build(b, idx, len(qubits))
    res = qcec.verify(qa, qb, timeout=timeout, run_zx_checker=False, run_alternating_checker=True,
                      run_simulation_checker=True, run_construction_checker=False, max_sims=max_sims,
                      check_partial_equivalence=False, transform_dynamic_circuit=False)
    s = str(res.equivalence)
    if "not_equivalent" in s:
        return "not_equivalent"
    if "probably" in s:
        return "probably_equivalent"
    if "equivalent" in s:
        return "equivalent"
    return "unknown"
