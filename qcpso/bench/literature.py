"""Related-work optimisers run on IBM-native circuits with a fixed mapping.

Every tool gets the same contract as HyPSO-QCO in ``ibm`` mode: the output
must be equivalent to the input on the same physical qubits (no relabelling,
no final permutation) and may use two-qubit gates only on the qubit pairs that
are already coupled in the input.

* **GUOQ** (Xu et al., ASPLOS'25): rewrite rules + BQSKit resynthesis in a
  random-walk search, IBM-Eagle gate set {rz, sx, x, cx}, objective TWO_Q
  (2q count, then total count), ``--preserve-mapping``.  GUOQ's resynthesis
  server synthesises blocks for all-to-all connectivity; it is run with a
  small patch (``--preserve_coupling``) that passes each block's coupling
  graph to BQSKit, so the output respects the mapping.
* **QUESO** (Xu et al., PLDI'23): the GUOQ binary with the flags recommended
  by its authors (``-opt TOTAL -search BEAM -temp 0 -q 8000 -resynth NONE``),
  plus ``--preserve-mapping``.
* **BQSKit** (Younis et al.): ``compile(optimization_level=3)`` with a
  :class:`MachineModel` whose coupling graph is the input's coupled pairs.
* **TKET** (Sivarajah et al.): connectivity-preserving pass sequence.

The tools that work in a {1q, CX} gate set receive the input converted exactly
by :func:`qcpso.native.to_cx`, and their outputs are converted back to
{rz, sx, x, ecr} (native ECR directions) with the same exact lowering
:func:`qcpso.native.to_native` that HyPSO-QCO uses, so that total gate counts
are comparable.  ECR counts equal the tools' CX counts.

GUOQ, QUESO and BQSKit use numerical synthesis (GUOQ/QUESO only for
resynthesis); their outputs are approximately equivalent (epsilon 1e-8).
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time

from ..circuit import Circuit, Gate
from ..io.qasm import parse_qasm, to_qasm
from ..native import native_directions, respects_coupling, to_cx, to_native

GUOQ_DIR = os.environ.get("GUOQ_DIR", "")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def compact(circ: Circuit):
    """Relabel the used qubits to 0..k-1 (returns circuit and the used list)."""
    used = sorted(circ.used_qubits())
    idx = {q: i for i, q in enumerate(used)}
    gates = [Gate(g.name, tuple(idx[q] for q in g.qubits), g.params) for g in circ.gates]
    return Circuit(max(1, len(used)), gates, circ.name), used


def expand(circ: Circuit, used, n: int) -> Circuit:
    gates = [Gate(g.name, tuple(used[q] for q in g.qubits), g.params) for g in circ.gates]
    return Circuit(n, gates, circ.name)


def back_to_native(small: Circuit, used, orig: Circuit) -> tuple[Circuit, bool]:
    """Tool output (compact, {1q, cx}) -> native ECR circuit on the device
    register; the flag says whether every 2q gate is on a coupled pair."""
    for g in small.gates:
        if len(g.qubits) > 2 or (len(g.qubits) == 2 and g.name != "cx"):
            raise ValueError(f"unexpected gate {g.name} in tool output")
    native = native_directions(orig)
    big = expand(small, used, orig.n_qubits)
    return to_native(big, native), respects_coupling(big, native)


def _qasm(circ: Circuit) -> str:
    return to_qasm(circ, clifford_t_names=False)


# --------------------------------------------------------------------------- #
# GUOQ / QUESO
# --------------------------------------------------------------------------- #
class ResynthServer:
    """GUOQ's BQSKit resynthesis server on its own port (context manager)."""

    def __init__(self, port: int, preserve_coupling: bool = True, log: str | None = None):
        self.port, self.preserve, self.log = port, preserve_coupling, log
        self.proc = None

    def __enter__(self):
        cmd = ["python", os.path.join(GUOQ_DIR, "resynth.py"), "--bqskit", "--bqskit_auto_workers",
               "--port", str(self.port)]
        if self.preserve:
            cmd.append("--preserve_coupling")
        fh = open(self.log, "w") if self.log else subprocess.DEVNULL
        self.proc = subprocess.Popen(cmd, cwd=GUOQ_DIR, stdout=fh, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        # wait until the port answers
        import socket
        for _ in range(240):
            try:
                with socket.create_connection(("localhost", self.port), timeout=1):
                    return self
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("resynthesis server did not start")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)


def run_guoq(circ: Circuit, workdir: str, time_limit: float = 3600.0, snapshots=(),
             variant: str = "guoq", port: int = 8080, seed: int = 0, heap: str | None = None) -> dict:
    """Run GUOQ (or QUESO) on a native circuit.

    Returns ``{t: (native circuit, respects_mapping)}`` for every snapshot
    time ``t`` (seconds) and for ``time_limit``.  GUOQ writes its best
    circuit continuously; the snapshots copy that file at the given times.
    """
    workdir = os.path.abspath(workdir)  # GUOQ runs with its own directory as cwd
    os.makedirs(workdir, exist_ok=True)
    small, used = compact(to_cx(circ))
    inp = os.path.join(workdir, "in.qasm")
    with open(inp, "w") as fh:
        fh.write(_qasm(small))
    outdir = os.path.join(workdir, "out")
    os.makedirs(outdir, exist_ok=True)
    jar = os.path.join(GUOQ_DIR, "target", "GUOQ-1.0-jar-with-dependencies.jar")
    heap = heap or os.environ.get("GUOQ_HEAP", "5g")
    cmd = ["java", f"-Xmx{heap}", "-cp", jar, "qoptimizer.Optimizer", "-g", "IBMN", "--preserve-mapping",
           "-out", outdir, "--seed", str(seed)]
    if variant == "guoq":
        cmd += ["-opt", "TWO_Q", "-resynth", "BQSKIT"]
    elif variant == "queso":
        cmd += ["-opt", "TOTAL", "-search", "BEAM", "-temp", "0", "-q", "8000", "-resynth", "NONE"]
    else:
        raise ValueError(variant)
    cmd.append(inp)
    env = dict(os.environ, GUOQ_RESYNTH_PORT=str(port))
    latest = os.path.join(outdir, "latest_sol__in.qasm")
    times = sorted(set(float(t) for t in snapshots if t < time_limit) | {float(time_limit)})
    log = open(os.path.join(workdir, "guoq.log"), "w")
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=GUOQ_DIR, env=env, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    saved = {}
    early = None
    try:
        for t in times:
            while time.time() - t0 < t and proc.poll() is None:
                time.sleep(1.0)
            dst = os.path.join(workdir, f"snap_{int(t)}.qasm")
            for _ in range(10):  # the file may be mid-write
                try:
                    src = latest if os.path.exists(latest) else inp
                    shutil.copy(src, dst)
                    parse_qasm(open(dst).read())
                    break
                except Exception:
                    time.sleep(0.5)
            saved[t] = dst
        early = proc.poll()
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        log.close()
    if early is not None and time.time() - t0 < 0.9 * time_limit:
        raise RuntimeError(f"GUOQ exited early (code {early}); see {os.path.join(workdir, 'guoq.log')}")
    res = {}
    for t, path in saved.items():
        out = parse_qasm(open(path).read())
        if out.n_qubits < small.n_qubits:
            out = Circuit(small.n_qubits, out.gates)
        res[t] = back_to_native(out, used, circ)
    return res


def load_snapshots(circ: Circuit, workdir: str, times) -> dict:
    """Rebuild :func:`run_guoq` results from the snapshot files of a finished run."""
    small, used = compact(to_cx(circ))
    res = {}
    for t in times:
        path = os.path.join(os.path.abspath(workdir), f"snap_{int(t)}.qasm")
        out = parse_qasm(open(path).read())
        if out.n_qubits < small.n_qubits:
            out = Circuit(small.n_qubits, out.gates)
        res[float(t)] = back_to_native(out, used, circ)
    return res


# --------------------------------------------------------------------------- #
# BQSKit
# --------------------------------------------------------------------------- #
def run_bqskit(circ: Circuit, level: int = 3, epsilon: float = 1e-8, seed: int = 0, workers: int | None = None):
    from bqskit import MachineModel, compile
    from bqskit.compiler import Compiler
    from bqskit.ir.lang.qasm2 import OPENQASM2Language
    native = native_directions(circ)
    small, used = compact(to_cx(circ))
    idx = {q: i for i, q in enumerate(used)}
    edges = sorted({tuple(sorted((idx[a], idx[b]))) for a, b in native})
    bc = OPENQASM2Language().decode(_qasm(small))
    model = MachineModel(small.n_qubits, coupling_graph=edges)
    t = time.time()
    with Compiler(num_workers=workers or -1) as compiler:
        out = compile(bc, model=model, optimization_level=level, synthesis_epsilon=epsilon,
                      compiler=compiler, seed=seed)
    dt = time.time() - t
    res = parse_qasm(out.to("qasm"))
    if res.n_qubits < small.n_qubits:
        res = Circuit(small.n_qubits, res.gates)
    nat, ok = back_to_native(res, used, circ)
    return nat, ok, dt


def run_bqskit_deletion(circ: Circuit, time_limit: float = 900.0, workers: int = 4, block_size: int = 3,
                        level: int = 1, epsilon: float = 1e-8, chunk: int = 3000, log=None,
                        max_block_size: int = 5):
    """BQSKit's deletion-only workflow (``build_gate_deletion_optimization_workflow``:
    partition into ``block_size``-qubit blocks, ``ScanningGateRemovalPass`` per
    block, unfold) under a wall-clock budget.

    Deleting gates can never couple a new qubit pair, so the output respects the
    mapping by construction.  Single-qubit runs are first fused into U3 gates, so
    that every remaining gate can be re-instantiated.  BQSKit has no time limit,
    so the circuit is processed in chunks of ``chunk`` gates on one compiler with
    ``workers`` workers; sweeps over all chunks repeat (with shifted chunk
    boundaries) while time is left.  When a sweep no longer lowers the gate count,
    the block size grows by one (up to ``max_block_size``), so that the whole
    budget is used; the run stops early only at a fixed point of the largest
    block size.  A chunk that is unfinished at the deadline is cancelled and kept
    unchanged.

    Returns ``(native circuit, respects_mapping, seconds, info)``."""
    from bqskit.compiler import Compiler
    from bqskit.compiler.compile import build_gate_deletion_optimization_workflow
    from bqskit.compiler.status import CompilationStatus
    from bqskit.ir.lang.qasm2 import OPENQASM2Language
    from ..pipeline import finish
    t0 = time.time()
    deadline = t0 + time_limit
    small, used = compact(finish(to_cx(circ), "continuous"))   # {u3, cx}, single-qubit runs fused
    workflow = build_gate_deletion_optimization_workflow(level, epsilon, block_size)
    lang = OPENQASM2Language()
    gates = list(small.gates)
    info = dict(sweeps=0, chunks_done=0, chunks_cancelled=0, cx_start=small.cx_count(), level=level,
                block_size=block_size, block_sizes=[block_size], fixed_point=False)

    def say(msg):
        if log:
            print(f"[bqskit-del {time.time() - t0:6.0f}s] {msg}", file=log, flush=True)

    with Compiler(num_workers=workers) as compiler:
        offset = 0
        while time.time() < deadline:
            before = (sum(1 for g in gates if g.name == "cx"), len(gates))
            out, cancelled = [], False
            bounds = list(range(0, len(gates), chunk))
            if offset and len(gates) > chunk:
                bounds = [0] + list(range(offset, len(gates), chunk))
            bounds.append(len(gates))
            for lo, hi in zip(bounds[:-1], bounds[1:]):
                part = gates[lo:hi]
                if cancelled or time.time() >= deadline or not part:
                    out.extend(part)
                    continue
                bc = lang.decode(_qasm(Circuit(small.n_qubits, part)))
                tid = compiler.submit(bc, workflow)
                while compiler.status(tid) != CompilationStatus.DONE:
                    if time.time() >= deadline:
                        compiler.cancel(tid)
                        cancelled = True
                        break
                    time.sleep(0.2)
                if cancelled:
                    info["chunks_cancelled"] += 1
                    out.extend(part)
                    continue
                res = parse_qasm(compiler.result(tid).to("qasm"))
                out.extend(finish(Circuit(small.n_qubits, res.gates), "continuous").gates)
                info["chunks_done"] += 1
            gates = out
            info["sweeps"] += 1
            after = (sum(1 for g in gates if g.name == "cx"), len(gates))
            say(f"sweep {info['sweeps']}: cx {before[0]} -> {after[0]}, gates {before[1]} -> {after[1]}"
                f" [block {block_size}]{' (deadline)' if cancelled else ''}")
            if cancelled:
                break
            if after >= before:   # fixed point at this block size: enlarge the blocks
                if block_size >= max_block_size:
                    info["fixed_point"] = True
                    break
                block_size += 1
                info["block_sizes"].append(block_size)
                workflow = build_gate_deletion_optimization_workflow(level, epsilon, block_size)
            offset = chunk // 2 if not offset else 0
    info["block_size"] = block_size
    dt = time.time() - t0
    nat, ok = back_to_native(Circuit(small.n_qubits, gates), used, circ)
    return nat, ok, dt, info


# --------------------------------------------------------------------------- #
# TKET (connectivity preserving)
# --------------------------------------------------------------------------- #
def run_tket_mp(circ: Circuit):
    """TKET passes that never introduce a new qubit interaction:
    ``SynthesiseTket`` / ``KAKDecomposition`` / ``CliffordSimp`` (no implicit
    swaps), iterated with ``RemoveRedundancies`` to a fixed point, then a
    rebase to {CX, U3}.  The output is checked for coupling anyway."""
    from pytket.circuit import OpType
    from pytket.passes import (AutoRebase, CliffordSimp, KAKDecomposition, RemoveRedundancies,
                               SequencePass, SynthesiseTket, RepeatWithMetricPass)
    from pytket.qasm import circuit_from_qasm_str, circuit_to_qasm_str
    small, used = compact(to_cx(circ))
    tk = circuit_from_qasm_str(_qasm(small))
    t = time.time()
    seq = SequencePass([SynthesiseTket(), KAKDecomposition(allow_swaps=False), CliffordSimp(allow_swaps=False),
                        SynthesiseTket(), RemoveRedundancies()])
    RepeatWithMetricPass(seq, lambda c: c.n_gates_of_type(OpType.CX) * 100000 + c.n_gates).apply(tk)
    AutoRebase({OpType.CX, OpType.U3}).apply(tk)
    RemoveRedundancies().apply(tk)
    dt = time.time() - t
    res = parse_qasm(circuit_to_qasm_str(tk, header="qelib1"))
    if res.n_qubits < small.n_qubits:
        res = Circuit(small.n_qubits, res.gates)
    nat, ok = back_to_native(res, used, circ)
    return nat, ok, dt
