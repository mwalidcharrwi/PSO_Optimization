"""Optional sound rewrite passes from TKET (pytket), used as entries of the
HyPSO-QCO pass library.

Only passes that never introduce a two-qubit interaction on a new qubit pair
are exposed (``allow_swaps=False`` everywhere), so they preserve the device
mapping of already-mapped circuits:

* ``CliffordSimp`` -- Clifford rewrite rules (Duncan & Fagan, arXiv:1901.10114);
* ``KAKDecomposition`` -- optimal two-qubit block resynthesis.

(``SynthesiseTket`` is exposed as a separate function but not used by
:func:`full`: its squashing drops small rotations, see :func:`_full`.)

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


CHUNK = 6000  # gates per chunk for large circuits (TKET's passes scale super-linearly)


BLOCK_QUBITS = 10   # wide circuits: TKET is applied inside convex blocks of at most this many qubits
STATS = {"blocks": 0, "rejected": 0}
# accepted block rewrites of the most recent block-wise call, as (original, replacement) gate lists on
# local qubits; kept so that their spectral-norm errors can be bounded exactly afterwards (Prop. 1(c))
LAST_BLOCKS: list = []


def full(circ: Circuit, chunk: int | None = None) -> Circuit:
    """TKET's exact connectivity-preserving passes (see :func:`_full`).

    Circuits with more than 20 used qubits cannot be checked by simulation,
    so they are partitioned into convex blocks of at most ``BLOCK_QUBITS``
    qubits; each block is optimised and *checked* separately and kept only if
    it is equivalent to the original block.  Narrower circuits larger than
    ``chunk`` gates are processed in consecutive (checked) chunks."""
    if len(circ.used_qubits()) > 20:
        return _blockwise(circ)
    chunk = CHUNK if chunk is None else chunk
    if chunk and len(circ.gates) > 2 * chunk:
        out = []
        for i in range(0, len(circ.gates), chunk):
            part = Circuit(circ.n_qubits, circ.gates[i:i + chunk])
            out.extend(_full(part).gates)
        return Circuit(circ.n_qubits, out, circ.name, circ.meta)
    return _full(circ)


CHECK_TOL = 1e-9


def _blockwise(circ: Circuit, max_qubits: int | None = None) -> Circuit:
    from .resynth import partition, rebuild
    max_qubits = max_qubits or BLOCK_QUBITS
    repl = []
    LAST_BLOCKS.clear()
    for qubits, idx in partition(circ, max_qubits):
        if sum(1 for i in idx if len(circ.gates[i].qubits) == 2) < 3:
            continue
        loc = {q: j for j, q in enumerate(qubits)}
        sub = Circuit(len(qubits), [Gate(circ.gates[i].name, tuple(loc[q] for q in circ.gates[i].qubits),
                                         circ.gates[i].params) for i in idx])
        STATS["blocks"] += 1
        out = _full(sub)
        if out is sub:
            continue
        if out.cx_count() > sub.cx_count():
            continue
        repl.append((idx, [Gate(g.name, tuple(qubits[q] for q in g.qubits), g.params) for g in out.gates]))
        LAST_BLOCKS.append((len(qubits), [(g.name, list(g.qubits), list(g.params)) for g in sub.gates],
                            [(g.name, list(g.qubits), list(g.params)) for g in out.gates]))
    return rebuild(circ, repl) if repl else circ


def _full(circ: Circuit) -> Circuit:
    """Fixed point of ``KAKDecomposition`` + ``CliffordSimp`` (no implicit
    swaps).  ``SynthesiseTket`` is *not* used: its single-qubit squashing drops
    small rotations (e.g. rz(3.8e-4) next to Clifford gates in QAE/QFT
    circuits), so it is not exact.  As a safety net the result is checked
    numerically (random-state test, <= 20 used qubits) and the input is
    returned unchanged if the check fails."""
    from pytket.circuit import OpType
    from pytket.passes import CliffordSimp, KAKDecomposition, RepeatWithMetricPass, SequencePass
    seq = SequencePass([KAKDecomposition(allow_swaps=False), CliffordSimp(allow_swaps=False)])
    rep = RepeatWithMetricPass(seq, lambda c: c.n_gates_of_type(OpType.CX) * 100000 + c.n_gates)
    out = _run(circ, [rep])
    from ..bench.deviation import deviation
    d = deviation(circ, out, n_states=1)["state_err"]
    if d is None or d > CHECK_TOL:  # unverifiable (> 20 qubits) or not exact: keep the input
        if d is not None:
            STATS["rejected"] += 1
        return circ
    return out
