"""Command line interface.

    python -m qcpso optimize input.qasm -o output.qasm --mode cliffordt --budget 1000
    python -m qcpso optimize input.qasm --mode hardware --device ibm_tokyo
    python -m qcpso optimize mapped.qasm -o out.qasm --mode ibm --time-limit 900 --resynth-workers 4
    python -m qcpso bench --suite builtin --mode cliffordt      (see qcpso.bench.run)
"""
from __future__ import annotations

import argparse
import json
import sys

from .framework import HyPSOConfig, optimize
from .io import load, save_qasm
from .pipeline import OBJECTIVES
from .pso.engine import PSOParams


def _optimize(argv):
    ap = argparse.ArgumentParser(prog="qcpso optimize")
    ap.add_argument("input", help=".qasm / .qc / .real file")
    ap.add_argument("-o", "--output", help="write optimised OpenQASM 2.0 here")
    ap.add_argument("--mode", default="cliffordt", choices=["cliffordt", "continuous", "hardware", "ibm"])
    ap.add_argument("--objective", default=None, choices=list(OBJECTIVES))
    ap.add_argument("--budget", type=int, default=1000, help="unique circuit evaluations")
    ap.add_argument("--time-limit", type=float, default=None, help="seconds")
    ap.add_argument("--swarm", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--device", default="ibm_tokyo", help="hardware mode device")
    ap.add_argument("--json", action="store_true", help="print metrics as JSON")
    ap.add_argument("--resynth-workers", type=int, default=4, help="ibm mode: block resynthesis processes")
    ap.add_argument("--no-resynth", action="store_true", help="ibm mode: swarm phase only (no memetic phase)")
    args = ap.parse_args(argv)
    circ = load(args.input)
    hw = None
    if args.mode == "hardware":
        from .hardware import HardwareSpec
        hw = HardwareSpec.from_name(args.device)
    cfg = HyPSOConfig(mode=args.mode, objective=args.objective, workers=args.workers, hardware=hw,
                      pso=PSOParams(max_evals=args.budget, time_limit=args.time_limit,
                                    swarm_size=args.swarm, seed=args.seed))
    if args.mode == "ibm":
        # v2: the time limit covers the swarm phase and the memetic resynthesis phase
        cfg.time_limit = args.time_limit
        cfg.resynth = not args.no_resynth
        cfg.resynth_workers = args.resynth_workers
        if args.time_limit is not None:
            cfg.pso.max_evals = 10 ** 9
    res = optimize(circ, cfg)
    if args.output:
        save_qasm(res.circuit, args.output)
    if args.json:
        print(json.dumps({"input": res.lowered_metrics, "greedy": res.greedy_metrics, "hypso": res.metrics,
                          "evals": res.evals, "time": res.time, "verified": res.verified,
                          "info": {k: v for k, v in res.info.items() if k not in ("measure_map", "memetic_history")}},
                         indent=2, default=str))
    else:
        print(f"{circ.name}: {res.summary()}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "optimize":
        _optimize(rest)
    elif cmd == "bench":
        from .bench.run import main as bench_main
        bench_main(rest)
    else:
        print(f"unknown command {cmd!r}\n{__doc__}")
        sys.exit(2)


if __name__ == "__main__":  # pragma: no cover
    main()
