"""Pass library, cleanup fix-point, target-specific finishing and cost models.

All passes are semantics preserving, so *any* pass schedule decoded from a
particle yields a circuit equivalent to the input.
"""
from __future__ import annotations

import math
from typing import Callable

from .circuit import Circuit, Gate
from .decompose import BASE_GATES, Lowerer
from .passes import cancel, fuse_1q, hadamard_reduce, phase_fold
from .passes.kak import resynthesize_blocks

MODES = ("cliffordt", "continuous", "hardware", "ibm")

# pass library exposed to the swarm (index 0 = no-op)
PASS_LIBRARY = ("skip", "cancel", "fold", "hred", "fold_cancel", "kak")

_TO_BASE = Lowerer()


def to_base(circ: Circuit) -> Circuit:
    """Lower any non-base gates (e.g. u3 produced by resynthesis)."""
    if all(g.name in BASE_GATES for g in circ.gates):
        return circ
    out = []
    for g in circ.gates:
        if g.name in BASE_GATES:
            out.append(g)
        else:
            tmp: list[Gate] = []
            _TO_BASE._lower(g, g.tag if isinstance(g.tag, tuple) else (0,), tmp, None, circ.n_qubits)
            out.extend(tmp)
    return Circuit(circ.n_qubits, out, circ.name, circ.meta)


def apply_pass(name: str, circ: Circuit, placement=None, mode: str = "cliffordt") -> Circuit:
    if name == "skip":
        return circ
    if name == "cancel":
        return cancel(circ)
    if name == "fold":
        return phase_fold(circ, placement)[0]
    if name == "hred":
        return hadamard_reduce(circ)
    if name == "fold_cancel":
        return cancel(phase_fold(circ, placement)[0])
    if name == "kak":
        if mode == "cliffordt":
            return circ  # arbitrary angles are not allowed in Clifford+T
        return to_base(resynthesize_blocks(circ)[0])
    raise ValueError(f"unknown pass {name!r}")


def cleanup(circ: Circuit, placement=None, mode: str = "cliffordt", max_rounds: int = 8) -> Circuit:
    """Fix-point of fold / cancel / Hadamard reduction."""
    for _ in range(max_rounds):
        size0 = len(circ)
        circ = cancel(circ)
        circ, _ = phase_fold(circ, placement)
        circ = cancel(circ)
        circ = hadamard_reduce(circ)
        circ, _ = phase_fold(circ, placement)
        circ = cancel(circ)
        if len(circ) >= size0:
            break
    return circ


GREEDY_SCHEDULE = ("hred", "cancel", "fold", "cancel", "hred", "fold_cancel")


def finish(circ: Circuit, mode: str, placement=None) -> Circuit:
    """Target-specific final stage."""
    if mode == "cliffordt":
        return circ
    # continuous targets: optimal 2q blocks, then fuse single-qubit runs
    for _ in range(3):
        before = circ.cx_count()
        circ = to_base(resynthesize_blocks(circ)[0])
        circ = cleanup(circ, placement, mode, max_rounds=3)
        if circ.cx_count() >= before:
            break
    circ = fuse_1q(circ)[0]
    circ = cancel(circ)
    circ = fuse_1q(circ)[0]
    return circ


# --------------------------------------------------------------------------- #
# metrics and objectives
# --------------------------------------------------------------------------- #
def metrics(circ: Circuit) -> dict:
    ops = circ.count_ops()
    twoq = sum(1 for g in circ.gates if len(g.qubits) == 2)
    return {
        "gates": len(circ.gates),
        "cx": ops.get("cx", 0),
        "twoq": twoq,
        "oneq": sum(1 for g in circ.gates if len(g.qubits) == 1),
        "t": circ.t_count(),
        "h": ops.get("h", 0),
        "depth": circ.depth(),
        "twoq_depth": circ.depth(only_multi=True),
    }


def fidelity_cost(m: dict, e1: float = 1e-3, e2: float = 1e-2) -> float:
    """-log of the estimated success probability (independent gate errors)."""
    return -(m["oneq"] * math.log1p(-e1) + m["twoq"] * math.log1p(-e2))


OBJECTIVES: dict[str, Callable[[dict], tuple]] = {
    "gates": lambda m: (m["gates"], m["cx"], m["t"], m["depth"]),
    "cx": lambda m: (m["cx"], m["gates"], m["depth"]),
    "twoq": lambda m: (m["twoq"], m["gates"], m["depth"]),
    "t": lambda m: (m["t"], m["cx"], m["gates"], m["depth"]),
    "depth": lambda m: (m["depth"], m["cx"], m["gates"]),
    "fidelity": lambda m: (round(fidelity_cost(m), 12), m["depth"]),
}


def default_objective(mode: str) -> str:
    return {"cliffordt": "gates", "ibm": "twoq"}.get(mode, "cx")
