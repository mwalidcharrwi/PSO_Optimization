"""Small linear-algebra helpers (Euler angles, phase-insensitive distances)."""
from __future__ import annotations

import cmath
import math

import numpy as np


def zyz_angles(u: np.ndarray, eps: float = 1e-12) -> tuple[float, float, float, float]:
    """Return (alpha, beta, gamma, delta) with U = e^{i alpha} Rz(beta) Ry(gamma) Rz(delta)."""
    u = np.asarray(u, dtype=complex)
    det = u[0, 0] * u[1, 1] - u[0, 1] * u[1, 0]
    alpha = cmath.phase(det) / 2.0
    v = u * cmath.exp(-1j * alpha)  # v in SU(2): [[e^{-is} c, -e^{-id} s], [e^{id} s, e^{is} c]]
    a00, a10 = abs(v[0, 0]), abs(v[1, 0])
    gamma = 2.0 * math.atan2(a10, a00)
    if a10 < eps:
        beta, delta = 2.0 * cmath.phase(v[1, 1]), 0.0
    elif a00 < eps:
        beta, delta = 2.0 * cmath.phase(v[1, 0]), 0.0
    else:
        s = cmath.phase(v[1, 1])  # (beta+delta)/2 (cos(gamma/2) >= 0)
        d = cmath.phase(v[1, 0])  # (beta-delta)/2 (sin(gamma/2) >= 0)
        beta, delta = s + d, s - d
    return alpha, beta, gamma, delta


def _rz(t):
    return np.array([[cmath.exp(-0.5j * t), 0], [0, cmath.exp(0.5j * t)]], dtype=complex)


def _ry(t):
    c, s = math.cos(t / 2), math.sin(t / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def _zyz_matrix(alpha, beta, gamma, delta):
    return cmath.exp(1j * alpha) * (_rz(beta) @ _ry(gamma) @ _rz(delta))


def u3_params(u: np.ndarray) -> tuple[float, float, float]:
    """(theta, phi, lambda) of U3 equal to ``u`` up to global phase."""
    _, beta, gamma, delta = zyz_angles(u)
    return gamma, beta, delta


def phase_distance(a: np.ndarray, b: np.ndarray) -> float:
    """sqrt(1 - |tr(a^dag b)|/d): 0 iff a == e^{i phi} b (for unitaries)."""
    d = a.shape[0]
    return math.sqrt(max(0.0, 1.0 - abs(np.vdot(a, b)) / d))


def is_identity_up_to_phase(u: np.ndarray, tol: float = 1e-9) -> bool:
    """Element-wise test u = e^{i phi} I (linear in the error, unlike
    :func:`phase_distance`, whose square root amplifies rounding noise)."""
    u = np.asarray(u)
    tr = np.trace(u)
    if abs(tr) < 1e-12:
        return False
    return float(np.max(np.abs(u - (tr / abs(tr)) * np.eye(u.shape[0])))) < tol
