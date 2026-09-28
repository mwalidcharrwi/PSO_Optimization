"""Connectivity-preserving numerical resynthesis of small blocks.

A *block* is a convex set of gates acting on at most ``max_qubits`` qubits.
Its CNOT skeleton (the ordered list of CNOTs, all on qubit pairs that the
input already couples) is turned into a parametrised template

    V(x) = L_m ... L_1 L_0,   L_0 = (x)_q U3(x_q),   L_j = (U3 x U3) CX_j,

and CNOTs are deleted one at a time: after a deletion, the U3 parameters are
re-instantiated (Levenberg-Marquardt with an analytic Jacobian, warm start
from the previous solution plus random restarts, optionally a small particle
swarm) until V(x) = e^{i phi} U_block to ``tol``.  Because only CNOTs are
removed, every CNOT of the result sits on a pair that was already coupled:
the device mapping is preserved by construction.  The result is numerically
exact (Frobenius residual below ``tol``, default 1e-10).
"""
from __future__ import annotations

import math
import time

import numpy as np
from scipy.optimize import least_squares

from ..circuit import Circuit, Gate
from ..linalg import is_identity_up_to_phase, u3_params

# --------------------------------------------------------------------------- #
# templates
# --------------------------------------------------------------------------- #


def _u3(t, p, l):
    ct, st = math.cos(t / 2), math.sin(t / 2)
    return np.array([[ct, -np.exp(1j * l) * st], [np.exp(1j * p) * st, np.exp(1j * (p + l)) * ct]])


def _du3(t, p, l):
    ct, st = math.cos(t / 2), math.sin(t / 2)
    el, ep, epl = np.exp(1j * l), np.exp(1j * p), np.exp(1j * (p + l))
    dt = np.array([[-st / 2, -el * ct / 2], [ep * ct / 2, -epl * st / 2]])
    dp = np.array([[0, 0], [1j * ep * st, 1j * epl * ct]])
    dl = np.array([[0, -1j * el * st], [0, 1j * epl * ct]])
    return dt, dp, dl


def _apply_1q(m, op, q, n):
    """op (2^n x 2^n) <- (m on qubit q) @ op, qubit 0 = most significant."""
    t = op.reshape((2,) * n + (-1,))
    t = np.tensordot(m, t, axes=([1], [q]))
    t = np.moveaxis(t, 0, q)
    return t.reshape(op.shape)


def _cx_perm(c, t, n):
    idx = np.arange(2 ** n)
    bits_c = (idx >> (n - 1 - c)) & 1
    return idx ^ (bits_c << (n - 1 - t))


_NP = {"u": 3, "z": 1}


def _rzm(p):
    return np.array([[1, 0], [0, np.exp(1j * p)]])


class Template:
    """U3 layer, then for every CNOT: CX followed by U3 on its two qubits.

    ``kinds`` optionally restricts single-qubit slots to Z rotations ("z",
    one parameter) instead of general U3 ("u", three parameters); slot order is
    q0..q_{n-1}, then (control, target) after every CNOT."""

    def __init__(self, n: int, cxs: list[tuple[int, int]], kinds=None):
        self.n = n
        self.cxs = list(cxs)
        n_slots = n + 2 * len(self.cxs)
        self.kinds = list(kinds) if kinds is not None else ["u"] * n_slots
        # factor list: ("u", q, kind) or ("c", perm, None)
        slots = iter(self.kinds)
        self.factors = [("u", q, next(slots)) for q in range(n)]
        for c, t in self.cxs:
            self.factors.append(("c", _cx_perm(c, t, n), None))
            self.factors += [("u", c, next(slots)), ("u", t, next(slots))]
        self.n_params = sum(_NP[k] for k in self.kinds)

    def unitary(self, x):
        n = self.n
        v = np.eye(2 ** n, dtype=complex)
        k = 0
        for kind, a, sk in self.factors:
            if kind == "u":
                if sk == "u":
                    v = _apply_1q(_u3(*x[k:k + 3]), v, a, n)
                else:
                    v = _apply_1q(_rzm(x[k]), v, a, n)
                k += _NP[sk]
            else:
                v = v[a]
        return v

    def residual(self, xphi, u):
        r = self.unitary(xphi[:-1]) - np.exp(1j * xphi[-1]) * u
        return np.concatenate([r.real.ravel(), r.imag.ravel()])

    def residual_and_jac(self, xphi, u):
        x, phi = xphi[:-1], xphi[-1]
        n, d = self.n, 2 ** self.n
        pref = [np.eye(d, dtype=complex)]
        mats = []
        k = 0
        for kind, a, sk in self.factors:
            if kind == "u":
                m = _u3(*x[k:k + 3]) if sk == "u" else _rzm(x[k])
                mats.append((m, k, sk))
                pref.append(_apply_1q(m, pref[-1], a, n))
                k += _NP[sk]
            else:
                mats.append((None, None, None))
                pref.append(pref[-1][a])
        v = pref[-1]
        e = np.exp(1j * phi)
        r = v - e * u
        cols = np.empty((2 * d * d, len(xphi)))
        suf = np.eye(d, dtype=complex)
        shp = (2,) * n + (d,)
        for i in range(len(self.factors) - 1, -1, -1):
            kind, a, _ = self.factors[i]
            if kind == "u":
                m, k0, sk = mats[i]
                if sk == "u":
                    ds = np.stack(_du3(*x[k0:k0 + 3]))                   # (3, 2, 2)
                else:
                    ds = np.array([[[0, 0], [0, 1j * np.exp(1j * x[k0])]]])
                nd = len(ds)
                t = np.tensordot(ds, pref[i].reshape(shp), axes=([2], [a]))  # (nd, 2, ...)
                t = np.moveaxis(t, 1, a + 1).reshape(nd, d, d)
                dv = np.matmul(suf, t)                                   # (nd, d, d)
                cols[: d * d, k0:k0 + nd] = dv.real.reshape(nd, -1).T
                cols[d * d:, k0:k0 + nd] = dv.imag.reshape(nd, -1).T
                suf = _apply_1q(m.T, suf.T, a, n).T
            else:
                suf = suf[:, np.argsort(a)]
        dphi = -1j * e * u
        cols[:, -1] = np.concatenate([dphi.real.ravel(), dphi.imag.ravel()])
        return np.concatenate([r.real.ravel(), r.imag.ravel()]), cols


def _lm(tpl, u, z, tol, max_iter):
    """Levenberg-Marquardt with early abort on stagnation.  Returns (z, ok)."""
    r, J = tpl.residual_and_jac(z, u)
    cost = r @ r
    lam = 1e-3
    hist = [cost]
    tol2 = tol * tol
    for it in range(max_iter):
        if cost < tol2:
            return z, True
        g = J.T @ r
        A = J.T @ J
        dA = np.diag(A).copy()
        while True:
            try:
                step = -np.linalg.solve(A + lam * (np.diag(dA) + 1e-12 * np.eye(len(z))), g)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            z2 = z + step
            r2 = tpl.residual(z2, u)
            c2 = r2 @ r2
            if c2 < cost:
                lam = max(lam / 3, 1e-12)
                z = z2
                r, J = tpl.residual_and_jac(z, u)
                cost = r @ r
                break
            lam *= 4
            if lam > 1e8:
                return z, cost < tol2
        hist.append(cost)
        # stagnation: a converging run improves fast; abort slow ones early
        if it >= 12 and cost > 1e-6 and cost > 0.8 * hist[-7]:
            return z, False
    return z, cost < tol2


def swarm_starts(tpl: Template, u: np.ndarray, rng, k: int = 2, swarm: int = 16, iters: int = 20,
                 anchor: np.ndarray | None = None) -> list[np.ndarray]:
    """Constriction-PSO over the template parameters (fitness: Hilbert-Schmidt
    infidelity 1 - |tr(U^+ V)|/d); the k best personal bests seed
    Levenberg-Marquardt.  With ``anchor`` (the warm start), half of the
    swarm is initialised around it."""
    d = u.shape[0]
    D = tpl.n_params

    def fit(x):
        return 1.0 - abs(np.vdot(u, tpl.unitary(x))) / d

    pos = rng.uniform(0, 2 * math.pi, (swarm, D))
    if anchor is not None:
        h = swarm // 2
        pos[:h] = anchor + rng.normal(scale=0.3, size=(h, D))
    vel = rng.normal(scale=0.3, size=(swarm, D))
    f = np.array([fit(x) for x in pos])
    pb, pf = pos.copy(), f.copy()
    for _ in range(iters):
        g = pb[np.argmin(pf)]
        r1, r2 = rng.random((swarm, D)), rng.random((swarm, D))
        vel = 0.7298 * (vel + 1.49618 * r1 * (pb - pos) + 1.49618 * r2 * (g - pos))
        pos = pos + vel
        f = np.array([fit(x) for x in pos])
        better = f < pf
        pb[better], pf[better] = pos[better], f[better]
    return [pb[i] for i in np.argsort(pf)[:k]]


def instantiate(tpl: Template, u: np.ndarray, starts: list[np.ndarray], tol: float = 1e-10,
                max_iter: int = 150):
    """Return parameters realising ``u`` (up to phase) or None."""
    for x0 in starts:
        v0 = tpl.unitary(x0)
        phi0 = np.angle(np.vdot(u, v0))
        z, ok = _lm(tpl, u, np.append(x0, phi0), tol, max_iter)
        if ok:
            return z[:-1]
    return None


# --------------------------------------------------------------------------- #
# block partitioning (greedy, convex)
# --------------------------------------------------------------------------- #
def partition(circ: Circuit, max_qubits: int = 3, rng=None, p_cut: float = 0.0,
              reverse: bool = False, cut_before: set | None = None) -> list[tuple[tuple[int, ...], list[int]]]:
    """Greedy convex partition into blocks of <= max_qubits qubits.  A qubit is
    'open' in at most one block; merging two open blocks (disjoint qubits, no
    path between them) keeps convexity.

    Variation (to expose different blocks in repeated rounds): ``reverse``
    scans the circuit from the end; with probability ``p_cut`` (or when the
    gate index is in ``cut_before``) a two-qubit gate starts a new block
    instead of joining/merging open blocks."""
    if reverse:
        m = len(circ.gates)
        rc = Circuit(circ.n_qubits, circ.gates[::-1])
        cb = None if cut_before is None else {m - 1 - i for i in cut_before}
        blocks = partition(rc, max_qubits, rng, p_cut, False, cb)
        return [(q, sorted(m - 1 - i for i in idx)) for q, idx in blocks]
    open_block: dict[int, int] = {}
    blocks: list[list] = []  # [set qubits, list idx, alive]
    pending: list[list[int]] = [[] for _ in range(circ.n_qubits)]

    def close(bid):
        for q in blocks[bid][0]:
            if open_block.get(q) == bid:
                del open_block[q]

    for i, g in enumerate(circ.gates):
        qs = g.qubits
        if len(qs) == 1:
            q = qs[0]
            if q in open_block:
                blocks[open_block[q]][1].append(i)
            else:
                pending[q].append(i)
            continue
        if len(qs) != 2:
            for q in qs:
                if q in open_block:
                    close(open_block[q])
                pending[q] = []
            continue
        a, b = qs
        ba, bb = open_block.get(a), open_block.get(b)
        forced = (cut_before is not None and i in cut_before) or (p_cut > 0 and rng is not None
                                                                   and rng.random() < p_cut)
        if forced:
            for bid in {ba, bb} - {None}:
                close(bid)
            nb = len(blocks)
            blocks.append([{a, b}, sorted(pending[a] + pending[b]) + [i]])
            pending[a], pending[b] = [], []
            open_block[a] = open_block[b] = nb
            continue
        if ba is not None and ba == bb:
            blocks[ba][1].append(i)
            continue
        qa = blocks[ba][0] if ba is not None else {a}
        qb = blocks[bb][0] if bb is not None else {b}
        if len(qa | qb) <= max_qubits:
            # merge (a's block absorbs b's)
            if ba is None:
                ba = len(blocks)
                blocks.append([{a}, sorted(pending[a])])
                pending[a] = []
                open_block[a] = ba
            if bb is not None:
                blocks[ba][0] |= blocks[bb][0]
                blocks[ba][1] = sorted(blocks[ba][1] + blocks[bb][1])
                for q in blocks[bb][0]:
                    open_block[q] = ba
                blocks[bb][0] = set()
                blocks[bb][1] = []
            else:
                blocks[ba][0].add(b)
                blocks[ba][1] = sorted(blocks[ba][1] + pending[b])
                pending[b] = []
                open_block[b] = ba
            blocks[ba][1].append(i)
            continue
        # cannot merge: extend the block that has room, close the other
        if ba is not None and len(qa) < max_qubits and bb is not None and len(qb) < max_qubits:
            # keep the larger block, close the other
            if len(blocks[ba][1]) >= len(blocks[bb][1]):
                close(bb)
                bb = None
            else:
                close(ba)
                ba = None
        if ba is not None and len(qa) < max_qubits:
            if bb is not None:
                close(bb)
            blocks[ba][0].add(b)
            blocks[ba][1] = sorted(blocks[ba][1] + pending[b])
            pending[b] = []
            open_block[b] = ba
            blocks[ba][1].append(i)
            continue
        if bb is not None and len(qb) < max_qubits:
            if ba is not None:
                close(ba)
            blocks[bb][0].add(a)
            blocks[bb][1] = sorted(blocks[bb][1] + pending[a])
            pending[a] = []
            open_block[a] = bb
            blocks[bb][1].append(i)
            continue
        if ba is not None:
            close(ba)
        if bb is not None:
            close(bb)
        nb = len(blocks)
        blocks.append([{a, b}, sorted(pending[a] + pending[b]) + [i]])
        pending[a], pending[b] = [], []
        open_block[a] = open_block[b] = nb
    return [(tuple(sorted(b[0])), b[1]) for b in blocks if b[0]]


# --------------------------------------------------------------------------- #
# block resynthesis by CNOT deletion
# --------------------------------------------------------------------------- #
def _block_local(circ: Circuit, qubits, idx):
    loc = {q: i for i, q in enumerate(qubits)}
    return [Gate(circ.gates[i].name, tuple(loc[q] for q in circ.gates[i].qubits), circ.gates[i].params)
            for i in idx]


def _unitary_of(gates, n):
    from ..sim import unitary
    return unitary(Circuit(n, gates))


def _params_from_gates(gates, n, cxs):
    """Exact template parameters reproducing the block: every single-qubit run
    is folded into the U3 slot that follows the last CNOT on its qubit."""
    slot_of = {q: q for q in range(n)}
    mats = [np.eye(2, dtype=complex) for _ in range(n + 2 * len(cxs))]
    k = n
    for g in gates:
        if len(g.qubits) == 1:
            s_ = slot_of[g.qubits[0]]
            mats[s_] = g.matrix() @ mats[s_]
        else:
            c, t = g.qubits
            slot_of[c], slot_of[t] = k, k + 1
            k += 2
    x = []
    for m in mats:
        x.extend(u3_params(m))
    return np.array(x, dtype=float)


def _gates_from_template(tpl: Template, x, qubits, tag=None) -> list[Gate]:
    out = []
    k = 0
    cx_i = 0
    for kind, a, sk in tpl.factors:
        if kind == "u":
            if sk == "z":
                ang = float(x[k])
                if abs(np.exp(1j * ang) - 1) > 1e-11:
                    out.append(Gate("rz", (qubits[a],), (ang,), tag))
            else:
                m = _u3(*x[k:k + 3])
                if not is_identity_up_to_phase(m, 1e-11):
                    t, p, l = u3_params(m)
                    out.append(Gate("u3", (qubits[a],), (t, p, l), tag))
            k += _NP[sk]
        else:
            c, t = tpl.cxs[cx_i]
            cx_i += 1
            out.append(Gate("cx", (qubits[c], qubits[t]), (), tag))
    return out


def sparsify(u, n, cxs, x, tol=1e-10, deadline=None):
    """Turn as many U3 slots as possible into Z rotations (virtual on IBM
    hardware) by warm-started re-instantiation.  Returns (kinds, params)."""
    kinds = ["u"] * (n + 2 * len(cxs))
    per = [np.array(x[3 * s:3 * s + 3]) for s in range(len(kinds))]
    for s_ in range(len(kinds)):
        if deadline is not None and time.time() > deadline:
            break
        th, ph, la = per[s_]
        trial = kinds[:s_] + ["z"] + kinds[s_ + 1:]
        x0 = np.concatenate([per[k] if k != s_ else np.array([ph + la]) for k in range(len(kinds))])
        xn = instantiate(Template(n, cxs, trial), u, [x0], tol=tol, max_iter=60)
        if xn is not None:
            kinds = trial
            per, off = [], 0
            for kd in kinds:
                per.append(np.array(xn[off:off + _NP[kd]]))
                off += _NP[kd]
    return kinds, np.concatenate(per) if per else np.zeros(0)


def _schmidt_rank(u, n, q):
    """Operator Schmidt rank of u across the cut {q} | rest."""
    t = u.reshape((2,) * (2 * n))
    perm = [q, n + q] + [k for k in range(n) if k != q] + [n + k for k in range(n) if k != q]
    m = t.transpose(perm).reshape(4, -1)
    sv = np.linalg.svd(m, compute_uv=False)
    return int(np.sum(sv > 1e-9 * sv[0]))


def cnot_lower_bounds(u, n) -> dict:
    """Lower bound on the number of CNOTs that touch each single-qubit cut:
    one CNOT at most doubles the operator Schmidt rank across a cut."""
    return {q: math.ceil(math.log2(max(1, _schmidt_rank(u, n, q)))) for q in range(n)}


def delete_cnots(u, n, cxs, x_init, rng, tol=1e-10, restarts=0, deadline=None, sweeps=2):
    """Scanning CNOT removal: try to delete each CNOT once per sweep (keeping
    successful deletions); stop when a sweep removes nothing.  Deletions that
    would violate the Schmidt-rank lower bound of a cut are not attempted."""
    lb = cnot_lower_bounds(u, n)
    cur, x = list(cxs), x_init
    for sweep in range(sweeps):
        removed = False
        j = len(cur) - 1 if sweep % 2 == 0 else 0
        order = range(len(cur) - 1, -1, -1) if sweep % 2 == 0 else range(len(cur))
        for j in list(order):
            if j >= len(cur):
                continue
            if deadline is not None and time.time() > deadline:
                return cur, x
            c, t = cur[j]
            cand = cur[:j] + cur[j + 1:]
            if any(sum(1 for e in cand if q in e) < lb[q] for q in (c, t)):
                continue
            tpl = Template(n, cand)
            s0 = 3 * (n + 2 * j)
            x0 = np.concatenate([x[:s0], x[s0 + 6:]])
            xn = instantiate(tpl, u, [x0], tol=tol)
            if xn is None and restarts > 0:
                more = (swarm_starts(tpl, u, rng, k=restarts, anchor=x0) if SWARM_RESTARTS else
                        [rng.uniform(0, 2 * math.pi, tpl.n_params) for _ in range(restarts)])
                xn = instantiate(tpl, u, more, tol=tol)
            if xn is not None:
                cur, x, removed = cand, xn, True
        if not removed:
            break
    if restarts > 0:
        cur, x = _delete_pairs(u, n, cur, x, rng, tol, restarts, deadline, lb)
    return cur, x


def _delete_pairs(u, n, cur, x, rng, tol, restarts, deadline, lb):
    """Deep mode: delete two CNOTs on the same qubit pair at once (consecutive
    in that pair's order); single deletions cannot remove such pairs, since an
    odd number of CNOTs across a cut can never be non-entangling."""
    j = 0
    while j < len(cur):
        if deadline is not None and time.time() > deadline:
            break
        pj = frozenset(cur[j])
        k = next((k for k in range(j + 1, len(cur)) if frozenset(cur[k]) == pj), None)
        if k is None:
            j += 1
            continue
        cand = cur[:j] + cur[j + 1:k] + cur[k + 1:]
        if any(sum(1 for e in cand if q in e) < lb[q] for q in pj):
            j += 1
            continue
        tpl = Template(n, cand)
        sj, sk = 3 * (n + 2 * j), 3 * (n + 2 * k)
        x0 = np.concatenate([x[:sj], x[sj + 6:sk], x[sk + 6:]])
        starts = [x0] + [rng.uniform(0, 2 * math.pi, tpl.n_params) for _ in range(restarts)]
        xn = instantiate(tpl, u, starts, tol=tol)
        if xn is not None:
            cur, x = cand, xn
        else:
            j += 1
    return cur, x


SWARM_RESTARTS = True  # deep mode: PSO-seeded restarts instead of uniform random ones

# generic templates for long blocks: a generic 3-qubit unitary needs at least
# 14 CNOTs, and alternating CNOTs on the two coupled pairs of a line reach it
# with <= 20 in practice; long blocks are first refitted to such a template.
GENERIC_CX = {2: 3, 3: 20}  # (4 qubits: >= 61 CNOTs for a generic unitary; no refit)


def _generic_skeleton(cxs, n, length):
    """Alternate over the coupled pairs present in the block (in first-use order)."""
    pairs = []
    for c, t in cxs:
        if (c, t) not in pairs and (t, c) not in pairs:
            pairs.append((c, t))
    return [pairs[k % len(pairs)] for k in range(length)]


def _refit_generic(u, n, cxs, rng, tol, deadline, starts=3):
    L = GENERIC_CX.get(n)
    if L is None or len(cxs) <= L:
        return None
    skel = _generic_skeleton(cxs, n, L)
    tpl = Template(n, skel)
    x = instantiate(tpl, u, [rng.uniform(0, 2 * math.pi, tpl.n_params) for _ in range(starts)], tol=tol,
                    max_iter=400)
    return None if x is None else (skel, x)


def _resynth_block(args):
    """Worker: (n, local gates, seed, tol, restarts, deadline, sparse) ->
    (cxs, x, kinds) or None."""
    n, gates, seed, tol, restarts, deadline, sparse = args
    cxs = [g.qubits for g in gates if len(g.qubits) == 2]
    u = _unitary_of(gates, n)
    x0 = _params_from_gates(gates, n, cxs)
    rng = np.random.default_rng(seed)
    start_cxs = cxs
    fit = _refit_generic(u, n, cxs, rng, tol, deadline)
    if fit is not None:
        start_cxs, x0 = fit
    new_cxs, x = delete_cnots(u, n, start_cxs, x0, rng, tol=tol, restarts=restarts, deadline=deadline)
    if len(new_cxs) < len(cxs):
        kinds = None
        if sparse:
            kinds, x = sparsify(u, n, new_cxs, x, tol=tol, deadline=deadline)
        return new_cxs, x, kinds
    return None


_BLOCK_CACHE: dict = {}


def _block_key(gates):
    return tuple((g.name, g.qubits, tuple(round(p, 12) for p in g.params)) for g in gates)


def resynthesize(circ: Circuit, max_qubits: int = 3, min_cx: int = 3, seed: int = 0, tol: float = 1e-10,
                 restarts: int = 0, time_limit: float | None = None, stats: dict | None = None,
                 workers: int = 1, blocks=None, pool=None, sparse: bool = True) -> Circuit:
    """Partition into <= max_qubits blocks and delete CNOTs where possible.

    Results are memoised per block (gate list), so re-running on a circuit
    that shares blocks with an earlier one is cheap."""
    deadline = None if time_limit is None else time.time() + time_limit
    blocks = partition(circ, max_qubits) if blocks is None else blocks
    jobs, meta = [], []
    for bi, (qubits, idx) in enumerate(blocks):
        gates = _block_local(circ, qubits, idx)
        ncx = sum(1 for g in gates if len(g.qubits) == 2)
        if ncx < min_cx or any(g.name != "cx" for g in gates if len(g.qubits) == 2):
            continue
        key = (len(qubits), _block_key(gates))
        meta.append((qubits, idx, key, ncx))
        prev = _BLOCK_CACHE.get(key, "missing")
        # recompute unknown blocks and failures obtained with fewer restarts
        if prev == "missing" or (isinstance(prev, int) and prev < restarts):
            jobs.append((key, (len(qubits), gates, seed + bi, tol, restarts, deadline, sparse)))
    # largest blocks first: they have the largest potential
    jobs.sort(key=lambda j: -sum(1 for g in j[1][1] if len(g.qubits) == 2))
    if pool is not None and len(jobs) > 1:
        results = pool.map(_resynth_block, [a for _, a in jobs], chunksize=1)
    elif workers > 1 and len(jobs) > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(workers) as p_:
            results = p_.map(_resynth_block, [a for _, a in jobs], chunksize=1)
    else:
        results = [_resynth_block(a) for _, a in jobs]
    timed_out = deadline is not None and time.time() > deadline
    for (key, args), r in zip(jobs, results):
        if not (timed_out and r is None):  # an unfinished block is not a proven failure
            _BLOCK_CACHE[key] = r if r is not None else args[4]  # failure: remember the restarts used
    repl = []
    saved = 0
    for qubits, idx, key, ncx in meta:
        r = _BLOCK_CACHE.get(key)
        if not isinstance(r, tuple):
            continue
        new_cxs, x, kinds = r
        saved += ncx - len(new_cxs)
        tag = circ.gates[idx[0]].tag
        repl.append((idx, _gates_from_template(Template(len(qubits), new_cxs, kinds), x, qubits, tag)))
    if stats is not None:
        stats.update(blocks=len(blocks), tried=len(meta), computed=len(jobs), saved=saved)
    if not repl:
        return circ
    return rebuild(circ, repl)


def rebuild(circ: Circuit, repl: list) -> Circuit:
    """Replace blocks (lists of gate indices) by new gate lists.

    The circuit DAG is contracted (every block becomes one node) and
    re-linearised by Kahn's algorithm with the original gate order as
    priority, so the result is correct for any convex block, whatever the
    scan direction that produced it.  A non-convex block would create a cycle;
    such blocks are detected and left unchanged."""
    import heapq
    n = len(circ.gates)
    node_of = list(range(n))
    for b, (idx, _) in enumerate(repl):
        for i in idx:
            node_of[i] = n + b
    succ: dict = {}
    indeg: dict = {}
    prio: dict = {}
    last: dict = {}
    for i, g in enumerate(circ.gates):
        v = node_of[i]
        prio.setdefault(v, i)
        indeg.setdefault(v, 0)
        for q in g.qubits:
            u = last.get(q)
            if u is not None and u != v:
                s_ = succ.setdefault(u, set())
                if v not in s_:
                    s_.add(v)
                    indeg[v] += 1
            last[q] = v
    heap = [(prio[v], v) for v in indeg if indeg[v] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        _, v = heapq.heappop(heap)
        order.append(v)
        for w in succ.get(v, ()):
            indeg[w] -= 1
            if indeg[w] == 0:
                heapq.heappush(heap, (prio[w], w))
    if len(order) != len(indeg):  # pragma: no cover - a non-convex block: drop all replacements
        bad = _non_convex(circ, repl)
        keep = [r for b, r in enumerate(repl) if b not in bad]
        return rebuild(circ, keep) if len(keep) < len(repl) else circ
    out = []
    for v in order:
        if v < n:
            out.append(circ.gates[v])
        else:
            out.extend(repl[v - n][1])
    return Circuit(circ.n_qubits, out, circ.name, circ.meta)


def _non_convex(circ: Circuit, repl: list) -> set:
    """Indices of replacement blocks whose gates are not contiguous on a wire."""
    bad = set()
    wires: dict = {}
    for i, g in enumerate(circ.gates):
        for q in g.qubits:
            wires.setdefault(q, []).append(i)
    for b, (idx, _) in enumerate(repl):
        S = set(idx)
        for q in {q for i in idx for q in circ.gates[i].qubits}:
            pos = [k for k, i in enumerate(wires[q]) if i in S]
            if pos[-1] - pos[0] + 1 != len(pos):
                bad.add(b)
                break
    return bad or set(range(len(repl)))


# --------------------------------------------------------------------------- #
# anytime driver (memetic phase of HyPSO-QCO)
# --------------------------------------------------------------------------- #
# (scan direction, random cuts, block size, restarts)
STRATEGIES = (("fwd", False, 3, 0), ("rev", False, 3, 0), ("fwd", True, 3, 0), ("rev", True, 3, 0),
              ("fwd", False, 4, 0), ("rev", False, 4, 0), ("fwd", True, 4, 0), ("rev", True, 4, 0),
              ("fwd", False, 3, 2), ("rev", False, 3, 2),
              ("fwd", False, 5, 0), ("rev", False, 5, 0))


def strategy_name(st) -> str:
    d, cut, q, rs = st
    return f"{d}{'_cut' if cut else ''}{q}{'_deep' if rs else ''}"


def resynthesis_round(circ: Circuit, strategy, rng, pool=None, workers: int = 1, min_cx: int = 2,
                      p_cut: float = 0.15, tol: float = 1e-10, time_limit=None,
                      stats: dict | None = None, sparse: bool = True) -> Circuit:
    """One partition + block-resynthesis round with the given partition strategy."""
    direction, cut, size, restarts = strategy
    blocks = partition(circ, size, rng=rng, p_cut=p_cut if cut else 0.0, reverse=(direction == "rev"))
    return resynthesize(circ, size, min_cx, seed=int(rng.integers(1 << 30)), tol=tol, stats=stats,
                        pool=pool, workers=workers, blocks=blocks, time_limit=time_limit, restarts=restarts,
                        sparse=sparse)
