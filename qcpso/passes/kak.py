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


def min_cnots(u: np.ndarray, tol: float = 1e-9) -> int:
    """Optimal CNOT count (exact classification; block unitaries built from
    exact gate products are accurate to ~1e-13, so tight tolerances are used
    to avoid calling a nearly-local gate such as cp(pi/2^20) local)."""
    u = np.asarray(u, dtype=complex)
    u = u / np.linalg.det(u) ** 0.25
    g = u @ _YY @ u.T @ _YY
    if np.allclose(g, np.eye(4), atol=tol) or np.allclose(g, -np.eye(4), atol=tol):
        return 0
    # 1 CNOT iff char. poly = (x^2 + 1)^2.  g is unitary, so its eigenvalues lie
    # on the unit circle and this is equivalent to tr g = 0 and tr g^2 = -4.
    # (Using traces instead of an eigen-solver also avoids sporadic LAPACK
    # non-convergence on highly degenerate spectra, e.g. SWAP-class blocks.)
    tr1 = np.trace(g)
    if abs(tr1) < 1e-7 and abs(np.trace(g @ g) + 4.0) < 1e-7:
        return 1
    if abs(tr1.imag) < tol:
        return 2
    return 3


def is_local(u: np.ndarray, tol: float = 1e-10) -> bool:
    """Exact product test via the operator-Schmidt decomposition.  Unlike the
    invariants used by :func:`min_cnots` (quadratic in the interaction
    strength), the second Schmidt coefficient is linear in it."""
    r = np.asarray(u).reshape(2, 2, 2, 2).transpose(0, 2, 1, 3).reshape(4, 4)
    sv = np.linalg.svd(r, compute_uv=False)
    return sv[1] < tol * max(1.0, sv[0])


def robust_min_cnots(u: np.ndarray) -> int:
    """:func:`min_cnots` corrected for nearly-local unitaries: a non-local
    gate within the 0-CNOT tolerance is close to the identity class and hence
    cannot be CNOT-equivalent, so at least two CNOTs are required."""
    k = min_cnots(u)
    if k == 0 and not is_local(u):
        return 2
    return k


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


def _layers(x, k):
    """U3 matrices and their angle derivatives for a single parameter vector."""
    xs = x.reshape(k + 1, 2, 3)
    t, p, l = xs[..., 0], xs[..., 1], xs[..., 2]
    c, s = np.cos(t / 2), np.sin(t / 2)
    el, ep, epl = np.exp(1j * l), np.exp(1j * p), np.exp(1j * (p + l))
    z = np.zeros_like(c, dtype=complex)
    U = np.stack([np.stack([c + 0j, -el * s], -1), np.stack([ep * s, epl * c], -1)], -2)
    dt = np.stack([np.stack([-s / 2 + 0j, -el * c / 2], -1), np.stack([ep * c / 2, -epl * s / 2], -1)], -2)
    dp = np.stack([np.stack([z, z], -1), np.stack([1j * ep * s, 1j * epl * c], -1)], -2)
    dl = np.stack([np.stack([z, -1j * el * s], -1), np.stack([z, 1j * epl * c], -1)], -2)
    return U, (dt, dp, dl)


def _residual(xphi, u, k):
    x, phi = xphi[:-1], xphi[-1]
    v = template_unitary(x[None, :], k)[0]
    d = v - np.exp(1j * phi) * u
    return np.concatenate([d.real.ravel(), d.imag.ravel()])


def _jacobian(xphi, u, k):
    """Exact Jacobian of the residual (prefix/suffix products)."""
    x, phi = xphi[:-1], xphi[-1]
    U, D = _layers(x, k)
    L = [np.kron(U[j, 0], U[j, 1]) for j in range(k + 1)]
    B = [np.eye(4, dtype=complex)]
    for j in range(1, k + 1):
        B.append(_CX @ L[j - 1] @ B[j - 1])
    A = [None] * (k + 1)
    A[k] = np.eye(4, dtype=complex)
    for j in range(k - 1, -1, -1):
        A[j] = A[j + 1] @ L[j + 1] @ _CX
    cols = []
    for j in range(k + 1):
        for w in range(2):
            for d in range(3):
                dl = np.kron(D[d][j, 0], U[j, 1]) if w == 0 else np.kron(U[j, 0], D[d][j, 1])
                dv = A[j] @ dl @ B[j]
                cols.append(np.concatenate([dv.real.ravel(), dv.imag.ravel()]))
    dphi = -1j * np.exp(1j * phi) * u
    cols.append(np.concatenate([dphi.real.ravel(), dphi.imag.ravel()]))
    return np.array(cols).T


def instantiate(u: np.ndarray, k: int, rng: np.random.Generator | None = None, swarm: int = 24,
                iters: int = 30, restarts: int = 3, tol: float = 1e-9):
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
    # --- Levenberg-Marquardt polishing (local, exact Jacobian) ------------
    for x0 in starts:
        v0 = template_unitary(x0[None, :], k)[0]
        phi0 = np.angle(np.vdot(u, v0))
        res = least_squares(_residual, np.append(x0, phi0), jac=_jacobian, args=(u, k), method="lm",
                            xtol=1e-15, ftol=1e-15, gtol=1e-15, max_nfev=400)
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
        kk = robust_min_cnots(u) if k is None else k
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
        k = robust_min_cnots(u)
        if ncx - k < min_gain:
            continue
        new = synthesize_2q(u, pair[0], pair[1])
        if sum(1 for g in new if g.name == "cx") >= ncx:
            continue  # numerical synthesis did not reach the predicted count
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
