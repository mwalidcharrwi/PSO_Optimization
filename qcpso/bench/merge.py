"""Merge several benchmark output folders into one summary.

    python -m qcpso.bench.merge --objective twoq --out results/ibm_testset results/part_*
"""
from __future__ import annotations

import argparse
import csv
import json
import os

from .run import summarise

_INT = {"n_qubits", "seed", "gates", "cx", "twoq", "oneq", "t", "h", "depth", "twoq_depth", "evals"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("parts", nargs="+")
    ap.add_argument("--objective", default="twoq")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    args = ap.parse_args(argv)
    rows, original = [], {}
    for d in args.parts:
        with open(os.path.join(d, "results.csv")) as fh:
            for r in csv.DictReader(fh):
                for k in list(r):
                    if k in _INT:
                        r[k] = int(r[k])
                    elif k == "time":
                        r[k] = float(r[k])
                    elif k == "verified":
                        r[k] = {"True": True, "False": False}.get(r[k])
                rows.append(r)
        with open(os.path.join(d, "original.json")) as fh:
            original.update(json.load(fh))
    os.makedirs(args.out, exist_ok=True)
    fields = ["circuit", "n_qubits", "method", "seed", "gates", "cx", "twoq", "oneq", "t", "h", "depth",
              "twoq_depth", "time", "evals", "verified"]
    with open(os.path.join(args.out, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, "original.json"), "w") as fh:
        json.dump(original, fh)
    text = (args.title + "\n\n" if args.title else "") + summarise(rows, original, args.objective)
    with open(os.path.join(args.out, "summary.md"), "w") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
