"""Baseline search strategies over the *same* genome/decoder as HyPSO-QCO.

Using an identical search space and evaluation oracle isolates the effect
of the search strategy:

* :class:`RandomSearch`
* :class:`GeneticAlgorithm`  (tournament selection, uniform crossover,
  categorical-aware mutation, elitism)
* :class:`SimulatedAnnealing` (single-gene neighbourhood, geometric cooling)
* :class:`StandardPSO` -- the canonical global-best inertia-weight PSO
  (Shi & Eberhart 1998 / Clerc constriction constants) with the usual
  continuous-relaxation decoding and *no* seeding, memetic search,
  restarts or discrete operators.  This is the PSO formulation used by the
  prior PSO-for-circuits literature and serves as the "prior PSO" baseline.

All return a :class:`qcpso.pso.engine.PSOResult`.
"""
from __future__ import annotations

import math
import time

import numpy as np

from .engine import PSOResult


class _Base:
    def __init__(self, problem, max_evals: int = 600, seed: int = 0, seeded: bool = True,
                 time_limit: float | None = None, max_requests_factor: int = 30):
        self.problem = problem
        self.max_evals = max_evals
        self.rng = np.random.default_rng(seed)
        self.seeded = seeded
        self.time_limit = time_limit
        self.card = np.asarray(problem.cardinality, dtype=int)
        self.D = problem.dim
        self.max_requests = max_evals * max_requests_factor
        self.t0 = time.time()
        self.best_x, self.best_f = None, None
        self.history = []

    def left(self) -> bool:
        if self.problem.n_evals >= self.max_evals or self.problem.n_requests >= self.max_requests:
            return False
        if self.time_limit is not None and time.time() - self.t0 > self.time_limit:
            return False
        return True

    def evaluate(self, X):
        F = self.problem.evaluate_batch(X)
        for x, f in zip(X, F):
            if self.best_f is None or f < self.best_f:
                self.best_x, self.best_f = np.array(x, copy=True), f
        self.history.append((len(self.history), self.problem.n_evals, time.time() - self.t0, self.best_f))
        return F

    def init_population(self, n):
        X = self.rng.random((n, self.D))
        if self.seeded:
            X[0] = self.problem.seed_positions()[0]
        return X

    def mutate_gene(self, x, g):
        k = int(self.card[g])
        if k > 1:
            cur = min(int(x[g] * k), k - 1)
            x[g] = (((cur + int(self.rng.integers(1, k))) % k) + 0.5) / k
        else:
            x[g] = self.rng.random()

    def result(self, iters) -> PSOResult:
        return PSOResult(self.best_x, self.best_f, self.history, self.problem.n_evals, iters,
                         time.time() - self.t0)


class RandomSearch(_Base):
    def run(self, batch: int = 20) -> PSOResult:
        X = self.init_population(batch)
        self.evaluate(X)
        it = 0
        while self.left():
            it += 1
            self.evaluate(self.rng.random((batch, self.D)))
        return self.result(it)


class GeneticAlgorithm(_Base):
    def run(self, pop: int = 20, pc: float = 0.9, pm: float | None = None, tour: int = 3,
            elite: int = 2) -> PSOResult:
        pm = pm if pm is not None else 1.0 / max(1, self.D)
        X = self.init_population(pop)
        F = self.evaluate(X)
        it = 0
        while self.left():
            it += 1
            order = sorted(range(pop), key=lambda i: F[i])
            new = [X[i].copy() for i in order[:elite]]
            while len(new) < pop:
                a = min(self.rng.choice(pop, tour, replace=False), key=lambda i: F[i])
                b = min(self.rng.choice(pop, tour, replace=False), key=lambda i: F[i])
                c = X[a].copy()
                if self.rng.random() < pc:
                    mask = self.rng.random(self.D) < 0.5
                    c[mask] = X[b][mask]
                for g in np.flatnonzero(self.rng.random(self.D) < pm):
                    self.mutate_gene(c, g)
                new.append(c)
            X = np.array(new)
            F = self.evaluate(X)
        return self.result(it)


class SimulatedAnnealing(_Base):
    """SA over genomes; costs are compared on their first (primary) component."""

    def run(self, t0: float = 2.0, alpha: float = 0.995, moves: int = 2) -> PSOResult:
        x = self.init_population(1)[0]
        f = self.evaluate(x[None, :])[0]
        T, it = t0, 0
        while self.left():
            it += 1
            y = x.copy()
            for g in self.rng.choice(self.D, size=min(moves, self.D), replace=False):
                self.mutate_gene(y, g)
            fy = self.evaluate(y[None, :])[0]
            d = float(fy[0] - f[0]) if isinstance(fy, tuple) else float(fy - f)
            if fy <= f or self.rng.random() < math.exp(-max(d, 1e-9) / max(T, 1e-9)):
                x, f = y, fy
            T *= alpha
        return self.result(it)


class StandardPSO(_Base):
    """Canonical gbest PSO with inertia weight (the 'prior PSO' baseline)."""

    def run(self, swarm: int = 20, w: float = 0.7298, c1: float = 1.49618, c2: float = 1.49618,
            vmax: float = 0.5) -> PSOResult:
        X = self.init_population(swarm)
        V = self.rng.uniform(-0.1, 0.1, X.shape)
        F = self.evaluate(X)
        P, PF = X.copy(), list(F)
        g = min(range(swarm), key=lambda i: PF[i])
        it = 0
        while self.left():
            it += 1
            G = P[g]
            r1, r2 = self.rng.random(X.shape), self.rng.random(X.shape)
            V = w * V + c1 * r1 * (P - X) + c2 * r2 * (G - X)
            V = np.clip(V, -vmax, vmax)
            X = np.clip(X + V, 0.0, 1.0 - 1e-12)
            F = self.evaluate(X)
            for i in range(swarm):
                if F[i] < PF[i]:
                    P[i], PF[i] = X[i].copy(), F[i]
            g = min(range(swarm), key=lambda i: PF[i])
        return self.result(it)
