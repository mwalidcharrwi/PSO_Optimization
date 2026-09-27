"""Mixed-variable particle swarm engine used by HyPSO-QCO.

Genes live in the unit hyper-cube and are decoded by the problem.  Genes are
either *continuous* (cardinality 0) or *categorical* (cardinality k > 1).

Continuous genes follow a hybrid of

* constriction-coefficient PSO (Clerc & Kennedy 2002) and
* quantum-behaved PSO (Sun, Feng & Xu 2004), chosen stochastically per move.

Categorical genes are **nominal** (the 108 CNOT networks of a Toffoli have no
order), so a continuous relaxation is a poor model.  Each particle instead
keeps, for every categorical gene, a *probability vector* over its categories
(categorical PSO in the spirit of Strasser et al., GECCO 2016).  The velocity
pulls this vector towards the one-hot vectors of the personal and
neighbourhood bests; the gene is then sampled from it, with an adaptive
exploration floor.

Further components:

* dynamic neighbourhood (von Neumann lbest early, gbest late),
* adaptive turbulence that grows with stagnation,
* elitist seeding with the problem's default decisions (the swarm can never
  be worse than the deterministic compiler it wraps) and opposition-based
  initialisation,
* stagnation restarts of the worst particles, and
* a **provenance-guided memetic local search** on the global best: if the
  problem exposes ``site_info(x)`` the moves are concentrated on the decision
  sites whose gates *survived* optimisation (i.e. poorly optimised regions),
  and include joint moves of adjacent sites.

Problem interface: ``dim``, ``cardinality``, ``evaluate_batch(X)`` returning
comparable costs, ``seed_positions()``, ``n_evals``; optionally
``site_info(x)`` and ``perm_groups``.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class PSOParams:
    swarm_size: int = 16
    max_iter: int = 200
    max_evals: int | None = 600
    time_limit: float | None = None
    variant: str = "hybrid"        # continuous genes: "spso" | "qpso" | "hybrid"
    categorical: str = "prob"      # categorical genes: "prob" (categorical PSO) | "relaxed"
    topology: str = "dynamic"      # "gbest" | "ring" | "vonneumann" | "dynamic"
    dynamic_switch: float = 0.5    # fraction of the budget after which dynamic -> gbest
    chi: float = 0.7298
    c1: float = 1.49618
    c2: float = 1.49618
    vmax: float = 0.35
    qpso_beta: tuple = (1.0, 0.5)
    p_qpso: float = 0.5            # hybrid: probability of a QPSO move
    cat_floor: float = 0.02        # exploration floor of categorical probabilities
    mutation: float = 0.01         # base turbulence rate per gene
    max_mutation: float = 0.15
    gene_copy: float = 0.15        # "relaxed" mode only: copy a categorical gene from the attractor
    patience: int = 5
    restart_frac: float = 0.5
    memetic: bool = True
    memetic_evals: int = 8
    guided: bool = True            # provenance-guided local search (if the problem supports it)
    opposition_init: bool = True
    elitist_seed: bool = True
    seed: int = 0


@dataclass
class PSOResult:
    best_x: np.ndarray
    best_cost: tuple
    history: list = field(default_factory=list)   # (iteration, evals, time, best_cost)
    evals: int = 0
    iterations: int = 0
    time: float = 0.0


class SwarmOptimizer:
    def __init__(self, problem, params: PSOParams | None = None):
        self.p = params or PSOParams()
        self.problem = problem
        self.rng = np.random.default_rng(self.p.seed)
        self.dim = problem.dim
        self.card = np.asarray(problem.cardinality, dtype=int)
        self.cat_idx = np.flatnonzero(self.card > 1)
        self.cont_idx = np.flatnonzero(self.card == 0)
        self.prob_mode = self.p.categorical == "prob" and len(self.cat_idx) > 0
        self.groups: dict[int, np.ndarray] = {}
        if self.prob_mode:
            for k in sorted(set(self.card[self.cat_idx].tolist())):
                self.groups[k] = np.flatnonzero(self.card == k)
        # genes moved by the continuous rule
        self.move_idx = self.cont_idx if self.prob_mode else np.arange(self.dim)

    # ------------------------------------------------------------------ #
    def _budget_left(self, t0) -> bool:
        p = self.p
        if p.max_evals is not None and self.problem.n_evals >= p.max_evals:
            return False
        if p.time_limit is not None and time.time() - t0 >= p.time_limit:
            return False
        if getattr(self.problem, "n_requests", 0) > 40 * (p.max_evals or 10 ** 9):
            return False  # swarm has fully converged onto cached points
        return True

    def _progress(self, it, t0) -> float:
        p = self.p
        fr = []
        if p.max_evals:
            fr.append(self.problem.n_evals / p.max_evals)
        if p.time_limit:
            fr.append((time.time() - t0) / p.time_limit)
        fr.append(it / max(1, p.max_iter))
        return min(1.0, max(fr))

    @staticmethod
    def _neighbours(S: int, kind: str):
        if kind == "ring":
            return [[(i - 1) % S, i, (i + 1) % S] for i in range(S)]
        if kind == "vonneumann":
            cols = max(1, int(round(math.sqrt(S))))
            rows = int(math.ceil(S / cols))
            nb = []
            for i in range(S):
                r, c = divmod(i, cols)
                cand = {i}
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    j = ((r + dr) % rows) * cols + (c + dc) % cols
                    if j < S:
                        cand.add(j)
                nb.append(sorted(cand))
            return nb
        return None  # gbest

    def _cats(self, X, idx, k):
        return np.minimum((X[:, idx] * k).astype(int), k - 1)

    def _soft_onehot(self, cats, k, a=0.5):
        pr = np.full(cats.shape + (k,), a / k)
        np.put_along_axis(pr, cats[..., None], 1.0 - a + a / k, axis=-1)
        return pr

    # ------------------------------------------------------------------ #
    def run(self) -> PSOResult:
        p, rng, D = self.p, self.rng, self.dim
        S = p.swarm_size
        t0 = time.time()
        # ---------------- initialisation ----------------
        X = rng.random((S, D))
        seeds = list(self.problem.seed_positions())[: max(1, S // 4)] if p.elitist_seed else []
        ns = len(seeds)
        for i, s in enumerate(seeds):
            X[i] = s
        if p.opposition_init:
            half = (S - ns) // 2
            for j in range(half):
                X[ns + half + j] = 1.0 - X[ns + j]
        V = rng.uniform(-p.vmax, p.vmax, (S, D)) * 0.5
        prob, pvel = {}, {}
        for k, idx in self.groups.items():
            prob[k] = self._soft_onehot(self._cats(X, idx, k), k)
            pvel[k] = np.zeros_like(prob[k])
        F = self.problem.evaluate_batch(X)
        P, PF = X.copy(), list(F)
        g = min(range(S), key=lambda i: PF[i])
        G, GF = P[g].copy(), PF[g]
        history = [(0, self.problem.n_evals, time.time() - t0, GF)]
        stall, mut = 0, p.mutation
        it = 0
        while it < p.max_iter and self._budget_left(t0):
            it += 1
            frac = self._progress(it, t0)
            topo = p.topology
            if topo == "dynamic":
                topo = "vonneumann" if frac < p.dynamic_switch else "gbest"
            nbrs = self._neighbours(S, topo)
            L = np.array([G if nbrs is None else P[min(nbrs[i], key=lambda j: PF[j])] for i in range(S)])
            beta = p.qpso_beta[0] + (p.qpso_beta[1] - p.qpso_beta[0]) * frac
            mbest = P.mean(axis=0)
            mi = self.move_idx
            # ---- continuous genes: hybrid SPSO / QPSO ----
            for i in range(S):
                use_q = p.variant == "qpso" or (p.variant == "hybrid" and rng.random() < p.p_qpso)
                if use_q:
                    phi = rng.random(len(mi))
                    att = phi * P[i, mi] + (1 - phi) * L[i, mi]
                    u = np.maximum(rng.random(len(mi)), 1e-12)
                    sign = np.where(rng.random(len(mi)) < 0.5, -1.0, 1.0)
                    newx = att + sign * beta * np.abs(mbest[mi] - X[i, mi]) * np.log(1.0 / u)
                    V[i, mi] = np.clip(newx - X[i, mi], -p.vmax, p.vmax)
                else:
                    r1, r2 = rng.random(len(mi)), rng.random(len(mi))
                    V[i, mi] = p.chi * (V[i, mi] + p.c1 * r1 * (P[i, mi] - X[i, mi]) + p.c2 * r2 * (L[i, mi] - X[i, mi]))
                    V[i, mi] = np.clip(V[i, mi], -p.vmax, p.vmax)
                X[i, mi] = X[i, mi] + V[i, mi]
                if not self.prob_mode and p.gene_copy > 0 and len(self.cat_idx):
                    idx = self.cat_idx[rng.random(len(self.cat_idx)) < p.gene_copy]
                    X[i, idx] = L[i, idx]
                if mut > 0 and len(mi):
                    m = mi[rng.random(len(mi)) < mut]
                    X[i, m] = rng.random(len(m))
            # ---- categorical genes: probability-vector PSO ----
            eps = min(0.5, p.cat_floor + mut)
            for k, idx in self.groups.items():
                ep = self._soft_onehot(self._cats(P, idx, k), k, 0.0)
                el = self._soft_onehot(self._cats(L, idx, k), k, 0.0)
                r1 = rng.random(ep.shape[:-1] + (1,))
                r2 = rng.random(ep.shape[:-1] + (1,))
                pvel[k] = p.chi * (pvel[k] + p.c1 * r1 * (ep - prob[k]) + p.c2 * r2 * (el - prob[k]))
                pr = np.clip(prob[k] + pvel[k], 0.0, None)
                pr /= np.maximum(pr.sum(axis=-1, keepdims=True), 1e-12)
                prob[k] = pr
                samp = (1 - eps) * pr + eps / k
                u = rng.random(samp.shape[:-1] + (1,))
                cats = np.minimum((np.cumsum(samp, axis=-1) < u).sum(axis=-1), k - 1)
                X[:, idx] = (cats + 0.5) / k
            # reflect continuous genes into the unit cube
            over, under = X > 1.0, X < 0.0
            X[over] = 2.0 - X[over]
            X[under] = -X[under]
            np.clip(X, 0.0, 1.0 - 1e-12, out=X)
            V[over | under] *= -0.5
            # ---- evaluation ----
            F = self.problem.evaluate_batch(X)
            improved = False
            for i in range(S):
                if F[i] <= PF[i]:
                    P[i], PF[i] = X[i].copy(), F[i]
                if F[i] < GF:
                    G, GF = X[i].copy(), F[i]
                    improved = True
            # ---- memetic local search around the global best ----
            if p.memetic and self._budget_left(t0):
                x2, f2 = self.local_search(G, GF, t0)
                if f2 < GF:
                    improved = True
                if f2 <= GF:
                    G, GF = x2, f2
                    worst = max(range(S), key=lambda j: PF[j])
                    P[worst], PF[worst] = G.copy(), GF
            if improved:
                stall, mut = 0, p.mutation
            else:
                stall += 1
                if stall >= p.patience:
                    for j in self._restart(X, V, PF, G):
                        for k, idx in self.groups.items():
                            prob[k][j] = self._soft_onehot(self._cats(X[j:j + 1], idx, k), k)[0]
                            pvel[k][j] = 0.0
                    mut = min(p.max_mutation, mut * 2 + 0.01)
                    stall = 0
            history.append((it, self.problem.n_evals, time.time() - t0, GF))
        return PSOResult(G, GF, history, self.problem.n_evals, it, time.time() - t0)

    # ------------------------------------------------------------------ #
    def _restart(self, X, V, PF, G):
        S, D = X.shape
        rng = self.rng
        order = sorted(range(S), key=lambda j: PF[j], reverse=True)
        k = max(1, int(self.p.restart_frac * S))
        for j in order[:k]:
            if rng.random() < 0.5:
                X[j] = rng.random(D)
            else:  # heavy mutation of the global best
                X[j] = G.copy()
                m = rng.random(D) < 0.2
                X[j, m] = rng.random(int(m.sum()))
            V[j] = rng.uniform(-self.p.vmax, self.p.vmax, D) * 0.5
        return order[:k]

    def _mutate(self, y, g):
        k = int(self.card[g])
        if k > 1:
            cur = min(int(y[g] * k), k - 1)
            y[g] = (((cur + int(self.rng.integers(1, k))) % k) + 0.5) / k
        else:
            y[g] = self.rng.random()

    def local_search(self, x: np.ndarray, f, t0):
        """(Provenance-guided) variable-neighbourhood moves around the global best."""
        rng = self.rng
        info = None
        if self.p.guided and hasattr(self.problem, "site_info"):
            info = self.problem.site_info(x)
        perm_groups = getattr(self.problem, "perm_groups", None) or []
        batch = []
        for _ in range(self.p.memetic_evals):
            y = x.copy()
            r = rng.random()
            if info is not None and info[0] and r < 0.85:
                sites, w, nbrs = info
                s = int(rng.choice(len(sites), p=w))
                r2 = rng.random()
                if r2 < 0.5:
                    self._mutate(y, int(rng.choice(sites[s])))
                elif r2 < 0.75:
                    for gi in sites[s]:
                        if rng.random() < 0.7:
                            self._mutate(y, gi)
                elif nbrs[s]:
                    s2 = int(rng.choice(nbrs[s]))
                    self._mutate(y, int(rng.choice(sites[s])))
                    self._mutate(y, int(rng.choice(sites[s2])))
                else:
                    self._mutate(y, int(rng.choice(sites[s])))
            elif perm_groups and r < 0.95:
                grp = perm_groups[int(rng.integers(len(perm_groups)))]
                a, b = rng.choice(grp, 2, replace=False)
                y[a], y[b] = y[b], y[a]
            else:
                n_moves = 1 if rng.random() < 0.7 else 2
                for gi in rng.choice(self.dim, size=min(n_moves, self.dim), replace=False):
                    self._mutate(y, int(gi))
            batch.append(y)
        if not batch or not self._budget_left(t0):
            return x, f
        fs = self.problem.evaluate_batch(np.array(batch))
        j = min(range(len(fs)), key=lambda i: fs[i])
        if fs[j] <= f:
            return batch[j], fs[j]
        return x, f
