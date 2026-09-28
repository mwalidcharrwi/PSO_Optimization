"""Side-by-side comparison with related work on already-mapped IBM circuits.

    python -m qcpso.bench.compare_ibm --suite test_circuits_new --out results/ibm_literature \\
        --methods hypso,guoq,queso --time-limit 900

Every method gets the same input file and the same contract (equivalence on
the same physical qubits, two-qubit gates only on pairs coupled in the
input, native {rz, sx, x, ecr} output with native ECR directions).  Anytime
methods (HyPSO-QCO, GUOQ, QUESO) get the same wall-clock budget on the same
machine; GUOQ/QUESO snapshots are also recorded at earlier times.

Output: ``results.csv`` (one row per circuit x method x seed, appended as
runs finish) and ``optimized/<circuit>__<method>__s<seed>.qasm``.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
import traceback

from ..circuit import Circuit
from ..io import load
from ..io.qasm import to_qasm
from ..native import native_directions, respects_coupling

FIELDS = ["circuit", "used_qubits", "method", "seed", "budget", "time", "ecr", "sx", "x", "rz", "oneq_phys",
          "gates", "depth", "twoq_depth", "coupling_ok", "verified", "note"]


def native_metrics(c: Circuit) -> dict:
    ops: dict = {}
    for g in c.gates:
        ops[g.name] = ops.get(g.name, 0) + 1
    other = set(ops) - {"ecr", "sx", "x", "rz"}
    if other:
        raise ValueError(f"non-native gates in output: {sorted(other)}")
    return dict(ecr=ops.get("ecr", 0), sx=ops.get("sx", 0), x=ops.get("x", 0), rz=ops.get("rz", 0),
                oneq_phys=ops.get("sx", 0) + ops.get("x", 0), gates=len(c.gates), depth=c.depth(),
                twoq_depth=c.depth(only_multi=True))


def _verify(orig: Circuit, out: Circuit):
    from ..framework import verify
    try:
        v = verify(orig, out)
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"
    return "pending" if v is None else ("equivalent" if v else "NOT_EQUIVALENT")


def _row(orig, name, method, seed, budget, dt, out, note=""):
    m = native_metrics(out)
    ok = respects_coupling(out, native_directions(orig)) and all(
        g.qubits in native_directions(orig) for g in out.gates if g.name == "ecr")
    return dict(circuit=name, used_qubits=len(orig.used_qubits()), method=method, seed=seed, budget=budget,
                time=round(dt, 1), coupling_ok=ok, verified=_verify(orig, out), note=note, **m)


def run_hypso(orig, time_limit, seed, workers, overrides=None):
    from ..framework import HyPSOConfig, optimize
    from ..pso.engine import PSOParams
    cfg = HyPSOConfig(mode="ibm", time_limit=time_limit, resynth_workers=workers, verify=False,
                      pso=PSOParams(max_evals=10 ** 9, max_iter=10 ** 9, seed=seed))
    for k, v in (overrides or {}).items():
        setattr(cfg, k, v)
    t = time.time()
    res = optimize(orig, cfg)
    info = {"swarm": res.info.get("swarm_metrics", {}), "evals": res.evals,
            "memetic": [(kind, j, [(r, round(tt, 1), list(c)) for r, tt, c in h])
                        for kind, j, h in res.info.get("memetic_history", [])]}
    return res.circuit, time.time() - t, info


HYPSO_VARIANTS = {
    "hypso": {},
    "hypso_noswarm": dict(resynth_share=1.0, elites=1),           # memetic phase from the elite seed only
    "hypso_noresynth": dict(resynth=False),                       # swarm phase only (v1 + TKET pass)
    "hypso_nosparse": dict(resynth_sparse=False),                 # no Z-slot sparsification
}


def main(argv=None):
    try:  # small dense linear algebra: one BLAS thread per process (workers run in parallel)
        from threadpoolctl import threadpool_limits
        threadpool_limits(1)
    except ImportError:  # pragma: no cover
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="test_circuits_new")
    ap.add_argument("--out", default="results/ibm_literature")
    ap.add_argument("--methods", default="hypso,guoq,queso")
    ap.add_argument("--circuits", default="", help="comma-separated subset (default: all)")
    ap.add_argument("--time-limit", type=float, default=900.0)
    ap.add_argument("--snapshots", default="60,300")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--port", type=int, default=8090)
    args = ap.parse_args(argv)
    os.makedirs(os.path.join(args.out, "optimized"), exist_ok=True)
    paths = sorted(glob.glob(os.path.join(args.suite, "*.qasm")))
    want = [c for c in args.circuits.split(",") if c]
    circs = []
    for p in paths:
        name = os.path.splitext(os.path.basename(p))[0]
        if not want or name in want:
            circs.append((name, load(p)))
    circs.sort(key=lambda nc: (want.index(nc[0]) if want else len(nc[1].gates)))
    csv_path = os.path.join(args.out, "results.csv")
    new_file = not os.path.exists(csv_path)
    snaps = [float(s) for s in args.snapshots.split(",") if s]
    for name, orig in circs:
        for method in args.methods.split(","):
            for seed in range(args.seed0, args.seed0 + args.seeds):
                rows, extra = [], {}
                try:
                    if method.startswith("hypso"):
                        ov = dict(HYPSO_VARIANTS.get(method, {}))
                        out, dt, extra = run_hypso(orig, args.time_limit, seed, args.workers, ov)
                        rows.append(_row(orig, name, method, seed, args.time_limit, dt, out))
                        outs = {method: out}
                    elif method in ("guoq", "queso"):
                        from . import literature as L
                        wd = os.path.join(args.out, "work", f"{name}_{method}_s{seed}")
                        t = time.time()
                        if method == "guoq":
                            os.makedirs(os.path.dirname(wd), exist_ok=True)
                            with L.ResynthServer(args.port, True, log=wd + "_server.log"):
                                res = L.run_guoq(orig, wd, args.time_limit, snaps, "guoq", args.port, seed)
                        else:
                            res = L.run_guoq(orig, wd, args.time_limit, snaps, "queso", args.port, seed)
                        outs = {}
                        for tt, (out, ok) in sorted(res.items()):
                            label = method if tt >= args.time_limit else f"{method}@{int(tt)}"
                            rows.append(_row(orig, name, label, seed, tt, tt, out,
                                             "" if ok else "violates coupling"))
                            outs[label] = out
                    elif method == "bqskit":
                        from . import literature as L
                        out, ok, dt = L.run_bqskit(orig, level=3, seed=seed, workers=args.workers)
                        rows.append(_row(orig, name, method, seed, "", dt, out, "" if ok else "violates coupling"))
                        outs = {method: out}
                    elif method == "tket_mp":
                        from . import literature as L
                        out, ok, dt = L.run_tket_mp(orig)
                        rows.append(_row(orig, name, method, seed, "", dt, out, "" if ok else "violates coupling"))
                        outs = {method: out}
                    elif method == "qiskit":
                        from .external import run_qiskit
                        out, dt = run_qiskit(orig, "ibm", seed=seed)
                        rows.append(_row(orig, name, method, seed, "", dt, out))
                        outs = {method: out}
                    else:
                        raise ValueError(f"unknown method {method}")
                except Exception as exc:  # keep going, record the failure
                    traceback.print_exc()
                    rows = [dict(circuit=name, used_qubits=len(orig.used_qubits()), method=method, seed=seed,
                                 note=f"failed: {type(exc).__name__}: {exc}"[:300])]
                    outs = {}
                for label, out in outs.items():
                    with open(os.path.join(args.out, "optimized", f"{name}__{label}__s{seed}.qasm"), "w") as fh:
                        fh.write(to_qasm(out, clifford_t_names=False))
                if extra:
                    with open(os.path.join(args.out, "optimized", f"{name}__{method}__s{seed}.json"), "w") as fh:
                        json.dump(extra, fh)
                with open(csv_path, "a", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
                    if new_file:
                        w.writeheader()
                        new_file = False
                    for r in rows:
                        w.writerow(r)
                for r in rows:
                    print(json.dumps({k: r.get(k) for k in ("circuit", "method", "seed", "time", "ecr", "oneq_phys",
                                                            "gates", "coupling_ok", "verified", "note")}),
                          flush=True)


if __name__ == "__main__":  # pragma: no cover
    main()
