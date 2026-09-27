"""Global phase folding on the path-sum representation, with *free placement*.

Sweep the circuit keeping, for every wire, its value as an affine function
(bit-mask of path variables + constant bit).  CNOT/X/SWAP update the
functions linearly, diagonal gates leave them unchanged, and every other
gate (H, U3, ...) assigns a fresh path variable to the qubits it touches.
Each Rz(theta) contributes the amplitude factor exp(i theta (2 p - 1)/2) to
every path, where p is the affine function of its wire, so all Rz terms with
the same *linear* part can be merged into a single rotation (sign flipped
for constant 1) placed at **any** point where some wire carries that parity.
(The same argument justifies the classic "phase folding" of Amy, Maslov &
Mosca and the rotation merging of Nam et al.)

The *placement* of each merged (or single) rotation is a free design choice.
The standard choice is the first occurrence.  HyPSO-QCO lets the swarm pick
among all "availability points": the positions of the original rotations
and both ends of every interval during which some wire holds the parity.
A rotation that sits between two otherwise-cancelling CNOTs can thus be
moved out of the way.
"""
from __future__ import annotations

from typing import Callable

from ..circuit import Circuit, Gate, is_zero_angle, norm_angle

# gates that act as affine maps on computational basis values
_DIAGONAL = {"rz", "z", "s", "sdg", "t", "tdg", "p", "u1", "cz", "ccz", "cp", "cu1", "crz", "rzz", "mcz", "id"}
_RZ_LIKE = {"rz": None, "p": None, "u1": None}

# placement(tag_of_first_member) -> None (default) | float in [0, 1)
PlacementFn = Callable[[object], "float | None"]


def phase_fold(circ: Circuit, placement: PlacementFn | None = None) -> tuple[Circuit, bool]:
    n = circ.n_qubits
    gates = circ.gates
    m = len(gates)
    val = [1 << q for q in range(n)]
    const = [0] * n
    nxt = n
    track = placement is not None
    start = [0] * n
    intervals: dict[int, list] = {}
    groups: dict[int, list] = {}

    def close(q, end):
        if track:
            intervals.setdefault(val[q], []).append((start[q], end, q, const[q]))

    for i, g in enumerate(gates):
        nm = g.name
        if nm in _RZ_LIKE:
            q = g.qubits[0]
            groups.setdefault(val[q], []).append((i, q, const[q], g.params[0]))
        elif nm == "x":
            q = g.qubits[0]
            close(q, i)
            const[q] ^= 1
            start[q] = i + 1
        elif nm == "cx":
            c, t = g.qubits
            close(t, i)
            val[t] ^= val[c]
            const[t] ^= const[c]
            start[t] = i + 1
        elif nm == "swap":
            a, b = g.qubits
            close(a, i)
            close(b, i)
            val[a], val[b] = val[b], val[a]
            const[a], const[b] = const[b], const[a]
            start[a] = start[b] = i + 1
        elif nm in _DIAGONAL:
            continue
        else:
            for q in g.qubits:
                close(q, i)
                val[q] = 1 << nxt
                nxt += 1
                const[q] = 0
                start[q] = i + 1
    for q in range(n):
        close(q, m)

    remove: set[int] = set()
    replace: dict[int, Gate] = {}
    insert: dict[int, list] = {}
    changed = False
    for key, members in groups.items():
        if key == 0:  # wire holds a constant: rotation is a global phase
            for (i, *_rest) in members:
                remove.add(i)
            changed = True
            continue
        total = 0.0
        for (i, q, c, th) in members:
            total += -th if c else th
        total = norm_angle(total)
        first = members[0]
        u = placement(gates[first[0]].tag) if track else None
        if len(members) == 1 and (u is None or u < 0.5):
            if gates[first[0]].name != "rz":  # canonicalise p/u1 -> rz
                replace[first[0]] = Gate("rz", gates[first[0]].qubits, (first[3],), gates[first[0]].tag)
            continue
        for (i, *_rest) in members:
            remove.add(i)
        if is_zero_angle(total):
            changed = True
            continue
        tag = gates[first[0]].tag
        if u is None or u < 0.5:
            i, q, c, _ = first
            replace[i] = Gate("rz", (q,), (-total if c else total,), tag)
            remove.discard(i)
            changed = changed or len(members) > 1
            continue
        # enumerate availability points (sorted by position)
        opts = [(i, q, c, "m") for (i, q, c, _) in members]
        for (s, e, q, c) in intervals.get(key, ()):
            opts.append((s, q, c, "i"))
            opts.append((e, q, c, "i"))
        opts.sort(key=lambda o: (o[0], o[1]))
        k = min(int((u - 0.5) * 2.0 * len(opts)), len(opts) - 1)
        pos, q, c, kind = opts[k]
        ang = -total if c else total
        if kind == "m":
            replace[pos] = Gate("rz", (q,), (ang,), tag)
            remove.discard(pos)
        else:
            insert.setdefault(pos, []).append(Gate("rz", (q,), (ang,), tag))
        changed = True
    if not changed and not replace:
        return circ, False
    out: list[Gate] = []
    for i, g in enumerate(gates):
        if i in insert:
            out.extend(insert[i])
        if i in remove:
            continue
        out.append(replace.get(i, g))
    if m in insert:
        out.extend(insert[m])
    # only a reduction in size counts as progress (relocations are free moves)
    return Circuit(n, out, circ.name, circ.meta), len(out) < m
