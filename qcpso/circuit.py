"""Light-weight quantum-circuit intermediate representation.

A :class:`Circuit` is an ordered list of :class:`Gate` objects acting on
``n`` qubits.  Every gate carries an optional *provenance tag* -- a tuple that
records which gate of the *input* circuit it was derived from.  Provenance is
what allows the PSO genome to stay aligned across particles (see
``qcpso/framework.py``): a gene always refers to the same input gate, no matter
which decomposition variants the particle has chosen elsewhere.

Matrix convention: the local matrix of a gate acting on ``(q0, q1, ...)`` uses
``q0`` as the most-significant bit (i.e. control qubits first for controlled
gates).  All equivalence checks are performed up to a global phase.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, Sequence

import numpy as np

PI = math.pi
TWO_PI = 2.0 * math.pi
ANGLE_TOL = 1e-9


# --------------------------------------------------------------------------- #
# Angle helpers
# --------------------------------------------------------------------------- #
def norm_angle(theta: float) -> float:
    """Map an angle to (-pi, pi]."""
    t = math.fmod(theta, TWO_PI)
    if t <= -PI:
        t += TWO_PI
    elif t > PI:
        t -= TWO_PI
    # snap tiny values / values next to a multiple of pi/4 to exact floats
    k = round(t / (PI / 4))
    if abs(t - k * PI / 4) < 1e-12:
        t = k * PI / 4
        if t <= -PI:
            t += TWO_PI
    return t


def is_zero_angle(theta: float, tol: float = ANGLE_TOL) -> bool:
    return abs(norm_angle(theta)) < tol


def is_multiple(theta: float, unit: float, tol: float = ANGLE_TOL) -> bool:
    k = theta / unit
    return abs(k - round(k)) * unit < tol


def is_t_angle(theta: float, tol: float = ANGLE_TOL) -> bool:
    """True for odd multiples of pi/4 (i.e. the rotation needs a T gate)."""
    t = norm_angle(theta)
    k = t / (PI / 4)
    return abs(k - round(k)) * (PI / 4) < tol and int(round(k)) % 2 != 0


def is_clifford_angle(theta: float, tol: float = ANGLE_TOL) -> bool:
    return is_multiple(norm_angle(theta), PI / 2, tol)


# --------------------------------------------------------------------------- #
# Gate matrices
# --------------------------------------------------------------------------- #
_I2 = np.eye(2, dtype=complex)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_SX = 0.5 * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], dtype=complex)


def _rx(t):
    c, s = math.cos(t / 2), math.sin(t / 2)
    return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)


def _ry(t):
    c, s = math.cos(t / 2), math.sin(t / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def _rz(t):
    return np.array([[np.exp(-0.5j * t), 0], [0, np.exp(0.5j * t)]], dtype=complex)


def _p(lam):
    return np.array([[1, 0], [0, np.exp(1j * lam)]], dtype=complex)


def _u3(theta, phi, lam):
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array(
        [[c, -np.exp(1j * lam) * s], [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c]],
        dtype=complex,
    )


def controlled(u: np.ndarray, n_controls: int = 1) -> np.ndarray:
    """Matrix of ``u`` controlled on ``n_controls`` leading qubits (all |1>)."""
    d = u.shape[0]
    size = d * (2 ** n_controls)
    m = np.eye(size, dtype=complex)
    m[size - d:, size - d:] = u
    return m


def _two(a, b):
    return np.kron(a, b)


_SWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=complex)
_ISWAP = np.array([[1, 0, 0, 0], [0, 0, 1j, 0], [0, 1j, 0, 0], [0, 0, 0, 1]], dtype=complex)


def _rxx(t):
    return np.cos(t / 2) * np.eye(4) - 1j * np.sin(t / 2) * np.kron(_X, _X)


def _ryy(t):
    return np.cos(t / 2) * np.eye(4) - 1j * np.sin(t / 2) * np.kron(_Y, _Y)


def _rzz(t):
    return np.diag(np.exp(-0.5j * t * np.array([1, -1, -1, 1]))).astype(complex)


def _rzx(t):
    return np.cos(t / 2) * np.eye(4) - 1j * np.sin(t / 2) * np.kron(_Z, _X)


def _ecr():
    # IBM echoed cross-resonance gate: rzx(-pi/4) (X x I) rzx(pi/4)
    return _rzx(-PI / 4) @ np.kron(_X, _I2) @ _rzx(PI / 4)


def _cswap():
    m = np.eye(8, dtype=complex)
    m[4:, 4:] = _SWAP
    return m


# name -> (num_qubits (None = variadic), num_params, matrix function)
GATE_SPECS: dict[str, tuple] = {
    "id": (1, 0, lambda: _I2),
    "x": (1, 0, lambda: _X),
    "y": (1, 0, lambda: _Y),
    "z": (1, 0, lambda: _Z),
    "h": (1, 0, lambda: _H),
    "s": (1, 0, lambda: _p(PI / 2)),
    "sdg": (1, 0, lambda: _p(-PI / 2)),
    "t": (1, 0, lambda: _p(PI / 4)),
    "tdg": (1, 0, lambda: _p(-PI / 4)),
    "sx": (1, 0, lambda: _SX),
    "sxdg": (1, 0, lambda: _SX.conj().T),
    "rx": (1, 1, _rx),
    "ry": (1, 1, _ry),
    "rz": (1, 1, _rz),
    "p": (1, 1, _p),
    "u1": (1, 1, _p),
    "u2": (1, 2, lambda phi, lam: _u3(PI / 2, phi, lam)),
    "u3": (1, 3, _u3),
    "u": (1, 3, _u3),
    "cx": (2, 0, lambda: controlled(_X)),
    "cy": (2, 0, lambda: controlled(_Y)),
    "cz": (2, 0, lambda: controlled(_Z)),
    "ch": (2, 0, lambda: controlled(_H)),
    "csx": (2, 0, lambda: controlled(_SX)),
    "swap": (2, 0, lambda: _SWAP),
    "iswap": (2, 0, lambda: _ISWAP),
    "dcx": (2, 0, lambda: _SWAP @ controlled(_X) @ _SWAP @ controlled(_X)),
    "crx": (2, 1, lambda t: controlled(_rx(t))),
    "cry": (2, 1, lambda t: controlled(_ry(t))),
    "crz": (2, 1, lambda t: controlled(_rz(t))),
    "cp": (2, 1, lambda t: controlled(_p(t))),
    "cu1": (2, 1, lambda t: controlled(_p(t))),
    "cu3": (2, 3, lambda a, b, c: controlled(_u3(a, b, c))),
    "cu": (2, 4, lambda a, b, c, g: controlled(np.exp(1j * g) * _u3(a, b, c))),
    "rxx": (2, 1, _rxx),
    "ryy": (2, 1, _ryy),
    "rzz": (2, 1, _rzz),
    "rzx": (2, 1, _rzx),
    "ecr": (2, 0, _ecr),
    "ccx": (3, 0, lambda: controlled(_X, 2)),
    "ccz": (3, 0, lambda: controlled(_Z, 2)),
    "cswap": (3, 0, _cswap),
    # variadic multi-controlled gates: last qubit is the target
    "mcx": (None, 0, None),
    "mcz": (None, 0, None),
    # multi-controlled single-qubit unitary (2x2 matrix stored in params[0])
    "mcu": (None, 1, None),
    # arbitrary unitary on its qubits (matrix stored in params[0])
    "unitary": (None, 1, None),
}

ONE_QUBIT_DIAGONAL = {"z", "s", "sdg", "t", "tdg", "rz", "p", "u1", "id"}
DIAGONAL_GATES = ONE_QUBIT_DIAGONAL | {"cz", "crz", "cp", "cu1", "rzz", "ccz", "mcz"}
SELF_INVERSE = {"x", "y", "z", "h", "cx", "cy", "cz", "swap", "ecr", "ccx", "ccz", "cswap", "mcx", "mcz", "ch", "id"}
INVERSE_NAME = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t", "sx": "sxdg", "sxdg": "sx"}


def gate_matrix(name: str, params: Sequence = (), n_qubits: int | None = None) -> np.ndarray:
    """Return the local unitary of a gate (control qubits first)."""
    if name == "unitary":
        return np.asarray(params[0], dtype=complex)
    if name == "mcx":
        return controlled(_X, n_qubits - 1)
    if name == "mcz":
        return controlled(_Z, n_qubits - 1)
    if name == "mcu":
        return controlled(np.asarray(params[0], dtype=complex), n_qubits - 1)
    try:
        spec = GATE_SPECS[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"unknown gate '{name}'") from exc
    return spec[2](*params)


# --------------------------------------------------------------------------- #
# Gate / Circuit
# --------------------------------------------------------------------------- #
class Gate:
    """A gate instance.  ``tag`` is the provenance tuple (see module doc)."""

    __slots__ = ("name", "qubits", "params", "tag")

    def __init__(self, name: str, qubits: Sequence[int], params: Sequence = (), tag=None):
        self.name = name
        self.qubits = tuple(qubits)
        self.params = tuple(params)
        self.tag = tag

    # ------------------------------------------------------------------ #
    def copy(self) -> "Gate":
        return Gate(self.name, self.qubits, self.params, self.tag)

    @property
    def num_qubits(self) -> int:
        return len(self.qubits)

    def matrix(self) -> np.ndarray:
        return gate_matrix(self.name, self.params, len(self.qubits))

    def inverse(self) -> "Gate":
        n = self.name
        if n in SELF_INVERSE:
            return self.copy()
        if n in INVERSE_NAME:
            return Gate(INVERSE_NAME[n], self.qubits, (), self.tag)
        if n in {"rx", "ry", "rz", "p", "u1", "crx", "cry", "crz", "cp", "cu1", "rxx", "ryy", "rzz", "rzx"}:
            return Gate(n, self.qubits, (-self.params[0],), self.tag)
        if n in {"u3", "u"}:
            th, ph, la = self.params
            return Gate(n, self.qubits, (-th, -la, -ph), self.tag)
        if n == "u2":
            ph, la = self.params
            return Gate("u3", self.qubits, (-PI / 2, -la, -ph), self.tag)
        if n == "cu3":
            th, ph, la = self.params
            return Gate(n, self.qubits, (-th, -la, -ph), self.tag)
        if n == "mcu":
            return Gate(n, self.qubits, (np.asarray(self.params[0]).conj().T,), self.tag)
        return Gate("unitary", self.qubits, (self.matrix().conj().T,), self.tag)

    def is_diagonal(self) -> bool:
        return self.name in DIAGONAL_GATES

    def __eq__(self, other):  # structural equality (ignores provenance)
        if not isinstance(other, Gate):
            return NotImplemented
        if self.name != other.name or self.qubits != other.qubits:
            return False
        if self.name in ("unitary", "mcu"):
            return np.allclose(self.params[0], other.params[0])
        return len(self.params) == len(other.params) and all(
            abs(a - b) < 1e-12 for a, b in zip(self.params, other.params)
        )

    def __hash__(self):
        return hash((self.name, self.qubits))

    def __repr__(self):
        if self.params and self.name not in ("unitary", "mcu"):
            ps = ",".join(f"{p:.6g}" for p in self.params)
            return f"{self.name}({ps}) {','.join(map(str, self.qubits))}"
        return f"{self.name} {','.join(map(str, self.qubits))}"


class Circuit:
    """An ordered gate list on ``n_qubits`` qubits."""

    def __init__(self, n_qubits: int, gates: Iterable[Gate] | None = None, name: str = "", meta=None):
        self.n_qubits = int(n_qubits)
        self.gates: list[Gate] = list(gates) if gates is not None else []
        self.name = name
        self.meta = dict(meta or {})

    # ------------------------------------------------------------------ #
    def append(self, name: str, qubits: Sequence[int], params: Sequence = (), tag=None) -> "Circuit":
        self.gates.append(Gate(name, qubits, params, tag))
        return self

    def add(self, gate: Gate) -> "Circuit":
        self.gates.append(gate)
        return self

    def extend(self, gates: Iterable[Gate]) -> "Circuit":
        self.gates.extend(gates)
        return self

    def copy(self) -> "Circuit":
        return Circuit(self.n_qubits, [g.copy() for g in self.gates], self.name, self.meta)

    def inverse(self) -> "Circuit":
        return Circuit(self.n_qubits, [g.inverse() for g in reversed(self.gates)], self.name + "_inv", self.meta)

    def __len__(self):
        return len(self.gates)

    def __iter__(self):
        return iter(self.gates)

    def __repr__(self):
        return f"Circuit(name={self.name!r}, n_qubits={self.n_qubits}, gates={len(self.gates)})"

    # ------------------------------------------------------------------ #
    # metrics
    # ------------------------------------------------------------------ #
    def count_ops(self) -> Counter:
        return Counter(g.name for g in self.gates)

    def size(self) -> int:
        return len(self.gates)

    def cx_count(self) -> int:
        return sum(1 for g in self.gates if g.name == "cx")

    def two_qubit_count(self) -> int:
        return sum(1 for g in self.gates if len(g.qubits) == 2)

    def multi_qubit_count(self) -> int:
        return sum(1 for g in self.gates if len(g.qubits) >= 2)

    def t_count(self) -> int:
        c = 0
        for g in self.gates:
            if g.name in ("t", "tdg"):
                c += 1
            elif g.name in ("rz", "p", "u1") and is_t_angle(g.params[0]):
                c += 1
        return c

    def depth(self, only_multi: bool = False) -> int:
        level = [0] * self.n_qubits
        for g in self.gates:
            if only_multi and len(g.qubits) < 2:
                continue
            d = max(level[q] for q in g.qubits) + 1
            for q in g.qubits:
                level[q] = d
        return max(level) if level else 0

    def used_qubits(self) -> set[int]:
        s: set[int] = set()
        for g in self.gates:
            s.update(g.qubits)
        return s
