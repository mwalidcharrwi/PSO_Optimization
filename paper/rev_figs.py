"""Figures for the revised DAC paper, at their final printed size.

    PYTHONPATH=. python paper/rev_figs.py

IEEE two-column: one column = 3.5 in, full width = 7.16 in.  Every figure is
drawn at that width (no scaling in LaTeX), in a Times-metric serif at 8 pt
(ticks and legends 7.5 pt), so the text matches the paper body.

Data: results/ibm_revision (revision runs) and results/ibm_literature (TKET,
QUESO); definitions as in qcpso.bench.report_revision.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from qcpso.bench.report_revision import CIRCUITS, LARGE, SMALL, collect, inputs, stat  # noqa: E402

OUT = os.path.join("paper", "figures_rev")
REV = "results/ibm_revision"
COL, FULL = 3.5, 7.16
BLUE, BLUE_L, ORANGE, AQUA, YELLOW, PINK, GREEN, GRAY = ("#2a78d6", "#86b6ef", "#eb6834", "#1baf7a", "#eda100",
                                                         "#e87ba4", "#008300", "#9b9a95")
INK, INK2, GRID, AXIS = "#0b0b0b", "#3d3c39", "#e1e0d9", "#a8a79f"


def setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5, "legend.frameon": False,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
        "xtick.major.size": 2.5, "ytick.major.size": 0, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
        "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "savefig.dpi": 300})
    return plt


def save(plt, fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    fig.savefig(os.path.join(OUT, name + ".png"))
    plt.close(fig)


# ----------------------------------------------------------------------------------------- data
def bq_tool(runs):
    return "bqskit_del2" if len(runs.get("bqskit_del2", {})) > len(runs.get("bqskit_del", {})) else "bqskit_del"


def mean_reduction(runs, inp, tool, key, circuits=CIRCUITS):
    rr = [1 - stat(runs, tool, c, key)[0] / inp[c][key] for c in circuits if stat(runs, tool, c, key)]
    return (100 * float(np.mean(rr)), len(rr)) if rr else (None, 0)


def _starts():
    """Start time (epoch) of every revision job, from the lane logs (last start wins)."""
    st = {}
    for f in glob.glob(os.path.join(REV, "logs", "lane_*.log")) + [os.path.join(REV, "logs", "phaseBC.log")]:
        if not os.path.exists(f):
            continue
        for line in open(f):
            m = re.match(r"^(\S+Z) start (\S+)", line)
            if m:
                st[m.group(2)] = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=dt.timezone.utc).timestamp()
    return st


def guoq_traces(inp):
    """{(circuit, seed): [(t_min, ecr)]} best-so-far traces of the revision GUOQ runs (30 s resolution),
    anchored with the recorded snapshots."""
    starts = _starts()
    tr = {}
    path = os.path.join(REV, "guoq_trace_phaseA.csv")   # committed copy (the live trace is not in git)
    if not os.path.exists(path):
        path = os.path.join(REV, "guoq_trace.csv")
    rows = list(csv.DictReader(open(path))) if os.path.exists(path) else []
    for r in rows:
        wd = r.get("workdir") or ""
        if not (str(r.get("mtime_s", "")).isdigit() and str(r.get("cx", "")).isdigit()):
            continue
        m = re.match(r".*guoq_([ab])/work/(.+)_guoq_s(\d+)$", wd)
        if not m:
            continue
        lane, c, s = m.group(1), m.group(2), int(m.group(3))
        if c not in inp:   # e.g. "heisenberg_32_tket": the GUOQ stage of TKET -> GUOQ
            continue
        jid = [k for k in starts if k.startswith(f"{lane}_{c}_guoq_s{s}_t")]
        if not jid:
            continue
        t0 = starts[jid[0]]
        t = (int(r["mtime_s"]) - t0) / 60
        if 0 <= t <= 61:
            tr.setdefault((c, s), []).append((t, int(r["cx"])))
    out = {}
    for (c, s), pts in tr.items():
        pts = sorted(set(pts))
        best, cur = [(0.0, inp[c]["ecr"])], inp[c]["ecr"]
        for t, e in pts:
            if e < cur:
                cur = e
                best.append((t, e))
        out[(c, s)] = best
    return out


def hypso_trace(path, total_s, input_ecr):
    """Best-so-far ECR over time of a HyPSO-QCO run (phases placed back to back, ending at total time)."""
    d = json.load(open(path))
    phases = d["memetic"]
    durs = [ph[2][-1][1] for ph in phases]
    t = total_s - sum(durs)
    pts, best = [(0.0, input_ecr)], None
    sw = d.get("swarm", {}).get("twoq")
    if sw is not None:
        pts.append((t / 60, sw))
    for (_, _, hist), du in zip(phases, durs):
        for _, tr, cost in hist:
            if best is None or cost[0] < best:
                best = cost[0]
            pts.append(((t + tr) / 60, best))
        t += du
    return pts


def bqskit_trace(c, tool, input_ecr):
    lg = os.path.join(REV, "bqskit_del", f"{c}_{tool}_s0.log")
    pts = [(0.0, input_ecr)]
    if os.path.exists(lg):
        for line in open(lg):
            m = re.search(r"\[bqskit-del\s+(\d+)s\] sweep \d+: cx (\d+) -> (\d+)", line)
            if m:
                pts.append((int(m.group(1)) / 60, min(int(m.group(3)), pts[-1][1])))
    return pts


def at(pts, t):
    v = pts[0][1]
    for tt, e in pts:
        if tt <= t:
            v = e
    return v


# ----------------------------------------------------------------------------------------- figures
def fig_mean_reduction(plt, runs, inp):
    """Mean reduction beyond Qiskit O3 (ECR and total gates), one bar per tool."""
    bq = bq_tool(runs)
    tools = [("queso", "QUESO"), ("tket", "TKET"), (bq, "BQSKit deletion"), ("ibm_ai", "IBM AI synthesis"),
             ("guoq15", "GUOQ"), ("guoq60", "GUOQ, 60 min"), ("hypso_rs", "HyPSO-QCO")]
    tools = [(t, lab) for t, lab in tools if runs.get(t)]
    fig, axes = plt.subplots(1, 2, figsize=(COL, 0.32 * len(tools) + 0.55), sharey=True)
    ys = np.arange(len(tools))
    for ax, (key, title) in zip(axes, (("ecr", "ECR gates"), ("gates", "all gates"))):
        vals = [mean_reduction(runs, inp, t, key)[0] for t, _ in tools]
        cols = [BLUE if t == "hypso_rs" else (ORANGE if t.startswith("guoq") else GRAY) for t, _ in tools]
        ax.barh(ys, vals, 0.68, color=cols, edgecolor="white", linewidth=0.5)
        for y, v in zip(ys, vals):
            ax.text(max(v, 0) + 1, y, f"{v:.1f}", va="center", fontsize=7.5, color=INK2)
        ax.set_title(title, loc="left", fontsize=8)
        ax.set_xlim(0, max(vals) * 1.25)
        ax.grid(axis="y", visible=False)
        ax.axvline(0, color=AXIS, lw=0.6)
    axes[0].set_yticks(ys, [lab for _, lab in tools])
    fig.supxlabel("mean reduction beyond Qiskit O3 over the ten circuits (%)", fontsize=8, y=0.0)
    fig.tight_layout(w_pad=0.6)
    save(plt, fig, "rev_fig1_mean_reduction")


def fig_vs_guoq(plt, runs, inp):
    """Per circuit: ECR gates fewer than GUOQ (15 min, mean of seeds) and than GUOQ at 60 min."""
    fig, ax = plt.subplots(figsize=(COL, 1.95))
    x = np.arange(len(CIRCUITS))
    w = 0.38
    m15, s15, m60 = [], [], []
    for c in CIRCUITS:
        h = [r["ecr"] for r in runs["hypso_rs"].get(c, [])]
        g15 = stat(runs, "guoq15", c)
        g60 = stat(runs, "guoq60", c)
        rel = [100 * (1 - e / g15[0]) for e in h] if (h and g15) else []
        m15.append(np.mean(rel) if rel else np.nan)
        s15.append(np.std(rel, ddof=1) if len(rel) > 1 else 0)
        m60.append(100 * (1 - np.mean(h) / g60[0]) if (h and g60) else np.nan)
    ax.bar(x - w / 2, m15, w, yerr=s15, color=BLUE, edgecolor="white", linewidth=0.5, label="vs GUOQ, 15 min",
           error_kw=dict(lw=0.7, capsize=1.5, ecolor=INK2))
    ax.bar(x + w / 2, m60, w, color=BLUE_L, edgecolor="white", linewidth=0.5, label="vs GUOQ, 60 min")
    ax.axhline(0, color=AXIS, lw=0.6)
    ax.set_xticks(x, [c.replace("_", r"\_") if False else c for c in CIRCUITS], rotation=35, ha="right")
    ax.set_ylabel("fewer ECR gates (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", ncol=1, handlelength=1.0)
    save(plt, fig, "rev_fig3a_vs_guoq")


def anytime_data(runs, inp):
    bq = bq_tool(runs)
    gtr = guoq_traces(inp)
    data = {}
    for c in SMALL:
        e0 = inp[c]["ecr"]
        d = {}
        hp = []
        for p in sorted(glob.glob(os.path.join(REV, "hypso_rs", "optimized", f"{c}__hypso_rs__s*.json"))):
            seed = int(p.split("__s")[-1][:-5])
            row = [r for r in runs["hypso_rs"].get(c, []) if r["seed"] == seed]
            if row:
                hp.append(hypso_trace(p, row[0]["time"], e0))
        d["hypso"] = hp
        d["guoq"] = [gtr[(c, s)] for s in (0, 1, 2) if (c, s) in gtr]
        d["guoq0"] = [gtr[(c, 0)]] if (c, 0) in gtr else []   # the 60-minute run
        d["bqskit"] = [bqskit_trace(c, bq, e0)] if runs.get(bq, {}).get(c) else []
        q = [(0.0, e0)]
        for lab, t in (("queso@60", 1), ("queso@300", 5), ("queso", 15)):
            for r in csv.DictReader(open("results/ibm_literature/queso/results.csv")):
                if r["circuit"] == c and r["method"] == lab:
                    q.append((t, min(int(r["ecr"]), q[-1][1])))
        d["queso"] = [q]
        d["tket"] = stat(runs, "tket", c)[0]
        data[c] = d
    return data


def fig_anytime(plt, runs, inp):
    """Mean remaining ECR fraction over the seven smaller circuits versus wall-clock time."""
    data = anytime_data(runs, inp)
    grid = np.concatenate([[0], np.geomspace(0.05, 60, 400)])
    fig, ax = plt.subplots(figsize=(COL, 2.05))

    def curve(key, tmax):
        vals = []
        for c in SMALL:
            trs = data[c][key]
            if not trs:
                return None
            e0 = inp[c]["ecr"]
            vals.append([np.mean([at(tr, t) for tr in trs]) / e0 for t in grid])
        v = 100 * np.mean(vals, axis=0)
        v[grid > tmax] = np.nan
        return v

    tket = 100 * np.mean([data[c]["tket"] / inp[c]["ecr"] for c in SMALL])
    ax.axhline(tket, color=AQUA, lw=1.0, ls=(0, (4, 2)), label="TKET (seconds)")
    for key, lab, col, tmax, ls, lw in (
            ("queso", "QUESO", YELLOW, 15, "-", 1.2), ("bqskit", "BQSKit deletion", PINK, 15, "-", 1.2),
            ("guoq", "GUOQ (3 seeds)", ORANGE, 15, "-", 1.2), ("guoq0", "GUOQ 60-min run", ORANGE, 60, (0, (1.2, 1.2)), 0.9),
            ("hypso", "HyPSO-QCO (3 seeds)", BLUE, 15, "-", 1.6)):
        v = curve(key, tmax)
        if v is not None:
            ax.plot(grid, v, color=col, lw=lw, ls=ls, label=lab)
    ax.axvline(15, color=AXIS, lw=0.6)
    ax.text(15.8, 0.02, "15 min", fontsize=7, color=INK2, va="bottom", transform=ax.get_xaxis_transform())
    ax.set_xscale("symlog", linthresh=1, linscale=0.6)
    ax.set_xlim(0, 60)
    ax.set_xticks([0, 0.5, 1, 2, 5, 10, 15, 30, 60], ["0", "0.5", "1", "2", "5", "10", "15", "30", "60"])
    ax.minorticks_off()
    ax.set_xlabel("wall-clock time (min)")
    ax.set_ylabel("ECR gates left (% of input)")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1.6, columnspacing=1.0)
    save(plt, fig, "rev_fig_anytime")
    return data


def fig_anytime_per_circuit(plt, runs, inp, data):
    fig, axes = plt.subplots(2, 4, figsize=(FULL, 3.1))
    for ax, c in zip(axes.flat, SMALL):
        d = data[c]
        ax.axhline(d["tket"], color=AQUA, lw=0.9, ls=(0, (4, 2)), label="TKET")
        for key, lab, col in (("queso", "QUESO", YELLOW), ("bqskit", "BQSKit deletion", PINK),
                              ("guoq", "GUOQ", ORANGE), ("hypso", "HyPSO-QCO", BLUE)):
            for i, tr in enumerate(d[key]):
                ax.step([p[0] for p in tr] + [60 if key == "guoq" and i == 0 else 15],
                        [p[1] for p in tr] + [tr[-1][1]], where="post", color=col,
                        lw=1.3 if key == "hypso" else 1.0, alpha=1 if i == 0 else 0.55, label=lab if i == 0 else None)
        ax.set_xscale("symlog", linthresh=1, linscale=0.6)
        ax.set_xlim(0, 60)
        ax.set_xticks([0, 1, 5, 15, 60], ["0", "1", "5", "15", "60"])
        ax.minorticks_off()
        ax.set_title(c, loc="left")
    axes.flat[-1].axis("off")
    h, l_ = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(h, l_, loc="center")
    fig.supxlabel("wall-clock time (min)", fontsize=8)
    fig.supylabel("best ECR count so far", fontsize=8)
    fig.tight_layout(w_pad=0.8, h_pad=0.8)
    save(plt, fig, "rev_fig_anytime_per_circuit")


def crossings(runs, inp, data):
    """When HyPSO-QCO's best-so-far ECR count first falls below GUOQ's final 15- and 60-minute values
    (per seed; markdown table for the RQ3 text)."""
    def first_below(tr, v):
        for t, e in tr:
            if e < v:
                return t
        return None

    lines = ["# Anytime crossings (generated by paper/rev_figs.py)", "",
             "Minutes until HyPSO-QCO's best-so-far ECR count is below GUOQ's final value "
             "(GUOQ 15 min: mean of three seeds; GUOQ 60 min: seed 0).  One value per HyPSO-QCO seed.", "",
             "| circuit | GUOQ 15 min | HyPSO-QCO passes it after (min) | GUOQ 60 min | HyPSO-QCO passes it after (min) |",
             "|---|---:|---|---:|---|"]
    all15, all60 = [], []
    for c in SMALL:
        g15, g60 = stat(runs, "guoq15", c), stat(runs, "guoq60", c)
        t15 = [first_below(tr, g15[0]) for tr in data[c]["hypso"]] if g15 else []
        t60 = [first_below(tr, g60[0]) for tr in data[c]["hypso"]] if g60 else []
        all15 += [t for t in t15 if t is not None]
        all60 += [t for t in t60 if t is not None]
        f = (lambda ts: ", ".join("never" if t is None else f"{t:.1f}" for t in ts))
        lines.append(f"| {c} | {g15[0]:.1f} | {f(t15)} | {g60[0]:.0f} | {f(t60)} |")
    if all15:
        lines += ["", f"Over all seeds: GUOQ 15 min passed after {min(all15):.1f}-{max(all15):.1f} min "
                      f"(median {np.median(all15):.1f}); GUOQ 60 min passed after {min(all60):.1f}-{max(all60):.1f} min "
                      f"(median {np.median(all60):.1f})."]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "anytime_crossings.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    plt = setup()
    runs, inp = collect(), inputs()
    if runs.get("hypso_rs"):
        fig_mean_reduction(plt, runs, inp)
        fig_vs_guoq(plt, runs, inp)
        data = fig_anytime(plt, runs, inp)
        fig_anytime_per_circuit(plt, runs, inp, data)
        crossings(runs, inp, data)
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
