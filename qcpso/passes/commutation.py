"""Sound, table-driven commutation test.

Every gate is classified per qubit as ``Z`` (block-diagonal in the
computational basis of that qubit, e.g. Rz or a CNOT control), ``X``
(block-diagonal in the Hadamard basis, e.g. X or a CNOT target) or ``O``
(anything else).  Two gates commute if on every shared qubit they have the
same class and it is not ``O``.  Proof: both gates are then of the form
sum_s P_s (x) A_s and sum_s P_s (x) B_s with the same projectors P_s on the
shared qubits and A_s, B_s acting on disjoint qubits.  The test can return a
false "no" but never a false "yes".
"""
from __future__ import annotations

from ..circuit import DIAGONAL_GATES, Gate

_X_TYPE_1Q = {"x", "rx", "sx", "sxdg"}


def wire_class(g: Gate, q: int) -> str:
    n = g.name
    if n in DIAGONAL_GATES:
        return "Z"
    if n in _X_TYPE_1Q:
        return "X"
    if n in ("cx", "ccx", "mcx"):
        return "X" if q == g.qubits[-1] else "Z"
    if n in ("cy", "ch", "crx", "cry", "cu3", "cu", "csx", "mcu", "cswap"):
        return "Z" if q == g.qubits[0] or (n == "mcu" and q != g.qubits[-1]) else "O"
    if n == "rxx":
        return "X"
    return "O"


def commute(a: Gate, b: Gate) -> bool:
    qa = a.qubits
    shared = [q for q in b.qubits if q in qa]
    if not shared:
        return True
    for q in shared:
        ca = wire_class(a, q)
        if ca == "O" or ca != wire_class(b, q):
            return False
    return True
