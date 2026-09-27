import numpy as np
import pytest

from qcpso.circuit import Circuit
from qcpso.io import parse_qasm, parse_qc, parse_real, to_qasm
from qcpso.sim import equal_up_to_phase, equivalent, unitary

SRC = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3]; qreg r[1];
creg c[4];
gate foo(a,b) x,y { rz(a/2) x; cx x,y; ry(-b*2+pi/3) y; }
h q; t q[0]; tdg q[1]; s q[2]; sdg q[0]; sx q[1]; sxdg q[2];
rx(0.3) q[0]; ry(-1.2) q[1]; rz(pi/7) q[2]; p(0.4) q[0]; u1(0.2) q[1]; u2(0.1,0.2) q[2];
u3(0.3,0.4,0.5) q[0]; U(1,2,3) r[0];
cx q[0],q[1]; cy q[1],q[2]; cz q[2],r[0]; ch q[0],r[0]; swap q[0],q[2]; crx(0.5) q[1],q[0];
cry(0.6) q[2],q[1]; crz(0.7) q[0],r[0]; cp(0.8) q[1],r[0]; cu1(0.9) q[2],q[0]; cu3(0.1,0.2,0.3) r[0],q[1];
rxx(0.3) q[0],q[1]; rzz(0.4) q[1],q[2]; ccx q[0],q[1],q[2]; cswap r[0],q[0],q[1]; rccx q[0],q[1],r[0];
foo(0.3,0.1) q[2],r[0]; cu(0.1,0.2,0.3,0.4) q[0],q[2]; csx q[1],q[0];
c3x q[0],q[1],q[2],r[0]; rc3x q[0],q[1],q[2],r[0]; c3sqrtx q[0],q[1],q[2],r[0];
barrier q;
cx q, r[0];
measure q[0] -> c[0];
"""


def test_qasm_matches_qiskit():
    qiskit = pytest.importorskip("qiskit")
    import qiskit.qasm2
    from qiskit.quantum_info import Operator
    c = parse_qasm(SRC)
    assert c.meta["measure"] == [(0, 0)]
    body = SRC.replace("measure q[0] -> c[0];", "").replace("barrier q;", "")
    qc = qiskit.qasm2.loads(body, custom_instructions=qiskit.qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
    assert equal_up_to_phase(unitary(c), Operator(qc.reverse_bits()).data, 1e-9)


def test_roundtrip():
    from qcpso.decompose import Lowerer
    c = Lowerer().lower(parse_qasm(SRC))
    c2 = parse_qasm(to_qasm(c))
    assert equivalent(c, c2)
    assert "measure q[0] -> c[0];" in to_qasm(c)


def test_qc_format():
    txt = """.v a b c d
.i a b c
BEGIN
H d
tof a b d
T* a
cnot a b
Z a b c
X a b c d
S* c
END
"""
    c = parse_qc(txt)
    assert c.n_qubits == 4
    assert [g.name for g in c.gates] == ["h", "ccx", "tdg", "cx", "ccz", "mcx", "sdg"]


def test_real_format():
    txt = """.version 1.0
.numvars 4
.variables a b c d
.begin
t1 a
t2 a b
t3 a b c
t4 a b c d
f3 a b c
v2 a b
v+2 b c
.end
"""
    c = parse_real(txt)
    assert [g.name for g in c.gates] == ["x", "cx", "ccx", "mcx", "cswap", "csx", "mcu"]
    from qcpso.decompose import Lowerer
    assert equivalent(c, Lowerer().lower(c))
