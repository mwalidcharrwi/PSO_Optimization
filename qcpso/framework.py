"""HyPSO-QCO: Hybrid, provenance-aligned Particle Swarm Optimisation for
Quantum Circuit Optimisation.

The swarm does **not** search the space of circuits.  It searches the space of
*compilation decisions* of a semantics-preserving optimisation program:

  genome = [ variant genes | placement genes | schedule genes | hardware genes ]

* variant genes   -- per multi-variant gate instance of the input (Toffoli /
                     CCZ network, T-polarity, T-placement; CZ/SWAP/CP/CRZ/RZZ
                     orientation ...), keyed by *provenance* so that gene i
                     means the same decision in every particle;
* placement genes -- per rotation (keyed by the semantic tag of the rotation,
                     e.g. "parity a^b of Toffoli #17"): keep the standard
                     location (< 0.5) or move the folded rotation to a
                     relative position among all availability points;
* schedule genes  -- a pass sequence drawn from the pass library, followed by
                     a fixed clean-up fix point;
* hardware genes  -- random-key initial layout and router hyper-parameters
                     (hardware mode only, see ``qcpso.hardware``).

Because every decoded program only applies sound rewrites, every particle is
an exactly-equivalent circuit (equivalence-by-construction); no fidelity
penalty or repair is needed, which is what lets PSO scale to circuits with
thousands of gates.
"""
from __future__ import annotations

import multiprocessing as mp
import time
import zlib
from dataclasses import dataclass, field

import numpy as np

from .circuit import Circuit, Gate
from .decompose import Lowerer
from .pipeline import (GREEDY_SCHEDULE, OBJECTIVES, PASS_LIBRARY, apply_pass, cleanup,
                       default_objective, finish, metrics, to_base)
from .native import native_directions, to_native
from .pso.engine import PSOParams, SwarmOptimizer

_WORKER_PROBLEM = None


def _stable_hash(obj) -> int:
    return zlib.crc32(repr(obj).encode())


def _worker_eval(x):
    return _WORKER_PROBLEM._evaluate_uncached(x)


@dataclass
class HyPSOConfig:
    mode: str = "cliffordt"            # "cliffordt" | "continuous" | "hardware" | "ibm"
    objective: str | None = None       # key of pipeline.OBJECTIVES (default by mode)
    n_schedule_slots: int = 6
    use_variants: bool = True
    # Free rotation placement is sound and available, but the ablation study
    # (results/ablation) shows it does not pay off at practical budgets, so it
    # is opt-in.
    use_placement: bool = False
    use_schedule: bool = True
    max_placement_genes: int = 512
    workers: int = 1
    pso: PSOParams = field(default_factory=PSOParams)
    hardware: object | None = None     # qcpso.hardware.HardwareSpec (hardware mode)
    verify: bool = True
    # ---- v2 (ibm mode): external exact passes and memetic resynthesis ----
    external_passes: bool = True       # TKET connectivity-preserving passes in the pass library
    resynth: bool = True               # memetic phase: connectivity-preserving block resynthesis
    time_limit: float | None = None    # overall wall-clock budget in seconds
    resynth_share: float = 0.75        # share of time_limit given to the memetic phase
    resynth_evals: int = 0             # without a time limit: number of memetic rounds (0 = until stall)
    resynth_workers: int = 4
    resynth_qubits: int = 4            # largest block size of the resynthesis partitions
    elites: int = 3                    # distinct swarm elites refined by the memetic phase (time-limited runs)
    deepen_qubits: int = 5             # largest block size in the final deepening phase
    resynth_sparse: bool = True        # turn U3 slots of resynthesised blocks into Z rotations
    large_gates: int = 50000           # time-limited runs on larger circuits skip the swarm phase
    verbose: bool = False


class CircuitProblem:
    """Genome <-> optimisation-program mapping plus a memoised cost oracle."""

    def __init__(self, circ: Circuit, cfg: HyPSOConfig):
        self.circ = circ
        self.cfg = cfg
        self.mode = cfg.mode
        self.objective = cfg.objective or default_objective(cfg.mode)
        self.obj_fn = OBJECTIVES[self.objective]
        self.lowerer = Lowerer(topology_variants=(cfg.mode == "hardware"))
        self.passes = PASS_LIBRARY if cfg.mode != "cliffordt" else PASS_LIBRARY[:-1]
        if cfg.mode == "ibm" and cfg.external_passes:
            from .passes import tket_bridge
            if tket_bridge.available():
                self.passes = self.passes + ("tket",)
        self.native_dirs = native_directions(circ) if cfg.mode == "ibm" else set()
        card: list[int] = []
        # ---- variant genes (provenance keyed) ----
        self.var_index: dict[tuple, list[int]] = {}
        if cfg.use_variants:
            for key, sizes in self.lowerer.sites(circ):
                idx = []
                for s in sizes:
                    idx.append(len(card))
                    card.append(int(s))
                self.var_index[key] = idx
        self.n_var = len(card)
        # ---- placement genes (semantic-tag keyed) ----
        self.place_index: dict = {}
        self.place_start = len(card)
        if cfg.use_placement:
            base = self.lowerer.lower(circ)
            tags = []
            seen = set()
            for g in base.gates:
                if g.name == "rz" and g.tag not in seen:
                    seen.add(g.tag)
                    tags.append(g.tag)
            n_place = min(len(tags), cfg.max_placement_genes)
            for i, t in enumerate(tags):
                self.place_index[t] = self.place_start + (i if i < n_place else _stable_hash(t) % max(1, n_place))
            card.extend([0] * n_place)
        self.n_place = len(card) - self.place_start
        # placement genes refine a good solution rather than define it: they are
        # "lazy" (see PSOParams.lazy) so they do not dilute the global search
        self.lazy_genes = np.arange(self.place_start, self.place_start + self.n_place)
        # ---- schedule genes ----
        self.sched_start = len(card)
        self.n_sched = cfg.n_schedule_slots if cfg.use_schedule else 0
        card.extend([len(self.passes)] * self.n_sched)
        # ---- lowering-mode gene (ibm mode): per-ECR variant genes, or the exact
        # greedy ECR -> CX conversion (native.to_cx), which pattern-based passes
        # such as TKET's CliffordSimp often simplify further ----
        self.lower_gene = None
        if cfg.mode == "ibm":
            self.lower_gene = len(card)
            card.append(2)
        # ---- hardware genes ----
        self.hw_start = len(card)
        self.hw = cfg.hardware
        if cfg.mode == "hardware":
            if self.hw is None:
                raise ValueError("hardware mode requires cfg.hardware (qcpso.hardware.HardwareSpec)")
            card.extend(self.hw.gene_cardinality(circ.n_qubits))
        self.dim = len(card)
        self.cardinality = np.asarray(card, dtype=int)
        self.perm_groups = ([np.arange(self.hw_start, self.hw_start + self.hw.cmap.n)]
                            if cfg.mode == "hardware" else [])
        self._init_sites()
        self.cache: dict = {}
        self.genomes: dict = {}
        self._built: dict = {}
        self.deadline: float | None = None
        self.n_evals = 0
        self.n_requests = 0
        self._pool = None

    # ------------------------------------------------------------------ #
    # provenance-based credit assignment (used by the guided local search)
    # ------------------------------------------------------------------ #
    def _init_sites(self):
        self.site_keys = [k for k, idx in self.var_index.items() if idx]
        self.site_genes = [self.var_index[k] for k in self.site_keys]
        self._site_set = set(self.site_keys)
        base = self.lowerer.lower(self.circ)
        self.site_size = self._prefix_counts(base)
        # neighbouring sites: consecutive sites acting on a common qubit
        per_qubit: dict[int, list[int]] = {}
        for si, k in enumerate(self.site_keys):
            for q in self.circ.gates[k[0]].qubits:
                per_qubit.setdefault(q, []).append(si)
        nb = [set() for _ in self.site_keys]
        for lst in per_qubit.values():
            for a, b in zip(lst, lst[1:]):
                if a != b:
                    nb[a].add(b)
                    nb[b].add(a)
        self.site_nbrs = [sorted(x) for x in nb]
        self._si_key, self._si_val = None, None

    def _prefix_counts(self, circ: Circuit) -> dict:
        counts: dict = {}
        ss = self._site_set
        for g in circ.gates:
            t = g.tag
            if isinstance(t, tuple):
                for L in range(1, len(t) + 1):
                    pre = t[:L]
                    if pre in ss:
                        counts[pre] = counts.get(pre, 0) + 1
        return counts

    def site_info(self, x):
        """(site gene lists, sampling weights, neighbour lists).  The weight of a
        site is the fraction of its gates that survived optimisation."""
        if not self.site_keys:
            return None
        key = self.phenotype_key(x)
        if key != self._si_key:
            circ, _ = self.build(x)
            cnt = self._prefix_counts(circ)
            w = np.array([(cnt.get(k, 0) + 1.0) / (self.site_size.get(k, 0) + 1.0) for k in self.site_keys])
            self._si_key, self._si_val = key, (self.site_genes, w / w.sum(), self.site_nbrs)
        return self._si_val

    # ------------------------------------------------------------------ #
    # genome decoding
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cat(u: float, k: int) -> int:
        return min(int(u * k), k - 1)

    def variant_choice(self, x):
        vi = self.var_index
        cat = self._cat

        def choice(key, sizes):
            idx = vi.get(key)
            if idx is None or len(idx) != len(sizes):
                return tuple(0 for _ in sizes)
            return tuple(cat(x[i], s) for i, s in zip(idx, sizes))

        return choice

    def placement_fn(self, x):
        if not self.n_place:
            return None
        pi = self.place_index

        def placement(tag):
            i = pi.get(tag)
            return None if i is None else float(x[i])

        return placement

    def schedule(self, x) -> list[str]:
        if not self.n_sched:
            return list(GREEDY_SCHEDULE)
        return [self.passes[self._cat(x[self.sched_start + j], len(self.passes))] for j in range(self.n_sched)]

    def phenotype_key(self, x) -> tuple:
        k = self.cardinality
        cats = tuple(self._cat(x[i], k[i]) for i in range(self.n_var))
        pl = tuple(0 if x[i] < 0.5 else 1 + int((x[i] - 0.5) * 2048)
                   for i in range(self.place_start, self.place_start + self.n_place))
        sc = tuple(self._cat(x[self.sched_start + j], len(self.passes)) for j in range(self.n_sched))
        hw = ()
        if self.lower_gene is not None:
            hw = (self._cat(x[self.lower_gene], 2),)
        if self.mode == "hardware":  # key on the decoded layout, not on the raw random keys
            layout, params = self.hw.decode(x[self.hw_start:], self.circ.n_qubits)
            hw = (tuple(layout), tuple(sorted(params.items())))
        return (cats, pl, sc, hw)

    def build(self, x, native: bool = True) -> tuple[Circuit, dict]:
        """Decode a genome into an optimised circuit (+ decode info).  In ibm
        mode ``native=False`` returns the {1q, cx} circuit before the final
        conversion to {rz, sx, x, ecr}.  The last few decodes are memoised
        (large circuits take minutes to decode)."""
        x = np.asarray(x, dtype=float)
        pk = self.phenotype_key(x)
        key = (pk, native)
        hit = self._built.get(key)
        if hit is not None:
            return hit[0], dict(hit[1])
        pre = self._built.get((pk, False)) if native and self.mode == "ibm" else None
        if pre is not None:  # native form from the memoised {1q, cx} form
            circ, info = to_native(pre[0], self.native_dirs), dict(pre[1])
        else:
            circ, info = self._build(x, native)
        self._built[key] = (circ, info)
        while len(self._built) > 6:
            self._built.pop(next(iter(self._built)))
        return circ, dict(info)

    def _build(self, x, native: bool) -> tuple[Circuit, dict]:
        placement = self.placement_fn(x)
        if self.lower_gene is not None and self._cat(x[self.lower_gene], 2) == 1:
            from .native import to_cx
            base = to_base(self.lowerer.lower(to_cx(self.circ)))
        else:
            base = self.lowerer.lower(self.circ, self.variant_choice(x))
        circ = base
        numeric = False
        for name in self.schedule(x):
            if name == "tket":
                # TKET snaps near-special angles: apply it only to exact circuits,
                # i.e. before any numerically synthesised block
                if numeric:
                    continue
                from .passes import tket_bridge
                circ = to_base(tket_bridge.full(circ))
                continue
            numeric |= name == "kak"
            circ = apply_pass(name, circ, placement, self.mode)
        circ = cleanup(circ, placement, self.mode)
        info: dict = {}
        if self.mode == "hardware":
            circ, info = self.hw.map_and_route(circ, x[self.hw_start:], placement)
            target = "continuous" if self.hw.continuous else "cliffordt"
            circ = cleanup(circ, placement, target)  # all passes preserve connectivity
            circ = finish(circ, target, placement)
        elif self.mode == "ibm":
            # already-mapped IBM circuits: optimise in {1q, CX} on the same coupled
            # pairs, then return to {rz, sx, x, ecr} in the native ECR directions
            circ = finish(circ, "continuous", placement)
            if native:
                self._built[(self.phenotype_key(x), False)] = (circ, dict(info))
                circ = to_native(circ, self.native_dirs)
        else:
            circ = finish(circ, self.mode, placement)
        return circ, info

    def cost_of(self, circ: Circuit) -> tuple:
        return self.obj_fn(metrics(circ))

    def _evaluate_uncached(self, x) -> tuple:
        circ, _ = self.build(x)
        return self.cost_of(circ)

    # ------------------------------------------------------------------ #
    # oracle
    # ------------------------------------------------------------------ #
    def seed_positions(self) -> list[np.ndarray]:
        x = np.empty(self.dim)
        k = self.cardinality
        for i in range(self.dim):
            x[i] = 0.5 / k[i] if k[i] > 1 else (0.25 if k[i] == 0 else 0.5)
        for j, name in enumerate(GREEDY_SCHEDULE[: self.n_sched]):
            x[self.sched_start + j] = (self.passes.index(name) + 0.5) / len(self.passes)
        if "tket" in self.passes and self.n_sched:
            y = x.copy()  # second elite seed: TKET first, then the greedy schedule
            y[self.sched_start] = (self.passes.index("tket") + 0.5) / len(self.passes)
            seeds = [x, y]
            if self.lower_gene is not None:
                z = y.copy()  # greedy ECR -> CX conversion, then TKET (usually the best
                z[self.lower_gene] = 0.75  # seed: evaluated second, before y)
                seeds = [x, z, y]
            return seeds
        if self.mode == "hardware":  # several good SabreLayout layouts as elite seeds
            if getattr(self, "_hw_seeds", None) is None:
                self._hw_seeds = self.hw.seed_genes_list(self.circ, k=3)
            seeds = []
            for g in self._hw_seeds:
                y = x.copy()
                y[self.hw_start:] = g
                seeds.append(y)
            return seeds
        return [x]

    def elites(self, k: int) -> list[np.ndarray]:
        """Genomes of the k best distinct phenotypes evaluated so far."""
        keys = sorted(self.cache, key=lambda key: self.cache[key])[:k]
        return [self.genomes[key] for key in keys if key in self.genomes]

    def perm_move(self, y, rng):
        """Hardware local move: relocate one logical qubit to a neighbouring
        physical qubit (swapping the random keys of the two positions)."""
        n = self.hw.cmap.n
        layout, _ = self.hw.decode(y[self.hw_start:], self.circ.n_qubits)
        p = layout[int(rng.integers(len(layout)))]
        nb = sorted(self.hw.cmap.adj[p])
        q = int(rng.choice(nb)) if nb and rng.random() < 0.8 else int(rng.integers(n))
        a, b = self.hw_start + p, self.hw_start + q
        y[a], y[b] = y[b], y[a]

    def evaluate_batch(self, X) -> list:
        X = np.atleast_2d(X)
        keys = [self.phenotype_key(x) for x in X]
        self.n_requests += len(X)
        todo, seen = [], {}
        for i, key in enumerate(keys):
            if key not in self.cache and key not in seen:
                seen[key] = i
                todo.append(i)
        if todo:
            if self.cfg.workers > 1 and len(todo) > 1:
                res = self._parallel([X[i] for i in todo])
            else:
                res = []
                for i in todo:
                    # a wall-clock deadline (set by optimize) stops a generation early;
                    # the first particles (the elite seeds) are always evaluated
                    if res and self.deadline is not None and time.time() > self.deadline:
                        break
                    res.append(self._evaluate_uncached(X[i]))
            for i, r in zip(todo, res):
                self.cache[keys[i]] = r
                self.genomes[keys[i]] = np.array(X[i], dtype=float)
            self.n_evals += len(res)
        worst = (float("inf"),)
        return [self.cache.get(k, worst) for k in keys]

    def _parallel(self, xs):
        global _WORKER_PROBLEM
        if self._pool is None:
            _WORKER_PROBLEM = self
            ctx = mp.get_context("fork")
            self._pool = ctx.Pool(self.cfg.workers)
        return self._pool.map(_worker_eval, xs, chunksize=max(1, len(xs) // (4 * self.cfg.workers)))

    def close(self):
        if self._pool is not None:
            self._pool.close()
            self._pool.join()
            self._pool = None

    def __getstate__(self):  # the pool cannot be pickled
        d = dict(self.__dict__)
        d["_pool"] = None
        d["_built"] = {}
        return d


@dataclass
class OptimizeResult:
    circuit: Circuit
    metrics: dict
    original_metrics: dict
    lowered_metrics: dict
    greedy_metrics: dict
    history: list
    evals: int
    time: float
    verified: bool | None
    genome: np.ndarray
    info: dict = field(default_factory=dict)

    def summary(self) -> str:
        o, g, m = self.lowered_metrics, self.greedy_metrics, self.metrics
        return (f"gates {o['gates']} -> greedy {g['gates']} -> HyPSO {m['gates']} | "
                f"cx {o['cx']} -> {g['cx']} -> {m['cx']} | T {o['t']} -> {g['t']} -> {m['t']} | "
                f"depth {o['depth']} -> {g['depth']} -> {m['depth']} | evals {self.evals} "
                f"| {self.time:.1f}s | verified={self.verified}")


def optimize(circ: Circuit, cfg: HyPSOConfig | None = None, **overrides) -> OptimizeResult:
    """Optimise ``circ`` with HyPSO-QCO."""
    cfg = cfg or HyPSOConfig()
    for k, v in overrides.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
        elif hasattr(cfg.pso, k):
            setattr(cfg.pso, k, v)
        else:
            raise TypeError(f"unknown option {k!r}")
    t0 = time.time()
    memetic = cfg.mode == "ibm" and cfg.resynth
    if cfg.time_limit is not None:
        import copy
        cfg = copy.copy(cfg)
        cfg.pso = copy.copy(cfg.pso)
        cfg.pso.time_limit = cfg.time_limit * ((1 - cfg.resynth_share) if memetic else 1.0)
    problem = CircuitProblem(circ, cfg)
    memetic_history: list = []
    try:
        large = memetic and cfg.time_limit is not None and len(circ.gates) > cfg.large_gates
        # very large circuits under a time limit: a decode takes minutes, so the
        # swarm phase is skipped and the strongest elite seed starts the memetic phase
        greedy_x = problem.seed_positions()[1 if large and len(problem.seed_positions()) > 1 else 0]
        td = time.time()
        greedy_circ, _ = problem.build(greedy_x)
        t_decode = time.time() - td
        gkey = problem.phenotype_key(greedy_x)
        problem.cache[gkey] = problem.cost_of(greedy_circ)
        problem.genomes[gkey] = np.array(greedy_x, dtype=float)
        problem.n_evals += 1
        pso_params = cfg.pso
        if large:
            import copy
            pso_params = copy.copy(cfg.pso)
            pso_params.swarm_size = 1
            pso_params.max_iter = 0
            pso_params.memetic = False
            pso_params.opposition_init = False
            problem.seed_positions = lambda: [greedy_x]  # noqa: E731  (only the evaluated seed)
        elif cfg.pso.time_limit is not None and t_decode * cfg.pso.swarm_size > cfg.pso.time_limit:
            # one swarm generation does not fit into the swarm budget (very large
            # circuits): evaluate only the elite seeds
            import copy
            pso_params = copy.copy(cfg.pso)
            pso_params.swarm_size = len(problem.seed_positions())
            pso_params.max_iter = 0
            pso_params.memetic = False
            pso_params.opposition_init = False
        if cfg.pso.time_limit is not None:
            problem.deadline = t0 + cfg.pso.time_limit
        engine = SwarmOptimizer(problem, pso_params)
        res = engine.run()
        problem.deadline = None
        best, info = problem.build(res.best_x)
        # the seeded default is always evaluated, keep the better of the two
        if cfg.pso.elitist_seed and problem.cost_of(greedy_circ) < problem.cost_of(best):
            best, res.best_x = greedy_circ, greedy_x
        swarm_metrics = metrics(best)
        if cfg.verbose:
            print(f"[hypso] swarm phase done at {time.time() - t0:.1f}s: {problem.n_evals} evals, "
                  f"best {problem.cost_of(best)}", flush=True)
        if memetic:
            # memetic phase: anytime connectivity-preserving resynthesis, first on the
            # distinct swarm elites (each until it stalls), then deepening on the best
            # circuit with larger blocks until the time budget is used up
            from .memetic import memetic_resynthesis
            from .native import to_cx

            def left():
                return None if cfg.time_limit is None else cfg.time_limit - (time.time() - t0)

            cands = problem.elites(max(1, cfg.elites)) or [res.best_x]
            if cfg.time_limit is None:
                cands = cands[:1]
            for j, xe in enumerate(cands):
                if left() is not None and left() <= 1:
                    break
                start, _ = problem.build(xe, native=False)
                if cfg.verbose:
                    print(f"[hypso] memetic on elite {j} from {time.time() - t0:.1f}s", flush=True)
                tl = None if left() is None else max(1.0, left())
                out, hist = memetic_resynthesis(start, problem.native_dirs, problem.obj_fn, time_limit=tl,
                                                rounds=cfg.resynth_evals, workers=cfg.resynth_workers,
                                                seed=cfg.pso.seed + j, max_qubits=cfg.resynth_qubits,
                                                verbose=cfg.verbose, stop_on_stall=True,
                                                sparse=cfg.resynth_sparse)
                memetic_history.append(("elite", j, hist))
                if problem.cost_of(out) < problem.cost_of(best):
                    best = out
            if left() is not None and left() > 1:
                out, hist = memetic_resynthesis(to_cx(best), problem.native_dirs, problem.obj_fn,
                                                time_limit=left(), workers=cfg.resynth_workers,
                                                seed=cfg.pso.seed + 101, max_qubits=cfg.deepen_qubits,
                                                verbose=cfg.verbose, sparse=cfg.resynth_sparse)
                memetic_history.append(("deepen", 0, hist))
                if problem.cost_of(out) < problem.cost_of(best):
                    best = out
    finally:
        problem.close()
    best.meta = dict(circ.meta)
    if info.get("measure_map") is not None:
        best.meta["measure"] = info["measure_map"]
    if memetic:
        info = dict(info, swarm_metrics=swarm_metrics, memetic_history=memetic_history,
                    swarm_skipped=bool(large))
    verified = verify(circ, best, info) if cfg.verify else None
    lowered = problem.lowerer.lower(circ)
    return OptimizeResult(best, metrics(best), metrics(circ), metrics(lowered), metrics(greedy_circ),
                          res.history, problem.n_evals, time.time() - t0, verified, res.best_x, info)


def verify(original: Circuit, optimised: Circuit, info: dict | None = None) -> bool | None:
    """Exact (small) or randomised (medium) equivalence check; None if too big."""
    from .sim import equivalent
    info = info or {}
    if "initial_layout" in info:
        from .hardware.verify import mapped_equivalent
        return mapped_equivalent(original, optimised, info["initial_layout"], info["final_layout"])
    # same register, no relabelling: compare on the qubits that are actually used
    used = sorted(original.used_qubits() | optimised.used_qubits())
    if len(used) > 20:
        return None
    idx = {q: i for i, q in enumerate(used)}
    k = max(1, len(used))
    a = Circuit(k, [Gate(g.name, tuple(idx[q] for q in g.qubits), g.params) for g in original.gates])
    b = Circuit(k, [Gate(g.name, tuple(idx[q] for q in g.qubits), g.params) for g in optimised.gates])
    return equivalent(a, b)


def greedy(circ: Circuit, mode: str = "cliffordt", hardware=None) -> Circuit:
    """The deterministic compiler that HyPSO-QCO wraps (default decisions)."""
    cfg = HyPSOConfig(mode=mode, hardware=hardware)
    p = CircuitProblem(circ, cfg)
    out, info = p.build(p.seed_positions()[0])
    out.meta = dict(circ.meta)
    return out


__all__ = ["HyPSOConfig", "CircuitProblem", "OptimizeResult", "optimize", "verify", "greedy"]
