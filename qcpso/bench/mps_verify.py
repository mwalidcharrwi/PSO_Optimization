"""Equivalence checking of large circuits with a Choi-state MPS ("alternating
miter" in tensor-network form).

For circuits A and B on n qubits, the operator M = A . B^dagger is
represented through its Choi state |M> = (M x I)|Phi+>^n, an MPS on 2n
qubits (copy-A and copy-B qubit of every wire adjacent).  Gates of A act on
the copy-A qubits, complex-conjugated gates of B on the copy-B qubits, and
the two circuits are advanced *in step* (proportionally to their two-qubit
gate counts), so that for equivalent circuits M stays close to the identity
and the bond dimension stays small.  Finally

    |<Phi+|M x I|Phi+>| = |tr M| / 2^n  = 1   iff   A = e^{i phi} B.

Truncation can only lower this overlap, so a value of 1 (to tolerance) is
conclusive (threshold 1 - 1e-9: one rotation changed by 1e-3 deviates by 1.3e-7);
a small value is conclusive only if no truncation occurred.

    python -m qcpso.bench.mps_verify input.qasm optimised.qasm
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict

import numpy as np

from ..circuit import Circuit
from ..io import load


def _site_order(qubits, gates):
    """DFS order along the interaction graph keeps most two-qubit gates local."""
    adj = defaultdict(set)
    for g in gates:
        if len(g.qubits) == 2:
            a, b = g.qubits
            adj[a].add(b)
            adj[b].add(a)
    order, seen = [], set()
    start = min(qubits, key=lambda q: (len(adj[q]), q))
    for root in [start] + sorted(qubits):
        if root in seen:
            continue
        stack = [root]
        while stack:
            q = stack.pop()
            if q in seen:
                continue
            seen.add(q)
            order.append(q)
            stack.extend(sorted(adj[q] - seen, reverse=True))
    return order


def choi_equivalence(a: Circuit, b: Circuit, max_bond: int = 2048, cutoff: float = 1e-12,
                     verbose: bool = False) -> dict:
    import quimb.tensor as qtn
    qubits = sorted(a.used_qubits() | b.used_qubits())
    order = _site_order(qubits, a.gates)
    pos = {q: i for i, q in enumerate(order)}
    n = len(order)
    circ = qtn.CircuitMPS(2 * n, max_bond=max_bond, cutoff=cutoff)
    for i in range(n):
        circ.apply_gate("H", 2 * i)
        circ.apply_gate("CNOT", 2 * i, 2 * i + 1)
    na2 = max(1, sum(1 for g in a.gates if len(g.qubits) == 2))
    nb2 = max(1, sum(1 for g in b.gates if len(g.qubits) == 2))
    i = j = ca = cb = 0
    peak = 1
    t0 = time.time()
    total = len(a.gates) + len(b.gates)
    step = 0
    while i < len(a.gates) or j < len(b.gates):
        take_a = j >= len(b.gates) or (i < len(a.gates) and ca / na2 <= cb / nb2)
        if take_a:
            g = a.gates[i]
            i += 1
            where = tuple(2 * pos[q] for q in g.qubits)
            circ.apply_gate_raw(g.matrix(), where, contract="swap+split")
            ca += len(g.qubits) == 2
        else:
            g = b.gates[j]
            j += 1
            where = tuple(2 * pos[q] + 1 for q in g.qubits)
            circ.apply_gate_raw(np.conj(g.matrix()), where, contract="swap+split")
            cb += len(g.qubits) == 2
        step += 1
        if step % 2000 == 0:
            peak = max(peak, circ.psi.max_bond())
            if verbose:
                print(f"  {step}/{total} gates, max bond {circ.psi.max_bond()}, {time.time() - t0:.0f}s",
                      flush=True)
    peak = max(peak, circ.psi.max_bond())
    bell = qtn.CircuitMPS(2 * n)
    for k in range(n):
        bell.apply_gate("H", 2 * k)
        bell.apply_gate("CNOT", 2 * k, 2 * k + 1)
    ov = complex(bell.psi.H @ circ.psi)
    return {"overlap": abs(ov), "peak_bond": int(peak), "truncated": bool(peak >= max_bond),
            "n_qubits": n, "seconds": round(time.time() - t0, 1)}


def main(argv=None):
    argv = argv or sys.argv[1:]
    a, b = load(argv[0]), load(argv[1])
    if b.n_qubits < a.n_qubits:
        b = Circuit(a.n_qubits, b.gates)
    res = choi_equivalence(a, b, verbose=True)
    res["deviation"] = 1 - res["overlap"]
    res["verdict"] = ("equivalent" if res["overlap"] > 1 - 1e-9 else
                      ("not_equivalent" if not res["truncated"] else "inconclusive"))
    print(res)


if __name__ == "__main__":  # pragma: no cover
    main()
