from qcpso.bench.generators import cuccaro_adder, qft
from qcpso.decompose import Lowerer
from qcpso.hardware import HardwareSpec, bidirectional_layout, lower_swaps, sabre_route
from qcpso.hardware.devices import device, grid
from qcpso.hardware.verify import mapped_equivalent


def test_devices():
    for name in ("ibm_qx5", "ibm_tokyo", "ibm_falcon27", "grid_3x4", "line_5", "ring_7"):
        cm = device(name)
        assert (cm.dist < 10 ** 6).all()  # connected


def test_sabre_routing_is_correct():
    cm = grid(3, 3)
    for circ in (qft(6), cuccaro_adder(3)):
        base = Lowerer().lower(circ)
        layout, _ = bidirectional_layout(base, cm, trials=2)
        phys, final, _ = sabre_route(base, cm, layout)
        phys = lower_swaps(phys)
        for g in phys.gates:
            if len(g.qubits) == 2:
                assert cm.connected(*g.qubits)
        assert mapped_equivalent(circ, phys, layout, final)


def test_layout_encoding_roundtrip():
    spec = HardwareSpec.from_name("grid_3x3")
    layout = [4, 0, 8, 2]
    genes = spec.encode(layout)
    dec, params = spec.decode(genes, 4)
    assert dec == layout and params["ext_size"] == 20
