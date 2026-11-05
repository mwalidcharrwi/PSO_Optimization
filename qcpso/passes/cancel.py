"""Commutation-aware gate cancellation and rotation merging.

For every gate we slide forward along its wire(s), skipping gates it
provably commutes with, until we hit its inverse (cancel both), a mergeable
rotation (merge) or a blocker.  Works on any gate set; it is most effective
on {h, x, rz, cx}.
"""
from __future__ import annotations

from ..circuit import Circuit, Gate, is_zero_angle, norm_angle
from .commutation import commute

_SELF_INV_1Q = {"h", "x", "y", "z"}
_ROT = {"rz", "rx", "ry", "p", "u1"}
_ROT_CANON = {"p": "rz", "u1": "rz"}  # equal up to global phase
_SELF_INV_2Q = {"cx", "cz", "swap", "cy", "ecr"}


def _wires(gates, n):
    wires = [[] for _ in range(n)]
    pos = {}
    for i, g in enumerate(gates):
        for q in g.qubits:
            pos[(i, q)] = len(wires[q])
            wires[q].append(i)
    return wires, pos


def _mergeable(a: Gate, b: Gate) -> bool:
    if a.qubits != b.qubits:
        return False
    na, nb = _ROT_CANON.get(a.name, a.name), _ROT_CANON.get(b.name, b.name)
    return na == nb and na in _ROT


def _is_inverse_pair(a: Gate, b: Gate) -> bool:
    if a.name != b.name:
        return False
    if a.name in _SELF_INV_1Q:
        return a.qubits == b.qubits
    if a.name in _SELF_INV_2Q:
        if a.name in ("cz", "swap"):
            return set(a.qubits) == set(b.qubits)
        return a.qubits == b.qubits
    if a.name in ("ccx", "ccz"):
        return a.qubits[-1] == b.qubits[-1] and set(a.qubits) == set(b.qubits) if a.name == "ccx" \
            else set(a.qubits) == set(b.qubits)
    return False


WINDOW = 256  # max. number of live gates skipped while sliding along a wire


def cancel_pass(circ: Circuit) -> tuple[Circuit, bool]:
    gates = list(circ.gates)
    m = len(gates)
    alive = [True] * m
    wires, pos = _wires(gates, circ.n_qubits)
    changed = False
    for i in range(m):
        if not alive[i]:
            continue
        g = gates[i]
        if len(g.qubits) == 1:
            q = g.qubits[0]
            wl = wires[q]
            seen = 0
            for p_ in range(pos[(i, q)] + 1, len(wl)):
                j = wl[p_]
                if not alive[j]:
                    continue
                seen += 1
                if seen > WINDOW:
                    break
                h = gates[j]
                if _is_inverse_pair(g, h):
                    alive[i] = alive[j] = False
                    changed = True
                    break
                if _mergeable(g, h):
                    ang = norm_angle(g.params[0] + h.params[0])
                    alive[i] = False
                    changed = True
                    if is_zero_angle(ang) and h.name in ("rz", "p", "u1"):
                        alive[j] = False
                    elif is_zero_angle(ang):
                        alive[j] = False
                    else:
                        gates[j] = Gate(_ROT_CANON.get(h.name, h.name), h.qubits, (ang,), h.tag)
                    break
                if commute(g, h):
                    continue
                break
        else:
            partner = None
            ok = True
            for q in g.qubits:
                wl = wires[q]
                found = None
                seen = 0
                for p_ in range(pos[(i, q)] + 1, len(wl)):
                    j = wl[p_]
                    if not alive[j]:
                        continue
                    seen += 1
                    if seen > WINDOW:
                        break
                    h = gates[j]
                    if _is_inverse_pair(g, h):
                        found = j
                        break
                    if commute(g, h):
                        continue
                    break
                if found is None or (partner is not None and partner != found):
                    ok = False
                    break
                partner = found
            if ok and partner is not None:
                alive[i] = alive[partner] = False
                changed = True
    if not changed:
        return circ, False
    return Circuit(circ.n_qubits, [g for g, a in zip(gates, alive) if a], circ.name, circ.meta), True


def cancel(circ: Circuit, max_iter: int = 50) -> Circuit:
    for _ in range(max_iter):
        circ, ch = cancel_pass(circ)
        if not ch:
            break
    return circ
