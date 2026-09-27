"""Two-qubit block resynthesis (continuous gate sets).

* :func:`min_cnots` -- optimal CNOT count of a 4x4 unitary from the
  invariants of Shende, Markov & Bullock (PRA 69, 062321, 2004).
* :func:`instantiate` -- numerical synthesis of a k-CNOT template
  ``(U3 x U3) [CX (U3 x U3)]^k``.  A small particle swarm explores the
  angle space and Levenberg-Marquardt polishes the best particles to
  machine precision ("swarm instantiation").
* :func:`resynthesize_blocks` -- collect maximal two-qubit blocks and replace
  a block by its optimal circuit when that saves CNOTs.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

from ..circuit import Circuit, Gate
from ..linalg import is_identity_up_to_phase, u3_params

_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_YY = np.kron(_Y, _Y)
_CX = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)


def min_cnots(u: np.ndarray, tol: float = 1e-7) -> int:
    u = np.asarray(u, dtype=complex)
    u = u / np.linalg.det(u) ** 0.25
    g = u @ _YY @ u.T @ _YY
    if np.allclose(g, np.eye(4), atol=tol) or np.allclose(g, -np.eye(4), atol=tol):
        return 0
    ev = np.linalg.eigvals(g)
    n_pi = int(np.sum(np.abs(ev - 1j) < 1e-5))
    n_mi = int(np.sum(np.abs(ev + 1j) < 1e-5))
    if n_pi == 2 and n_mi == 2:
        return 1
    if abs(np.trace(g).imag) < tol:
        return 2
    return 3


# --------------------------------------------------------------------------- #
# numerical instantiation
# --------------------------------------------------------------------------- #
def _u3_batch(t, p, l):
    """U3 matrices for arrays of angles -> shape (..., 2, 2)."""
    c, s = np.cos(t / 2), np.sin(t / 2)
    m = np.empty(t.shape + (2, 2), dtype=complex)
    m[..., 0, 0] = c
    m[..., 0, 1] = -np.exp(1j * l) * s
    m[..., 1, 0] = np.exp(1j * p) * s
    m[..., 1, 1] = np.exp(1j * (p + l)) * c
    return m


def template_unitary(x: np.ndarray, k: int) -> np.ndarray:
    """Batched template evaluation; x has shape (B, 6(k+1))."""
    x = np.atleast_2d(x)
    B = x.shape[0]
    xs = x.reshape(B, k + 1, 2, 3)
    mats = _u3_batch(xs[..., 0], xs[..., 1], xs[..., 2])  # (B, k+1, 2, 2, 2)
    layer = np.einsum("blij,blkm->blikjm", mats[:, :, 0], mats[:, :, 1]).reshape(B, k + 1, 4, 4)
    v = layer[:, 0]
    for i in range(1, k + 1):
        v = layer[:, i] @ (_CX @ v)
    return v


def _infidelity(v: np.ndarray, u: np.ndarray) -> np.ndarray:
    tr = np.einsum("bij,ij->b", v.conj(), u)
    return 1.0 - np.abs(tr) / 4.0


def _residual(xphi, u, k):
    x, phi = xphi[:-1], xphi[-1]
    v = template_unitary(x[None, :], k)[0]
    d = v - np.exp(1j * phi) * u
    return np.concatenate([d.real.ravel(), d.imag.ravel()])


def instantiate(u: np.ndarray, k: int, rng: np.random.Generator | None = None, swarm: int = 24,
                iters: int = 30, restarts: int = 6, tol: float = 1e-10):
    """Find x with template_unitary(x, k) == e^{i phi} u.  Returns x or None."""
    rng = rng or np.random.default_rng(7)
    dim = 6 * (k + 1)
    # --- swarm exploration (global) ---------------------------------------
    pos = rng.uniform(0, 2 * math.pi, size=(swarm, dim))
    vel = rng.normal(scale=0.3, size=(swarm, dim))
    fit = _infidelity(template_unitary(pos, k), u)
    pbest, pfit = pos.copy(), fit.copy()
    for _ in range(iters):
        g = pbest[np.argmin(pfit)]
        r1, r2 = rng.random((swarm, dim)), rng.random((swarm, dim))
        vel = 0.729 * vel + 1.494 * r1 * (pbest - pos) + 1.494 * r2 * (g - pos)
        pos = pos + vel
        fit = _infidelity(template_unitary(pos, k), u)
        better = fit < pfit
        pbest[better], pfit[better] = pos[better], fit[better]
    order = np.argsort(pfit)
    starts = [pbest[i] for i in order[:restarts]]
    starts += [rng.uniform(0, 2 * math.pi, size=dim) for _ in range(restarts)]
    # --- Levenberg-Marquardt polishing (local) ----------------------------
    for x0 in starts:
        v0 = template_unitary(x0[None, :], k)[0]
        phi0 = np.angle(np.vdot(u, v0))
        res = least_squares(_residual, np.append(x0, phi0), args=(u, k), method="lm",
                            xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=4000)
        if np.linalg.norm(res.fun) < tol:
            return res.x[:-1]
    return None


_CACHE: dict = {}


def _cache_key(u: np.ndarray):
    flat = u.ravel()
    j = int(np.argmax(np.abs(flat) > 1e-6))
    ph = flat[j] / abs(flat[j])
    return np.round(u / ph, 9).tobytes()


def synthesize_2q(u: np.ndarray, a: int, b: int, k: int | None = None) -> list[Gate]:
    """Optimal-CNOT circuit (u3 + cx gates) for a 4x4 unitary on qubits (a, b)."""
    u = np.asarray(u, dtype=complex)
    key = _cache_key(u)
    tpl = _CACHE.get(key)
    if tpl is None:
        kk = min_cnots(u) if k is None else k
        x = None
        while x is None and kk <= 3:
            x = instantiate(u, kk)
            if x is None:
                kk += 1
        if x is None:  # pragma: no cover - should not happen
            raise RuntimeError("two-qubit synthesis failed")
        tpl = (kk, x)
        _CACHE[key] = tpl
    kk, x = tpl
    xs = x.reshape(kk + 1, 2, 3)
    gates: list[Gate] = []
    for layer in range(kk + 1):
        if layer:
            gates.append(Gate("cx", (a, b)))
        for w, q in enumerate((a, b)):
            th, ph, la = xs[layer, w]
            m = _u3_batch(np.array(th), np.array(ph), np.array(la))
            if is_identity_up_to_phase(m, 1e-11):
                continue
            t2, p2, l2 = u3_params(m)
            gates.append(Gate("u3", (q,), (t2, p2, l2)))
    return gates


# --------------------------------------------------------------------------- #
# block collection and resynthesis
# --------------------------------------------------------------------------- #
def collect_2q_blocks(circ: Circuit) -> list[tuple[tuple[int, int], list[int]]]:
    open_block: dict[int, int] = {}
    blocks: list[list] = []
    pending: list[list[int]] = [[] for _ in range(circ.n_qubits)]

    def close(q):
        bid = open_block.get(q)
        if bid is not None:
            for x in blocks[bid][0]:
                open_block.pop(x, None)

    for i, g in enumerate(circ.gates):
        qs = g.qubits
        if len(qs) == 1:
            q = qs[0]
            if q in open_block:
                blocks[open_block[q]][1].append(i)
            else:
                pending[q].append(i)
        elif len(qs) == 2:
            a, b = qs
            ba, bb = open_block.get(a), open_block.get(b)
            if ba is not None and ba == bb:
                blocks[ba][1].append(i)
                continue
            close(a)
            close(b)
            idx = sorted(pending[a] + pending[b]) + [i]
            pending[a], pending[b] = [], []
            blocks.append([(a, b), idx])
            open_block[a] = open_block[b] = len(blocks) - 1
        else:
            for q in qs:
                close(q)
                pending[q] = []
    return [(tuple(b[0]), b[1]) for b in blocks]


def block_unitary(circ: Circuit, pair, idx) -> np.ndarray:
    a, b = pair
    local = {a: 0, b: 1}
    sub = Circuit(2, [Gate(circ.gates[i].name, tuple(local[q] for q in circ.gates[i].qubits),
                           circ.gates[i].params) for i in idx])
    from ..sim import unitary
    return unitary(sub)


def resynthesize_blocks(circ: Circuit, min_gain: int = 1) -> tuple[Circuit, bool]:
    """Replace every 2q block whose optimal CNOT count is smaller."""
    blocks = collect_2q_blocks(circ)
    remove: set[int] = set()
    insert: dict[int, list[Gate]] = {}
    for pair, idx in blocks:
        ncx = sum(1 for i in idx if len(circ.gates[i].qubits) == 2)
        if ncx < 2:
            continue
        u = block_unitary(circ, pair, idx)
        k = min_cnots(u)
        if ncx - k < min_gain:
            continue
        new = synthesize_2q(u, pair[0], pair[1])
        tag = circ.gates[idx[0]].tag
        new = [Gate(g.name, g.qubits, g.params, tag) for g in new]
        remove.update(idx)
        insert[idx[-1]] = new
    if not remove:
        return circ, False
    out: list[Gate] = []
    for i, g in enumerate(circ.gates):
        if i in insert:
            out.extend(insert[i])
        elif i not in remove:
            out.append(g)
    return Circuit(circ.n_qubits, out, circ.name, circ.meta), True
