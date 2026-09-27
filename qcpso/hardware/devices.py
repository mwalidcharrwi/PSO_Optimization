"""Coupling maps of common architectures (undirected edges)."""
from __future__ import annotations

from collections import deque

import numpy as np


class CouplingMap:
    def __init__(self, n: int, edges, name: str = ""):
        self.n = int(n)
        self.name = name
        self.edges = sorted({tuple(sorted(map(int, e))) for e in edges if e[0] != e[1]})
        self.adj = [set() for _ in range(self.n)]
        for a, b in self.edges:
            self.adj[a].add(b)
            self.adj[b].add(a)
        self.dist = self._all_pairs()

    def _all_pairs(self) -> np.ndarray:
        d = np.full((self.n, self.n), 10 ** 6, dtype=np.int64)
        for s in range(self.n):
            d[s, s] = 0
            q = deque([s])
            while q:
                u = q.popleft()
                for v in self.adj[u]:
                    if d[s, v] > d[s, u] + 1:
                        d[s, v] = d[s, u] + 1
                        q.append(v)
        return d

    def connected(self, a: int, b: int) -> bool:
        return b in self.adj[a]

    def __repr__(self):
        return f"CouplingMap({self.name!r}, n={self.n}, edges={len(self.edges)})"


def line(n: int) -> CouplingMap:
    return CouplingMap(n, [(i, i + 1) for i in range(n - 1)], f"line_{n}")


def ring(n: int) -> CouplingMap:
    return CouplingMap(n, [(i, (i + 1) % n) for i in range(n)], f"ring_{n}")


def grid(rows: int, cols: int) -> CouplingMap:
    e = []
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if c + 1 < cols:
                e.append((i, i + 1))
            if r + 1 < rows:
                e.append((i, i + cols))
    return CouplingMap(rows * cols, e, f"grid_{rows}x{cols}")


def full(n: int) -> CouplingMap:
    return CouplingMap(n, [(i, j) for i in range(n) for j in range(i + 1, n)], f"full_{n}")


# IBM QX5 / Rueschlikon (16 qubits), as used by Zulehner, Paler & Wille (2018)
_QX5 = [(1, 0), (1, 2), (2, 3), (3, 4), (3, 14), (5, 4), (6, 5), (6, 7), (6, 11), (7, 10), (8, 7), (9, 8),
        (9, 10), (11, 10), (12, 5), (12, 11), (12, 13), (13, 4), (13, 14), (15, 0), (15, 2), (15, 14)]

# IBM Q Tokyo (20 qubits), as used by Li, Ding & Xie (SABRE, 2019)
_TOKYO = ([(r * 5 + c, r * 5 + c + 1) for r in range(4) for c in range(4)]
          + [(i, i + 5) for i in range(15)]
          + [(1, 7), (2, 6), (3, 9), (4, 8), (5, 11), (6, 10), (7, 13), (8, 12), (11, 17), (12, 16),
             (13, 19), (14, 18)])

# IBM Falcon r4 heavy-hex (27 qubits)
_FALCON27 = [(0, 1), (1, 2), (1, 4), (2, 3), (3, 5), (4, 7), (5, 8), (6, 7), (7, 10), (8, 9), (8, 11),
             (10, 12), (11, 14), (12, 13), (12, 15), (13, 14), (14, 16), (15, 18), (16, 19), (17, 18),
             (18, 21), (19, 20), (19, 22), (21, 23), (22, 25), (23, 24), (24, 25), (25, 26)]


def device(name: str) -> CouplingMap:
    name = name.lower()
    if name in ("qx5", "ibm_qx5", "rueschlikon"):
        return CouplingMap(16, _QX5, "ibm_qx5")
    if name in ("tokyo", "ibm_tokyo"):
        return CouplingMap(20, _TOKYO, "ibm_tokyo")
    if name in ("falcon27", "heavyhex27", "ibm_falcon27"):
        return CouplingMap(27, _FALCON27, "ibm_falcon27")
    kind, _, size = name.partition("_")
    if kind == "line":
        return line(int(size))
    if kind == "ring":
        return ring(int(size))
    if kind == "full":
        return full(int(size))
    if kind == "grid":
        r, c = size.split("x")
        return grid(int(r), int(c))
    raise ValueError(f"unknown device {name!r}")


DEVICES = ["ibm_qx5", "ibm_tokyo", "ibm_falcon27", "line_N", "ring_N", "grid_RxC", "full_N"]
