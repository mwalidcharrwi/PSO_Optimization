"""Stage-by-stage contribution analysis for IBM-native circuits.

S0 input
S1 native re-synthesis only: ECR -> CX (default lowering) -> ECR with the
   greedy Clifford-wrapper choice and minimal {rz, sx, x} runs (no rewriting)
S2 + CNOT-level sound passes (cancellation, phase folding, H-reduction)
S3 + optimal two-qubit block resynthesis          (= the deterministic 'greedy')
S4 + swarm search (HyPSO-QCO, best run from results.csv)

    python -m qcpso.bench.breakdown_ibm test_circuits_new results/ibm_testset
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
import time

from ..decompose import Lowerer
from ..io import load
from ..native import native_directions, to_native
from ..pipeline import GREEDY_SCHEDULE, apply_pass, cleanup, finish, metrics


def stages(circ):
    nat = native_directions(circ)
    low = Lowerer().lower(circ)
    s1 = to_native(low, nat)
    c = low
    for p in GREEDY_SCHEDULE:
        c = apply_pass(p, c, None, "ibm")
    c = cleanup(c, None, "ibm")
    s2 = to_native(c, nat)
    s3 = to_native(finish(c, "continuous", None), nat)
    return s1, s2, s3


def main(argv=None):
    argv = argv or sys.argv[1:]
    inputs, res_dir = argv[0], argv[1]
    best = {}
    with open(os.path.join(res_dir, "results.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["method"] == "hypso":
                k = (int(r["twoq"]), int(r["gates"]), int(r["depth"]))
                if r["circuit"] not in best or k < best[r["circuit"]]:
                    best[r["circuit"]] = k
    out = {}
    paths = sorted(glob.glob(os.path.join(inputs, "*.qasm")), key=os.path.getsize)
    for p in paths:
        circ = load(p)
        t = time.time()
        s1, s2, s3 = stages(circ)
        row = {"S0": metrics(circ), "S1": metrics(s1), "S2": metrics(s2), "S3": metrics(s3)}
        row = {k: {m: v[m] for m in ("twoq", "gates", "depth")} for k, v in row.items()}
        if circ.name in best:
            row["S4"] = dict(zip(("twoq", "gates", "depth"), best[circ.name]))
        out[circ.name] = row
        print(circ.name, json.dumps(row), f"{time.time() - t:.0f}s", flush=True)
        with open(os.path.join(res_dir, "breakdown.json"), "w") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":  # pragma: no cover
    main()
