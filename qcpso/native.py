"""IBM native gate set {rz, sx, x, ecr} with fixed device mapping.

* ``ECR`` is registered as an IR gate (matrix = rzx(-pi/4) (X x I) rzx(pi/4),
  identical to the definition shipped in IBM-transpiled QASM files).
* Exact Clifford decompositions ECR = (P x Q) CX (R x S) are enumerated
  once (64 per CNOT orientation) and exposed as decomposition variants, so
  the swarm chooses how every ECR is lowered.
* :func:`to_native` converts an optimised {1q, CX} circuit back to
  {rz, sx, x, ecr}, respecting the native ECR direction of every coupled
  pair, and re-synthesises each single-qubit run with the minimal number of
  rz/sx/x gates.
"""
from __future__ import annotations

import itertools
import math
from functools import lru_cache

import numpy as np

from .circuit import PI, Circuit, Gate, _H, _X, _rzx, controlled, norm_angle
from .linalg import is_identity_up_to_phase, u3_params

ECR_MATRIX = _rzx(-PI / 4) @ np.kron(_X, np.eye(2)) @ _rzx(PI / 4)
_S = np.diag([1, 1j])
_CX = controlled(_X)
_CXR = np.kron(_H, _H) @ _CX @ np.kron(_H, _H)


def _key(m):
    flat = m.ravel()
    k = int(np.argmax(np.abs(flat) > 1e-9))
    ph = flat[k] / abs(flat[k])
    return tuple(np.round((m / ph).ravel(), 6))


@lru_cache(maxsize=None)
def clifford_words():
    """The 24 single-qubit Cliffords (mod phase) as shortest words over {h, s}."""
    words = {(): np.eye(2, dtype=complex)}
    seen = {_key(words[()]): ()}
    frontier = [()]
    while frontier:
        nxt = []
        for w in frontier:
            for g, gm in (("h", _H), ("s", _S)):
                m = gm @ words[w]
                k = _key(m)
                if k not in seen:
                    seen[k] = w + (g,)
                    words[w + (g,)] = m
                    nxt.append(w + (g,))
        frontier = nxt
    return words, seen


def _split(u):
    r = u.reshape(2, 2, 2, 2).transpose(0, 2, 1, 3).reshape(4, 4)
    U, s, Vh = np.linalg.svd(r)
    if s[1] > 1e-9:
        return None
    return (U[:, 0] * math.sqrt(s[0])).reshape(2, 2), (Vh[0] * math.sqrt(s[0])).reshape(2, 2)


def _word_cost(w):
    """Base-gate count of a word after merging consecutive s gates."""
    c, prev = 0, None
    for g in w:
        if g == "s" and prev == "s":
            continue
        c += 1
        prev = g
    return c


@lru_cache(maxsize=None)
def ecr_decompositions(per_orientation: int = 8):
    """Variants of ECR(0,1) = post . CX . pre, as (orientation, wr, ws, wp, wq):
    orientation 0 uses CX(0,1), 1 uses CX(1,0); words are applied as
    wr on qubit 0 and ws on qubit 1 before the CNOT, wp/wq after it."""
    words, seen = clifford_words()
    out = []
    for orient, C in enumerate((_CX, _CXR)):
        sols = []
        for (wr, R), (ws, S) in itertools.product(words.items(), repeat=2):
            rest = ECR_MATRIX @ (C @ np.kron(R, S)).conj().T
            sp = _split(rest)
            if sp is None:
                continue
            wp, wq = seen.get(_key(sp[0])), seen.get(_key(sp[1]))
            if wp is None or wq is None:
                continue
            cost = sum(_word_cost(w) for w in (wr, ws, wp, wq))
            sols.append((cost, wr, ws, wp, wq))
        sols.sort()
        out.extend((orient,) + s[1:] for s in sols[:per_orientation])
    return tuple(out)


def _word_gates(word, q, inverse=False):
    gs = []
    seq = reversed(word) if inverse else word
    for g in seq:
        if g == "h":
            gs.append(Gate("h", (q,)))
        else:
            gs.append(Gate("rz", (q,), (-PI / 2 if inverse else PI / 2,)))
    return gs


def ecr_lowering(a: int, b: int, orient: int, idx: int) -> list[Gate]:
    """ECR(a,b) as {h, rz, cx} gates using variant (orient, idx)."""
    variants = [v for v in ecr_decompositions() if v[0] == orient]
    _, wr, ws, wp, wq = variants[idx % len(variants)]
    cx = Gate("cx", (a, b)) if orient == 0 else Gate("cx", (b, a))
    return _word_gates(wr, a) + _word_gates(ws, b) + [cx] + _word_gates(wp, a) + _word_gates(wq, b)


@lru_cache(maxsize=None)
def _cx_via_ecr_template(ecr_reversed: bool):
    """CX(0,1) as (pre gates, ECR wires, post gates) on abstract wires 0/1."""
    # ECR(0,1) = post . CX(o) . pre  =>  CX(o) = post^-1 . ECR(0,1) . pre^-1
    orient = 1 if ecr_reversed else 0  # we need CX(0,1) expressed via ECR(1,0) when reversed
    v = [x for x in ecr_decompositions() if x[0] == orient][0]
    _, wr, ws, wp, wq = v
    if not ecr_reversed:
        # CX(0,1) = (wp x wq)^-1 ECR(0,1) (wr x ws)^-1
        pre = [("w", wr, 0, True), ("w", ws, 1, True)]
        post = [("w", wp, 0, True), ("w", wq, 1, True)]
        return pre, (0, 1), post
    # ECR(0,1) = post . CX(1,0) . pre ; relabel 0<->1:
    # ECR(1,0) = post' . CX(0,1) . pre'  with words acting on swapped wires
    pre = [("w", wr, 1, True), ("w", ws, 0, True)]
    post = [("w", wp, 1, True), ("w", wq, 0, True)]
    return pre, (1, 0), post


def cx_to_ecr(c: int, t: int, native: set) -> list[Gate]:
    """CX(c,t) with an ECR in the native direction of the pair (c,t)."""
    rev = (c, t) not in native and (t, c) in native
    pre, (e0, e1), post = _cx_via_ecr_template(rev)
    wires = (c, t)
    gs: list[Gate] = []
    for _, w, q, inv in pre:
        gs += _word_gates(w, wires[q], inverse=inv)
    gs.append(Gate("ecr", (wires[e0], wires[e1])))
    for _, w, q, inv in post:
        gs += _word_gates(w, wires[q], inverse=inv)
    return gs


# --------------------------------------------------------------------------- #
# minimal single-qubit synthesis in {rz, sx, x}
# --------------------------------------------------------------------------- #
_SPECIAL_TOL = 1e-7  # angles within this of a special value use the shorter form


def _rz(q, a):
    a = norm_angle(a)
    return [] if abs(a) < 1e-9 else [Gate("rz", (q,), (a,))]


def zsx_gates(u: np.ndarray, q: int) -> list[Gate]:
    """Fewest-gate {rz, sx, x} circuit for a 2x2 unitary (up to global phase)."""
    if is_identity_up_to_phase(u, 1e-9):
        return []
    th, ph, la = u3_params(u)
    th = norm_angle(th)
    tol = _SPECIAL_TOL
    cand = []
    if abs(th) < tol:
        cand.append(_rz(q, ph + la))
    if abs(abs(th) - PI) < tol:  # U3(pi, phi, lam) = Rz(phi) X Rz(lam + pi) (circuit: rz, x, rz)
        cand.append(_rz(q, la + PI) + [Gate("x", (q,))] + _rz(q, ph))
    if abs(th - PI / 2) < tol:  # U2(phi, lam) = Rz(phi + pi/2) SX Rz(lam - pi/2)
        cand.append(_rz(q, la - PI / 2) + [Gate("sx", (q,))] + _rz(q, ph + PI / 2))
    if abs(th + PI / 2) < tol:
        cand.append(_rz(q, la + PI / 2) + [Gate("sx", (q,))] + _rz(q, ph - PI / 2))
    # general: U3(th, phi, lam) = Rz(phi + pi) SX Rz(th + pi) SX Rz(lam)
    cand.append(_rz(q, la) + [Gate("sx", (q,))] + _rz(q, th + PI) + [Gate("sx", (q,))] + _rz(q, ph + PI))
    for c in sorted(cand, key=len):
        if _check(c, u):
            return c
    raise RuntimeError("single-qubit ZSX synthesis failed")  # pragma: no cover


def _check(gates, u):
    m = np.eye(2, dtype=complex)
    for g in gates:
        m = g.matrix() @ m
    return is_identity_up_to_phase(m.conj().T @ u, 1e-6)


def native_directions(circ: Circuit) -> set:
    return {g.qubits for g in circ.gates if g.name == "ecr"}


def _word_matrix(word, inverse=False):
    m = np.eye(2, dtype=complex)
    seq = reversed(word) if inverse else word
    for g in seq:
        gm = _H if g == "h" else (_S.conj().T if inverse else _S)
        m = gm @ m
    return m


@lru_cache(maxsize=None)
def cx_ecr_candidates(reversed_ecr: bool):
    """All exact ways to write CX(c,t) with one ECR: tuples of 2x2 matrices
    (pre_c, pre_t, post_c, post_t) and the ECR wires as (0,1)=(c,t) or (1,0)."""
    words, seen = clifford_words()
    out = []
    for v in ecr_decompositions(per_orientation=64):
        orient, wr, ws, wp, wq = v
        if orient != (1 if reversed_ecr else 0):
            continue
        R, S_, P, Q = (_word_matrix(w, inverse=True) for w in (wr, ws, wp, wq))
        if not reversed_ecr:  # CX(0,1) = (P^-1 x Q^-1) ECR(0,1) (R^-1 x S^-1)
            out.append((R, S_, P, Q, (0, 1)))
        else:                  # relabelled: CX(0,1) = (Q^-1 x P^-1) ECR(1,0) (S^-1 x R^-1)
            out.append((S_, R, Q, P, (1, 0)))
    # sanity check once
    for pre_c, pre_t, post_c, post_t, (e0, e1) in out:
        E = ECR_MATRIX if (e0, e1) == (0, 1) else _SWAP4 @ ECR_MATRIX @ _SWAP4
        m = np.kron(post_c, post_t) @ E @ np.kron(pre_c, pre_t)
        assert is_identity_up_to_phase(m.conj().T @ _CX, 1e-9)
    return tuple(out)


@lru_cache(maxsize=None)
def _candidate_tables(reversed_ecr: bool):
    """Distinct pre-wrappers per wire (up to phase) and index maps."""
    cands = cx_ecr_candidates(reversed_ecr)
    pc_list, pt_list, pc_idx, pt_idx = [], [], [], []
    kc, kt = {}, {}
    for pre_c, pre_t, *_ in cands:
        a, b = _key(pre_c), _key(pre_t)
        if a not in kc:
            kc[a] = len(pc_list)
            pc_list.append(pre_c)
        if b not in kt:
            kt[b] = len(pt_list)
            pt_list.append(pre_t)
        pc_idx.append(kc[a])
        pt_idx.append(kt[b])
    return cands, pc_list, pt_list, pc_idx, pt_idx


_SWAP4 = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=complex)


def zsx_cost(u: np.ndarray) -> int:
    """Number of {rz, sx, x} gates :func:`zsx_gates` emits, in closed form."""
    if is_identity_up_to_phase(u, 1e-9):
        return 0
    th, ph, la = u3_params(u)
    th = norm_angle(th)
    tol = _SPECIAL_TOL

    def nz(*angles):
        return sum(1 for a in angles if abs(norm_angle(a)) >= 1e-9)

    if abs(th) < tol:
        return nz(ph + la)
    best = nz(la) + nz(th + PI) + nz(ph + PI) + 2
    if abs(abs(th) - PI) < tol:
        best = min(best, nz(la + PI, ph) + 1)
    if abs(th - PI / 2) < tol:
        best = min(best, nz(la - PI / 2, ph + PI / 2) + 1)
    if abs(th + PI / 2) < tol:
        best = min(best, nz(la + PI / 2, ph - PI / 2) + 1)
    return best


def to_native(circ: Circuit, native: set) -> Circuit:
    """{1q, cx} -> {rz, sx, x, ecr}.

    Single-qubit gates are accumulated per wire.  For each CNOT, the ECR
    direction is the native one of the pair, and among all exact Clifford
    wrappings of CX by one ECR the one minimising the native cost of the
    two pending single-qubit runs is chosen (greedy, left to right); the
    remaining wrapper becomes the start of the next runs.
    """
    n = circ.n_qubits
    out: list[Gate] = []
    pend = [np.eye(2, dtype=complex) for _ in range(n)]

    def flush(q):
        out.extend(zsx_gates(pend[q], q))
        pend[q] = np.eye(2, dtype=complex)

    for g in circ.gates:
        if len(g.qubits) == 1:
            q = g.qubits[0]
            pend[q] = g.matrix() @ pend[q]
        elif g.name == "cx":
            c, t = g.qubits
            rev = (c, t) not in native and (t, c) in native
            cands, pc_list, pt_list, pc_idx, pt_idx = _candidate_tables(rev)
            cc = [zsx_cost(m @ pend[c]) for m in pc_list]   # <= 24 distinct wrappers per wire
            ct = [zsx_cost(m @ pend[t]) for m in pt_list]
            j = min(range(len(cands)), key=lambda i: cc[pc_idx[i]] + ct[pt_idx[i]])
            pre_c, pre_t, post_c, post_t, (e0, e1) = cands[j]
            out.extend(zsx_gates(pre_c @ pend[c], c))
            out.extend(zsx_gates(pre_t @ pend[t], t))
            wires = (c, t)
            out.append(Gate("ecr", (wires[e0], wires[e1]), (), g.tag))
            pend[c], pend[t] = post_c, post_t
        elif g.name == "ecr":
            for q in g.qubits:
                flush(q)
            out.append(Gate("ecr", g.qubits, (), g.tag))
        else:
            raise ValueError(f"to_native: unexpected gate {g.name}")
    for q in range(n):
        flush(q)
    res = Circuit(n, out, circ.name, circ.meta)
    from .passes import cancel
    return cancel(res)


def to_cx(circ: Circuit) -> Circuit:
    """{rz, sx, x, ecr} -> {rz, sx, x, cx} (the IBM-Eagle CX form used by
    GUOQ/QUESO and by synthesis tools).

    Every ECR becomes one CNOT (either orientation) wrapped in single-qubit
    Cliffords; the wrapping is chosen, as in :func:`to_native`, to minimise
    the native cost of the pending single-qubit runs.  Existing CNOTs are
    kept.  Exact (no approximation).
    """
    n = circ.n_qubits
    out: list[Gate] = []
    pend = [np.eye(2, dtype=complex) for _ in range(n)]

    def flush(q):
        out.extend(zsx_gates(pend[q], q))
        pend[q] = np.eye(2, dtype=complex)

    for g in circ.gates:
        if len(g.qubits) == 1:
            q = g.qubits[0]
            pend[q] = g.matrix() @ pend[q]
        elif g.name == "cx":
            for q in g.qubits:
                flush(q)
            out.append(g)
        elif g.name == "ecr":
            a, b = g.qubits
            best = None
            # CX(c,t) = (post_c x post_t) E (pre_c x pre_t)  =>
            # E = (post_c^+ x post_t^+) CX(c,t) (pre_c^+ x pre_t^+)
            for rev in (False, True):
                c, t = (a, b) if not rev else (b, a)
                cands, pc_list, pt_list, pc_idx, pt_idx = _candidate_tables(rev)
                cc = [zsx_cost(m.conj().T @ pend[c]) for m in pc_list]
                ct = [zsx_cost(m.conj().T @ pend[t]) for m in pt_list]
                for i in range(len(cands)):
                    cost = cc[pc_idx[i]] + ct[pt_idx[i]]
                    if best is None or cost < best[0]:
                        best = (cost, c, t, cands[i])
            _, c, t, (pre_c, pre_t, post_c, post_t, _w) = best
            out.extend(zsx_gates(pre_c.conj().T @ pend[c], c))
            out.extend(zsx_gates(pre_t.conj().T @ pend[t], t))
            out.append(Gate("cx", (c, t), (), g.tag))
            pend[c], pend[t] = post_c.conj().T, post_t.conj().T
        else:
            raise ValueError(f"to_cx: unexpected gate {g.name}")
    for q in range(n):
        flush(q)
    return Circuit(n, out, circ.name, circ.meta)


def respects_coupling(circ: Circuit, native: set) -> bool:
    """True iff every two-qubit gate acts on a pair coupled in ``native``."""
    pairs = {frozenset(e) for e in native}
    return all(frozenset(g.qubits) in pairs for g in circ.gates if len(g.qubits) == 2)


__all__ = ["ECR_MATRIX", "ecr_decompositions", "ecr_lowering", "cx_to_ecr", "zsx_gates", "to_native",
           "native_directions", "cx_ecr_candidates", "to_cx", "respects_coupling"]
