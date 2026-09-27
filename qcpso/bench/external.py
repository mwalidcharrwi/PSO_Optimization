"""External optimisers used as baselines (all optional dependencies).

* Qiskit ``transpile(optimization_level=3)``
* TKET ``FullPeepholeOptimise`` (+ rebase)
* PyZX ``full_reduce`` + ``extract_circuit`` + ``basic_optimization``

Every tool receives the *same* input circuit (Toffolis etc. undecomposed, so
each tool applies its own decomposition) and its output is re-expressed in the
comparison gate set: {h, x, rz, cx} for Clifford+T mode, {u3, cx} with fused
single-qubit runs for continuous mode.
"""
from __future__ import annotations

import time

from ..circuit import Circuit, Gate
from ..decompose import mcu_gates, mcx_gates
from ..io.qasm import parse_qasm, to_qasm
from ..passes import fuse_1q
from ..pipeline import to_base


def _prepare(circ: Circuit) -> Circuit:
    """Expand gates that plain QASM 2 cannot express (large mcx, mcu)."""
    out = []
    n = circ.n_qubits
    for g in circ.gates:
        if g.name == "mcx" and len(g.qubits) > 5:
            out.extend(mcx_gates(list(g.qubits[:-1]), g.qubits[-1], [q for q in range(n) if q not in g.qubits]))
        elif g.name == "mcz":
            t = g.qubits[-1]
            out.append(Gate("h", (t,)))
            out.extend(mcx_gates(list(g.qubits[:-1]), t, [q for q in range(n) if q not in g.qubits]))
            out.append(Gate("h", (t,)))
        elif g.name == "mcu":
            out.extend(mcu_gates(list(g.qubits[:-1]), g.qubits[-1], g.params[0],
                                 [q for q in range(n) if q not in g.qubits]))
        elif g.name == "unitary":
            raise ValueError("arbitrary unitaries are not supported by the external baselines")
        else:
            out.append(g)
    c = Circuit(n, out, circ.name)
    return _prepare(c) if any(g.name in ("mcu", "mcz") or (g.name == "mcx" and len(g.qubits) > 5)
                              for g in c.gates) else c


def canonical(circ: Circuit, mode: str) -> Circuit:
    """Express a circuit in the comparison gate set of ``mode``."""
    base = to_base(circ)
    if mode == "cliffordt":
        return base
    return fuse_1q(base)[0]


_RENAME = {"cp": "cu1", "p": "u1", "u": "u3"}


def _qasm_in(circ: Circuit) -> str:
    c = _prepare(circ)
    c = Circuit(c.n_qubits, [Gate(_RENAME.get(g.name, g.name), g.qubits, g.params) for g in c.gates], c.name)
    return to_qasm(c, clifford_t_names=True)


def run_qiskit(circ: Circuit, mode: str = "cliffordt", seed: int = 0, level: int = 3,
               allow_permutation: bool = False):
    import qiskit
    import qiskit.qasm2
    from qiskit.transpiler import PassManager, generate_preset_pass_manager
    from qiskit.transpiler.passes import ElidePermutations
    qc = qiskit.qasm2.loads(_qasm_in(circ), custom_instructions=qiskit.qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
    basis = ["h", "x", "rz", "cx"] if mode == "cliffordt" else ["u", "cx"]
    t = time.time()
    pm = generate_preset_pass_manager(level, basis_gates=basis, seed_transpiler=seed)
    if pm.init is not None and not allow_permutation:
        # ElidePermutations relabels output qubits instead of keeping final SWAPs,
        # which breaks strict equivalence; drop it so every tool is compared on the
        # same (strict) contract.
        tasks = [x for t_ in pm.init._tasks for x in (t_ if isinstance(t_, list) else [t_])]
        pm.init = PassManager([x for x in tasks if not isinstance(x, ElidePermutations)])
    out = pm.run(qc)
    dt = time.time() - t
    res = parse_qasm(qiskit.qasm2.dumps(out))
    return canonical(res, mode), dt


def run_tket(circ: Circuit, mode: str = "cliffordt"):
    from pytket.passes import AutoRebase, FullPeepholeOptimise, RemoveRedundancies
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    from pytket.circuit import OpType
    tk = circuit_from_qasm_str(_qasm_in(circ))
    t = time.time()
    FullPeepholeOptimise(allow_swaps=False).apply(tk)  # strict: no implicit wire swaps
    if mode == "cliffordt":
        AutoRebase({OpType.CX, OpType.H, OpType.Rz, OpType.X}).apply(tk)
    else:
        AutoRebase({OpType.CX, OpType.U3}).apply(tk)
    RemoveRedundancies().apply(tk)
    dt = time.time() - t
    res = parse_qasm(circuit_to_qasm_str(tk, header="qelib1"))
    return canonical(res, mode), dt


def run_pyzx(circ: Circuit, mode: str = "cliffordt"):
    import pyzx as zx
    c = zx.Circuit.from_qasm(_qasm_in(circ))
    t = time.time()
    g = c.to_graph()
    zx.simplify.full_reduce(g, quiet=True)
    c2 = zx.extract_circuit(g.copy())
    c3 = zx.optimize.basic_optimization(c2.to_basic_gates())
    dt = time.time() - t
    res = parse_qasm(c3.to_basic_gates().to_qasm())
    return canonical(res, mode), dt


EXTERNAL = {"qiskit": run_qiskit, "tket": run_tket, "pyzx": run_pyzx}


def available() -> list[str]:
    names = []
    for mod, name in (("qiskit", "qiskit"), ("pytket", "tket"), ("pyzx", "pyzx")):
        try:
            __import__(mod)
            names.append(name)
        except ImportError:
            pass
    return names
