"""Benchmark runner: HyPSO-QCO vs. baselines, with statistics.

Examples
--------
    python -m qcpso.bench.run --suite builtin --mode cliffordt --seeds 3 --budget 600
    python -m qcpso.bench.run --suite path/to/benchmarks --mode continuous \
        --methods greedy,hypso,spso,ga,qiskit,tket --out results/cont

Outputs ``results.csv`` (one row per circuit x method x seed),
``summary.md`` (tables + Wilcoxon / Friedman statistics) and
``convergence.json`` (best-so-far traces of the search methods).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

from ..circuit import Circuit
from ..framework import CircuitProblem, HyPSOConfig, verify
from ..io import load
from ..pipeline import OBJECTIVES, default_objective, metrics
from ..pso.baselines import GeneticAlgorithm, RandomSearch, SimulatedAnnealing, StandardPSO
from ..pso.engine import PSOParams, SwarmOptimizer
from . import external
from .generators import builtin_suite

SEARCH_METHODS = {"hypso", "spso", "spso_seeded", "ga", "sa", "rs"}
ABLATIONS = {
    "hypso_novar": dict(use_variants=False),
    "hypso_place": dict(use_placement=True),                        # opt-in: lazy placement genes
    "hypso_place_eager": dict(use_placement=True, pso=dict(lazy=False)),
    "hypso_nosched": dict(use_schedule=False),
    "hypso_nomemetic": dict(pso=dict(memetic=False)),
    "hypso_spso": dict(pso=dict(variant="spso")),
    "hypso_qpso": dict(pso=dict(variant="qpso")),
    "hypso_gbest": dict(pso=dict(topology="gbest")),
    "hypso_noseed": dict(pso=dict(elitist_seed=False)),
    "hypso_relaxed": dict(pso=dict(categorical="relaxed")),
    "hypso_unguided": dict(pso=dict(guided=False)),
    "hypso_ls4": dict(pso=dict(memetic_evals=4)),
}
DEFAULT_METHODS = "greedy,hypso,spso,ga,sa,rs,qiskit,tket,pyzx"


def load_suite(spec: str, scale: str = "small") -> list[Circuit]:
    if spec in ("builtin", "small", "tiny", "large", "continuous", "hardware", "ablation"):
        return builtin_suite(scale if spec == "builtin" else spec)
    paths = []
    if os.path.isdir(spec):
        for ext in ("*.qasm", "*.qc", "*.real"):
            paths.extend(glob.glob(os.path.join(spec, "**", ext), recursive=True))
    else:
        paths = [p for p in spec.split(",") if p]
    circs = []
    for p in sorted(paths):
        try:
            circs.append(load(p))
        except Exception as exc:  # keep going, but report
            print(f"[skip] {p}: {exc}", file=sys.stderr)
    return circs


SWARM_SIZE = 16


def _make_cfg(mode, objective, budget, seed, workers, hardware, overrides=None, time_limit=None):
    cfg = HyPSOConfig(mode=mode, objective=objective, workers=workers, hardware=hardware,
                      pso=PSOParams(max_evals=budget, max_iter=10 ** 6, seed=seed, time_limit=time_limit,
                                    swarm_size=SWARM_SIZE))
    for k, v in (overrides or {}).items():
        if k == "pso":
            for kk, vv in v.items():
                setattr(cfg.pso, kk, vv)
        else:
            setattr(cfg, k, v)
    return cfg


def run_method(method: str, circ: Circuit, mode: str, objective: str, budget: int, seed: int,
               workers: int = 1, hardware=None, do_verify: bool = True, time_limit: float | None = None) -> dict:
    t0 = time.time()
    history = None
    evals = 0
    info = {}
    if method in external.EXTERNAL:
        if mode == "hardware":
            raise ValueError("use qcpso.hardware baselines for hardware mode")
        out, dt = external.EXTERNAL[method](circ, mode)
        info = {}
    else:
        overrides = ABLATIONS.get(method)
        cfg = _make_cfg(mode, objective, budget, seed, workers, hardware, overrides, time_limit)
        problem = CircuitProblem(circ, cfg)
        try:
            if method == "greedy":
                x = problem.seed_positions()[0]
            elif method == "hypso" or method in ABLATIONS:
                res = SwarmOptimizer(problem, cfg.pso).run()
                x, history = res.best_x, res.history
            else:
                cls = {"spso": StandardPSO, "spso_seeded": StandardPSO, "ga": GeneticAlgorithm,
                       "sa": SimulatedAnnealing, "rs": RandomSearch}[method]
                seeded = method != "spso"
                kw = {"swarm": SWARM_SIZE} if cls is StandardPSO else ({"pop": SWARM_SIZE} if cls is GeneticAlgorithm else {})
                res = cls(problem, max_evals=budget, seed=seed, seeded=seeded, time_limit=time_limit).run(**kw)
                x, history = res.best_x, res.history
            out, info = problem.build(x)
            evals = problem.n_evals
        finally:
            problem.close()
        dt = time.time() - t0
    m = metrics(out)
    ok = None
    if do_verify:
        try:
            ok = verify(circ, out, info)
        except Exception as exc:  # pragma: no cover - reported, not fatal
            print(f"[verify-error] {circ.name} {method}: {exc}", file=sys.stderr)
            ok = False
    row = dict(circuit=circ.name, n_qubits=circ.n_qubits, method=method, seed=seed, time=round(dt, 3),
               evals=evals, verified=ok, **m)
    if history:
        row["_history"] = [(h[1], list(h[3]) if isinstance(h[3], tuple) else h[3]) for h in history]
    row["_circuit"] = out
    return row


# --------------------------------------------------------------------------- #
# statistics / reporting
# --------------------------------------------------------------------------- #
def _primary(objective):
    return {"gates": "gates", "cx": "cx", "t": "t", "depth": "depth", "fidelity": "cx", "twoq": "twoq"}[objective]


def summarise(rows: list[dict], original: dict, objective: str, reference: str = "hypso") -> str:
    from scipy import stats
    prim = _primary(objective)
    key_fn = OBJECTIVES[objective]
    methods = list(dict.fromkeys(r["method"] for r in rows))
    circuits = list(dict.fromkeys(r["circuit"] for r in rows))
    agg: dict = defaultdict(dict)  # circuit -> method -> dict(mean metrics, best, std)
    for c in circuits:
        for m in methods:
            rs = [r for r in rows if r["circuit"] == c and r["method"] == m]
            if not rs:
                continue
            d = {}
            for k in ("gates", "cx", "twoq", "t", "depth", "time"):
                vals = [r[k] for r in rs]
                d[k] = float(np.mean(vals))
                d[k + "_std"] = float(np.std(vals))
            d["best"] = min(rs, key=lambda r: key_fn(r))
            d["verified"] = all(r["verified"] in (True, None) for r in rs)
            agg[c][m] = d
    lines = [f"# Benchmark summary (objective: `{objective}`, primary metric: `{prim}`)", ""]
    # ---- per-circuit table ------------------------------------------------
    hdr = "| circuit | qubits | lowered | " + " | ".join(methods) + " |"
    lines += ["## Primary metric per circuit (mean over seeds; best in bold)", "", hdr,
              "|" + "---|" * (3 + len(methods))]
    for c in circuits:
        vals = {m: agg[c][m][prim] for m in methods if m in agg[c]}
        best = min(vals.values())
        cells = []
        for m in methods:
            if m not in vals:
                cells.append("-")
                continue
            s = f"{vals[m]:.1f}" if vals[m] != int(vals[m]) else f"{int(vals[m])}"
            if not agg[c][m]["verified"]:
                s += " (!)"
            cells.append(f"**{s}**" if abs(vals[m] - best) < 1e-9 else s)
        o = original[c]
        lines.append(f"| {c} | {o['n_qubits']} | {o[prim]} | " + " | ".join(cells) + " |")
    lines.append("")
    # ---- secondary metrics table ------------------------------------------
    lines += ["## All metrics of the reference method vs. lowered input", "",
              "| circuit | gates | 2q gates | T | depth | time (s) |", "|---|---|---|---|---|---|"]
    for c in circuits:
        if reference not in agg[c]:
            continue
        o, d = original[c], agg[c][reference]
        lines.append(f"| {c} | {o['gates']} -> {d['gates']:.1f} | {o['twoq']} -> {d['twoq']:.1f} | "
                     f"{o['t']} -> {d['t']:.1f} | {o['depth']} -> {d['depth']:.1f} | {d['time']:.1f} |")
    lines.append("")
    # ---- aggregate reductions ------------------------------------------------
    lines += ["## Average reduction w.r.t. the lowered input (%)", "",
              "| method | gates | 2q gates | T | depth | mean time (s) |", "|---|---|---|---|---|---|"]
    for m in methods:
        red = defaultdict(list)
        tt = []
        for c in circuits:
            if m not in agg[c]:
                continue
            for k in ("gates", "twoq", "t", "depth"):
                if original[c][k] > 0:
                    red[k].append(100.0 * (1 - agg[c][m][k] / original[c][k]))
            tt.append(agg[c][m]["time"])
        cells = [f"{np.mean(red[k]):.2f}" if red[k] else "-" for k in ("gates", "twoq", "t", "depth")]
        lines.append(f"| {m} | " + " | ".join(cells) + f" | {np.mean(tt):.2f} |")
    lines.append("")
    # ---- pairwise statistics --------------------------------------------------
    if reference in methods:
        lines += [f"## `{reference}` vs. each method on `{prim}` (per-circuit means)", "",
                  "| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |",
                  "|---|---|---|---|---|---|"]
        for m in methods:
            if m == reference:
                continue
            a, b = [], []
            for c in circuits:
                if reference in agg[c] and m in agg[c]:
                    a.append(agg[c][reference][prim])
                    b.append(agg[c][m][prim])
            a, b = np.array(a), np.array(b)
            if not len(a):
                continue
            w = int(np.sum(a < b - 1e-9))
            t = int(np.sum(np.abs(a - b) <= 1e-9))
            l_ = int(np.sum(a > b + 1e-9))
            imp = np.mean([100 * (1 - x / y) for x, y in zip(a, b) if y > 0]) if len(a) else float("nan")
            try:
                p = stats.wilcoxon(a, b, alternative="less").pvalue if np.any(a != b) else 1.0
            except ValueError:
                p = float("nan")
            lines.append(f"| {m} | {w} | {t} | {l_} | {imp:.2f} | {p:.3g} |")
        lines.append("")
    # ---- Friedman test + average ranks --------------------------------------
    full = [c for c in circuits if all(m in agg[c] for m in methods)]
    if len(methods) >= 3 and len(full) >= 2:
        mat = np.array([[agg[c][m][prim] for m in methods] for c in full])
        ranks = np.array([stats.rankdata(r) for r in mat])
        avg = ranks.mean(axis=0)
        try:
            fr = stats.friedmanchisquare(*mat.T)
            ptxt = f"chi2 = {fr.statistic:.3f}, p = {fr.pvalue:.3g}"
        except ValueError:
            ptxt = "n/a"
        lines += ["## Friedman test and average ranks (lower is better)", "", f"Friedman: {ptxt}", "",
                  "| method | average rank |", "|---|---|"]
        for m, r in sorted(zip(methods, avg), key=lambda z: z[1]):
            lines.append(f"| {m} | {r:.2f} |")
        lines.append("")
    n_bad = sum(1 for r in rows if r["verified"] is False)
    lines.append(f"Equivalence check: {sum(1 for r in rows if r['verified'] is True)} verified, "
                 f"{sum(1 for r in rows if r['verified'] is None)} not checked (too large, or --no-verify), "
                 f"{n_bad} FAILED.")
    return "\n".join(lines) + "\n"


_FIELDS = ["circuit", "n_qubits", "method", "seed", "gates", "cx", "twoq", "oneq", "t", "h", "depth",
           "twoq_depth", "time", "evals", "verified"]


def _append_partial(out_dir: str, row: dict) -> None:
    """Crash-safe incremental log of finished runs (results_partial.csv)."""
    path = os.path.join(out_dir, "results_partial.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", default="builtin", help="builtin|tiny|large|<dir>|<file,file,...>")
    ap.add_argument("--mode", default="cliffordt", choices=["cliffordt", "continuous", "hardware", "ibm"])
    ap.add_argument("--objective", default=None, choices=list(OBJECTIVES))
    ap.add_argument("--methods", default=DEFAULT_METHODS)
    ap.add_argument("--budget", type=int, default=600, help="unique evaluations per search run")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--device", default=None, help="hardware mode: device name (see qcpso.hardware.devices)")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--time-limit", type=float, default=None, help="seconds per search run (in addition to --budget)")
    ap.add_argument("--swarm", type=int, default=16, help="swarm / population size of the search methods")
    ap.add_argument("--save-circuits", action="store_true", help="write every output circuit to <out>/circuits/")
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)
    objective = args.objective or default_objective(args.mode)
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    avail = external.available()
    methods = [m for m in methods if m not in external.EXTERNAL or m in avail]
    hardware = None
    if args.mode == "hardware":
        from ..hardware import HardwareSpec
        hardware = HardwareSpec.from_name(args.device or "grid_4x4")
        from ..hardware import baselines as hwb
        methods = [m for m in methods if m not in external.EXTERNAL] + \
            [m for m in args.methods.split(",") if m in hwb.HW_BASELINES]
    global SWARM_SIZE
    SWARM_SIZE = args.swarm
    circuits = load_suite(args.suite)
    os.makedirs(args.out, exist_ok=True)
    if args.save_circuits:
        os.makedirs(os.path.join(args.out, "circuits"), exist_ok=True)
    rows, conv, original = [], {}, {}
    from ..decompose import Lowerer
    low = Lowerer()
    for circ in circuits:
        # reference: the lowered input; for already-compiled IBM circuits the input itself
        om = metrics(circ) if args.mode == "ibm" else metrics(low.lower(circ))
        om["n_qubits"] = len(circ.used_qubits()) if args.mode == "ibm" else circ.n_qubits
        original[circ.name] = om
        print(f"== {circ.name} ({circ.n_qubits} qubits, {om['gates']} lowered gates)", flush=True)
        for m in methods:
            seeds = range(args.seeds) if (m in SEARCH_METHODS or m in ABLATIONS) else [0]
            for s in seeds:
                try:
                    if args.mode == "hardware" and m not in SEARCH_METHODS and m not in ABLATIONS \
                            and m != "greedy":
                        from ..hardware import baselines as hwb
                        row = hwb.run_hw_baseline(m, circ, hardware, seed=s, do_verify=not args.no_verify)
                    else:
                        row = run_method(m, circ, args.mode, objective, args.budget, s, args.workers,
                                         hardware, not args.no_verify, args.time_limit)
                except Exception as exc:
                    print(f"   [error] {m} seed {s}: {type(exc).__name__}: {exc}", file=sys.stderr)
                    continue
                out_circ = row.pop("_circuit", None)
                if args.save_circuits and out_circ is not None:
                    from ..io import save_qasm
                    fn = f"{circ.name}__{m}__s{s}.qasm".replace("^", "")
                    try:
                        out_circ.meta = dict(circ.meta)
                        save_qasm(out_circ, os.path.join(args.out, "circuits", fn), clifford_t_names=False)
                    except Exception as exc:  # pragma: no cover
                        print(f"   [save-error] {fn}: {exc}", file=sys.stderr)
                hist = row.pop("_history", None)
                if hist:
                    conv[f"{circ.name}|{m}|{s}"] = hist
                rows.append(row)
                _append_partial(args.out, row)
                print(f"   {m:16s} s={s} gates={row['gates']:6d} cx={row['cx']:5d} 2q={row['twoq']:6d} t={row['t']:5d} "
                      f"depth={row['depth']:5d} time={row['time']:7.2f}s verified={row['verified']}", flush=True)
    fields = ["circuit", "n_qubits", "method", "seed", "gates", "cx", "twoq", "oneq", "t", "h", "depth",
              "twoq_depth", "time", "evals", "verified"]
    with open(os.path.join(args.out, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.out, "convergence.json"), "w") as fh:
        json.dump(conv, fh)
    with open(os.path.join(args.out, "original.json"), "w") as fh:
        json.dump(original, fh)
    summary = summarise(rows, original, objective)
    with open(os.path.join(args.out, "summary.md"), "w") as fh:
        fh.write(f"Mode: `{args.mode}`, budget: {args.budget} unique evaluations, seeds: {args.seeds}\n\n")
        if args.mode == "hardware":
            fh.write(f"Device: `{hardware.cmap.name}`.  The `lowered` column is the *unrouted* logical circuit "
                     "(no connectivity constraint); all other columns are routed, connectivity-respecting "
                     "circuits verified with their initial/final layouts.\n\n")
        fh.write(summary)
    print("\n" + summary)
    return rows


if __name__ == "__main__":  # pragma: no cover
    main()
