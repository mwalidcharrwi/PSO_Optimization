"""Circuit readers/writers.  :func:`load` dispatches on the file extension."""
from __future__ import annotations

import os

from ..circuit import Circuit
from .qasm import QasmError, load_qasm, parse_qasm, save_qasm, to_qasm
from .qc import load_qc, parse_qc
from .real import load_real, parse_real


def load(path: str) -> Circuit:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".qc":
        return load_qc(path)
    if ext == ".real":
        return load_real(path)
    with open(path) as fh:
        text = fh.read()
    if "OPENQASM 3" in text:
        return _load_qasm3(path, text)
    return load_qasm(path)


def _load_qasm3(path: str, text: str) -> Circuit:
    """OpenQASM 3 via Qiskit (optional dependency), converted to QASM 2."""
    try:
        import qiskit.qasm2
        import qiskit.qasm3
    except ImportError as exc:  # pragma: no cover
        raise QasmError("OpenQASM 3 input requires qiskit + qiskit_qasm3_import") from exc
    qc = qiskit.qasm3.loads(text)
    circ = parse_qasm(qiskit.qasm2.dumps(qc), name=os.path.splitext(os.path.basename(path))[0])
    return circ


__all__ = ["load", "load_qasm", "parse_qasm", "save_qasm", "to_qasm", "load_qc", "parse_qc",
           "load_real", "parse_real", "QasmError"]
