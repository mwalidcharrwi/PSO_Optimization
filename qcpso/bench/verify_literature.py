"""Deviation of every saved output under results/ibm_literature from its input.

* <= 20 used qubits: random-state deviation (see :mod:`qcpso.bench.deviation`);
* larger circuits: Choi-state MPS miter (:mod:`qcpso.bench.mps_verify`),
  deviation = 1 - |<Phi+|A B^+ x I|Phi+>|.

Classes: ``exact`` (< 1e-9), ``numerically exact`` (< 1e-6), ``approximate``.

    python -m qcpso.bench.verify_literature results/ibm_literature [--large] [--only substr]
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import time

from ..circuit import Circuit
from ..io import load
from .deviation import deviation

FIELDS = ["file", "circuit", "method", "seed", "used_qubits", "check", "deviation", "class", "seconds", "detail"]


def classify(dev):
    if dev is None:
        return "unchecked"
    return "exact" if dev < 1e-9 else ("numerically exact" if dev < 1e-6 else "approximate")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--suite", default="test_circuits_new")
    ap.add_argument("--large", action="store_true", help="also run the MPS miter for > 20 used qubits")
    ap.add_argument("--only", default="", help="substring filter on file names")
    ap.add_argument("--max-bond", type=int, default=2048)
    args = ap.parse_args(argv)
    out_csv = os.path.join(args.root, "verification.csv")
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv) as fh:
            done = {r["file"] for r in csv.DictReader(fh) if r["class"] != "unchecked"}
    files = sorted(glob.glob(os.path.join(args.root, "**", "optimized", "*.qasm"), recursive=True))
    new = not os.path.exists(out_csv)
    for path in files:
        rel = os.path.relpath(path, args.root)
        if rel in done or (args.only and args.only not in rel):
            continue
        name, method, seed = os.path.basename(path)[:-5].split("__")
        orig = load(os.path.join(args.suite, name + ".qasm"))
        out = load(path)
        if out.n_qubits < orig.n_qubits:
            out = Circuit(orig.n_qubits, out.gates)
        t = time.time()
        d = deviation(orig, out)
        check, dev, detail = "statevector", d["state_err"], ""
        if dev is None:
            if not args.large:
                continue
            from .mps_verify import choi_equivalence
            r = choi_equivalence(orig, out, max_bond=args.max_bond)
            check, dev = "choi-mps", 1.0 - r["overlap"]
            detail = f"peak bond {r['peak_bond']}{' (truncated)' if r['truncated'] else ''}"
        row = dict(file=rel, circuit=name, method=method, seed=seed.lstrip("s"), used_qubits=d["used_qubits"],
                   check=check, deviation=f"{dev:.3e}", **{"class": classify(dev)},
                   seconds=round(time.time() - t, 1), detail=detail)
        with open(out_csv, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if new:
                w.writeheader()
                new = False
            w.writerow(row)
        print(row, flush=True)


if __name__ == "__main__":  # pragma: no cover
    main()
