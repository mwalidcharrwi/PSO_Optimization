"""Side-by-side report: HyPSO-QCO vs related work on the supplied circuits.

    python -m qcpso.bench.report_literature results/ibm_literature > results/ibm_literature/REPORT_TABLES.md

Reads every ``results.csv`` below the given folder (one sub-folder per run
group, written by :mod:`qcpso.bench.compare_ibm`) plus the v1 results in
``results/ibm_testset`` and prints Markdown tables (means over seeds).
"""
from __future__ import annotations

import csv
import glob
import math
import os
import sys
from collections import defaultdict

import numpy as np

ORDER = ["qiskit", "tket_mp", "bqskit", "queso", "guoq@60", "guoq@300", "guoq", "hypso_v1", "hypso_noswarm",
         "hypso_nosparse", "hypso_w1", "hypso"]
LABEL = {
    "qiskit": "Qiskit O3", "tket_mp": "TKET (conn.-preserving)", "bqskit": "BQSKit O3", "queso": "QUESO (15 min)",
    "guoq@60": "GUOQ 1 min", "guoq@300": "GUOQ 5 min", "guoq": "GUOQ 15 min", "hypso_v1": "HyPSO-QCO v1",
    "hypso_noswarm": "v2 w/o swarm", "hypso_nosparse": "v2 w/o sparsify", "hypso_w1": "v2, 1 worker",
    "hypso": "**HyPSO-QCO v2 (15 min)**",
}
INPUT_ORDER = ["mult_8", "heisenberg_8", "add_17", "qae_17", "qft_16", "hubbard_8", "hhl_8", "heisenberg_32",
               "grover_10", "hubbard_18"]


def load_rows(root: str):
    rows = []
    for path in glob.glob(os.path.join(root, "**", "results.csv"), recursive=True):
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r.get("ecr") not in (None, ""):
                    rows.append(r)
    return rows


def v1_rows(v1_dir: str = "results/ibm_testset"):
    """HyPSO-QCO v1 outputs (saved optimised circuits) re-measured in the same way."""
    from ..io import load
    from .compare_ibm import native_metrics
    rows = []
    for path in sorted(glob.glob(os.path.join(v1_dir, "optimized", "*_hypso.qasm"))):
        name = os.path.basename(path)[: -len("_hypso.qasm")]
        m = native_metrics(load(path))
        rows.append(dict(circuit=name, method="hypso_v1", seed="0", time="", **{k: str(v) for k, v in m.items()}))
    return rows


def input_metrics(suite: str = "test_circuits_new"):
    from ..io import load
    from .compare_ibm import native_metrics
    out = {}
    for path in glob.glob(os.path.join(suite, "*.qasm")):
        c = load(path)
        m = native_metrics(c)
        m["used_qubits"] = len(c.used_qubits())
        out[os.path.splitext(os.path.basename(path))[0]] = m
    return out


def aggregate(rows):
    agg = defaultdict(lambda: defaultdict(list))
    ver = defaultdict(set)
    for r in rows:
        agg[(r["circuit"], r["method"])]["_n"].append(1)
        for k in ("ecr", "oneq_phys", "gates", "depth", "time", "sx", "x", "rz"):
            if r.get(k) not in (None, ""):
                agg[(r["circuit"], r["method"])][k].append(float(r[k]))
        if r.get("verified"):
            ver[(r["circuit"], r["method"])].add(r["verified"])
        if r.get("coupling_ok") == "False":
            ver[(r["circuit"], r["method"])].add("COUPLING VIOLATED")
    return agg, ver


def fidelity_estimate(m, e2=7e-3, e1=2.5e-4):
    """Estimated success probability with IBM-Eagle-like error rates (rz virtual)."""
    return math.exp(m["ecr"] * math.log1p(-e2) + m["oneq_phys"] * math.log1p(-e1))


def _fmt(v):
    return f"{v:,.1f}" if abs(v - round(v)) > 1e-9 else f"{int(round(v)):,}"


def table(agg, inp, metric, title, methods, circuits, lower_better=True):
    out = [f"### {title}", "",
           "| circuit | input | " + " | ".join(LABEL.get(m, m) for m in methods) + " |",
           "|---|---:|" + "---:|" * len(methods)]
    for c in circuits:
        vals = {m: float(np.mean(agg[(c, m)][metric])) for m in methods if agg.get((c, m), {}).get(metric)}
        best = min(vals.values()) if vals else None
        cells = []
        for m in methods:
            if m not in vals:
                cells.append("–")
                continue
            s = _fmt(vals[m])
            cells.append(f"**{s}**" if best is not None and abs(vals[m] - best) < 1e-9 else s)
        out.append(f"| {c} | {_fmt(inp[c][metric])} | " + " | ".join(cells) + " |")
    out.append("")
    return out


def reductions(agg, inp, metric, methods, circuits):
    out = [f"| method | mean {metric} reduction vs input | geo-mean ratio | circuits |", "|---|---:|---:|---:|"]
    for m in methods:
        rs = [np.mean(agg[(c, m)][metric]) / inp[c][metric] for c in circuits if agg.get((c, m), {}).get(metric)]
        if rs:
            out.append(f"| {LABEL.get(m, m)} | {100 * (1 - np.mean(rs)):.1f} % | {np.exp(np.mean(np.log(rs))):.3f} "
                       f"| {len(rs)} |")
    out.append("")
    return out


def head_to_head(agg, circuits, ref, others, metric):
    from scipy.stats import wilcoxon
    out = [f"| HyPSO-QCO v2 vs | {metric}: wins / ties / losses | one-sided Wilcoxon p |", "|---|---|---:|"]
    for m in others:
        pairs = [(np.mean(agg[(c, ref)][metric]), np.mean(agg[(c, m)][metric])) for c in circuits
                 if agg.get((c, ref), {}).get(metric) and agg.get((c, m), {}).get(metric)]
        if not pairs:
            continue
        a = np.array(pairs)
        w = int(np.sum(a[:, 0] < a[:, 1] - 1e-9))
        l_ = int(np.sum(a[:, 0] > a[:, 1] + 1e-9))
        t = len(a) - w - l_
        d = a[:, 0] - a[:, 1]
        p = wilcoxon(d, alternative="less").pvalue if np.any(np.abs(d) > 1e-9) else float("nan")
        out.append(f"| {LABEL.get(m, m)} | {w} / {t} / {l_} | {p:.4f} |")
    out.append("")
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    root = argv[0]
    rows = load_rows(root) + v1_rows()
    inp = input_metrics()
    agg, ver = aggregate(rows)
    methods = [m for m in ORDER if any((c, m) in agg for c in inp)]
    circuits = [c for c in INPUT_ORDER if c in inp]
    for c in circuits:
        inp[c]["fid"] = fidelity_estimate(inp[c])
        for m in methods:
            if (c, m) in agg and agg[(c, m)].get("ecr") and agg[(c, m)].get("oneq_phys"):
                agg[(c, m)]["fid"] = [fidelity_estimate(dict(ecr=e, oneq_phys=o))
                                      for e, o in zip(agg[(c, m)]["ecr"], agg[(c, m)]["oneq_phys"])]
    out = []
    out += table(agg, inp, "ecr", "Two-qubit (ECR) gate count", methods, circuits)
    out += table(agg, inp, "oneq_phys", "Physical single-qubit gates (sx + x; rz is virtual)", methods, circuits)
    out += table(agg, inp, "gates", "Total native gates (rz + sx + x + ecr)", methods, circuits)
    out += table(agg, inp, "depth", "Circuit depth", methods, circuits)
    out += ["### Estimated success probability (ECR error 7e-3, sx/x error 2.5e-4, rz free)", "",
            "| circuit | input | " + " | ".join(LABEL.get(m, m) for m in methods) + " |",
            "|---|---:|" + "---:|" * len(methods)]
    for c in circuits:
        cells = []
        for m in methods:
            f = agg.get((c, m), {}).get("fid")
            cells.append(f"{np.mean(f):.3g}" if f else "–")
        out.append(f"| {c} | {inp[c]['fid']:.3g} | " + " | ".join(cells) + " |")
    out.append("")
    out += ["### Mean reductions over the circuits each method completed", ""]
    for metric in ("ecr", "oneq_phys", "gates"):
        out += reductions(agg, inp, metric, methods, circuits)
    if any((c, "hypso") in agg for c in circuits):
        others = [m for m in methods if m != "hypso"]
        for metric in ("ecr", "gates"):
            out += head_to_head(agg, circuits, "hypso", others, metric)
    devs = defaultdict(list)
    vpath = os.path.join(root, "verification.csv")
    if os.path.exists(vpath):
        with open(vpath) as fh:
            for r in csv.DictReader(fh):
                devs[(r["circuit"], r["method"])].append((float(r["deviation"]), r["check"]))
    out += ["### Runtime (s) and verification", "",
            "Deviation: random-state (<= 20 qubits) or Choi-MPS (> 20 qubits) distance to the input, maximum over "
            "seeds; < 1e-9 exact, < 1e-6 numerically exact, otherwise approximate.", "",
            "| circuit | method | seeds | mean time (s) | max deviation | check | coupling / ECR directions |",
            "|---|---|---:|---:|---:|---|---|"]
    for c in circuits:
        for m in methods:
            if (c, m) in agg:
                t = agg[(c, m)].get("time")
                v = ver.get((c, m), set())
                cp = "VIOLATED" if "COUPLING VIOLATED" in v else "ok"
                dv = devs.get((c, m))
                dev = f"{max(d for d, _ in dv):.1e}" if dv else "–"
                chk = dv[0][1] if dv else "–"
                ts = f"{np.mean(t):.0f}" if t else "–"
                out.append(f"| {c} | {LABEL.get(m, m)} | {len(agg[(c, m)]['_n'])} | {ts} | {dev} | {chk} | {cp} |")
    print("\n".join(out))


if __name__ == "__main__":  # pragma: no cover
    main()
