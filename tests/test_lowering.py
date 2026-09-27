import itertools

import numpy as np
import pytest

from qcpso.circuit import GATE_SPECS, Circuit, Gate, _SX
from qcpso.decompose import BASE_GATES, Lowerer, ccz_networks, mcx_gates
from qcpso.sim import equivalent

LOW = Lowerer(topology_variants=True)
SINGLE = [n for n, s in GATE_SPECS.items() if n not in ("unitary", "mcu", "mcx", "mcz")]


@pytest.mark.parametrize("name", SINGLE)
def test_every_gate_and_variant(name):
    rng = np.random.default_rng(abs(hash(name)) % 2 ** 32)
    nq, npar, _ = GATE_SPECS[name]
    params = tuple(rng.uniform(-3, 3, size=npar))
    qs = tuple(int(q) for q in rng.permutation(4)[:nq])
    c = Circuit(4, [Gate(name, qs, params)])
    sizes = LOW.variant_sizes(c.gates[0])
    combos = list(itertools.product(*[range(s) for s in sizes])) if sizes else [()]
    if len(combos) > 40:
        combos = [combos[i] for i in rng.choice(len(combos), 40, replace=False)]
    for v in combos:
        d = LOW.lower(c, lambda k, s: v)
        assert {g.name for g in d.gates} <= BASE_GATES
        assert equivalent(c, d), (name, v)


def test_network_counts():
    assert len(ccz_networks("full")) == 108
    for m in range(3):
        nets = ccz_networks(f"line{m}")
        assert len(nets) == 4 and all(len(n) == 8 for n in nets)
    assert all(len(n) == 6 for n in ccz_networks("full"))


def test_all_toffoli_variants():
    c = Circuit(3, [Gate("ccx", (2, 0, 1))])
    for net in range(len(LOW.networks)):
        for pol in range(2):
            for pl in range(2):
                d = LOW.lower(c, lambda k, s: (net, pol, pl))
                assert d.t_count() == 7
                assert equivalent(c, d)


@pytest.mark.parametrize("n,k", [(4, 3), (5, 3), (5, 4), (6, 4), (7, 5), (8, 6)])
def test_mcx(n, k):
    c = Circuit(n, [Gate("mcx", tuple(range(k + 1)))])
    assert equivalent(c, LOW.lower(c))


def test_mcu_and_cswap():
    c = Circuit(4, [Gate("mcu", (0, 1, 2, 3), (_SX,)), Gate("cswap", (3, 0, 2))])
    for v in [(0,), (1,)]:
        assert equivalent(c, LOW.lower(c, lambda k, s: v + (0,) * (len(s) - 1)))


def test_provenance_tags_are_semantic():
    c = Circuit(3, [Gate("ccx", (0, 1, 2))])
    tags_a = sorted(g.tag for g in LOW.lower(c, lambda k, s: (0, 0, 0)).gates if g.name == "rz")
    tags_b = sorted(g.tag for g in LOW.lower(c, lambda k, s: (57, 1, 1)).gates if g.name == "rz")
    assert tags_a == tags_b  # the same parity term keeps the same tag in every variant


def test_barenco_dirty_ancilla():
    for k in (3, 4, 5):
        n = 2 * k - 1
        ctrl, anc, t = list(range(k)), list(range(k, 2 * k - 2)), 2 * k - 2
        c = Circuit(n, mcx_gates(ctrl, t, anc))
        ref = Circuit(n, [Gate("mcx", tuple(ctrl) + (t,))])
        assert equivalent(c, ref)
