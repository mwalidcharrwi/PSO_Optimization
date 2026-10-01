"""Method diagrams of the paper package (called by build_package.py).

* diag1..diag3: Mermaid sources (``figures/src/*.mmd``), rendered to PDF/SVG/PNG with
  mermaid-cli (``npx @mermaid-js/mermaid-cli``) when Node and Chromium are available;
* diag4: circuit-level schematic of one block resynthesis step (matplotlib).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

INIT = ('%%{init: {"theme": "base", "flowchart": {"curve": "basis", "htmlLabels": true}, "themeVariables": '
        '{"fontFamily": "Liberation Sans, DejaVu Sans, sans-serif", "fontSize": "15px", '
        '"primaryTextColor": "#0b0b0b", "lineColor": "#52514e", "clusterBkg": "#f7f9fc", '
        '"clusterBorder": "#c3c2b7", "edgeLabelBackground": "#ffffff"}}}%%')
CLASSES = """
  classDef io fill:#f0efec,stroke:#898781,stroke-width:1px,color:#0b0b0b;
  classDef p1 fill:#e6f0fc,stroke:#2a78d6,stroke-width:1px,color:#0b0b0b;
  classDef p2 fill:#cde2fb,stroke:#1c5cab,stroke-width:1px,color:#0b0b0b;
  classDef chk fill:#ffffff,stroke:#52514e,stroke-width:1px,color:#0b0b0b;
  classDef tool fill:#ffffff,stroke:#c3c2b7,stroke-width:1px,color:#0b0b0b;
  classDef opt fill:#ffffff,stroke:#2a78d6,stroke-width:1px,stroke-dasharray:4 3,color:#52514e;
"""

DIAGRAMS = {
    "diag1_framework_workflow": """flowchart LR
  IN(["<b>Mapped input circuit C</b><br/>IBM native {rz, sx, x, ecr}<br/>fixed qubit layout"]):::io
  subgraph P1["<b>Phase 1 · particle swarm over compilation decisions</b> · 25 % of budget T"]
    direction TB
    S0["<b>initialise</b><br/>3 elite seeds from the deterministic compiler<br/>+ random and opposition-based particles"]:::p1
    S1["<b>decode</b> each particle with the sound compiler<br/>ECR lowering variants → pass schedule<br/>→ clean-up → native re-synthesis<br/><i>every candidate is exactly equivalent to C</i>"]:::p1
    S2["<b>evaluate</b> f(C′) = (ECR count, gates, depth)"]:::p1
    S3["<b>update</b> personal / neighbourhood bests<br/>categorical PSO (nominal genes)<br/>SPSO/QPSO (continuous genes)<br/>provenance-guided local search"]:::p1
    S0 --> S1 --> S2 --> S3
    S3 -->|"next iteration"| S1
  end
  subgraph P2["<b>Phase 2 · memetic, connectivity-preserving resynthesis</b> · remaining time"]
    direction TB
    M0["<b>choose strategy</b> by adaptive operator selection<br/>scan direction × cuts × block size 3–5 × restarts"]:::p2
    M1["<b>partition</b> into convex blocks"]:::p2
    M2["<b>per block, in parallel</b><br/>delete CNOTs inside the block's own skeleton<br/>re-instantiate by Levenberg–Marquardt<br/>(Frobenius residual below 1e-10)"]:::p2
    M3["<b>Z-slot sparsification</b><br/>U3 → virtual Rz where possible"]:::p2
    M4{"checks pass and<br/>CNOTs not higher?"}:::chk
    M0 --> M1 --> M2 --> M3 --> M4
    M4 -->|"accept / discard"| M0
    SCH["2a · refine each elite until it stalls<br/>2b · deepen the best with ≤ 5-qubit blocks"]:::opt
  end
  OUT(["<b>Optimised circuit C′</b><br/>same physical qubits<br/>only coupled pairs<br/>native ECR directions<br/>checked equivalent"]):::io
  IN --> P1
  P1 ==>|"up to 3<br/>distinct elites"| P2
  P2 ==>|"deadline T"| OUT
""",
    "diag2_particle_decoding": """flowchart LR
  subgraph X["<b>Particle</b> x ∈ [0,1)^D · one gene per decision, keyed by provenance"]
    direction TB
    G1["<b>variant genes</b><br/>exact decomposition of every multi-variant gate<br/>e.g. 16 ECR→CNOT lowerings, 120 Toffoli networks × polarity"]:::p1
    G2["<b>lowering-mode gene</b><br/>per-ECR variants or greedy exact conversion"]:::p1
    G3["<b>schedule genes</b><br/>6 slots ∈ {skip, cancel, fold, hred, kak, tket}"]:::p1
    G4["<b>hardware genes</b> (logical circuits only)<br/>layout keys + router parameters"]:::opt
  end
  subgraph D["<b>Decoder</b> = semantics-preserving compiler"]
    direction TB
    D1["1 · lower gates with the chosen variants"]:::p2
    D2["2 · run the chosen passes in order"]:::p2
    D3["3 · clean-up fix point<br/>cancel → fold → hred"]:::p2
    D4["4 · native re-synthesis<br/>CX → ECR in the native direction · fewest rz/sx/x"]:::p2
    D1 --> D2 --> D3 --> D4
  end
  G1 --> D1
  G2 --> D1
  G3 --> D2
  G4 -.-> D1
  D4 --> C(["candidate C′ ≡ C<br/>by construction"]):::io
  C --> F{"cost f(C′)"}:::chk
  F --> U["<b>swarm update</b><br/>categorical PSO: one probability vector per gene<br/>w ← χ[w + c1r1(e(p) − π) + c2r2(e(l) − π)] · π ← normalise(max(π + w, 0))"]:::p1
  U -.->|"new positions"| G1
""",
    "diag3_evaluation_protocol": """flowchart LR
  B(["<b>10 IBM-Eagle circuits</b><br/>transpiled by Qiskit<br/>at optimisation level 3<br/>1.9k–357k gates · 8–32 used qubits"]):::io
  K{"<b>common contract</b><br/>same physical qubits<br/>only coupled pairs<br/>native ECR directions"}:::chk
  subgraph T["<b>optimisers</b> · same 4-core machine"]
    direction TB
    T2["TKET, connectivity-preserving"]:::tool
    T3["QUESO · 15 min"]:::tool
    T4["GUOQ · 15 min · coupling-aware resynthesis"]:::tool
    T5["<b>HyPSO-QCO</b> · 15 min<br/>+ 1-worker and no-swarm variants"]:::p1
    T2 ~~~ T3 ~~~ T4 ~~~ T5
  end
  subgraph E["<b>evaluation</b> · identical for every tool"]
    direction TB
    N["exact conversion to {rz, sx, x, ecr}"]:::p2
    V["equivalence check of every output<br/>statevector (≤ 20 qubits) · Choi-state MPS miter"]:::p2
    M["metrics: ECR · total gates · sx + x · depth<br/>estimated success probability"]:::p2
    S["statistics: wins / ties / losses<br/>one-sided Wilcoxon signed-rank"]:::p2
    N --> V --> M --> S
  end
  B --> K --> T --> E
""",
}


def _mmdc():
    npx = shutil.which("npx")
    if not npx:
        return None
    cfg = {"args": ["--no-sandbox"]}
    for exe in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome", shutil.which("chromium") or "",
                shutil.which("google-chrome") or ""):
        if exe and os.path.exists(exe):
            cfg["executablePath"] = exe
            break
    return npx, cfg


def render_mermaid(fig_dir):
    src = os.path.join(fig_dir, "src")
    os.makedirs(src, exist_ok=True)
    tool = _mmdc()
    for name, body in DIAGRAMS.items():
        path = os.path.join(src, name + ".mmd")
        with open(path, "w") as fh:
            fh.write(INIT + "\n" + body + CLASSES)
        if tool is None:
            print(f"[diagrams] npx not found; wrote {path} only")
            continue
        npx, cfg = tool
        css = os.path.join(src, "font.css")
        with open(css, "w") as fh:
            fh.write("* { font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif !important; }\n")
        pcfg = os.path.join(src, "puppeteer.json")
        with open(pcfg, "w") as fh:
            json.dump(cfg, fh)
        env = dict(os.environ, PUPPETEER_SKIP_DOWNLOAD="1")
        for ext, extra in (("pdf", ["--pdfFit"]), ("svg", []), ("png", ["-s", "3"])):
            out = os.path.join(fig_dir, f"{name}.{ext}")
            r = subprocess.run([npx, "-y", "@mermaid-js/mermaid-cli@11", "-i", path, "-o", out, "-p", pcfg,
                                "-b", "white", "-C", css, "-q"] + extra, env=env, capture_output=True, text=True, timeout=300)
            if r.returncode:
                print(f"[diagrams] mermaid-cli failed for {name}.{ext}: {r.stderr[-400:]}")


# ------------------------------------------------------------------------------------ diag4
def block_schematic(fig_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch

    INK, INK2, MUTED, AXIS = "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
    U3F, U3E, GRAYF, RED = "#e6f0fc", "#2a78d6", "#f0efec", "#e34948"
    ys = {0: 2.0, 1: 1.0, 2: 0.0}

    def box(ax, x, q, label, fc, ec):
        ax.add_patch(FancyBboxPatch((x - 0.32, ys[q] - 0.28), 0.64, 0.56,
                                    boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=0.9, zorder=3))
        ax.text(x, ys[q], label, ha="center", va="center", fontsize=6.2, color=INK, zorder=4)

    def cx(ax, x, c, t, deleted=False):
        col = AXIS if deleted else INK
        ax.plot([x, x], [ys[c], ys[t]], color=col, lw=1.0, zorder=2)
        ax.plot([x], [ys[c]], "o", color=col, ms=4.2, zorder=3)
        ax.add_patch(Circle((x, ys[t]), 0.17, fc="white", ec=col, lw=1.0, zorder=3))
        ax.plot([x - 0.17, x + 0.17], [ys[t], ys[t]], color=col, lw=1.0, zorder=4)
        ax.plot([x, x], [ys[t] - 0.17, ys[t] + 0.17], color=col, lw=1.0, zorder=4)
        if deleted:
            ax.plot([x], [(ys[c] + ys[t]) / 2], marker="x", color=RED, ms=7, mew=1.6, zorder=5)

    def wires(ax, x0, x1):
        for q, y in ys.items():
            ax.plot([x0, x1], [y, y], color=AXIS, lw=0.9, zorder=1)
            ax.text(x0 - 0.12, y, f"q{q}", ha="right", va="center", fontsize=6.5, color=INK2)

    skeleton = [(0, 1), (1, 2), (0, 1), (1, 2)]

    def panel_a(ax):
        ops = [("u", 0), ("u", 1), ("c", 0, 1), ("u", 1), ("c", 1, 2), ("u", 2), ("u", 0), ("c", 0, 1),
               ("u", 1), ("c", 1, 2), ("u", 2)]
        last, xs = {0: 0.0, 1: 0.0, 2: 0.0}, []
        for op in ops:  # as-soon-as-possible layout
            qs = [op[1]] if op[0] == "u" else [op[1], op[2]]
            x = max(last[q] for q in qs) + 1.0
            for q in qs:
                last[q] = x
            xs.append(x)
        wires(ax, 0.3, max(xs) + 0.6)
        for op, x in zip(ops, xs):
            if op[0] == "u":
                box(ax, x, op[1], "1q", GRAYF, MUTED)
            else:
                cx(ax, x, op[1], op[2])
        return max(xs) + 0.6

    def panel_t(ax, deleted=(), sparse=(), lab="U3"):
        end = 0.9 + 1.7 * len(skeleton) + 0.35
        wires(ax, 0.3, end)
        for q in ys:
            sp = ("L", q) in sparse
            box(ax, 0.9, q, "Rz" if sp else lab, "white" if sp else U3F, U3E)
        for j, (c, t) in enumerate(skeleton):
            x = 0.9 + 1.7 * j + 0.95
            cx(ax, x, c, t, deleted=j in deleted)
            if j in deleted:
                continue
            for q in (c, t):
                sp = (j, q) in sparse
                box(ax, x + 0.8, q, "Rz" if sp else lab, "white" if sp else U3F, U3E)
        return end

    fig, axes = plt.subplots(1, 4, figsize=(7.4, 1.32), gridspec_kw=dict(width_ratios=[9.1, 8.2, 8.2, 8.2]))
    ends = [panel_a(axes[0]), panel_t(axes[1]), panel_t(axes[2], deleted=(1, 2), lab="U3′"),
            panel_t(axes[3], deleted=(1, 2), sparse={("L", 2), (0, 0), (3, 2)}, lab="U3′")]
    titles = ["(a) block from the mapped circuit:\n4 CNOTs on coupled pairs",
              "(b) template on its own CNOT\nskeleton (exact start)",
              "(c) delete CNOTs, LM refit; accept\nif " + r"$\|V(x)-e^{i\varphi}U\|_F<10^{-10}$",
              "(d) Z-slot sparsification:\nU3 → Rz (free on IBM hardware)"]
    for ax, t, e in zip(axes, titles, ends):
        ax.set_title(t, fontsize=6.3, color=INK, loc="left", pad=2)
        ax.set_xlim(-0.35, e + 0.1)
        ax.set_ylim(-0.45, 2.45)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.tight_layout(w_pad=0.9, rect=(0, 0.1, 1, 1))
    fig.text(0.5, 0.0, "Only CNOTs that already exist in the block can be removed, so no new qubit pair appears "
             "and the device mapping is unchanged (here 4 → 2 CNOTs).", ha="center", fontsize=6.8, color=INK2)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(fig_dir, f"diag4_block_resynthesis.{ext}"), bbox_inches="tight", dpi=220)
    plt.close(fig)


def make(fig_dir):
    render_mermaid(fig_dir)
    block_schematic(fig_dir)
