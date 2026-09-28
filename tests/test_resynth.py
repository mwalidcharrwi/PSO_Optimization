"""Connectivity-preserving block resynthesis, DAG rebuild, TKET bridge,
ECR <-> CX conversion and the memetic phase."""
import numpy as np
import pytest

from qcpso.circuit import Circuit, Gate
from qcpso.native import native_directions, respects_coupling, to_cx, to_native
from qcpso.passes import resynth as R
from qcpso.sim import equivalent


def _random_line_circuit(n, m, seed, two_q="cx"):
    rng = np.random.default_rng(seed)
    gs = []
    for _ in range(m):
        r = rng.integers(4)
        if r == 0:
            a = int(rng.integers(n - 1))
            gs.append(Gate(two_q, (a, a + 1) if rng.random() < 0.5 else (a + 1, a)))
        elif r == 1:
            gs.append(Gate("rz", (int(rng.integers(n)),), (float(rng.normal()),)))
        elif r == 2:
            gs.append(Gate("h", (int(rng.integers(n)),)))
        else:
            gs.append(Gate("sx", (int(rng.integers(n)),)))
    return Circuit(n, gs)


def test_template_jacobian_matches_finite_differences():
    rng = np.random.default_rng(3)
    tpl = R.Template(3, [(0, 1), (1, 2), (0, 1), (2, 1)])
    u = np.linalg.qr(rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8)))[0]
    z = rng.normal(size=tpl.n_params + 1)
    r, J = tpl.residual_and_jac(z, u)
    eps = 1e-6
    for k in range(len(z)):
        zz = z.copy()
        zz[k] += eps
        assert np.allclose((tpl.residual(zz, u) - r) / eps, J[:, k], atol=1e-4)


def test_params_from_gates_reproduce_block():
    c = _random_line_circuit(3, 40, 1)
    cxs = [g.qubits for g in c.gates if len(g.qubits) == 2]
    x = R._params_from_gates(c.gates, 3, cxs)
    tpl = R.Template(3, cxs)
    u = R._unitary_of(c.gates, 3)
    ph = np.vdot(tpl.unitary(x), u)
    assert abs(abs(ph) - 8) < 1e-9


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("strategy", R.STRATEGIES[:4])
def test_resynthesis_round_is_equivalent_and_keeps_coupling(seed, strategy):
    c = _random_line_circuit(4, 90, seed)
    rng = np.random.default_rng(seed)
    d = R.resynthesis_round(c, strategy, rng)
    assert d.cx_count() <= c.cx_count()
    assert equivalent(c, d)
    pairs = {frozenset(g.qubits) for g in c.gates if len(g.qubits) == 2}
    assert all(frozenset(g.qubits) in pairs for g in d.gates if len(g.qubits) == 2)


def test_redundant_cnots_are_removed():
    gs = [Gate("cx", (0, 1)), Gate("rz", (0,), (0.7,)), Gate("cx", (0, 1)), Gate("cx", (1, 2)),
          Gate("h", (2,)), Gate("h", (2,)), Gate("cx", (1, 2)), Gate("sx", (1,)), Gate("cx", (1, 2))]
    c = Circuit(3, gs)
    d = R.resynthesize(c, 3, 2, restarts=2)  # "deep" mode: restarts and pair deletions
    assert equivalent(c, d)
    assert d.cx_count() <= 1


def test_rebuild_handles_reverse_partitions():
    # the block {q1,q2} must be placed *after* the cx(0,1) that precedes it on q1
    c = _random_line_circuit(4, 120, 7)
    blocks = R.partition(c, 3, reverse=True)
    repl = [(idx, [c.gates[i] for i in idx]) for _, idx in blocks]
    assert equivalent(c, R.rebuild(c, repl))


def test_partition_blocks_are_contiguous_on_wires():
    c = _random_line_circuit(5, 150, 11)
    rng = np.random.default_rng(0)
    for rev in (False, True):
        for cut in (0.0, 0.3):
            blocks = R.partition(c, 3, rng=rng, p_cut=cut, reverse=rev)
            wires = {}
            for i, g in enumerate(c.gates):
                for q in g.qubits:
                    wires.setdefault(q, []).append(i)
            for _, idx in blocks:  # every block is contiguous on each of its wires
                S = set(idx)
                for q in {q for i in idx for q in c.gates[i].qubits}:
                    pos = [k for k, i in enumerate(wires[q]) if i in S]
                    assert pos[-1] - pos[0] + 1 == len(pos)
            seen = set()
            for qs, idx in blocks:
                assert len(qs) <= 3
                assert not (set(idx) & seen)
                seen |= set(idx)


def test_to_cx_roundtrip_is_exact():
    c = _random_line_circuit(4, 80, 5, two_q="ecr")
    c = Circuit(4, [g for g in c.gates if g.name != "h"])  # native input: {rz, sx, ecr}
    d = to_cx(c)
    assert all(g.name in ("rz", "sx", "x", "cx") for g in d.gates)
    assert equivalent(c, d)
    e = to_native(d, native_directions(c))
    assert equivalent(c, e) and respects_coupling(e, native_directions(c))
    assert all(g.qubits in native_directions(c) for g in e.gates if g.name == "ecr")


def test_tket_bridge_roundtrip_and_passes():
    pytest.importorskip("pytket")
    from qcpso.passes import tket_bridge as TB
    c = _random_line_circuit(4, 80, 9)
    for f in (TB.clifford_simp, TB.synthesise, TB.kak, TB.full):
        d = f(c)
        assert equivalent(c, d)
        pairs = {frozenset(g.qubits) for g in c.gates if len(g.qubits) == 2}
        assert all(frozenset(g.qubits) in pairs for g in d.gates if len(g.qubits) == 2)


def test_memetic_phase_on_native_circuit():
    from qcpso.memetic import memetic_resynthesis
    from qcpso.pipeline import OBJECTIVES
    c = _random_line_circuit(4, 100, 13, two_q="ecr")
    c = Circuit(4, [g for g in c.gates if g.name != "h"])
    native = native_directions(c)
    out, hist = memetic_resynthesis(to_cx(c), native, OBJECTIVES["twoq"], rounds=4, workers=1, max_qubits=3)
    assert all(g.name in ("rz", "sx", "x", "ecr") for g in out.gates)
    assert all(g.qubits in native for g in out.gates if g.name == "ecr")
    assert equivalent(c, out)
    assert sum(g.name == "ecr" for g in out.gates) <= sum(g.name == "ecr" for g in c.gates)
