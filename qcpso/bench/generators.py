"""Programmatic benchmark circuits (standard reversible/arithmetic families).

These mirror the families of the widely used Nam-Ross-Su-Childs-Maslov
suite (tof_n, barenco_tof_n, vbe_adder, gf2^n_mult, qft) so the framework
can be exercised before external benchmark files are supplied.
"""
from __future__ import annotations

import math

import numpy as np

from ..circuit import Circuit
from ..decompose import mcx_gates


def tof_n(n: int) -> Circuit:
    """n-controlled Toffoli with n-2 clean ancillas (compute/uncompute ladder)."""
    ctrl = list(range(n))
    anc = list(range(n, 2 * n - 2))
    t = 2 * n - 2
    c = Circuit(2 * n - 1, name=f"tof_{n}")
    chain = [(ctrl[0], ctrl[1], anc[0])] + [(ctrl[i + 1], anc[i - 1], anc[i]) for i in range(1, n - 2)]
    for a, b, d in chain:
        c.append("ccx", (a, b, d))
    c.append("ccx", (ctrl[n - 1], anc[n - 3], t))
    for a, b, d in reversed(chain):
        c.append("ccx", (a, b, d))
    return c


def barenco_tof_n(n: int) -> Circuit:
    """n-controlled Toffoli with n-2 *dirty* ancillas (Barenco et al. Lemma 7.2)."""
    ctrl = list(range(n))
    anc = list(range(n, 2 * n - 2))
    t = 2 * n - 2
    c = Circuit(2 * n - 1, name=f"barenco_tof_{n}")
    c.extend(mcx_gates(ctrl, t, anc))
    return c


def cuccaro_adder(n: int) -> Circuit:
    """Cuccaro et al. ripple-carry adder: qubits cin, (a_i, b_i)*, cout."""
    cin, cout = 0, 2 * n + 1
    a = [1 + 2 * i for i in range(n)]
    b = [2 + 2 * i for i in range(n)]
    c = Circuit(2 * n + 2, name=f"cuccaro_adder_{n}")

    def maj(x, y, z):
        c.append("cx", (z, y)).append("cx", (z, x)).append("ccx", (x, y, z))

    def uma(x, y, z):
        c.append("ccx", (x, y, z)).append("cx", (z, x)).append("cx", (x, y))

    maj(cin, b[0], a[0])
    for i in range(1, n):
        maj(a[i - 1], b[i], a[i])
    c.append("cx", (a[n - 1], cout))
    for i in range(n - 1, 0, -1):
        uma(a[i - 1], b[i], a[i])
    uma(cin, b[0], a[0])
    return c


def vbe_adder(n: int) -> Circuit:
    """Vedral-Barenco-Ekert plain adder with carry register."""
    a = list(range(n))
    b = list(range(n, 2 * n))
    cr = list(range(2 * n, 3 * n + 1))
    c = Circuit(3 * n + 1, name=f"vbe_adder_{n}")

    def carry(ci, ai, bi, co, inv=False):
        seq = [("ccx", (ai, bi, co)), ("cx", (ai, bi)), ("ccx", (ci, bi, co))]
        for g in (reversed(seq) if inv else seq):
            c.append(*g)

    def summ(ci, ai, bi):
        c.append("cx", (ai, bi)).append("cx", (ci, bi))

    for i in range(n):
        carry(cr[i], a[i], b[i], cr[i + 1])
    c.append("cx", (a[n - 1], b[n - 1]))
    summ(cr[n - 1], a[n - 1], b[n - 1])
    for i in range(n - 2, -1, -1):
        carry(cr[i], a[i], b[i], cr[i + 1], inv=True)
        summ(cr[i], a[i], b[i])
    return c


_GF2_POLY = {2: (0, 1), 3: (0, 1), 4: (0, 1), 5: (0, 2), 6: (0, 1), 7: (0, 1), 8: (0, 1, 3, 4)}


def gf2_mult(n: int) -> Circuit:
    """GF(2^n) multiplier c ^= a*b mod p(x) using Toffolis."""
    low = _GF2_POLY[n]
    a, b, cc = list(range(n)), list(range(n, 2 * n)), list(range(2 * n, 3 * n))
    c = Circuit(3 * n, name=f"gf2^{n}_mult")

    def reduce(k):
        vec = {k}
        while True:
            hi = [x for x in vec if x >= n]
            if not hi:
                return sorted(vec)
            h = max(hi)
            vec ^= {h}
            for e in low:
                vec ^= {h - n + e}

    for i in range(n):
        for j in range(n):
            for m in reduce(i + j):
                c.append("ccx", (a[i], b[j], cc[m]))
    return c


def qft(n: int, swaps: bool = True) -> Circuit:
    c = Circuit(n, name=f"qft_{n}")
    for i in range(n):
        c.append("h", (i,))
        for j in range(i + 1, n):
            c.append("cp", (j, i), (math.pi / 2 ** (j - i),))
    if swaps:
        for i in range(n // 2):
            c.append("swap", (i, n - 1 - i))
    return c


def qaoa_maxcut(n: int, p: int = 1, degree: int = 3, seed: int = 0) -> Circuit:
    rng = np.random.default_rng(seed)
    edges = set()
    while len(edges) < n * degree // 2:
        a, b = sorted(rng.choice(n, 2, replace=False))
        edges.add((int(a), int(b)))
    c = Circuit(n, name=f"qaoa_{n}_p{p}")
    for q in range(n):
        c.append("h", (q,))
    for _ in range(p):
        g, bt = rng.uniform(0, math.pi, 2)
        for (a, b) in sorted(edges):
            c.append("rzz", (a, b), (float(g),))
        for q in range(n):
            c.append("rx", (q,), (float(bt),))
    return c


def random_clifford_t(n: int, m: int, seed: int = 0, p_ccx: float = 0.1) -> Circuit:
    rng = np.random.default_rng(seed)
    c = Circuit(n, name=f"rand_ct_{n}_{m}_s{seed}")
    one = ["h", "s", "sdg", "t", "tdg", "x", "z"]
    for _ in range(m):
        r = rng.random()
        if r < p_ccx and n >= 3:
            q = rng.choice(n, 3, replace=False)
            c.append("ccx", tuple(int(x) for x in q))
        elif r < p_ccx + 0.3:
            q = rng.choice(n, 2, replace=False)
            c.append("cx", tuple(int(x) for x in q))
        else:
            c.append(str(rng.choice(one)), (int(rng.integers(n)),))
    return c


def builtin_suite(scale: str = "small") -> list[Circuit]:
    """A default benchmark suite (used until external benchmarks are given)."""
    if scale == "tiny":
        return [tof_n(3), barenco_tof_n(3), cuccaro_adder(2), gf2_mult(2), qft(3)]
    suite = [
        tof_n(3), tof_n(4), tof_n(5), tof_n(10),
        barenco_tof_n(3), barenco_tof_n(4), barenco_tof_n(5), barenco_tof_n(10),
        vbe_adder(3), cuccaro_adder(4), cuccaro_adder(8),
        gf2_mult(4), gf2_mult(5), gf2_mult(6),
        qft(4), qft(8),
        random_clifford_t(6, 150, seed=1), random_clifford_t(8, 300, seed=2),
    ]
    if scale == "large":
        suite += [tof_n(20), barenco_tof_n(20), cuccaro_adder(16), gf2_mult(8), qft(16), qaoa_maxcut(12, 2)]
    return suite
