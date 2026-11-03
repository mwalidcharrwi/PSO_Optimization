"""IBM's AI synthesis passes (qiskit-ibm-transpiler, local mode) under the
re-optimisation contract.

The passes collect Clifford, linear-function, permutation and Pauli-network
blocks and re-synthesise them with reinforcement-learning models
(Kremer et al. 2024; Dubal et al. 2025), keeping a block only if the result is
better (``replace_only_if_better``).  The coupling map given to every pass
contains only the qubit pairs that the input already couples, so the output
cannot couple a new pair; CNOT directions are fixed afterwards by HyPSO-QCO's
exact native lowering, like for every other CNOT-based tool.

Runs in a separate environment (qiskit-ibm-transpiler 0.18 needs Qiskit 2.1-2.2;
the local models are downloaded from huggingface.co on first use):

    /home/user/aienv/bin/python scripts/run_ai_synthesis.py [--circuits a,b] [--reps 1]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=os.path.join(ROOT, "test_circuits_new"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "ibm_revision", "ai_synthesis"))
    ap.add_argument("--circuits", default="")
    ap.add_argument("--reps", type=int, default=2, help="passes over the four collect/synthesise stages")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    import qiskit.qasm2
    from qiskit.transpiler import CouplingMap, PassManager
    from qiskit_ibm_transpiler.ai.collection import (CollectCliffords, CollectLinearFunctions,
                                                      CollectPauliNetworks, CollectPermutations)
    from qiskit_ibm_transpiler.ai.synthesis import (AICliffordSynthesis, AILinearFunctionSynthesis,
                                                     AIPauliNetworkSynthesis, AIPermutationSynthesis)

    from qcpso.bench.compare_ibm import FIELDS, _row
    from qcpso.bench.literature import _qasm, back_to_native, compact
    from qcpso.circuit import Circuit
    from qcpso.io import load
    from qcpso.io.qasm import parse_qasm, to_qasm
    from qcpso.native import native_directions, to_cx

    os.makedirs(os.path.join(args.out, "optimized"), exist_ok=True)
    want = [c for c in args.circuits.split(",") if c]
    paths = sorted(glob.glob(os.path.join(args.suite, "*.qasm")), key=os.path.getsize)
    csv_path = os.path.join(args.out, "results.csv")
    new_file = not os.path.exists(csv_path)
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        if want and name not in want:
            continue
        orig = load(p)
        small, used = compact(to_cx(orig))
        idx = {q: i for i, q in enumerate(used)}
        edges = sorted({(idx[a], idx[b]) for a, b in native_directions(orig)})
        cm = CouplingMap([list(e) for e in edges] + [[b, a] for a, b in edges])
        qc = qiskit.qasm2.loads(_qasm(small), custom_instructions=qiskit.qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        kw = dict(coupling_map=cm, replace_only_if_better=True, local_mode=True, max_threads=args.threads)
        stages = []
        for _ in range(args.reps):
            stages += [CollectCliffords(), AICliffordSynthesis(**kw),
                       CollectLinearFunctions(), AILinearFunctionSynthesis(**kw),
                       CollectPermutations(), AIPermutationSynthesis(**kw),
                       CollectPauliNetworks(), AIPauliNetworkSynthesis(**kw)]
        t = time.time()
        out_qc = PassManager(stages).run(qc)
        dt = time.time() - t
        from qiskit import transpile
        out_qc = transpile(out_qc, basis_gates=["cx", "u3"], optimization_level=0)   # unroll synthesised blocks
        res = parse_qasm(qiskit.qasm2.dumps(out_qc))
        if res.n_qubits < small.n_qubits:
            res = Circuit(small.n_qubits, res.gates)
        nat, ok = back_to_native(res, used, orig)
        row = _row(orig, name, "ibm_ai", 0, "", dt, nat, "" if ok else "violates coupling")
        with open(os.path.join(args.out, "optimized", f"{name}__ibm_ai__s0.qasm"), "w") as fh:
            fh.write(to_qasm(nat, clifford_t_names=False))
        with open(csv_path, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            if new_file:
                w.writeheader()
                new_file = False
            w.writerow(row)
        print(json.dumps({k: row.get(k) for k in ("circuit", "time", "ecr", "gates", "coupling_ok", "verified")}),
              flush=True)


if __name__ == "__main__":
    main()
