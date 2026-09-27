import itertools

import numpy as np

from qcpso.circuit import Circuit, Gate, _u3
from qcpso.decompose import Lowerer
from qcpso.framework import CircuitProblem, HyPSOConfig, verify
from qcpso.io import parse_qasm
from qcpso.native import cx_ecr_candidates, cx_to_ecr, to_native, zsx_cost, zsx_gates
from qcpso.pso.engine import PSOParams
from qcpso.sim import equivalent

HEADER = """OPENQASM 2.0;
include "qelib1.inc";
gate rzx(param0) q0,q1 { h q1; cx q0,q1; rz(param0) q1; cx q0,q1; h q1; }
gate ecr q0,q1 { rzx(pi/4) q0,q1; x q0; rzx(-pi/4) q0,q1; }
gate ecr_1234 q0,q1 { s q0; sx q1; cx q0,q1; x q0; }
"""


def test_parser_keeps_ecr_native_and_aliases_equivalent_definitions():
    c = parse_qasm(HEADER + "qreg q[3];\necr q[0],q[1];\necr_1234 q[1],q[2];\nsx q[2];\n")
    assert [g.name for g in c.gates] == ["ecr", "ecr", "sx"]
    ref = parse_qasm("OPENQASM 2.0;\ninclude \"qelib1.inc\";\n" + HEADER.split("\n", 2)[2].replace(
        "gate ecr_1234", "gate e2") + "qreg q[3];\ne2 q[0],q[1];\n")
    assert ref.gates[0].name == "ecr"


def test_ecr_lowering_variants():
    low = Lowerer()
    for pair in ((0, 1), (1, 0)):
        e = Circuit(2, [Gate("ecr", pair)])
        for o, i in itertools.product(range(2), range(8)):
            assert equivalent(e, low.lower(e, lambda k, s: (o, i)))


def test_cx_to_ecr_all_directions_and_candidates():
    for native in ({(0, 1)}, {(1, 0)}):
        for c, t in ((0, 1), (1, 0)):
            g = cx_to_ecr(c, t, native)
            assert equivalent(Circuit(2, [Gate("cx", (c, t))]), Circuit(2, g))
            assert all(x.qubits in native for x in g if x.name == "ecr")
    assert len(cx_ecr_candidates(False)) == 64 and len(cx_ecr_candidates(True)) == 64


def test_zsx_minimal_and_cost_formula():
    rng = np.random.default_rng(5)
    for _ in range(300):
        th, ph, la = rng.uniform(-4, 4, 3)
        if rng.random() < 0.5:
            th = rng.choice([0, np.pi / 2, -np.pi / 2, np.pi])
        u = _u3(th, ph, la)
        gs = zsx_gates(u, 0)
        assert {g.name for g in gs} <= {"rz", "sx", "x"} and len(gs) <= 5
        assert zsx_cost(u) == len(gs)
        assert equivalent(Circuit(1, [Gate("unitary", (0,), (u,))]), Circuit(1, gs))


def test_ibm_mode_end_to_end_preserves_mapping():
    rng = np.random.default_rng(2)
    edges = [(0, 1), (2, 1), (2, 3), (4, 3)]
    c = Circuit(6)
    for _ in range(120):
        r = rng.random()
        if r < 0.3:
            c.append("ecr", edges[rng.integers(len(edges))])
        elif r < 0.65:
            c.append("rz", (int(rng.integers(5)),), (float(rng.uniform(-3, 3)),))
        elif r < 0.9:
            c.append("sx", (int(rng.integers(5)),))
        else:
            c.append("x", (int(rng.integers(5)),))
    res = CircuitProblem(c, HyPSOConfig(mode="ibm", pso=PSOParams(max_evals=30)))
    out, _ = res.build(res.seed_positions()[0])
    assert {g.name for g in out.gates} <= {"rz", "sx", "x", "ecr"}
    assert all(g.qubits in set(edges) for g in out.gates if g.name == "ecr")  # native directions kept
    assert out.two_qubit_count() <= c.two_qubit_count()
    assert verify(c, out) is True
    native = to_native(Circuit(3, [Gate("cx", (1, 0)), Gate("h", (2,))]), {(0, 1)})
    assert all(g.qubits == (0, 1) for g in native.gates if g.name == "ecr")
