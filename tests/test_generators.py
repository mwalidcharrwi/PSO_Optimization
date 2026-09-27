import itertools

from qcpso.bench.generators import cuccaro_adder, gf2_mult, tof_n, vbe_adder, barenco_tof_n


def run_classical(circ, bits):
    b = list(bits)
    for g in circ.gates:
        q = g.qubits
        if g.name == "x":
            b[q[0]] ^= 1
        elif g.name == "cx":
            b[q[1]] ^= b[q[0]]
        elif g.name in ("ccx", "mcx"):
            b[q[-1]] ^= int(all(b[x] for x in q[:-1]))
        else:
            raise ValueError(g.name)
    return b


def test_cuccaro_adds():
    n = 3
    c = cuccaro_adder(n)
    for a, bb in itertools.product(range(2 ** n), repeat=2):
        bits = [0] * c.n_qubits
        for i in range(n):
            bits[1 + 2 * i] = (a >> i) & 1
            bits[2 + 2 * i] = (bb >> i) & 1
        out = run_classical(c, bits)
        s = sum(out[2 + 2 * i] << i for i in range(n)) + (out[2 * n + 1] << n)
        assert s == a + bb


def test_vbe_adds():
    n = 3
    c = vbe_adder(n)
    for a, bb in itertools.product(range(2 ** n), repeat=2):
        bits = [0] * c.n_qubits
        for i in range(n):
            bits[i] = (a >> i) & 1
            bits[n + i] = (bb >> i) & 1
        out = run_classical(c, bits)
        s = sum(out[n + i] << i for i in range(n)) + (out[3 * n] << n)
        assert s == a + bb
        assert [out[i] for i in range(n)] == [(a >> i) & 1 for i in range(n)]


def gf_mul(a, b, n, poly):
    r = 0
    for i in range(n):
        if (b >> i) & 1:
            r ^= a << i
    for k in range(2 * n - 2, n - 1, -1):
        if (r >> k) & 1:
            r ^= poly << (k - n)
    return r


def test_gf2_mult():
    n, poly = 4, 0b10011
    c = gf2_mult(n)
    for a, bb in itertools.product(range(2 ** n), repeat=2):
        bits = [(a >> i) & 1 for i in range(n)] + [(bb >> i) & 1 for i in range(n)] + [0] * n
        out = run_classical(c, bits)
        assert sum(out[2 * n + i] << i for i in range(n)) == gf_mul(a, bb, n, poly)


def test_toffoli_families():
    for circ in (tof_n(4), barenco_tof_n(4)):
        n = 4
        for x in range(2 ** n):
            bits = [(x >> i) & 1 for i in range(n)] + [0] * (circ.n_qubits - n)
            out = run_classical(circ, bits)
            assert out[-1] == int(x == 2 ** n - 1)
            assert out[:n] == bits[:n]
