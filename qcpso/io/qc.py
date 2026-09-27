""".qc reader (the format of the Feynman / Tpar tool-chains and of the
Nam-Ross-Su-Childs-Maslov benchmark suite).

Example::

    .v a b c d
    .i a b c
    BEGIN
    H d
    tof a b d
    T* a
    cnot a b
    END

Gate names are case-insensitive: ``H X Y Z S P S* P* T T* cnot tof``; a
multi-argument ``X``/``Z``/``Y``/``tof`` is a multi-controlled gate whose last
argument is the target.  Sub-circuit definitions (``BEGIN name(args)``) are
inlined.
"""
from __future__ import annotations

import os

from ..circuit import Circuit, Gate

_ONE = {"h": "h", "x": "x", "y": "y", "z": "z", "s": "s", "p": "s", "s*": "sdg", "p*": "sdg",
        "t": "t", "t*": "tdg"}


class QcError(ValueError):
    pass


def parse_qc(text: str, name: str = "") -> Circuit:
    variables: list[str] = []
    subs: dict[str, tuple[list[str], list[list[str]]]] = {}
    main: list[list[str]] | None = None
    cur_name, cur_args, cur_body = None, [], None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        toks = line.replace(",", " ").split()
        head = toks[0]
        if head == ".v":
            variables = toks[1:]
            continue
        if head.startswith("."):
            continue
        if head.upper() == "BEGIN":
            rest = line[len(head):].strip()
            if rest:
                sub = rest.replace("(", " ").replace(")", " ").replace(",", " ").split()
                cur_name, cur_args = sub[0], sub[1:]
            else:
                cur_name, cur_args = None, []
            cur_body = []
            continue
        if head.upper() == "END":
            if cur_name is None:
                main = cur_body
            else:
                subs[cur_name] = (cur_args, cur_body)
            cur_body = None
            continue
        if cur_body is None:
            raise QcError(f"statement outside BEGIN/END: {line!r}")
        cur_body.append(toks)
    if main is None:
        raise QcError("no main BEGIN/END block")
    index = {v: i for i, v in enumerate(variables)}
    gates: list[Gate] = []

    def emit(stmts, env):
        for toks in stmts:
            g, args = toks[0], [env.get(a, a) for a in toks[1:]]
            for a in args:
                if a not in index:
                    index[a] = len(index)
            qs = [index[a] for a in args]
            gl = g.lower()
            if g in subs:
                formal, body = subs[g]
                emit(body, dict(zip(formal, args)))
            elif gl in ("tof", "toffoli", "cnot", "cx") or (gl in ("x", "not") and len(qs) > 1):
                _mc(gates, "x", qs)
            elif gl == "z" and len(qs) > 1:
                _mc(gates, "z", qs)
            elif gl == "y" and len(qs) > 1:
                if len(qs) == 2:
                    gates.append(Gate("cy", qs))
                else:
                    raise QcError("multi-controlled Y is not supported")
            elif gl in ("zd",):
                _mc(gates, "z", qs)
            elif gl == "swap":
                gates.append(Gate("swap", qs))
            elif gl in _ONE:
                for q in qs:
                    gates.append(Gate(_ONE[gl], (q,)))
            else:
                raise QcError(f"unsupported .qc gate {g!r}")

    emit(main, {})
    return Circuit(len(index), gates, name=name, meta={"variables": variables})


def _mc(gates, kind, qs):
    k = len(qs) - 1
    if kind == "x":
        name = {0: "x", 1: "cx", 2: "ccx"}.get(k, "mcx")
    else:
        name = {0: "z", 1: "cz", 2: "ccz"}.get(k, "mcz")
    gates.append(Gate(name, qs))


def load_qc(path: str) -> Circuit:
    with open(path) as fh:
        return parse_qc(fh.read(), name=os.path.splitext(os.path.basename(path))[0])
