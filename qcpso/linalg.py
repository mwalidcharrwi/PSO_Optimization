"""Small linear-algebra helpers (Euler angles, phase-insensitive distances)."""
from __future__ import annotations

import cmath
import math

import numpy as np


def zyz_angles(u: np.ndarray, eps: float = 1e-12) -> tuple[float, float, float, float]:
    """Return (alpha, beta, gamma, delta) with U = e^{i alpha} Rz(beta) Ry(gamma) Rz(delta)."""
    u = np.asarray(u, dtype=complex)
    det = np.linalg.det(u)
    alpha = cmath.phase(det) / 2.0
    v = u * cmath.exp(-1j * alpha)
    a00, a10, a11 = abs(v[0, 0]), abs(v[1, 0]), v[1, 1]
    gamma = 2.0 * math.atan2(a10, a00)
    if a10 < eps:
        beta, delta = 2.0 * cmath.phase(a11), 0.0
    elif a00 < eps:
        beta, delta = 2.0 * cmath.phase(v[1, 0]), 0.0
    else:
        s = cmath.phase(a11)  # (beta+delta)/2
        d = cmath.phase(v[1, 0])  # (beta-delta)/2
        beta, delta = s + d, s - d
    # fix a possible sign ambiguity (det root) by checking the reconstruction
    rec = _zyz_matrix(alpha, beta, gamma, delta)
    if not np.allclose(rec, u, atol=1e-8):
        alpha += math.pi
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
    return phase_distance(u, np.eye(u.shape[0])) < tol
