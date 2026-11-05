"""Memetic phase of HyPSO-QCO (v2): anytime, connectivity-preserving block
resynthesis applied to the circuits found by the swarm.

Each round partitions the current circuit into convex blocks of at most three
qubits with one of four partition strategies (forward / reverse greedy scan,
with or without random block cuts), removes CNOTs from every block by
numerical re-instantiation (:mod:`qcpso.passes.resynth`), and applies the
exact clean-up passes.  The strategy of the next round is chosen by adaptive
operator selection (probability matching on the CNOTs saved per second), and
block results are memoised, so repeated partitions cost little.  A round is
kept if it does not increase the CNOT count; the best native circuit seen is
returned.
"""
from __future__ import annotations

import multiprocessing as mp
import time

import numpy as np

from .circuit import Circuit
from .native import to_native
from .passes.resynth import STRATEGIES, resynthesis_round, strategy_name
from .pipeline import cleanup, finish, metrics, to_base


def _native(circ: Circuit, native_dirs) -> Circuit:
    return to_native(finish(circ, "continuous"), native_dirs)


ROUND_TOL = 1e-7


def _round_ok(old: Circuit, new: Circuit) -> bool:
    """Random-state equivalence of two consecutive memetic states (<= 20 used
    qubits; larger circuits rely on the per-block checks only)."""
    if new is old or (len(new.gates) == len(old.gates) and all(a == b for a, b in zip(new.gates, old.gates))):
        return True
    from .bench.deviation import deviation
    d = deviation(old, new, n_states=1)["state_err"]
    return d is None or d < ROUND_TOL


def memetic_resynthesis(circ: Circuit, native_dirs, objective, time_limit: float | None = None,
                        rounds: int = 0, workers: int = 4, seed: int = 0, max_qubits: int = 3,
                        verbose: bool = False, stop_on_stall: bool = False,
                        min_qubits: int = 2, sparse: bool = True,
                        lineage: dict | None = None) -> tuple[Circuit, list]:
    """Refine a {1q, cx} circuit; returns (best native circuit, history).

    ``objective`` maps a metrics dict to a comparable cost.  Stops at
    ``time_limit`` seconds, after ``rounds`` rounds (if > 0), or when every
    strategy has failed twice in a row (without a limit, or if
    ``stop_on_stall``).

    ``lineage`` (in/out) counts the accepted block replacements behind the
    returned circuit and the sum / maximum of their spectral-norm error bounds
    (Proposition 1(c)); pass the counts of the starting circuit, if any."""
    t0 = time.time()
    rng = np.random.default_rng(seed)
    cur = to_base(circ)
    best = _native(cur, native_dirs)
    best_cost = objective(metrics(best))
    history = [(0, 0.0, best_cost)]
    lin = dict(blocks=0, eps_sum=0.0, eps_max=0.0, rounds=0)
    if lineage:
        lin.update({k: lineage[k] for k in lin if k in lineage})
    best_lin = dict(lin)
    strategies = [st for st in STRATEGIES if min_qubits <= st[2] <= max_qubits]
    ns = len(strategies)
    quality = np.ones(ns)          # probability matching (adaptive operator selection)
    p_min = 0.1
    fails = rejected = 0
    pool = mp.get_context("fork").Pool(workers) if workers > 1 else None
    r = 0
    try:
        while True:
            left = None if time_limit is None else time_limit - (time.time() - t0)
            if left is not None and left <= 0:
                break
            if rounds and r >= rounds:
                break
            if (stop_on_stall or (not rounds and time_limit is None)) and fails >= 2 * ns:
                break
            if r < ns:
                k = r  # try every strategy once first (cheap 3-qubit ones come first)
            else:
                prob = p_min / ns + (1 - p_min) * quality / quality.sum()
                k = int(rng.choice(ns, p=prob / prob.sum()))
            ts = time.time()
            before = cur.cx_count()
            rstats: dict = {}
            new = resynthesis_round(cur, strategies[k], rng, pool=pool, p_cut=0.1 + 0.2 * rng.random(),
                                    time_limit=left, sparse=sparse, stats=rstats)
            new = to_base(cleanup(to_base(new), None, "continuous"))
            saved = before - new.cx_count()
            if new.cx_count() <= before and not _round_ok(cur, new):
                rejected += 1  # safety net: never accept a round that changes the circuit's action
                import sys
                print(f"[memetic] round {r + 1} ({strategy_name(strategies[k])}) rejected: output not "
                      f"equivalent to its input", file=sys.stderr, flush=True)
                new, saved = cur, 0
            if new.cx_count() <= before:
                if new is not cur:  # accepted round: its block replacements join the lineage
                    lin["blocks"] += rstats.get("accepted", 0)
                    lin["eps_sum"] += rstats.get("eps_sum", 0.0)
                    lin["eps_max"] = max(lin["eps_max"], rstats.get("eps_max", 0.0))
                    lin["rounds"] += 1
                cur = new
                nat = _native(cur, native_dirs)
                c = objective(metrics(nat))
                if c < best_cost:
                    best, best_cost = nat, c
                    best_lin = dict(lin)
            reward = max(0, saved) / max(1e-3, time.time() - ts)
            quality[k] = 0.7 * quality[k] + 0.3 * (reward + 1e-3)
            fails = fails + 1 if saved <= 0 else 0
            r += 1
            history.append((r, time.time() - t0, best_cost))
            if verbose:
                print(f"  [memetic] round {r} {strategy_name(strategies[k]):12s} saved {saved:4d} cx {cur.cx_count()} "
                      f"best {best_cost} {time.time() - t0:.0f}s", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    if lineage is not None:
        lineage.clear()
        lineage.update(best_lin)
    return best, history
