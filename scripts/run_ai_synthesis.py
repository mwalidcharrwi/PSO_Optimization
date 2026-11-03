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


def _clifford_words():
    """The 24 single-qubit Cliffords as shortest words over {h, s, sdg, x, z} (up to phase)."""
    import itertools
    import numpy as np
    from qcpso.circuit import Gate
    mats = {"h": np.array([[1, 1], [1, -1]]) / np.sqrt(2), "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
            "x": np.array([[0, 1], [1, 0]]), "z": np.diag([1, -1])}
    words = {}
    for length in range(0, 5):
        for w in itertools.product(mats, repeat=length):
            u = np.eye(2, dtype=complex)
            for g in w:
                u = mats[g] @ u
            key = _canon(u)
            if key not in words:
                words[key] = list(w)
    assert len(words) == 24, len(words)
    return words


def _canon(u):
    import numpy as np
    k = np.argmax(np.abs(u.ravel()) > 1e-6)
    v = u / (u.ravel()[k] / abs(u.ravel()[k]))
    return tuple(np.round(v.ravel(), 6))


def expose_cliffords(circ):
    """Exact rewrite of every maximal single-qubit run: a Clifford run becomes named Clifford gates
    (so that IBM's collectors see it, as they would before basis translation); any other run
    becomes rz . sx . rz . sx . rz."""
    import numpy as np
    from qcpso.circuit import Circuit, Gate
    from qcpso.linalg import u3_params
    words = _clifford_words()
    out, run = [], {}

    def flush(q):
        u = run.pop(q, None)
        if u is None:
            return
        w = words.get(_canon(u))
        if w is not None:
            out.extend(Gate(g, (q,)) for g in w)
            return
        t, p, l = u3_params(u)   # U3(t, p, l) = e^{i(p+l)/2} Rz(p) Rx(-pi/2) ... ; use the ZSXZSXZ form
        out.extend([Gate("rz", (q,), (l,)), Gate("sx", (q,)), Gate("rz", (q,), (t + np.pi,)), Gate("sx", (q,)),
                    Gate("rz", (q,), (p + 3 * np.pi,))])

    for g in circ.gates:
        if len(g.qubits) == 1:
            run[g.qubits[0]] = g.matrix() @ run.get(g.qubits[0], np.eye(2, dtype=complex))
        else:
            for q in g.qubits:
                flush(q)
            out.append(g)
    for q in list(run):
        flush(q)
    return Circuit(circ.n_qubits, out, circ.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default=os.path.join(ROOT, "test_circuits_new"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "ibm_revision", "ai_synthesis"))
    ap.add_argument("--circuits", default="")
    ap.add_argument("--reps", type=int, default=2, help="passes over the four collect/synthesise stages")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--pauli", action="store_true",
                    help="also run AIPauliNetworkSynthesis (off: in local mode its output was not equivalent to "
                         "its input on mult_8, 67 instead of 311 CX, so it cannot be used under the contract)")
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
        small = expose_cliffords(small)
        idx = {q: i for i, q in enumerate(used)}
        edges = sorted({(idx[a], idx[b]) for a, b in native_directions(orig)})
        cm = CouplingMap([list(e) for e in edges] + [[b, a] for a, b in edges])
        qc = qiskit.qasm2.loads(_qasm(small), custom_instructions=qiskit.qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
        kw = dict(coupling_map=cm, replace_only_if_better=True, local_mode=True, max_threads=args.threads)
        stages = []
        for _ in range(args.reps):   # IBM's level-3 post-routing collection (front and back), all four syntheses
            for back in (False, True):
                stages += [CollectCliffords(collect_from_back=back), AICliffordSynthesis(**kw),
                           CollectLinearFunctions(do_commutative_analysis=True, collect_from_back=back),
                           AILinearFunctionSynthesis(**kw),
                           CollectPermutations(collect_from_back=back), AIPermutationSynthesis(**kw)]
                if args.pauli:
                    stages += [CollectPauliNetworks(collect_from_back=back), AIPauliNetworkSynthesis(**kw)]
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
