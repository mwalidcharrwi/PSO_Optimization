"""OpenQASM 2.0 reader / writer (self-contained, no Qiskit dependency).

Supported: ``qreg``/``creg``, ``include "qelib1.inc"`` (built in), user
``gate`` definitions (inlined), register broadcasting, parameter expressions
(``pi``, ``+ - * / ^``, ``sin cos tan exp ln sqrt``), ``barrier`` (dropped),
terminal ``measure`` (recorded in ``circuit.meta['measure']`` and re-emitted
by the writer) and ``reset`` on fresh qubits.
"""
from __future__ import annotations

import math
import os
import re
from fractions import Fraction

import numpy as np

from ..circuit import GATE_SPECS, Circuit, Gate, _SX, controlled, gate_matrix, norm_angle

# gates whose QASM name maps directly onto the IR
_DIRECT = {
    n for n in GATE_SPECS if n not in ("mcx", "mcz", "mcu", "unitary")
}
_ALIASES = {"U": "u3", "CX": "cx", "u0": "id", "cnot": "cx", "toffoli": "ccx", "fredkin": "cswap",
            "cphase": "cp"}

# qelib1 gates that are not IR primitives -> defined in QASM terms
_QELIB_EXTRA = """
gate rccx a,b,c { u2(0,pi) c; u1(pi/4) c; cx b,c; u1(-pi/4) c; cx a,c; u1(pi/4) c; cx b,c; u1(-pi/4) c; u2(0,pi) c; }
gate rc3x a,b,c,d { u2(0,pi) d; u1(pi/4) d; cx c,d; u1(-pi/4) d; u2(0,pi) d; cx a,d; u1(pi/4) d; cx b,d;
  u1(-pi/4) d; cx a,d; u1(pi/4) d; cx b,d; u1(-pi/4) d; u2(0,pi) d; u1(pi/4) d; cx c,d; u1(-pi/4) d; u2(0,pi) d; }
"""


class QasmError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# expression evaluation
# --------------------------------------------------------------------------- #
_TOKEN = re.compile(r"\s*(?:(\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)|([A-Za-z_][A-Za-z_0-9]*)|(\*\*|[-+*/^()]))")
_FUNCS = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp, "ln": math.log,
          "sqrt": math.sqrt, "asin": math.asin, "acos": math.acos, "atan": math.atan}


def eval_expr(text: str, env: dict | None = None) -> float:
    env = env or {}
    toks = []
    pos = 0
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise QasmError(f"bad expression: {text!r}")
        pos = m.end()
        num, ident, op = m.groups()
        if num is not None:
            toks.append(("n", float(num)))
        elif ident is not None:
            toks.append(("i", ident))
        else:
            toks.append(("o", "^" if op == "**" else op))
    toks.append(("e", None))
    i = 0

    def peek():
        return toks[i]

    def take():
        nonlocal i
        t = toks[i]
        i += 1
        return t

    def expr():
        v = term()
        while peek() in (("o", "+"), ("o", "-")):
            op = take()[1]
            r = term()
            v = v + r if op == "+" else v - r
        return v

    def term():
        v = unary()
        while peek() in (("o", "*"), ("o", "/")):
            op = take()[1]
            r = unary()
            v = v * r if op == "*" else v / r
        return v

    def unary():
        if peek() == ("o", "-"):
            take()
            return -unary()
        if peek() == ("o", "+"):
            take()
            return unary()
        return power()

    def power():
        b = atom()
        if peek() == ("o", "^"):
            take()
            return b ** unary()
        return b

    def atom():
        kind, val = take()
        if kind == "n":
            return val
        if kind == "i":
            if val == "pi":
                return math.pi
            if val in _FUNCS and peek() == ("o", "("):
                take()
                v = expr()
                if take() != ("o", ")"):
                    raise QasmError(f"missing ')' in {text!r}")
                return _FUNCS[val](v)
            if val in env:
                return env[val]
            raise QasmError(f"unknown identifier {val!r} in {text!r}")
        if (kind, val) == ("o", "("):
            v = expr()
            if take() != ("o", ")"):
                raise QasmError(f"missing ')' in {text!r}")
            return v
        raise QasmError(f"unexpected token {val!r} in {text!r}")

    v = expr()
    if peek()[0] != "e":
        raise QasmError(f"trailing tokens in {text!r}")
    return float(v)


def _split_top(s: str, sep: str = ",") -> list[str]:
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur))
    return [x.strip() for x in out]


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
class _GateDef:
    __slots__ = ("params", "args", "body")

    def __init__(self, params, args, body):
        self.params, self.args, self.body = params, args, body


_STMT_GATE_CALL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*)\s*(\((.*)\))?\s*(.*)$", re.S)


class _Parser:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir
        self.qregs: dict[str, tuple[int, int]] = {}
        self.cregs: dict[str, tuple[int, int]] = {}
        self.n_qubits = 0
        self.n_clbits = 0
        self.defs: dict[str, _GateDef] = {}
        self.gates: list[Gate] = []
        self.measures: list[tuple[int, int]] = []
        self.measured: set[int] = set()
        self.touched: set[int] = set()
        self.barriers = 0
        self.native_ok: set[str] = set()
        self.alias: dict[str, str] = {}

    # -------------------------------------------------------------- #
    def parse(self, text: str):
        text = re.sub(r"//[^\n]*", "", text)
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        i, n = 0, len(text)
        while i < n:
            while i < n and text[i].isspace():
                i += 1
            if i >= n:
                break
            if text.startswith("gate", i) and (i + 4 < n and text[i + 4].isspace()):
                j = text.index("{", i)
                k = self._match_brace(text, j)
                self._define(text[i + 4:j], text[j + 1:k])
                i = k + 1
                continue
            j = text.find(";", i)
            if j < 0:
                raise QasmError(f"missing ';' near: {text[i:i + 40]!r}")
            self._statement(text[i:j].strip())
            i = j + 1

    @staticmethod
    def _match_brace(text, j):
        depth = 0
        for k in range(j, len(text)):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    return k
        raise QasmError("unbalanced braces")

    def _define(self, header: str, body: str):
        header = header.strip()
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)\s*(?:\((.*?)\))?\s*(.*)$", header, re.S)
        if not m:
            raise QasmError(f"bad gate header {header!r}")
        name, params, args = m.group(1), m.group(2), m.group(3)
        params = [p.strip() for p in params.split(",")] if params and params.strip() else []
        args = [a.strip() for a in args.split(",") if a.strip()]
        stmts = [s.strip() for s in body.split(";") if s.strip()]
        self.defs[name] = _GateDef(params, args, stmts)
        self._maybe_native(name)

    def _maybe_native(self, name: str):
        """Use the IR primitive instead of inlining a user definition when the
        definition is equivalent (e.g. IBM files define ``ecr`` via two
        ``rzx``; inlining would cost 4 CNOTs instead of 1)."""
        spec = GATE_SPECS.get(name)
        d = self.defs[name]
        if spec is None and not d.params and len(d.args) == 2:
            # e.g. Qiskit exports ECR instances as `ecr_140451863465232`
            self._maybe_alias(name)
            return
        if spec is None or spec[0] is None or spec[0] != len(d.args) or spec[1] != len(d.params):
            return
        try:
            from ..sim import equal_up_to_phase, unitary
            vals = [0.3 + 0.7 * i for i in range(len(d.params))]
            sub = _Parser(self.base_dir)
            sub.defs = {k: v for k, v in self.defs.items() if k != name}
            sub.native_ok = set(self.native_ok)
            sub.qregs = {"q": (0, len(d.args))}
            sub.n_qubits = len(d.args)
            for st in d.body:
                sub._gate_call_inner(st, dict(zip(d.params, vals)), dict(zip(d.args, range(len(d.args)))))
            got = unitary(Circuit(len(d.args), sub.gates))
            want = gate_matrix(name, vals, len(d.args))
            if equal_up_to_phase(got, want, 1e-9):
                self.native_ok.add(name)
        except Exception:
            pass

    def _def_unitary(self, name, vals):
        from ..sim import unitary
        d = self.defs[name]
        sub = _Parser(self.base_dir)
        sub.defs = {k: v for k, v in self.defs.items() if k != name}
        sub.native_ok = set(self.native_ok)
        sub.alias = dict(self.alias)
        for st in d.body:
            sub._gate_call_inner(st, dict(zip(d.params, vals)), dict(zip(d.args, range(len(d.args)))))
        return unitary(Circuit(len(d.args), sub.gates))

    def _maybe_alias(self, name):
        try:
            from ..sim import equal_up_to_phase
            got = self._def_unitary(name, [])
            for native in ("ecr", "cx", "cz", "swap"):
                if equal_up_to_phase(got, gate_matrix(native, (), 2), 1e-9):
                    self.alias[name] = native
                    return
        except Exception:
            pass

    # -------------------------------------------------------------- #
    def _statement(self, st: str):
        if not st:
            return
        head = st.split(None, 1)[0]
        if head == "OPENQASM":
            ver = st.split()[1]
            if not ver.startswith("2"):
                raise QasmError("only OpenQASM 2.x is supported natively (use qcpso.io.load for QASM 3)")
            return
        if head == "include":
            fname = st.split(None, 1)[1].strip().strip('"')
            if fname == "qelib1.inc":
                self.parse(_QELIB_EXTRA)
                return
            path = os.path.join(self.base_dir or ".", fname)
            with open(path) as fh:
                self.parse(fh.read())
            return
        if head in ("qreg", "creg"):
            m = re.match(r"^(qreg|creg)\s+([A-Za-z_][A-Za-z_0-9]*)\s*\[\s*(\d+)\s*\]$", st)
            if not m:
                raise QasmError(f"bad register declaration {st!r}")
            kind, name, size = m.group(1), m.group(2), int(m.group(3))
            if kind == "qreg":
                self.qregs[name] = (self.n_qubits, size)
                self.n_qubits += size
            else:
                self.cregs[name] = (self.n_clbits, size)
                self.n_clbits += size
            return
        if head == "opaque":
            return
        if head == "barrier":
            self.barriers += 1
            return
        if head == "if":
            raise QasmError("classically-controlled operations are not supported")
        if head == "measure":
            m = re.match(r"^measure\s+(.+?)\s*->\s*(.+)$", st)
            if not m:
                raise QasmError(f"bad measure {st!r}")
            qs = self._resolve(m.group(1), self.qregs)
            cs = self._resolve(m.group(2), self.cregs)
            if len(qs) != len(cs):
                raise QasmError("measure register size mismatch")
            for q, c in zip(qs, cs):
                self.measures.append((q, c))
                self.measured.add(q)
            return
        if head == "reset":
            for q in self._resolve(st.split(None, 1)[1], self.qregs):
                if q in self.touched:
                    raise QasmError("mid-circuit reset is not supported")
            return
        self._gate_call(st, {}, None)

    def _resolve(self, arg: str, regs) -> list[int]:
        arg = arg.strip()
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)\s*(?:\[\s*(\d+)\s*\])?$", arg)
        if not m or m.group(1) not in regs:
            raise QasmError(f"unknown register reference {arg!r}")
        off, size = regs[m.group(1)]
        if m.group(2) is None:
            return list(range(off, off + size))
        idx = int(m.group(2))
        if idx >= size:
            raise QasmError(f"index out of range: {arg!r}")
        return [off + idx]

    def _gate_call(self, st: str, penv: dict, qenv: dict | None):
        m = _STMT_GATE_CALL.match(st)
        if not m:
            raise QasmError(f"cannot parse statement {st!r}")
        name = m.group(1)
        pexprs = _split_top(m.group(3)) if m.group(3) is not None and m.group(3).strip() else []
        params = [eval_expr(p, penv) for p in pexprs]
        argtxt = [a for a in _split_top(m.group(4)) if a]
        if qenv is not None:  # inside a gate body: arguments are formal names
            qubit_lists = [[qenv[a]] for a in argtxt]
        else:
            qubit_lists = [self._resolve(a, self.qregs) for a in argtxt]
        # broadcasting
        width = max((len(l) for l in qubit_lists), default=1)
        for l in qubit_lists:
            if len(l) not in (1, width):
                raise QasmError(f"register size mismatch in {st!r}")
        for b in range(width):
            qs = [l[0] if len(l) == 1 else l[b] for l in qubit_lists]
            self._emit(name, params, qs)

    def _emit(self, name: str, params: list, qs: list[int]):
        if name == "barrier":
            return
        if len(set(qs)) != len(qs):
            raise QasmError(f"repeated qubit in {name} {qs}")
        for q in qs:
            if q in self.measured:
                raise QasmError("gate after measurement (mid-circuit measurement) is not supported")
            self.touched.add(q)
        if name in self.alias:
            self.gates.append(Gate(self.alias[name], qs))
            return
        if name in self.defs and name not in self.native_ok:
            d = self.defs[name]
            if len(d.params) != len(params) or len(d.args) != len(qs):
                raise QasmError(f"wrong arity calling {name}")
            penv = dict(zip(d.params, params))
            qenv = dict(zip(d.args, qs))
            for st in d.body:
                if st.split(None, 1)[0] == "barrier":
                    continue
                self._gate_call_inner(st, penv, qenv)
            return
        name = _ALIASES.get(name, name)
        if name == "c3x":
            self.gates.append(Gate("mcx", qs))
            return
        if name == "c4x":
            self.gates.append(Gate("mcx", qs))
            return
        if name == "c3sqrtx":
            self.gates.append(Gate("mcu", qs, (_SX,)))
            return
        if name not in _DIRECT:
            raise QasmError(f"unsupported gate '{name}'")
        spec = GATE_SPECS[name]
        if spec[0] is not None and spec[0] != len(qs):
            raise QasmError(f"gate {name} expects {spec[0]} qubits")
        if spec[1] != len(params):
            raise QasmError(f"gate {name} expects {spec[1]} parameters")
        self.gates.append(Gate(name, qs, params))

    def _gate_call_inner(self, st, penv, qenv):
        m = _STMT_GATE_CALL.match(st)
        name = m.group(1)
        pexprs = _split_top(m.group(3)) if m.group(3) is not None and m.group(3).strip() else []
        params = [eval_expr(p, penv) for p in pexprs]
        qs = [qenv[a] for a in _split_top(m.group(4)) if a]
        self._emit(name, params, qs)


def parse_qasm(text: str, name: str = "", base_dir: str | None = None) -> Circuit:
    p = _Parser(base_dir)
    p.parse(text)
    meta = {"qregs": p.qregs, "cregs": p.cregs, "n_clbits": p.n_clbits, "measure": p.measures,
            "barriers": p.barriers}
    return Circuit(p.n_qubits, p.gates, name=name, meta=meta)


def load_qasm(path: str) -> Circuit:
    with open(path) as fh:
        text = fh.read()
    name = os.path.splitext(os.path.basename(path))[0]
    return parse_qasm(text, name=name, base_dir=os.path.dirname(os.path.abspath(path)))


# --------------------------------------------------------------------------- #
# writer
# --------------------------------------------------------------------------- #
def format_angle(theta: float) -> str:
    frac = Fraction(theta / math.pi).limit_denominator(64)
    if abs(float(frac) * math.pi - theta) < 1e-12:
        if frac == 0:
            return "0"
        num, den = frac.numerator, frac.denominator
        s = "-" if num < 0 else ""
        num = abs(num)
        core = "pi" if num == 1 else f"{num}*pi"
        return s + (core if den == 1 else f"{core}/{den}")
    return repr(float(theta))


_CLIFFORD_T_NAMES = {1: "t", 2: "s", 3: None, 4: "z", -1: "tdg", -2: "sdg", -3: None}


def to_qasm(circ: Circuit, clifford_t_names: bool = True) -> str:
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    names = {g.name for g in circ.gates}
    if names & {"rzx", "ecr"}:  # not in qelib1: emit the standard (Qiskit) definitions
        lines.append("gate rzx(param0) q0,q1 { h q1; cx q0,q1; rz(param0) q1; cx q0,q1; h q1; }")
    if "ecr" in names:
        lines.append("gate ecr q0,q1 { rzx(pi/4) q0,q1; x q0; rzx(-pi/4) q0,q1; }")
    lines.append(f"qreg q[{circ.n_qubits}];")
    meas = circ.meta.get("measure") or []
    n_cl = circ.meta.get("n_clbits", 0)
    if meas:
        lines.append(f"creg c[{max(n_cl, 1 + max(c for _, c in meas))}];")
    for g in circ.gates:
        qs = ",".join(f"q[{q}]" for q in g.qubits)
        name = g.name
        if name in ("rz", "p", "u1") and clifford_t_names:
            t = norm_angle(g.params[0])
            k = t / (math.pi / 4)
            if abs(k - round(k)) < 1e-9 and _CLIFFORD_T_NAMES.get(int(round(k))):
                if int(round(k)) == 0:
                    continue
                lines.append(f"{_CLIFFORD_T_NAMES[int(round(k))]} {qs};")
                continue
            if abs(t) < 1e-12:
                continue
        if name == "mcx":
            k = len(g.qubits) - 1
            if k == 1:
                name = "cx"
            elif k == 2:
                name = "ccx"
            elif k in (3, 4):
                name = f"c{k}x"
            else:
                raise QasmError("cannot write mcx with more than 4 controls; lower the circuit first")
        if name in ("unitary", "mcu", "mcz"):
            raise QasmError(f"cannot write '{name}' to QASM; lower the circuit first")
        if g.params:
            ps = ",".join(format_angle(p) for p in g.params)
            lines.append(f"{name}({ps}) {qs};")
        else:
            lines.append(f"{name} {qs};")
    for q, c in meas:
        lines.append(f"measure q[{q}] -> c[{c}];")
    return "\n".join(lines) + "\n"


def save_qasm(circ: Circuit, path: str, **kw) -> None:
    with open(path, "w") as fh:
        fh.write(to_qasm(circ, **kw))


def mcu_matrix(u: np.ndarray, n_qubits: int) -> np.ndarray:
    return controlled(np.asarray(u, dtype=complex), n_qubits - 1)
