import math

import numpy as np
import pytest

from qcpso.circuit import Circuit, Gate
from qcpso.decompose import Lowerer
from qcpso.passes import cancel, fuse_1q, hadamard_reduce, phase_fold
from qcpso.passes.commutation import commute
from qcpso.passes.kak import collect_2q_blocks, min_cnots, resynthesize_blocks, synthesize_2q
from qcpso.pipeline import cleanup
from qcpso.sim import equivalent, unitary

LOW = Lowerer()


def rand_circuit(rng, n=5, m=60):
    c = Circuit(n)
    for _ in range(m):
        r = rng.random()
        if r < 0.35:
            a, b = rng.choice(n, 2, replace=False)
            c.append("cx", (int(a), int(b)))
        elif r < 0.5:
            c.append("h", (int(rng.integers(n)),))
        elif r < 0.55:
            c.append("x", (int(rng.integers(n)),))
        elif r < 0.62:
            a, b, t = rng.choice(n, 3, replace=False)
            c.append("ccx", (int(a), int(b), int(t)))
        else:
            c.append("rz", (int(rng.integers(n)),), (float(rng.choice([1, -1, 2, -2, 3, 4])) * math.pi / 4,))
    return c


@pytest.mark.parametrize("seed", range(25))
def test_passes_are_sound(seed):
    rng = np.random.default_rng(seed)
    c = rand_circuit(rng)
    b = LOW.lower(c, lambda k, s: tuple(int(rng.integers(x)) for x in s))
    place = (lambda tag: float(rng.random())) if seed % 2 else None
    x = cancel(b)
    y, _ = phase_fold(x, place)
    z = hadamard_reduce(y)
    w = cleanup(z, place)
    for cc in (x, y, z, w):
        assert equivalent(c, cc)
    assert len(w) <= len(b)
    assert w.t_count() <= b.t_count()


def test_hadamard_rules_numerically():
    s, sd = (math.pi / 2,), (-math.pi / 2,)
    pairs = [
        ([("h", (0,)), ("rz", (0,), s), ("h", (0,))], [("rz", (0,), sd), ("h", (0,)), ("rz", (0,), sd)]),
        ([("h", (0,)), ("rz", (0,), sd), ("h", (0,))], [("rz", (0,), s), ("h", (0,)), ("rz", (0,), s)]),
        ([("h", (0,)), ("h", (1,)), ("cx", (0, 1)), ("h", (0,)), ("h", (1,))], [("cx", (1, 0))]),
        ([("h", (1,)), ("rz", (1,), s), ("cx", (0, 1)), ("rz", (1,), sd), ("h", (1,))],
         [("rz", (1,), sd), ("cx", (0, 1)), ("rz", (1,), s)]),
        ([("h", (1,)), ("rz", (1,), sd), ("cx", (0, 1)), ("rz", (1,), s), ("h", (1,))],
         [("rz", (1,), s), ("cx", (0, 1)), ("rz", (1,), sd)]),
    ]
    for lhs, rhs in pairs:
        a = Circuit(2, [Gate(*g) for g in lhs])
        b = Circuit(2, [Gate(*g) for g in rhs])
        assert equivalent(a, b)
        red = hadamard_reduce(a)
        assert equivalent(a, red)
        assert red.count_ops().get("h", 0) < a.count_ops().get("h", 0)


def test_commutation_is_conservative():
    rng = np.random.default_rng(3)
    names = [("h", 1), ("x", 1), ("rz", 1), ("cx", 2), ("cz", 2), ("swap", 2), ("ccx", 3)]
    for _ in range(300):
        (n1, k1), (n2, k2) = [names[i] for i in rng.integers(len(names), size=2)]
        q1 = tuple(int(q) for q in rng.permutation(3)[:k1])
        q2 = tuple(int(q) for q in rng.permutation(3)[:k2])
        g1 = Gate(n1, q1, (0.3,) if n1 == "rz" else ())
        g2 = Gate(n2, q2, (1.1,) if n2 == "rz" else ())
        if commute(g1, g2):
            ab = unitary(Circuit(3, [g1, g2]))
            ba = unitary(Circuit(3, [g2, g1]))
            assert np.allclose(ab, ba)


def test_phase_fold_merges_across_hadamards_on_other_wires():
    c = Circuit(2).append("rz", (0,), (math.pi / 4,)).append("h", (1,)).append("cx", (1, 0)) \
        .append("cx", (1, 0)).append("rz", (0,), (math.pi / 4,))
    f, _ = phase_fold(c)
    assert f.t_count() == 0 and equivalent(c, f)


def test_kak_counts_and_synthesis():
    rng = np.random.default_rng(0)
    for k in range(4):
        c = Circuit(2)
        for i in range(k + 1):
            if i:
                c.append("cx", (0, 1))
            for q in range(2):
                c.append("u3", (q,), tuple(rng.uniform(0, 6, 3)))
        u = unitary(c)
        assert min_cnots(u) == k
        g = synthesize_2q(u, 0, 1)
        assert sum(1 for x in g if x.name == "cx") == k
        assert equivalent(c, Circuit(2, g))


def test_block_resynthesis_and_fusion():
    c = Circuit(3).append("cp", (0, 1), (0.7,)).append("swap", (0, 1)).append("cx", (1, 2)) \
        .append("h", (2,)).append("cx", (2, 1)).append("cx", (1, 2))
    b = LOW.lower(c)
    r, changed = resynthesize_blocks(b)
    assert changed and r.cx_count() < b.cx_count() and equivalent(c, r)
    f, _ = fuse_1q(r)
    assert equivalent(c, f)
    assert all(len(blk[0]) == 2 for blk in collect_2q_blocks(b))
