"""Verify saved output circuits (<out>/circuits/*.qasm) against their inputs.

Uses statevector simulation on the used qubits when possible and MQT QCEC
otherwise.  Writes <out>/verification.csv.

    python -m qcpso.bench.verify_saved --inputs test_circuits_new results/ibm_part3a
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import time

from ..framework import verify
from ..io import load
from .qcec_verify import qcec_equivalent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True, help="folder with the original circuits")
    ap.add_argument("outs", nargs="+", help="benchmark output folders")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--only-large", action="store_true", help="only circuits with > 20 used qubits")
    args = ap.parse_args(argv)
    originals = {os.path.splitext(os.path.basename(p))[0].replace("^", ""): p
                 for p in glob.glob(os.path.join(args.inputs, "*.qasm"))}
    for out in args.outs:
        rows = []
        for path in sorted(glob.glob(os.path.join(out, "circuits", "*.qasm"))):
            name = os.path.basename(path)[:-5]
            circ_name, method, seed = name.split("__")
            if method == "qiskit_input":
                continue
            orig = load(originals[circ_name])
            opt = load(path)
            if opt.n_qubits < orig.n_qubits:
                from ..circuit import Circuit
                opt = Circuit(orig.n_qubits, opt.gates)
            used = len(orig.used_qubits() | opt.used_qubits())
            if args.only_large and used <= 20:
                continue
            t = time.time()
            v = verify(orig, opt)
            how = "statevector"
            if v is None:
                how = "qcec"
                verdict = qcec_equivalent(orig, opt, timeout=args.timeout)
            else:
                verdict = "equivalent" if v else "not_equivalent"
            rows.append(dict(circuit=circ_name, method=method, seed=seed, used_qubits=used, method_used=how,
                             verdict=verdict, seconds=round(time.time() - t, 1)))
            print(rows[-1], flush=True)
        with open(os.path.join(out, "verification.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["circuit", "method", "seed", "used_qubits", "method_used",
                                               "verdict", "seconds"])
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":  # pragma: no cover
    main()
