"""Compact report for the IBM-native test set (input vs Qiskit vs greedy vs
standard PSO vs HyPSO-QCO).

    python -m qcpso.bench.report_ibm results/ibm_testset > results/ibm_testset/REPORT.md
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

METHODS = ["qiskit", "greedy", "spso", "hypso"]
LABEL = {"qiskit": "Qiskit O3", "greedy": "greedy (no swarm)", "spso": "standard PSO", "hypso": "HyPSO-QCO"}


def _load(d):
    with open(os.path.join(d, "results.csv")) as fh:
        rows = list(csv.DictReader(fh))
    with open(os.path.join(d, "original.json")) as fh:
        orig = json.load(fh)
    ver = {}
    vpath = os.path.join(d, "verification.csv")
    if os.path.exists(vpath):
        with open(vpath) as fh:
            for r in csv.DictReader(fh):
                ver[(r["circuit"], r["method"], r["seed"])] = r["verdict"]
    return rows, orig, ver


def main(argv=None):
    d = (argv or sys.argv[1:])[0]
    rows, orig, ver = _load(d)
    agg = defaultdict(lambda: defaultdict(list))
    vstat = defaultdict(set)
    for r in rows:
        c, m = r["circuit"], r["method"]
        agg[c][m].append({k: float(r[k]) for k in ("twoq", "gates", "depth", "time")})
        v = r["verified"]
        if v in ("", "None"):
            v = ver.get((c, m, "s" + r["seed"]), "unchecked")
        vstat[(c, m)].add({"True": "verified", "False": "FAILED"}.get(v, v))
    circuits = sorted(agg, key=lambda c: orig[c]["gates"])
    out = []
    for metric, title in (("twoq", "Two-qubit (ECR) gate count"), ("gates", "Total native gate count"),
                          ("depth", "Circuit depth")):
        out += [f"### {title} (mean over seeds; best in bold)", "",
                "| circuit | used qubits | input | " + " | ".join(LABEL[m] for m in METHODS) + " | HyPSO vs input |",
                "|---|---|---|" + "---|" * len(METHODS) + "---|"]
        for c in circuits:
            vals = {m: np.mean([x[metric] for x in agg[c][m]]) for m in METHODS if agg[c].get(m)}
            best = min(list(vals.values()) + [orig[c][metric]])
            cells = []
            for m in METHODS:
                if m not in vals:
                    cells.append("–")
                    continue
                s = f"{vals[m]:.1f}" if vals[m] != int(vals[m]) else f"{int(vals[m])}"
                cells.append(f"**{s}**" if abs(vals[m] - best) < 1e-9 else s)
            o = orig[c][metric]
            red = f"{100 * (1 - vals['hypso'] / o):+.2f} %" if "hypso" in vals and o else "–"
            red = red.replace("+", "−", 1) if red.startswith("+") else red.replace("-", "+", 1)
            out.append(f"| {c} | {orig[c]['n_qubits']} | {int(o)} | " + " | ".join(cells) + f" | {red} |")
        out.append("")
    out += ["### Runs, budgets and verification", "",
            "| circuit | method | seeds | mean time (s) | equivalence |", "|---|---|---|---|---|"]
    for c in circuits:
        for m in METHODS:
            if agg[c].get(m):
                out.append(f"| {c} | {LABEL[m]} | {len(agg[c][m])} | "
                           f"{np.mean([x['time'] for x in agg[c][m]]):.0f} | {', '.join(sorted(vstat[(c, m)]))} |")
    print("\n".join(out))


if __name__ == "__main__":  # pragma: no cover
    main()
