"""Optional sound rewrite passes from TKET (pytket), used as entries of the
HyPSO-QCO pass library.

Only passes that never introduce a two-qubit interaction on a new qubit pair
are exposed (``allow_swaps=False`` everywhere), so they preserve the device
mapping of already-mapped circuits:

* ``CliffordSimp`` -- Clifford rewrite rules (Duncan & Fagan, arXiv:1901.10114);
* ``SynthesiseTket`` -- commutation of single-qubit gates through CNOTs and
  single-qubit squashing;
* ``KAKDecomposition`` -- optimal two-qubit block resynthesis.

The circuits are exchanged gate by gate (no QASM round trip).  Output gates
are {cx, u3}; callers lower u3 with :func:`qcpso.pipeline.to_base`.
"""
from __future__ import annotations

import math

from ..circuit import Circuit, Gate

_PI = math.pi


def available() -> bool:
    try:
        import pytket  # noqa: F401
        return True
    except ImportError:  # pragma: no cover
        return False


def to_tket(circ: Circuit):
    from pytket.circuit import Circuit as TkCircuit, OpType
    tk = TkCircuit(circ.n_qubits)
    for g in circ.gates:
        n, q = g.name, g.qubits
        if n == "cx":
            tk.CX(*q)
        elif n == "rz":
            tk.Rz(g.params[0] / _PI, q[0])
        elif n == "h":
            tk.H(q[0])
        elif n == "x":
            tk.X(q[0])
        elif n == "sx":
            tk.SX(q[0])
        elif n in ("u3", "u"):
            tk.U3(g.params[0] / _PI, g.params[1] / _PI, g.params[2] / _PI, q[0])
        elif len(q) == 1:
            from ..linalg import u3_params
            t, p, l = u3_params(g.matrix())
            tk.U3(t / _PI, p / _PI, l / _PI, q[0])
        else:
            raise ValueError(f"tket bridge: unsupported gate {n}")
    return tk


def from_tket(tk, n_qubits: int, name: str = "", meta=None) -> Circuit:
    from pytket.circuit import OpType
    from pytket.passes import AutoRebase
    AutoRebase({OpType.CX, OpType.U3}).apply(tk)
    gates = []
    for cmd in tk.get_commands():
        t = cmd.op.type
        qs = tuple(q.index[0] for q in cmd.qubits)
        if t == OpType.CX:
            gates.append(Gate("cx", qs))
        elif t == OpType.U3:
            a, b, c = (float(p) * _PI for p in cmd.op.params)
            gates.append(Gate("u3", qs, (a, b, c)))
        elif t in (OpType.Barrier,):
            continue
        else:  # pragma: no cover
            raise ValueError(f"tket bridge: unexpected {t}")
    return Circuit(n_qubits, gates, name, meta or {})


def _run(circ: Circuit, passes) -> Circuit:
    tk = to_tket(circ)
    for p in passes:
        p.apply(tk)
    return from_tket(tk, circ.n_qubits, circ.name, circ.meta)


def clifford_simp(circ: Circuit) -> Circuit:
    from pytket.passes import CliffordSimp
    return _run(circ, [CliffordSimp(allow_swaps=False)])


def synthesise(circ: Circuit) -> Circuit:
    from pytket.passes import SynthesiseTket
    return _run(circ, [SynthesiseTket()])


def kak(circ: Circuit) -> Circuit:
    from pytket.passes import KAKDecomposition
    return _run(circ, [KAKDecomposition(allow_swaps=False)])


def full(circ: Circuit) -> Circuit:
    """Fixed point of the three passes (the TKET-mp baseline pipeline)."""
    from pytket.circuit import OpType
    from pytket.passes import (CliffordSimp, KAKDecomposition, RemoveRedundancies, RepeatWithMetricPass,
                               SequencePass, SynthesiseTket)
    seq = SequencePass([SynthesiseTket(), KAKDecomposition(allow_swaps=False), CliffordSimp(allow_swaps=False),
                        SynthesiseTket(), RemoveRedundancies()])
    rep = RepeatWithMetricPass(seq, lambda c: c.n_gates_of_type(OpType.CX) * 100000 + c.n_gates)
    return _run(circ, [rep])
