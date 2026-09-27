"""Hardware-aware mode: joint swarm optimisation of logical decisions, the
initial qubit layout (random-key encoding) and router hyper-parameters."""
from __future__ import annotations

import numpy as np

from ..circuit import Circuit
from ..decompose import Lowerer
from ..passes import cancel
from .devices import CouplingMap, device
from .router import bidirectional_layout, layout_candidates, lower_swaps, sabre_route

EXT_SIZES = (0, 5, 10, 20, 40)
WEIGHTS = (0.1, 0.25, 0.5, 0.75, 1.0)
DECAYS = (0.0, 0.001, 0.01, 0.05)
N_TIEBREAK = 8


class HardwareSpec:
    """Device + genome segment for hardware-aware optimisation.

    Genes: ``n_phys`` random keys (layout) + [ext-set size, look-ahead weight,
    decay, tie-break seed] (categorical).
    """

    def __init__(self, cmap: CouplingMap, continuous: bool = True, layout_trials: int = 4, seed: int = 0):
        self.cmap = cmap
        self.continuous = continuous
        self.layout_trials = layout_trials
        self.seed = seed

    @classmethod
    def from_name(cls, name: str, **kw) -> "HardwareSpec":
        return cls(device(name), **kw)

    # ---------------------------------------------------------------- #
    def gene_cardinality(self, n_log: int) -> list[int]:
        if n_log > self.cmap.n:
            raise ValueError(f"circuit needs {n_log} qubits, device {self.cmap.name} has {self.cmap.n}")
        return [0] * self.cmap.n + [len(EXT_SIZES), len(WEIGHTS), len(DECAYS), N_TIEBREAK]

    def decode(self, genes, n_log: int):
        n = self.cmap.n
        order = np.argsort(np.asarray(genes[:n]), kind="stable")
        layout = [int(p) for p in order[:n_log]]
        c = genes[n:]

        def cat(u, k):
            return min(int(u * k), k - 1)

        params = dict(ext_size=EXT_SIZES[cat(c[0], len(EXT_SIZES))], weight=WEIGHTS[cat(c[1], len(WEIGHTS))],
                      decay_delta=DECAYS[cat(c[2], len(DECAYS))], seed=cat(c[3], N_TIEBREAK))
        return layout, params

    def encode(self, layout, params=None) -> np.ndarray:
        n = self.cmap.n
        keys = np.empty(n + 4)
        rest = [p for p in range(n) if p not in layout]
        for i, p in enumerate(list(layout) + rest):
            keys[p] = (i + 0.5) / n
        params = params or dict(ext_size=20, weight=0.5, decay_delta=0.001, seed=0)
        keys[n] = (EXT_SIZES.index(params["ext_size"]) + 0.5) / len(EXT_SIZES)
        keys[n + 1] = (WEIGHTS.index(params["weight"]) + 0.5) / len(WEIGHTS)
        keys[n + 2] = (DECAYS.index(params["decay_delta"]) + 0.5) / len(DECAYS)
        keys[n + 3] = (params["seed"] + 0.5) / N_TIEBREAK
        return keys

    def seed_genes(self, circ: Circuit) -> np.ndarray:
        """Genes of the SabreLayout (bidirectional) layout of the default lowering."""
        return self.seed_genes_list(circ, k=1)[0]

    def seed_genes_list(self, circ: Circuit, k: int = 3) -> list[np.ndarray]:
        """Genes of the k best distinct SabreLayout layouts (fewest SWAPs first)."""
        base = cancel(Lowerer().lower(circ))
        cands = layout_candidates(base, self.cmap, trials=max(self.layout_trials, 2 * k), seed=self.seed)
        out, seen = [], set()
        for _, layout in cands:
            if tuple(layout) not in seen:
                seen.add(tuple(layout))
                out.append(self.encode(layout))
            if len(out) >= k:
                break
        return out

    def map_and_route(self, circ: Circuit, genes, placement=None):
        layout, params = self.decode(genes, circ.n_qubits)
        phys, final, n_swaps = sabre_route(circ, self.cmap, layout, **params)
        phys = lower_swaps(phys)
        info = {"initial_layout": layout, "final_layout": final, "swaps": n_swaps, "router": params}
        meas = circ.meta.get("measure") if circ.meta else None
        if meas:
            info["measure_map"] = [(final[q], c) for q, c in meas]
        return phys, info


__all__ = ["HardwareSpec", "CouplingMap", "device", "sabre_route", "bidirectional_layout", "lower_swaps"]
