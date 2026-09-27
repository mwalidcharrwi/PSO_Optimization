"""Hardware-mode baselines: Qiskit O3 and TKET with the device coupling map.

(The deterministic ``greedy`` method of the runner -- default logical
decisions + SabreLayout + SABRE routing + clean-up -- is the in-framework
baseline.)"""
from __future__ import annotations

import time

from ..bench.external import _qasm_in, canonical
from ..io.qasm import parse_qasm
from ..pipeline import metrics
from .verify import mapped_equivalent


def run_qiskit_hw(circ, spec, seed: int = 0, level: int = 3):
    import qiskit
    import qiskit.qasm2
    from qiskit.transpiler import CouplingMap as QCM
    from qiskit.transpiler import PassManager, generate_preset_pass_manager
    from qiskit.transpiler.passes import ElidePermutations
    qc = qiskit.qasm2.loads(_qasm_in(circ), custom_instructions=qiskit.qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
    edges = [list(e) for e in spec.cmap.edges] + [[b, a] for a, b in spec.cmap.edges]
    basis = ["u", "cx"] if spec.continuous else ["h", "x", "rz", "cx"]
    t = time.time()
    pm = generate_preset_pass_manager(level, basis_gates=basis, coupling_map=QCM(edges), seed_transpiler=seed)
    if pm.init is not None:
        tasks = [x for t_ in pm.init._tasks for x in (t_ if isinstance(t_, list) else [t_])]
        pm.init = PassManager([x for x in tasks if not isinstance(x, ElidePermutations)])
    out = pm.run(qc)
    dt = time.time() - t
    n = circ.n_qubits
    init = list(out.layout.initial_index_layout())[:n]
    final = list(out.layout.final_index_layout())[:n]
    res = canonical(parse_qasm(qiskit.qasm2.dumps(out)), "continuous" if spec.continuous else "cliffordt")
    return res, dt, {"initial_layout": init, "final_layout": final}


def run_tket_hw(circ, spec, seed: int = 0):
    from pytket.architecture import Architecture
    from pytket.circuit import OpType, Qubit
    from pytket.passes import (AutoRebase, DefaultMappingPass, FullPeepholeOptimise, RemoveRedundancies,
                               SequencePass, SynthesiseTket)
    from pytket.predicates import CompilationUnit
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    from ..circuit import Circuit
    tk = circuit_from_qasm_str(_qasm_in(circ))
    arch = Architecture([tuple(e) for e in spec.cmap.edges])
    rebase = AutoRebase({OpType.CX, OpType.U3} if spec.continuous else {OpType.CX, OpType.H, OpType.Rz, OpType.X})
    seq = SequencePass([FullPeepholeOptimise(allow_swaps=False), DefaultMappingPass(arch), SynthesiseTket(),
                        rebase, RemoveRedundancies()])
    cu = CompilationUnit(tk)
    t = time.time()
    seq.apply(cu)
    dt = time.time() - t
    out = cu.circuit
    idx = lambda node: node.index[0]
    init = [idx(cu.initial_map[Qubit("q", i)]) for i in range(circ.n_qubits)]
    final = [idx(cu.final_map[Qubit("q", i)]) for i in range(circ.n_qubits)]
    out.rename_units({q: Qubit("q", idx(q)) for q in out.qubits})
    res = parse_qasm(circuit_to_qasm_str(out, header="qelib1"))
    if res.n_qubits < spec.cmap.n:
        res = Circuit(spec.cmap.n, res.gates)
    res = canonical(res, "continuous" if spec.continuous else "cliffordt")
    return res, dt, {"initial_layout": init, "final_layout": final}


HW_BASELINES = {"qiskit": run_qiskit_hw, "tket": run_tket_hw}


def run_hw_baseline(method, circ, spec, seed: int = 0, do_verify: bool = True) -> dict:
    out, dt, info = HW_BASELINES[method](circ, spec, seed=seed)
    ok = mapped_equivalent(circ, out, info["initial_layout"], info["final_layout"]) if do_verify else None
    m = metrics(out)
    return dict(circuit=circ.name, n_qubits=circ.n_qubits, method=method, seed=seed, time=round(dt, 3),
                evals=0, verified=ok, **m)
