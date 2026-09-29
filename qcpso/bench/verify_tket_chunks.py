"""Chunk-level check of the TKET pass on circuits too large for a
statevector check (> 20 used qubits).

Diagnostic tool.  It re-runs TKET's ``KAKDecomposition`` + ``CliffordSimp``
(:func:`qcpso.passes.tket_bridge._full`) on consecutive gate chunks of a
large circuit and checks each chunk against its TKET output with the
Choi-state MPS miter.  It showed that the unchecked chunked pass was not
exact on ``hubbard_18`` (deviation 1e-5 on one chunk).  Therefore
:func:`qcpso.passes.tket_bridge.full` now works block-wise on such
circuits, and it checks every block by simulation.

    python -m qcpso.bench.verify_tket_chunks test_circuits_new/hubbard_18.qasm [--chunk 6000]
"""
from __future__ import annotations

import argparse
import json
import time

from ..circuit import Circuit
from ..framework import CircuitProblem, HyPSOConfig
from ..io import load
from ..native import to_cx
from ..passes import tket_bridge as TB
from ..pipeline import to_base
from .mps_verify import choi_equivalence


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("circuit")
    ap.add_argument("--chunk", type=int, default=TB.CHUNK)
    ap.add_argument("--max-bond", type=int, default=512)
    ap.add_argument("--schedule", default="global", choices=["global", "qubit"])
    ap.add_argument("--max-chunks", type=int, default=0)
    args = ap.parse_args(argv)
    circ = load(args.circuit)
    # the seed that starts the memetic phase for large circuits: exact greedy
    # ECR -> CX conversion, then the TKET pass
    p = CircuitProblem(circ, HyPSOConfig(mode="ibm"))
    base = to_base(p.lowerer.lower(to_cx(circ)))
    gates = base.gates
    worst, t0 = 0.0, time.time()
    for k, i in enumerate(range(0, len(gates), args.chunk)):
        part = Circuit(base.n_qubits, gates[i:i + args.chunk])
        out = to_base(TB._full(part))
        if args.max_chunks and k >= args.max_chunks:
            break
        r = choi_equivalence(part, Circuit(base.n_qubits, out.gates), max_bond=args.max_bond, schedule=args.schedule)
        dev = 1.0 - r["overlap"]
        worst = max(worst, dev)
        print(json.dumps({"chunk": k, "gates": len(part.gates), "cx": part.cx_count(), "cx_after": out.cx_count(),
                          "deviation": f"{dev:.2e}", "peak_bond": r["peak_bond"], "truncated": r["truncated"],
                          "seconds": r["seconds"]}), flush=True)
    print(json.dumps({"chunks": k + 1, "worst_deviation": f"{worst:.2e}", "seconds": round(time.time() - t0)}))


if __name__ == "__main__":  # pragma: no cover
    main()
