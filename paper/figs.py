"""Data figures of the paper package (called by build_package.py).

One visual system for every figure:
* categorical colours in the validated fixed order (dataviz reference palette):
  HyPSO-QCO blue, GUOQ orange, TKET aqua, QUESO yellow (Qiskit O3 is not compared: the
  supplied circuits are its output);
  grouped bars follow that order so that neighbouring bars stay CVD-separable;
* HyPSO-QCO variants and pipeline stages use one-hue (blue) ordinal steps;
* thin marks, 1 px surface gaps between bars, hairline grid, text in ink colours.
"""
from __future__ import annotations

import math
import os

import numpy as np

PAL = {"hypso": "#2a78d6", "guoq": "#eb6834", "tket_mp": "#1baf7a", "queso": "#eda100",
       "hypso_w1": "#86b6ef", "hypso_noswarm": "#1c5cab", "hypso_v1": "#c3c2b7"}
STAGE = ["#86b6ef", "#3987e5", "#1c5cab"]          # ordinal blue ramp (validated --ordinal)
INK, INK2, MUTED, GRID, AXIS, REST = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#d9d8d2"
TOOLS = ["queso", "tket_mp", "guoq", "hypso"]   # bar order = validated adjacency
NAME = {"queso": "QUESO", "tket_mp": "TKET", "guoq": "GUOQ", "hypso": "HyPSO-QCO",
        "hypso_w1": "HyPSO-QCO, 1 worker", "hypso_noswarm": "HyPSO-QCO w/o swarm phase",
        "hypso_v1": "HyPSO-QCO v1"}


def _setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 8.5, "axes.titlesize": 8.5, "axes.titleweight": "bold",
        "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.labelcolor": INK2, "text.color": INK,
        "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
        "xtick.major.size": 0, "ytick.major.size": 0, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.5,
        "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 7.5,
        "savefig.bbox": "tight", "savefig.dpi": 220})
    return plt


def make(ctx, fig_dir):
    plt = _setup()
    by, inp, circuits, small = ctx["by"], ctx["inp"], ctx["circuits"], ctx["small"]
    val, red = ctx["val"], ctx["red"]

    def save(fig, name):
        fig.savefig(os.path.join(fig_dir, name + ".pdf"))
        fig.savefig(os.path.join(fig_dir, name + ".png"))
        plt.close(fig)

    def legend_top(ax, ncol, y=1.02, **kw):
        ax.legend(ncol=ncol, loc="lower left", bbox_to_anchor=(0, y), handlelength=1.2, columnspacing=1.0, **kw)

    x = np.arange(len(circuits))

    # ---- fig1 / fig2: reductions per circuit ------------------------------------------------------
    for key, name, ylab in (("ecr", "fig1_ecr_reduction", "ECR reduction vs input (%)"),
                            ("gates", "fig2_total_gate_reduction", "total-gate reduction vs input (%)")):
        fig, ax = plt.subplots(figsize=(7.2, 2.7))
        w = 0.84 / len(TOOLS)
        for i, m in enumerate(TOOLS):
            ys = [red(val(by, c, m, key), inp[c][key]) for c in circuits]
            xs = x + (i - (len(TOOLS) - 1) / 2) * w
            ax.bar(xs, ys, w, label=NAME[m], color=PAL[m], edgecolor="white", linewidth=0.6)
            if m == "hypso":
                for xi, yi in zip(xs, ys):
                    ax.text(xi, yi + 1.2, f"{yi:.0f}", ha="center", va="bottom", fontsize=6.5, color=INK2)
        ax.axhline(0, color=AXIS, lw=0.8)
        ax.set_xticks(x, circuits, rotation=30, ha="right")
        ax.set_ylabel(ylab)
        ax.grid(axis="x", visible=False)
        legend_top(ax, 5)
        save(fig, name)

    # ---- fig3: anytime ---------------------------------------------------------------------------
    traces = ctx["traces"]
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 4.0))
    for ax, c in zip(axes.flat, small):
        ax.axhline(val(by, c, "tket_mp", "ecr"), color=PAL["tket_mp"], lw=1.0, label="TKET (instant)")
        for m, mk in (("queso", "s"), ("guoq", "o")):
            pts, _ = traces[c][m]
            ax.step([p[0] / 60 for p in pts], [p[1] for p in pts], where="post", color=PAL[m], lw=1.3,
                    marker=mk, ms=3.5, label=NAME[m] + " (sampled 1/5/15 min)")
        for m, ls in (("hypso_noswarm", (0, (4, 1.5))), ("hypso_w1", (0, (1.5, 1.2))), ("hypso", "-")):
            pts, _ = traces[c][m]
            ax.step([p[0] / 60 for p in pts] + [15.0], [p[1] for p in pts] + [pts[-1][1]], where="post",
                    color=PAL[m], lw=1.5, ls=ls, label=NAME[m])
        ax.set_title(c, loc="left")
        ax.set_xlim(0, 15.3)
        ax.set_xticks([0, 5, 10, 15])
        ax.tick_params(labelsize=7)
    axes.flat[-1].axis("off")
    h, l_ = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(h, l_, loc="center", fontsize=7)
    fig.supxlabel("wall-clock time (min)", fontsize=8.5, color=INK2)
    fig.supylabel("best ECR count so far", fontsize=8.5, color=INK2)
    fig.tight_layout()
    save(fig, "fig3_anytime")

    # ---- fig4: relative to GUOQ ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ms2 = ["hypso_w1", "hypso", "hypso_noswarm"]
    w = 0.27
    for i, m in enumerate(ms2):
        ys = [val(by, c, m, "ecr") / val(by, c, "guoq", "ecr") if val(by, c, m, "ecr") else np.nan for c in circuits]
        ax.bar(x + (i - 1) * w, ys, w, label=NAME[m], color=PAL[m], edgecolor="white", linewidth=0.6)
    ax.axhline(1.0, color=PAL["guoq"], lw=1.3, label="GUOQ, 15 min (= 1)")
    ax.set_xticks(x, circuits, rotation=30, ha="right")
    ax.set_ylabel("ECR count relative to GUOQ")
    ax.set_ylim(0.5, 1.1)
    ax.grid(axis="x", visible=False)
    ax.text(8, 0.53, "large circuits: only the full\nconfiguration was run", ha="center", va="bottom",
            fontsize=6.5, color=MUTED)
    legend_top(ax, 4)
    save(fig, "fig4_relative_to_guoq")

    # ---- fig5: search strategies (logical suites) ------------------------------------------------
    suites, bred = ctx["suites"], ctx["bred"]
    order = ["greedy", "rs", "spso", "ga", "sa", "hypso"]
    lab = {"greedy": "greedy (no search)", "rs": "random search", "spso": "canonical PSO", "ga": "GA", "sa": "SA",
           "hypso": "HyPSO-QCO swarm"}
    col = {"greedy": REST, "rs": "#e87ba4", "spso": "#eda100", "ga": "#1baf7a", "sa": "#eb6834", "hypso": "#2a78d6"}
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    xs0 = np.arange(len(suites))
    w = 0.84 / len(order)
    for i, m in enumerate(order):
        ys = [next(r["reduction_pct"] for r in bred if r["suite"] == s and r["method"] == m) for s, _, _ in suites]
        ax.bar(xs0 + (i - (len(order) - 1) / 2) * w, ys, w, label=lab[m], color=col[m], edgecolor="white",
               linewidth=0.6)
    ax.set_xticks(xs0, ["Clifford+T\n(18 circuits, gates)", "continuous\n(11 circuits, CX)",
                        "IBM Tokyo 20q\n(8 circuits, CX)"])
    ax.set_ylabel("mean reduction vs lowered input (%)")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.grid(axis="x", visible=False)
    legend_top(ax, 3)
    save(fig, "fig5_search_strategies")

    # ---- fig6: component ablation (emphasis) -----------------------------------------------------
    babl = ctx["babl"]
    names = {"hypso_novar": "no decomposition variants", "hypso_relaxed": "continuous relaxation (no categorical PSO)",
             "hypso_place": "with placement genes", "hypso_noseed": "no elitist seed",
             "hypso_spso": "SPSO only", "hypso_qpso": "QPSO only", "hypso_place_eager": "eager placement genes",
             "hypso_unguided": "unguided local search", "hypso_gbest": "gbest topology only",
             "hypso_nosched": "no schedule genes", "hypso_nomemetic": "no local search"}
    full = next(a for a in babl if a["variant"] == "hypso")["gates_pct"]
    rows = sorted([a for a in babl if a["variant"] != "hypso"], key=lambda a: a["gates_pct"] - full)
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    ys = [a["gates_pct"] - full for a in rows]
    sig = [a.get("wilcoxon_p", 1) < 0.05 for a in rows]
    ax.barh(range(len(rows)), ys, 0.7, color=[PAL["hypso"] if s else REST for s in sig], edgecolor="white",
            linewidth=0.6)
    for i, (v, s) in enumerate(zip(ys, sig)):
        if s:
            ax.text(v - 0.3, i, f"{v:+.1f} pp", ha="right", va="center", fontsize=6.5, color=INK2)
    ax.set_yticks(range(len(rows)), [names.get(a["variant"], a["variant"]) for a in rows], fontsize=7)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(min(ys) - 3.5, 1.5)
    ax.set_xlabel("change in mean gate reduction vs the full swarm (percentage points)")
    ax.set_title("blue: removing the component is significantly worse (p < 0.05)", loc="left",
                 fontweight="normal", color=INK2, fontsize=7)
    save(fig, "fig6_component_ablation")

    # ---- fig7: absolute ECRs removed (scalability) ----------------------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    for m, mk in (("tket_mp", "^"), ("guoq", "s"), ("hypso", "o")):
        ys = [max(inp[c]["ecr"] - val(by, c, m, "ecr"), 0.5) for c in circuits]
        ax.plot(x, ys, color=PAL[m], lw=1.2, marker=mk, ms=5, mec="white", mew=0.8, label=NAME[m])
    for xi, c in enumerate(circuits):
        v = inp[c]["ecr"] - val(by, c, "hypso", "ecr")
        ax.text(xi, v * 1.35, f"{int(round(v)):,}", ha="center", va="bottom", fontsize=6.5, color=INK2)
    ax.set_yscale("log")
    ax.set_ylim(0.4, 3e4)
    ax.set_yticks([0.5, 1, 10, 100, 1000, 10000], ["0", "1", "10", "100", "1,000", "10,000"])
    ax.minorticks_off()
    ax.set_xticks(x, [f"{c} ({inp[c]['gates'] / 1000:.0f}k)" if inp[c]["gates"] >= 10000 else
                      f"{c} ({inp[c]['gates'] / 1000:.1f}k)" for c in circuits], rotation=30, ha="right",
                  fontsize=7)
    ax.set_xlabel("circuit (input gate count), ordered by size")
    ax.set_ylabel("ECR gates removed (log)")
    ax.grid(axis="x", visible=False)
    legend_top(ax, 3)
    save(fig, "fig7_ecr_removed_by_size")

    # ---- fig8: where the reduction arises (phase breakdown) --------------------------------------
    ph = ctx["phase"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ys = np.arange(len(ph))[::-1]
    for yi, r in zip(ys, ph):
        e0 = r["input_ecr"]
        p1 = e0 - r["after_phase1_ecr"]
        p2a = r["after_phase1_ecr"] - r["best_elite_ecr"]
        p2b = r["best_elite_ecr"] - r["final_ecr"]
        segs = [(p1, STAGE[0]), (p2a, STAGE[1]), (p2b, STAGE[2]), (r["final_ecr"], REST)]
        left = 0.0
        for v, cc in segs:
            ax.barh(yi, 100 * v / e0, 0.66, left=left, color=cc, edgecolor="white", linewidth=0.8)
            left += 100 * v / e0
        removed = 100 * (e0 - r["final_ecr"]) / e0
        ax.text(removed + 1.0, yi, f"{removed:.1f} % removed", va="center", fontsize=6.8, color=INK2)
    ax.set_yticks(ys, [r["circuit"] + (" *" if r["large_mode"] else "") for r in ph])
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the input's ECR gates (%)")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    from matplotlib.patches import Patch
    hs = [Patch(color=STAGE[0], label="removed in phase 1 (swarm; * seed only)"),
          Patch(color=STAGE[1], label="removed by memetic resynthesis of the elites (2a)"),
          Patch(color=STAGE[2], label="removed by deepening (2b)"),
          Patch(color=REST, label="remaining")]
    ax.legend(handles=hs, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.02), handlelength=1.2)
    save(fig, "fig8_phase_breakdown")

    # ---- fig9: win matrix (ECR relative to HyPSO-QCO) -------------------------------------------
    cols = ["queso", "tket_mp", "guoq", "hypso_v1", "hypso"]
    mat = np.array([[val(by, c, m, "ecr") / val(by, c, "hypso", "ecr") for m in cols] for c in circuits])
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#f4f8fe", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab",
                                                      "#0d366b"])
    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    im = ax.imshow(np.clip(mat, 1.0, 2.0), cmap=cmap, vmin=1.0, vmax=2.0, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            ax.text(j, i, f"{v:.2f}" if v < 10 else f"{v:.1f}", ha="center", va="center", fontsize=6.8,
                    color="white" if v > 1.55 else INK)
    ax.set_xticks(range(len(cols)), [NAME[m] for m in cols], rotation=25, ha="right")
    ax.set_yticks(range(len(circuits)), circuits)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, ticks=[1.0, 1.25, 1.5, 1.75, 2.0])
    cb.ax.set_yticklabels(["1.00", "1.25", "1.50", "1.75", "≥ 2"], fontsize=7)
    cb.outline.set_visible(False)
    cb.set_label("ECR count ÷ HyPSO-QCO's", fontsize=7.5, color=INK2)
    save(fig, "fig9_ecr_relative_matrix")

    # ---- fig10: all metrics, mean reduction -------------------------------------------------------
    metrics = [("ecr", "ECR"), ("gates", "total gates"), ("oneq_phys", "physical 1q (sx + x)"), ("depth", "depth")]
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    xm = np.arange(len(metrics))
    w = 0.84 / len(TOOLS)
    for i, m in enumerate(TOOLS):
        ys = [np.mean([red(val(by, c, m, k), inp[c][k]) for c in circuits]) for k, _ in metrics]
        xs = xm + (i - (len(TOOLS) - 1) / 2) * w
        ax.bar(xs, ys, w, label=NAME[m], color=PAL[m], edgecolor="white", linewidth=0.6)
        for xi, yi in zip(xs, ys):
            if m in ("hypso", "guoq") or abs(yi) < 1:
                ax.text(xi, max(yi, 0) + 1.0, f"{yi:.1f}", ha="center", va="bottom", fontsize=6.3, color=INK2)
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xticks(xm, [lbl for _, lbl in metrics])
    ax.set_ylabel("mean reduction vs input (%)\nover the 10 circuits")
    ax.grid(axis="x", visible=False)
    legend_top(ax, 5)
    save(fig, "fig10_all_metrics")

    # ---- fig11: estimated success probability gain -----------------------------------------------
    def log_fid(m):
        return m["ecr"] * math.log1p(-7e-3) + m["oneq_phys"] * math.log1p(-2.5e-4)

    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    yy = np.arange(len(small))[::-1]
    for m, mk in (("tket_mp", "^"), ("guoq", "s"), ("hypso", "o")):
        gains = [math.exp(log_fid(dict(ecr=val(by, c, m, "ecr"), oneq_phys=val(by, c, m, "oneq_phys"))) -
                          log_fid(inp[c])) for c in small]
        ax.scatter(gains, yy, s=34, marker=mk, color=PAL[m], edgecolor="white", linewidth=0.8, zorder=3,
                   label=NAME[m])
        if m == "hypso":
            for g, yv in zip(gains, yy):
                ax.text(g * 1.35, yv, f"×{g:,.1f}" if g < 1000 else f"×{g:.1e}", va="center", fontsize=6.8,
                        color=INK2)
    ax.set_xscale("log")
    ax.set_yticks(yy, small)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(0.8, 3e8)
    ax.set_xlabel("estimated success probability ÷ input's (log; ECR error 7e-3, sx/x 2.5e-4)")
    legend_top(ax, 3)
    save(fig, "fig11_success_probability_gain")

    # ---- fig12: time to beat GUOQ's 15-minute result ---------------------------------------------
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    yy = np.arange(len(small))[::-1]
    h = 0.26
    for i, m in enumerate(("hypso_w1", "hypso", "hypso_noswarm")):
        ts = []
        for c in small:
            g = val(by, c, "guoq", "ecr")
            pts = sorted(traces[c][m][0])
            t = next((tt for tt, e, *_ in pts if e < g), None)
            ts.append(t)
        for yv, t in zip(yy, ts):
            yb = yv + (1 - i) * h
            if t is None:
                ax.text(0.2, yb, "not reached in 15 min", va="center", fontsize=6.3, color=MUTED)
            else:
                ax.barh(yb, t / 60, h, color=PAL[m], edgecolor="white", linewidth=0.6,
                        label=NAME[m] if yv == yy[0] else None)
                if m == "hypso":
                    ax.text(t / 60 + 0.2, yb, f"{t / 60:.1f}", va="center", fontsize=6.3, color=INK2)
    ax.axvline(15, color=PAL["guoq"], lw=1.3)
    ax.text(14.8, yy[-1] - 0.45, "GUOQ's own\n15-min budget", ha="right", va="center", fontsize=6.5, color=INK2)
    ax.set_yticks(yy, small)
    ax.set_xlim(0, 16)
    ax.set_ylim(yy[-1] - 0.75, yy[0] + 0.55)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel("minutes until the ECR count drops below GUOQ's 15-minute result")
    legend_top(ax, 3)
    save(fig, "fig12_time_to_beat_guoq")

    # ---- fig13: verification ---------------------------------------------------------------------
    dev = ctx["dev"]
    fig, ax = plt.subplots(figsize=(5.6, 2.5))
    rows = TOOLS[::-1]
    ax.axvspan(1e-17, 1e-9, color="#f4f8fe", zorder=0)
    ax.axvspan(1e-9, 1e-6, color="#fbfbf9", zorder=0)
    rng = np.random.default_rng(0)
    for yi, m in enumerate(rows):
        ds = [d[0] for (c, mm), d in dev.items() if mm == m]
        jit = rng.uniform(-0.18, 0.18, len(ds))
        ax.scatter(np.maximum(ds, 1e-16), yi + jit, s=22, color=PAL[m], edgecolor="white", linewidth=0.6, zorder=3)
        ax.text(max(ds) * 2.2, yi, f"max {max(ds):.1e}", va="center", fontsize=6.5, color=INK2)
    for xv in (1e-9, 1e-6):
        ax.axvline(xv, color=AXIS, lw=0.8)
    ax.text(3e-13, len(rows) - 0.35, "exact", ha="center", fontsize=6.5, color=MUTED)
    ax.text(3e-8, len(rows) - 0.35, "numerically exact", ha="center", fontsize=6.5, color=MUTED)
    ax.text(3e-5, len(rows) - 0.35, "approximate", ha="center", fontsize=6.5, color=MUTED)
    ax.set_xscale("log")
    ax.set_xlim(1e-16, 1e-3)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_yticks(range(len(rows)), [NAME[m] for m in rows])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("deviation of each output from its input (log)")
    save(fig, "fig13_verification")
