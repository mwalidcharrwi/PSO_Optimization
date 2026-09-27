"""RevLib ``.real`` reader (reversible circuits: multiple-control Toffoli
``tN``, Fredkin ``fN``, controlled-V ``vN`` and controlled-V+ ``v+N``)."""
from __future__ import annotations

import os

import numpy as np

from ..circuit import Circuit, Gate, _SX


class RealError(ValueError):
    pass


def parse_real(text: str, name: str = "") -> Circuit:
    variables: list[str] = []
    gates: list[Gate] = []
    in_body = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        toks = line.split()
        head = toks[0].lower()
        if head == ".variables":
            variables = toks[1:]
            continue
        if head == ".begin":
            in_body = True
            continue
        if head == ".end":
            break
        if head.startswith("."):
            continue
        if not in_body:
            continue
        idx = {v: i for i, v in enumerate(variables)}
        try:
            qs = [idx[a] for a in toks[1:]]
        except KeyError as exc:
            raise RealError(f"unknown line {exc} in {line!r}") from exc
        kind = head.rstrip("0123456789")
        if kind == "t":
            k = len(qs) - 1
            gates.append(Gate({0: "x", 1: "cx", 2: "ccx"}.get(k, "mcx"), qs))
        elif kind == "f":
            *ctrl, a, b = qs
            if not ctrl:
                gates.append(Gate("swap", (a, b)))
            elif len(ctrl) == 1:
                gates.append(Gate("cswap", (ctrl[0], a, b)))
            else:  # multi-controlled swap = CX(b,a) C^k+1 X(ctrl+[a] -> b) CX(b,a)
                gates.append(Gate("cx", (b, a)))
                gates.append(Gate("mcx", tuple(ctrl) + (a, b)))
                gates.append(Gate("cx", (b, a)))
        elif kind in ("v", "v+"):
            u = _SX if kind == "v" else _SX.conj().T
            if len(qs) == 1:
                gates.append(Gate("sx" if kind == "v" else "sxdg", qs))
            elif len(qs) == 2 and kind == "v":
                gates.append(Gate("csx", qs))
            else:
                gates.append(Gate("mcu", qs, (np.array(u),)))
        else:
            raise RealError(f"unsupported .real gate {toks[0]!r}")
    return Circuit(len(variables), gates, name=name, meta={"variables": variables})


def load_real(path: str) -> Circuit:
    with open(path) as fh:
        return parse_real(fh.read(), name=os.path.splitext(os.path.basename(path))[0])
