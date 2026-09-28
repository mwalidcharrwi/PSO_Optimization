# PSO_Optimization — HyPSO-QCO

**Hybrid, Provenance-aligned Particle Swarm Optimisation for Quantum Circuit
Optimisation.**

HyPSO-QCO optimises quantum circuits (gate count, CNOT count, T-count,
depth, estimated fidelity) with a particle swarm.  Unlike earlier PSO
approaches, it does not search over circuits. It searches the *decisions of
a semantics-preserving optimisation program*:

* which decomposition variant each Toffoli/CCZ/CZ/SWAP/CP/… uses, including
  108 BFS-enumerated minimal CCZ networks, T polarity and T placement;
* optionally, where each folded phase rotation is placed (free placement in
  path-sum phase folding; opt-in, see the ablation);
* the order of optimisation passes; and
* in hardware mode, the qubit layout and router hyper-parameters, chosen
  jointly with nearest-neighbour Toffoli networks.

Every particle therefore decodes to an **exactly equivalent** circuit
(equivalence by construction, additionally verified numerically).  This
lets PSO scale to circuits with thousands of gates.  The swarm combines
categorical PSO for nominal decisions, hybrid constriction/quantum-behaved
PSO for continuous genes, a provenance-aligned genome, elitist seeding with
the deterministic compiler, and a provenance-guided memetic local search.

**v2 (`ibm` mode, already-mapped hardware circuits)** adds a memetic phase
to the swarm.  The swarm's distinct elites are refined by
*connectivity-preserving numerical resynthesis*: convex 3–5-qubit blocks
lose CNOTs inside their own CNOT skeleton, so the device mapping cannot
change.  Single-qubit slots are sparsified to virtual Rz gates, and
partition strategies are chosen adaptively under a wall-clock budget.
On the supplied benchmarks, v2 beats GUOQ, QUESO, TKET and Qiskit on every
circuit (see below).

* Method: [docs/FRAMEWORK.md](docs/FRAMEWORK.md)
* Literature survey and research gaps: [docs/RELATED_WORK.md](docs/RELATED_WORK.md)
* Novel directions (implemented and open): [docs/RESEARCH_DIRECTIONS.md](docs/RESEARCH_DIRECTIONS.md)
* Benchmark results: [results/](results/)
* **Honest assessment of what the proposed approach contributes (and what it does not):**
  [docs/CONTRIBUTION_ASSESSMENT.md](docs/CONTRIBUTION_ASSESSMENT.md)

## Results on the built-in suites

These results cover the `cliffordt`, `continuous` and `hardware` modes,
which v2 does not change (its memetic phase is part of `ibm` mode only).
They use 3 seeds per search method.
Every output of the main experiments is verified equivalent to its input by
simulation.  Full tables, per-circuit numbers and the protocol are in
[results/](results/).

**Mean reduction vs. the lowered input, and average Friedman rank (lower is better)**

| mode (primary metric) | HyPSO-QCO | SA* | GA* | standard PSO* | Qiskit O3 | TKET | PyZX |
|---|---|---|---|---|---|---|---|
| Clifford+T, 18 circuits (total gates) | **35.1 %**, rank **2.11** | 35.0 %, 2.11 | 34.7 %, 2.67 | 33.3 %, 3.67 | 9.2 %, 7.28 | −5.6 %, 8.14 | −13.9 %, 8.58 |
| continuous {U3, CX}, 11 circuits (CNOTs) | **21.9 %**, rank **2.45** | 20.7 %, 3.00 | 21.1 %, 2.86 | 18.3 %, 4.36 | 2.2 %, 6.95 | 4.9 %, 5.86 | −48.4 %, 9.00 |
| IBM Tokyo, 8 circuits (CNOTs incl. routing) | 7.6 % below greedy, rank **2.00** | rank 2.38 | rank **2.00** | rank 7.38 | rank 5.50 | rank 6.88 | – |

\* same decoder, genome and evaluation budget as HyPSO-QCO (only the search strategy differs).

* **Versus Qiskit O3, TKET and PyZX, HyPSO-QCO wins on every Clifford+T
  circuit** (18/18 each; 28.8 %, 37.1 % and 41.8 % fewer gates on average;
  one-sided Wilcoxon p ≤ 1e-4).  In continuous mode it wins or ties on all
  circuits except QFT, where TKET saves 2 CNOTs.  On IBM Tokyo it uses 15.8 %
  fewer CNOTs than Qiskit O3 (7/8 wins, p = 0.008) and 19.9 % fewer than TKET
  (8/8, p = 0.004).
* **Versus the prior PSO formulation** (canonical gbest PSO on the same
  decoder): better on every circuit where they differ (p ≤ 0.004 in all
  three modes).
* **Versus GA and SA on the same decoder:** HyPSO-QCO has the best (or
  tied-best) average rank in every mode.  It is significantly better than GA
  in Clifford+T (p = 0.008) and continuous (p = 0.047) modes; the other
  differences to GA/SA are not significant at 3 seeds.
* T-counts match phase-folding optima (for example tof_10: 71, the value
  reported by Nam et al.).

**Ablation** ([results/ablation](results/ablation/summary.md), 6 Toffoli-heavy circuits):
removing decomposition-variant genes costs 20.9 % more gates (p = 0.016).
Replacing categorical PSO by a continuous relaxation costs 2.0 % (p = 0.016).
Enabling free rotation placement costs 1.6 % (p = 0.016), so it is opt-in.
Seeding, memetic search, pass-schedule genes, guidance and topology are
neutral at this budget (< 1 %, not significant).

## Results on the supplied benchmarks (`test_circuits_new`): comparison with related work

The ten supplied circuits are already transpiled for a 127-qubit IBM
device ({rz, sx, x, ecr}).  HyPSO-QCO **v2** (`ibm` mode) and the related
tools re-optimise them under one contract:
* equivalence on the same physical qubits;
* two-qubit gates only on pairs coupled in the input;
* native ECR directions.

The anytime tools each got a **15-minute budget per circuit** on the same
4-core machine.  Report: [results/ibm_literature/REPORT.md](results/ibm_literature/REPORT.md);
protocol: [results/ibm_literature/README.md](results/ibm_literature/README.md).

**ECR count** (fewer is better):

| circuit | input | Qiskit O3 | TKET† | QUESO | GUOQ | HyPSO-QCO v1 | **HyPSO-QCO v2** |
|---|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 311 | 311 | 299 | 311 | 199 | 309 | **157** |
| heisenberg_8 | 420 | 420 | 420 | 420 | 326 | 420 | **283** |
| add_17 | 499 | 499 | 495 | 499 | 421 | 491 | **389** |
| qae_17 | 541 | 541 | 537 | 541 | 428 | 527 | **413** |
| qft_16 | 614 | 614 | 610 | 614 | 536 | 604 | **511** |
| hubbard_8 | 1,344 | 1,344 | 1,251 | 1,336 | 1,165 | 1,334 | **935** |
| hhl_8 | 2,377 | 2,377 | 2,365 | 2,377 | 500 | 2,375 | **324** |
| heisenberg_32 | 3,942 | 4,024 | 3,834 | 3,942 | 3,878 | 3,882 | **3,465** |
| grover_10 | 16,397 | 16,397 | 14,453 | 16,397 | 16,393 | 16,395 | **13,530** |
| hubbard_18 | 33,958 | 33,456 | 29,547 | 33,926 | 33,829 | 30,415 | **28,232** |
| mean reduction | – | −0.1 % | 4.1 % | 0.1 % | 20.2 % | 1.9 % | **30.8 %** |

† TKET's connectivity-preserving passes.  GUOQ ran with coupling-aware
resynthesis (`third_party/`).  QUESO used its authors' settings.

* **ECRs:** HyPSO-QCO v2 has the fewest on every circuit, against every
  tool (10/0/0 each; one-sided Wilcoxon p = 0.001).
* **Total gates:** also the fewest on every circuit.  The mean reduction
  vs the input is 55.7 %, against 43.4 % for GUOQ and 36.2 % for TKET.
* **Physical single-qubit gates** (sx, x): fewest on 8 of 10 circuits.
  On `qae_17` it ties with GUOQ; on `heisenberg_8` QUESO has fewer
  (330 vs 425), though QUESO keeps all 420 ECRs.
* **Compute-matched run:** with one resynthesis worker, matching GUOQ's
  single search thread, it still has fewer ECRs than GUOQ on all 7 circuits
  of up to 17 qubits.
* **Verification:** outputs are exact or numerically exact.  The
  deviations from the inputs are 1e-10 to 4e-8, checked by simulation or
  a Choi-state MPS miter.

The v2 gains come mainly from the new **memetic phase**:
connectivity-preserving resynthesis of multi-qubit blocks by CNOT deletion,
applied to the swarm's elites (see
[docs/FRAMEWORK.md §7b](docs/FRAMEWORK.md)).  The swarm's share is
quantified by an ablation in the report and in
[docs/CONTRIBUTION_ASSESSMENT.md](docs/CONTRIBUTION_ASSESSMENT.md).

```bash
python -m qcpso optimize mapped.qasm -o out.qasm --mode ibm --time-limit 900 --resynth-workers 4
```

Results of v1 (no memetic phase) on the same circuits, with GA, SA and
standard PSO on the same decoder, are in
[results/ibm_testset/REPORT.md](results/ibm_testset/REPORT.md).

## Installation

```bash
pip install -r requirements.txt     # numpy, scipy (+ optional qiskit, pytket, pyzx, pytest)
python -m pytest -q tests           # 127 tests: lowering, pass soundness, I/O, routing, framework, resynthesis
```

## Quick start

```bash
# optimise one circuit (OpenQASM 2 / .qc / RevLib .real)
python -m qcpso optimize my_circuit.qasm -o my_circuit.opt.qasm --mode cliffordt --budget 1000
python -m qcpso optimize my_circuit.qasm --mode continuous --budget 1000       # {U3, CX}
python -m qcpso optimize my_circuit.qasm --mode hardware --device ibm_tokyo   # layout + routing

# benchmark a folder of circuits against all baselines, with statistics
python -m qcpso bench --suite path/to/benchmarks --mode cliffordt --seeds 5 --budget 1000 --out results/mine
```

```python
from qcpso.io import load
from qcpso.framework import optimize, HyPSOConfig
from qcpso.pso.engine import PSOParams

res = optimize(load("adder.qasm"), HyPSOConfig(mode="cliffordt", pso=PSOParams(max_evals=1000)))
print(res.summary())      # lowered -> greedy -> HyPSO metrics, equivalence check
```

Modes: `cliffordt` ({H, X, Rz, CNOT}; T-count reported), `continuous`
({U3, CNOT}), `hardware` (coupling maps `ibm_tokyo`, `ibm_qx5`,
`ibm_falcon27`, `line_N`, `ring_N`, `grid_RxC`, `full_N`), and `ibm`, which
re-optimises circuits already transpiled to IBM's native {rz, sx, x, ecr}
while keeping their qubit mapping and ECR directions.  Objectives:
`gates`, `cx`, `t`, `depth`, `fidelity`.

## Evaluating on your own benchmark circuits

Put the circuits (`.qasm`, `.qc` or `.real`; sub-folders are fine) into one
directory and run:

```bash
# Clifford+T gate set, total gate count (then CNOT, T, depth)
python -m qcpso bench --suite path/to/benchmarks --mode cliffordt --seeds 5 --budget 1000 --out results/bench_ct
# NISQ gate set {U3, CX}, CNOT count first
python -m qcpso bench --suite path/to/benchmarks --mode continuous --seeds 5 --budget 500 --out results/bench_cont
# device-constrained compilation
python -m qcpso bench --suite path/to/benchmarks --mode hardware --device ibm_tokyo --seeds 5 --budget 300 \
    --methods greedy,hypso,spso,ga,sa,rs,qiskit,tket --out results/bench_hw
```

Useful flags: `--objective {gates,cx,t,depth,fidelity}`, `--workers N`
(parallel evaluation), `--methods` (any subset of the baselines and
ablations below), `--no-verify` (skip simulation for very large circuits).
Terminal measurements are kept, barriers are dropped, and circuits with
mid-circuit measurement or classical control are rejected with an error.

## Baselines included

| baseline | what it is |
|---|---|
| `greedy` | the deterministic Nam-style optimiser that HyPSO-QCO wraps (default decisions) |
| `spso` | canonical global-best PSO (prior PSO formulation), same decoder and budget |
| `ga`, `sa`, `rs` | genetic algorithm, simulated annealing, random search over the same genome |
| `qiskit` | Qiskit `optimization_level=3` (strict equivalence: permutation elision disabled) |
| `tket` | TKET `FullPeepholeOptimise` (+ `DefaultMappingPass` in hardware mode) |
| `pyzx` | PyZX `full_reduce` + extraction + basic optimisation |
| `hypso_*` | ablations (no variants / schedule / memetic / guidance, with placement (lazy or eager), relaxed categorical, SPSO-only, QPSO-only, static gbest, unseeded) |

The benchmark runner writes `results.csv`, `summary.md` (per-circuit tables,
average reductions, wins/ties/losses, one-sided Wilcoxon signed-rank tests,
Friedman test with average ranks) and `convergence.json`.

## Repository layout

```
qcpso/
  circuit.py        IR with provenance tags, gate library
  io/               OpenQASM 2 (+3 via Qiskit), .qc, .real readers/writers
  sim.py            unitary / statevector equivalence checking
  decompose.py      lowering with decomposition variants (BFS CCZ networks, mcx with dirty ancillas)
  passes/           sound rewrites: cancellation, phase folding (free placement), H-reduction, KAK, fusion
  pipeline.py       pass library, clean-up fix point, cost models
  pso/engine.py     mixed categorical/continuous PSO (categorical PSO + SPSO/QPSO, memetic, restarts)
  pso/baselines.py  standard PSO, GA, SA, random search
  framework.py      HyPSO-QCO: genome <-> optimisation program, optimize()
  hardware/         coupling maps, SABRE router, layout genes, mapped verification, HW baselines
  bench/            generators, external baselines, benchmark runner with statistics
tests/              pytest suite
docs/               framework, related work, research directions
results/            benchmark outputs
```

## Note on the reference paper

The task referred to "the paper above", but no paper was attached, so the
framework is built from the open literature (see the survey).  When the
paper is available, its method can be added as another strategy in
`qcpso/pso/baselines.py` and compared under the same budget with
`python -m qcpso bench`.
