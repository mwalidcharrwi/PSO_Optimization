import pytest

from qcpso.bench.generators import barenco_tof_n, gf2_mult, qft, tof_n
from qcpso.framework import HyPSOConfig, greedy, optimize
from qcpso.hardware import HardwareSpec
from qcpso.pipeline import metrics
from qcpso.pso.engine import PSOParams


@pytest.mark.parametrize("mode", ["cliffordt", "continuous"])
def test_optimize_logical(mode):
    for circ in (tof_n(3), barenco_tof_n(3), gf2_mult(2)):
        res = optimize(circ, HyPSOConfig(mode=mode, pso=PSOParams(max_evals=60, seed=0)))
        assert res.verified is True
        key = "gates" if mode == "cliffordt" else "cx"
        assert res.metrics[key] <= res.greedy_metrics[key]
        g = greedy(circ, mode)
        assert metrics(g)[key] == res.greedy_metrics[key]


def test_swarm_beats_greedy_on_toffoli_ladder():
    res = optimize(barenco_tof_n(4), HyPSOConfig(pso=PSOParams(max_evals=250, seed=1)))
    assert res.verified and res.metrics["gates"] < res.greedy_metrics["gates"]


@pytest.mark.parametrize("variant", ["spso", "qpso", "hybrid"])
def test_engine_variants(variant):
    res = optimize(tof_n(3), HyPSOConfig(pso=PSOParams(max_evals=40, variant=variant, seed=2)))
    assert res.verified


def test_hardware_mode_respects_coupling():
    spec = HardwareSpec.from_name("line_6", continuous=True)
    for circ in (tof_n(3), qft(4)):
        res = optimize(circ, HyPSOConfig(mode="hardware", hardware=spec, pso=PSOParams(max_evals=40, seed=0)))
        assert res.verified is True
        for g in res.circuit.gates:
            if len(g.qubits) == 2:
                assert spec.cmap.connected(*g.qubits)
