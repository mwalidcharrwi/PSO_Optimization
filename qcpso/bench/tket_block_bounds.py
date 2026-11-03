"""Exact spectral-norm bounds for the TKET block rewrites behind large-mode outputs.

Large-mode runs save every accepted TKET block rewrite (original and replacement,
at most 10 qubits).  For each, ||U - e^{i phi} V||_F (optimal phase) is computed
from the full unitaries; it bounds the spectral-norm error eps_j of Proposition 1(c).

    python -m qcpso.bench.tket_block_bounds results/ibm_revision/hypso_rs [--workers 4]
"""
from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os

import numpy as np


def _eps(block):
    from ..circuit import Circuit, Gate
    from ..sim import unitary
    n, a, b = block
    ua = unitary(Circuit(n, [Gate(x, tuple(q), tuple(p)) for x, q, p in a]))
    ub = unitary(Circuit(n, [Gate(x, tuple(q), tuple(p)) for x, q, p in b]))
    inner = np.vdot(ub, ua)
    return float(np.linalg.norm(ua - inner / abs(inner) * ub))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="results/ibm_revision/tket_block_bounds.json")
    args = ap.parse_args(argv)
    res = json.load(open(args.out)) if os.path.exists(args.out) else {}
    for p in sorted(glob.glob(os.path.join(args.folder, "optimized", "*.json"))):
        name, _, seed = os.path.basename(p)[:-5].split("__")
        key = f"{name}__{seed}"
        blocks = json.load(open(p)).get("tket_blocks") or []
        if not blocks or key in res:
            continue
        with mp.get_context("fork").Pool(args.workers) as pool:
            eps = pool.map(_eps, blocks, chunksize=1)
        res[key] = dict(n=len(eps), eps_sum=float(np.sum(eps)), eps_max=float(np.max(eps)))
        print(key, res[key], flush=True)
        with open(args.out, "w") as fh:
            json.dump(res, fh, indent=1)


if __name__ == "__main__":  # pragma: no cover
    main()
