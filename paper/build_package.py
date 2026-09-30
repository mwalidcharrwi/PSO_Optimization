"""Build the paper results package from the saved experiment results.

    PYTHONPATH=. python paper/build_package.py

Reads ``results/`` (nothing is re-run) and writes
* ``paper/data/*.csv``  -- tidy numbers behind every table and figure,
* ``paper/figures/*.pdf|png`` -- figures,
* ``paper/tables.tex``  -- LaTeX (booktabs) tables.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from qcpso.bench.report_literature import input_metrics, load_rows, v1_rows  # noqa: E402

LIT = "results/ibm_literature"
OUT = "paper"
DATA, FIG = os.path.join(OUT, "data"), os.path.join(OUT, "figures")
os.makedirs(DATA, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

CIRCUITS = ["mult_8", "heisenberg_8", "add_17", "qae_17", "qft_16", "hubbard_8", "hhl_8", "heisenberg_32",
            "grover_10", "hubbard_18"]
SMALL = CIRCUITS[:7]
LABEL = {
    "qiskit": "Qiskit O3", "tket_mp": "TKET", "queso@60": "QUESO (1 min)", "queso@300": "QUESO (5 min)",
    "queso": "QUESO", "guoq@60": "GUOQ (1 min)", "guoq@300": "GUOQ (5 min)", "guoq": "GUOQ",
    "hypso_v1": "HyPSO-QCO v1 (swarm only)", "hypso_noswarm": "HyPSO-QCO w/o swarm phase",
    "hypso_w1": "HyPSO-QCO (1 worker)", "hypso": "HyPSO-QCO",
}
RELATED = ["qiskit", "tket_mp", "queso", "guoq"]


# ----------------------------------------------------------------------------- data
def load_all():
    rows = load_rows(LIT) + v1_rows()
    by = {}
    for r in rows:
        by[(r["circuit"], r["method"])] = r
    dev = {}
    with open(os.path.join(LIT, "verification.csv")) as fh:
        for r in csv.DictReader(fh):
            dev[(r["circuit"], r["method"])] = (float(r["deviation"]), r["check"], r["class"])
    return by, dev, input_metrics()


def val(by, c, m, k):
    r = by.get((c, m))
    return None if r is None or r.get(k) in (None, "") else float(r[k])


def red(x, x0):
    return 100.0 * (1 - x / x0)


def tt(name):
    return "\\texttt{" + name.replace("_", "\\_") + "}"


def write_csv(path, fields, rows):
    fields = list(fields) + [k for r in rows for k in r if k not in fields]
    fields = list(dict.fromkeys(fields))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def trace(json_path, total_time, input_ecr):
    """Best-so-far ECR over wall-clock time of a HyPSO-QCO v2 run.

    The memetic phases run one after another; their per-round logs are placed
    back-to-back so that the last phase ends at the run's total time (decoding
    gaps between phases are attributed to the swarm phase)."""
    d = json.load(open(json_path))
    phases = d["memetic"]
    durs = [ph[2][-1][1] for ph in phases]
    start = total_time - sum(durs)
    pts = [(0.0, input_ecr, None)]
    best = None
    t = start
    for (kind, j, hist), dur in zip(phases, durs):
        for _, tr, cost in hist:
            cost = tuple(cost)
            if best is None or cost < best:
                best = cost
            pts.append((t + tr, best[0], best[1]))
        t += dur
    return pts, start


# ----------------------------------------------------------------------------- stats
def wtl(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    w, l_ = int(np.sum(a < b - 1e-9)), int(np.sum(a > b + 1e-9))
    return w, len(a) - w - l_, l_


def wilcoxon_less(a, b):
    from scipy.stats import wilcoxon
    d = np.asarray(a, float) - np.asarray(b, float)
    return float("nan") if not np.any(np.abs(d) > 1e-9) else float(wilcoxon(d, alternative="less").pvalue)


# ----------------------------------------------------------------------------- built-in suites
def md_table(text, header_regex):
    """Parse the first Markdown table after a header line matching the regex."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.search(header_regex, ln):
            rows, j = [], i + 1
            while j < len(lines) and not lines[j].startswith("|"):
                j += 1
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip("|").split("|")])
                j += 1
            head, body = rows[0], [r for r in rows[2:]]
            return head, body
    raise KeyError(header_regex)


def builtin():
    suites = [("cliffordt", "Clifford+T (18 circuits, gates)", "gates"),
              ("continuous", "continuous {U3, CX} (11 circuits, CX)", "cx"),
              ("hardware_tokyo", "IBM Tokyo 20q (8 circuits, CX)", "cx")]
    out_red, out_h2h, out_rank = [], [], []
    for folder, name, metric in suites:
        text = open(f"results/{folder}/summary.md").read()
        head, body = md_table(text, r"^## Average reduction")
        for r in body:
            d = dict(zip(head, r))
            out_red.append(dict(suite=folder, method=d["method"], metric=metric,
                                reduction_pct=float(d[metric]), gates_pct=float(d["gates"]),
                                cx_pct=float(d["cx"]), time_s=float(d["mean time (s)"])))
        head, body = md_table(text, r"^## `hypso` vs\. each method")
        for r in body:
            d = dict(zip(head, r))
            out_h2h.append(dict(suite=folder, metric=metric, method=d["method"], wins=int(d["wins"]),
                                ties=int(d["ties"]), losses=int(d["losses"]),
                                mean_improvement_pct=float(d["mean improvement (%)"]),
                                wilcoxon_p=float(d["Wilcoxon p (one-sided)"])))
        head, body = md_table(text, r"^## Friedman")
        fr = re.search(r"Friedman: chi2 = ([\d.]+), p = ([\de.+-]+)", text)
        for r in body:
            out_rank.append(dict(suite=folder, method=r[0], avg_rank=float(r[1]),
                                 friedman_chi2=float(fr.group(1)), friedman_p=float(fr.group(2))))
    text = open("results/ablation/summary.md").read()
    head, body = md_table(text, r"^## Average reduction")
    abl = [dict(variant=r[0], gates_pct=float(r[1]), cx_pct=float(r[2]), depth_pct=float(r[4])) for r in body]
    head, body = md_table(text, r"^## `hypso` vs\. each method")
    for r in body:
        d = dict(zip(head, r))
        for a in abl:
            if a["variant"] == d["method"]:
                a.update(wins=int(d["wins"]), ties=int(d["ties"]), losses=int(d["losses"]),
                         full_better_by_pct=float(d["mean improvement (%)"]),
                         wilcoxon_p=float(d["Wilcoxon p (one-sided)"]))
    return suites, out_red, out_h2h, out_rank, abl


# ----------------------------------------------------------------------------- main
def main():
    by, dev, inp = load_all()
    # queso snapshots (kept out of the report tables) for the anytime figure
    with open(os.path.join(LIT, "queso", "results.csv")) as fh:
        for r in csv.DictReader(fh):
            by.setdefault((r["circuit"], r["method"]), r)

    # --- benchmarks
    bench = []
    for c in CIRCUITS:
        m = inp[c]
        bench.append(dict(circuit=c, used_qubits=m["used_qubits"], gates=m["gates"], ecr=m["ecr"],
                          oneq_phys=m["oneq_phys"], rz=m["rz"], depth=m["depth"], twoq_depth=m["twoq_depth"]))
    write_csv(os.path.join(DATA, "benchmarks.csv"), list(bench[0]), bench)

    # --- comparison
    methods = RELATED + ["guoq@60", "guoq@300", "queso@60", "queso@300", "hypso_v1", "hypso_w1", "hypso_noswarm",
                         "hypso"]
    comp = []
    for c in CIRCUITS:
        for m in methods:
            if (c, m) not in by:
                continue
            r = by[(c, m)]
            dv = dev.get((c, m))
            comp.append(dict(circuit=c, method=m, label=LABEL[m], ecr=int(float(r["ecr"])),
                             oneq_phys=int(float(r["oneq_phys"])), gates=int(float(r["gates"])),
                             depth=int(float(r["depth"])), time_s=r.get("time", ""),
                             ecr_reduction_pct=round(red(float(r["ecr"]), inp[c]["ecr"]), 2),
                             gates_reduction_pct=round(red(float(r["gates"]), inp[c]["gates"]), 2),
                             coupling_ok=r.get("coupling_ok", ""),
                             deviation=f"{dv[0]:.2e}" if dv else "", check=dv[1] if dv else "",
                             equivalence_class=dv[2] if dv else ""))
    write_csv(os.path.join(DATA, "ibm_comparison.csv"), list(comp[0]), comp)

    # --- summary statistics
    summ = []
    for m in RELATED + ["hypso_v1", "hypso"]:
        cs = [c for c in CIRCUITS if (c, m) in by]
        e = [red(val(by, c, m, "ecr"), inp[c]["ecr"]) for c in cs]
        g = [red(val(by, c, m, "gates"), inp[c]["gates"]) for c in cs]
        o = [red(val(by, c, m, "oneq_phys"), inp[c]["oneq_phys"]) for c in cs]
        dd = [red(val(by, c, m, "depth"), inp[c]["depth"]) for c in cs]
        row = dict(method=m, label=LABEL[m], circuits=len(cs), mean_ecr_red=np.mean(e), mean_gates_red=np.mean(g),
                   mean_oneq_red=np.mean(o), mean_depth_red=np.mean(dd),
                   geomean_ecr_ratio=float(np.exp(np.mean(np.log([1 - x / 100 for x in e])))))
        if m != "hypso":
            for k in ("ecr", "gates"):
                a = [val(by, c, "hypso", k) for c in cs]
                b = [val(by, c, m, k) for c in cs]
                w, t, l_ = wtl(a, b)
                row[f"hypso_{k}_w_t_l"] = f"{w}/{t}/{l_}"
                row[f"hypso_{k}_wilcoxon_p"] = wilcoxon_less(a, b)
        summ.append(row)
    for r in summ:
        for k, v in list(r.items()):
            if isinstance(v, (float, np.floating)):
                r[k] = round(float(v), 4)
    fields = sorted({k for r in summ for k in r}, key=lambda k: list(summ[0]).index(k) if k in summ[0] else 99)
    write_csv(os.path.join(DATA, "summary_stats.csv"), fields, summ)

    # --- compute-matched / ablation (7 circuits)
    abl7 = []
    for c in SMALL:
        abl7.append(dict(circuit=c, input_ecr=inp[c]["ecr"], guoq=int(val(by, c, "guoq", "ecr")),
                         hypso_1worker=int(val(by, c, "hypso_w1", "ecr")), hypso=int(val(by, c, "hypso", "ecr")),
                         hypso_no_swarm=int(val(by, c, "hypso_noswarm", "ecr")),
                         guoq_gates=int(val(by, c, "guoq", "gates")),
                         hypso_1worker_gates=int(val(by, c, "hypso_w1", "gates")),
                         hypso_gates=int(val(by, c, "hypso", "gates")),
                         hypso_no_swarm_gates=int(val(by, c, "hypso_noswarm", "gates"))))
    write_csv(os.path.join(DATA, "compute_matched_and_ablation.csv"), list(abl7[0]), abl7)

    # --- anytime traces
    tr_rows, traces = [], defaultdict(dict)
    for c in SMALL:
        for m, path in (("hypso", f"{LIT}/hypso/optimized/{c}__hypso__s0.json"),
                        ("hypso_w1", f"{LIT}/hypso_w1/{c}/optimized/{c}__hypso_w1__s0.json"),
                        ("hypso_noswarm", f"{LIT}/ablation/optimized/{c}__hypso_noswarm__s0.json")):
            pts, s0 = trace(path, val(by, c, m, "time"), inp[c]["ecr"])
            traces[c][m] = (pts, s0)
            for t, e, g in pts:
                tr_rows.append(dict(circuit=c, method=m, t_s=round(t, 1), best_ecr=e, best_gates=g if g else "",
                                    memetic_start_s=round(s0, 1)))
        for m in ("guoq", "queso"):
            pts = [(0.0, inp[c]["ecr"])] + [(float(s), val(by, c, f"{m}@{s}", "ecr")) for s in (60, 300)] + \
                  [(900.0, val(by, c, m, "ecr"))]
            traces[c][m] = (pts, None)
            for t, e in pts:
                tr_rows.append(dict(circuit=c, method=m, t_s=t, best_ecr=int(e), best_gates="", memetic_start_s=""))
    write_csv(os.path.join(DATA, "anytime_traces.csv"), list(tr_rows[0]), tr_rows)

    # --- phase breakdown (where the ECR reduction arises)
    ph_rows = []
    for c in CIRCUITS:
        d = json.load(open(f"{LIT}/hypso/optimized/{c}__hypso__s0.json"))
        phases = d["memetic"]
        elites = [p for p in phases if p[0] == "elite"]
        deep = [p for p in phases if p[0] == "deepen"]
        row = dict(circuit=c, input_ecr=inp[c]["ecr"], swarm_evals=d["evals"], after_phase1_ecr=d["swarm"]["twoq"],
                   elites_refined=len(elites), best_elite_ecr=min(p[2][-1][2][0] for p in elites),
                   after_deepening_ecr=deep[0][2][-1][2][0] if deep else "",
                   final_ecr=int(val(by, c, "hypso", "ecr")), memetic_rounds=sum(len(p[2]) - 1 for p in phases),
                   large_mode=int(d["evals"] <= 1))
        p2 = f"{LIT}/ablation/optimized/{c}__hypso_noswarm__s0.json"
        if os.path.exists(p2):
            d2 = json.load(open(p2))
            row.update(noswarm_seed_ecr=d2["swarm"]["twoq"], noswarm_rounds=sum(len(p[2]) - 1 for p in d2["memetic"]),
                       noswarm_final_ecr=int(val(by, c, "hypso_noswarm", "ecr")))
        ph_rows.append(row)
    write_csv(os.path.join(DATA, "phase_breakdown.csv"), list(ph_rows[0]), ph_rows)

    # --- built-in suites
    suites, bred, bh2h, brank, babl = builtin()
    write_csv(os.path.join(DATA, "builtin_reductions.csv"), list(bred[0]), bred)
    write_csv(os.path.join(DATA, "builtin_hypso_vs_methods.csv"), list(bh2h[0]), bh2h)
    write_csv(os.path.join(DATA, "builtin_ranks.csv"), list(brank[0]), brank)
    write_csv(os.path.join(DATA, "builtin_ablation.csv"), list(babl[0]), babl)

    import figs
    import diagrams
    figs.make(dict(by=by, inp=inp, circuits=CIRCUITS, small=SMALL, val=val, red=red, traces=traces, suites=suites,
                   bred=bred, babl=babl, phase=ph_rows, dev=dev), FIG)
    diagrams.make(FIG)
    tables(by, dev, inp, summ, abl7, bh2h, bred, brank, babl)
    print("package written to", OUT)


# ----------------------------------------------------------------------------- LaTeX tables
def tables(by, dev, inp, summ, abl7, bh2h, bred, brank, babl):
    L = ["% Generated by paper/build_package.py -- do not edit by hand.",
         "% Requires \\usepackage{booktabs}.", ""]

    def fmt(v):
        return f"{int(round(v)):,}".replace(",", "{,}")

    def bold_min(vals):
        m = min(v for v in vals if v is not None)
        return [("--" if v is None else (f"\\textbf{{{fmt(v)}}}" if abs(v - m) < 1e-9 else fmt(v))) for v in vals]

    # T1 benchmarks
    L += ["\\begin{table}[t]\\centering\\small",
          "\\caption{Benchmarks: IBM-Eagle-mapped circuits in $\\{rz, sx, x, ecr\\}$ (127-qubit device).}",
          "\\label{tab:benchmarks}",
          "\\begin{tabular}{lrrrrr}\\toprule",
          "circuit & used qubits & gates & ECR & $sx{+}x$ & depth \\\\\\midrule"]
    for c in CIRCUITS:
        m = inp[c]
        L.append(f"{tt(c)} & {m['used_qubits']} & {fmt(m['gates'])} & {fmt(m['ecr'])} & "
                 f"{fmt(m['oneq_phys'])} & {fmt(m['depth'])} \\\\")
    L += ["\\bottomrule\\end{tabular}\\end{table}", ""]

    # T2/T3 main metrics
    for key, cap, lab in (("ecr", "Two-qubit (ECR) gate count after optimisation (15\\,min per circuit for the anytime "
                                  "tools; best in bold).", "tab:ecr"),
                          ("gates", "Total native gate count after optimisation.", "tab:gates"),
                          ("oneq_phys", "Physical single-qubit gates ($sx+x$; $rz$ is virtual).", "tab:oneq"),
                          ("depth", "Circuit depth.", "tab:depth")):
        ms = RELATED + (["hypso_v1"] if key == "ecr" else []) + ["hypso"]
        L += ["\\begin{table}[t]\\centering\\small", f"\\caption{{{cap}}}", f"\\label{{{lab}}}",
              "\\begin{tabular}{l r " + "r" * len(ms) + "}\\toprule",
              "circuit & input & " + " & ".join(LABEL[m].replace(" (swarm only)", "") for m in ms) + " \\\\\\midrule"]
        for c in CIRCUITS:
            vals = [val(by, c, m, key) for m in ms]
            L.append(f"{tt(c)} & {fmt(inp[c][key])} & " + " & ".join(bold_min(vals)) +
                     " \\\\")
        reds = []
        for m in ms:
            reds.append(np.mean([red(val(by, c, m, key), inp[c][key]) for c in CIRCUITS]))
        L += ["\\midrule", "mean reduction & -- & " + " & ".join(f"{r:.1f}\\%" for r in reds) + " \\\\",
              "\\bottomrule\\end{tabular}\\end{table}", ""]

    # T4 statistics
    L += ["\\begin{table}[t]\\centering\\small",
          "\\caption{HyPSO-QCO vs each tool over the 10 circuits: wins/ties/losses and one-sided Wilcoxon "
          "signed-rank $p$ (HyPSO-QCO $<$ tool).}", "\\label{tab:stats}",
          "\\begin{tabular}{lcccc}\\toprule",
          "& \\multicolumn{2}{c}{ECR} & \\multicolumn{2}{c}{total gates} \\\\",
          "tool & W/T/L & $p$ & W/T/L & $p$ \\\\\\midrule"]
    for r in summ:
        if r["method"] == "hypso":
            continue
        L.append(f"{r['label'].replace(' (swarm only)', '')} & {r['hypso_ecr_w_t_l']} & {r['hypso_ecr_wilcoxon_p']:.3f} & "
                 f"{r['hypso_gates_w_t_l']} & {r['hypso_gates_wilcoxon_p']:.3f} \\\\")
    L += ["\\bottomrule\\end{tabular}\\end{table}", ""]

    # T5 compute matched + ablation
    L += ["\\begin{table}[t]\\centering\\small",
          "\\caption{Compute-matched run (1 resynthesis worker, like GUOQ's single search thread) and ablation of "
          "the swarm phase (whole budget to the memetic phase). ECR count / total gates, 15\\,min each.}",
          "\\label{tab:ablation}",
          "\\begin{tabular}{lcccc}\\toprule",
          "circuit & GUOQ & HyPSO-QCO (1 worker) & HyPSO-QCO & w/o swarm phase \\\\\\midrule"]
    for r in abl7:
        L.append(f"{tt(r['circuit'])} & {fmt(r['guoq'])} / {fmt(r['guoq_gates'])} & "
                 f"{fmt(r['hypso_1worker'])} / {fmt(r['hypso_1worker_gates'])} & "
                 f"{fmt(r['hypso'])} / {fmt(r['hypso_gates'])} & "
                 f"{fmt(r['hypso_no_swarm'])} / {fmt(r['hypso_no_swarm_gates'])} \\\\")
    means = []
    for k in ("guoq", "hypso_1worker", "hypso", "hypso_no_swarm"):
        means.append(np.mean([red(r[k], r["input_ecr"]) for r in abl7]))
    L += ["\\midrule", "mean ECR reduction & " + " & ".join(f"{m:.1f}\\%" for m in means) + " \\\\",
          "\\bottomrule\\end{tabular}\\end{table}", ""]

    # T6 verification
    L += ["\\begin{table}[t]\\centering\\small",
          "\\caption{Equivalence of every output with its input: largest deviation over the checked circuits "
          "(random-state test for $\\le 20$ used qubits, Choi-state MPS miter for \\texttt{heisenberg\\_32}).}",
          "\\label{tab:verification}",
          "\\begin{tabular}{lrl}\\toprule", "method & max.\\ deviation & worst circuit \\\\\\midrule"]
    for m in RELATED + ["hypso", "hypso_w1", "hypso_noswarm"]:
        ds = [(d[0], c) for (c, mm), d in dev.items() if mm == m and not (m == "qiskit" and d[0] > 0.5)]
        d0, c0 = max(ds)
        L.append(f"{LABEL[m]} & {d0:.1e} & {tt(c0)} \\\\")
    L += ["\\bottomrule\\end{tabular}", "\\\\[2pt]\\footnotesize Qiskit's output on \\texttt{heisenberg\\_32} "
          "(undirected-map fallback) fails the same-qubit contract (deviation 0.98) and is excluded above. "
          "\\texttt{hubbard\\_18} (31 used qubits) has no end-to-end check for any tool.",
          "\\end{table}", ""]

    # T7 built-in suites: search strategies
    L += ["\\begin{table}[t]\\centering\\small",
          "\\caption{Search strategies on the same genome, decoder and budget (built-in logical suites, 3 seeds). "
          "Mean reduction of the primary metric vs the lowered input; HyPSO-QCO vs each: W/T/L and one-sided "
          "Wilcoxon $p$.}", "\\label{tab:search}",
          "\\begin{tabular}{l" + "rc" * 3 + "}\\toprule",
          "& \\multicolumn{2}{c}{Clifford+T (18; gates)} & \\multicolumn{2}{c}{continuous (11; CX)} & "
          "\\multicolumn{2}{c}{IBM Tokyo (8; CX)} \\\\",
          "method & red. & W/T/L ($p$) & red. & W/T/L ($p$) & red. & W/T/L ($p$) \\\\\\midrule"]
    lab = {"greedy": "greedy (no search)", "rs": "random search", "spso": "canonical PSO", "ga": "GA",
           "sa": "SA", "hypso": "HyPSO-QCO", "qiskit": "Qiskit O3", "tket": "TKET", "pyzx": "PyZX"}
    for m in ["greedy", "rs", "spso", "ga", "sa", "qiskit", "tket", "pyzx", "hypso"]:
        cells = []
        for s in ("cliffordt", "continuous", "hardware_tokyo"):
            rr = [r for r in bred if r["suite"] == s and r["method"] == m]
            hh = [r for r in bh2h if r["suite"] == s and r["method"] == m]
            if not rr:
                cells += ["--", "--"]
                continue
            cells.append(f"{rr[0]['reduction_pct']:.1f}\\%")
            cells.append("--" if not hh else f"{hh[0]['wins']}/{hh[0]['ties']}/{hh[0]['losses']} "
                                             f"({hh[0]['wilcoxon_p']:.3g})")
        L.append(f"{lab[m]} & " + " & ".join(cells) + " \\\\")
    L += ["\\bottomrule\\end{tabular}\\end{table}", ""]

    # T8 component ablation
    L += ["\\begin{table}[t]\\centering\\small",
          "\\caption{Component ablation of the swarm (6 Toffoli-heavy circuits, 600 evaluations, 3 seeds): mean "
          "gate reduction and full swarm vs variant (W/T/L, one-sided Wilcoxon $p$).}", "\\label{tab:components}",
          "\\begin{tabular}{lrcr}\\toprule", "variant & gate red. & W/T/L & $p$ \\\\\\midrule"]
    for a in babl:
        if a["variant"] == "hypso":
            L.append(f"full HyPSO-QCO swarm & {a['gates_pct']:.1f}\\% & -- & -- \\\\")
        else:
            L.append(f"{tt(a['variant'])} & {a['gates_pct']:.1f}\\% & "
                     f"{a['wins']}/{a['ties']}/{a['losses']} & {a['wilcoxon_p']:.3f} \\\\")
    L += ["\\bottomrule\\end{tabular}\\end{table}", ""]
    open(os.path.join(OUT, "tables.tex"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
