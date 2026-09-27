# PSO_Optimization — HyPSO-QCO

**Hybrid, Provenance-aligned Particle Swarm Optimisation for Quantum Circuit
Optimisation.**

HyPSO-QCO optimises quantum circuits (gate count, CNOT count, T-count,
depth, estimated fidelity) with a particle swarm.  Unlike earlier PSO
approaches, it does not search over circuits. It searches the *decisions of
a semantics-preserving optimisation program*:

* which decomposition variant each Toffoli/CCZ/CZ/SWAP/CP/… uses, including
  108 BFS-enumerated minimal CCZ networks, T polarity and T placement;
* where each folded phase rotation is placed (free placement in path-sum
  phase folding);
* the order of optimisation passes; and
* in hardware mode, the qubit layout and router hyper-parameters, chosen
  jointly with nearest-neighbour Toffoli networks.

Every particle therefore decodes to an **exactly equivalent** circuit
(equivalence by construction, additionally verified numerically).  This
lets PSO scale to circuits with thousands of gates.  The swarm combines
categorical PSO for nominal decisions, hybrid constriction/quantum-behaved
PSO for continuous genes, a provenance-aligned genome, elitist seeding with
the deterministic compiler, and a provenance-guided memetic local search.

* Method: [docs/FRAMEWORK.md](docs/FRAMEWORK.md)
* Literature survey and research gaps: [docs/RELATED_WORK.md](docs/RELATED_WORK.md)
* Novel directions (implemented and open): [docs/RESEARCH_DIRECTIONS.md](docs/RESEARCH_DIRECTIONS.md)
* Benchmark results: [results/](results/)

## Installation

```bash
pip install -r requirements.txt     # numpy, scipy (+ optional qiskit, pytket, pyzx, pytest)
python -m pytest -q tests           # 100 tests: lowering, pass soundness, I/O, routing, framework
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
`ibm_falcon27`, `line_N`, `ring_N`, `grid_RxC`, `full_N`).  Objectives:
`gates`, `cx`, `t`, `depth`, `fidelity`.

## Baselines included

| baseline | what it is |
|---|---|
| `greedy` | the deterministic Nam-style optimiser that HyPSO-QCO wraps (default decisions) |
| `spso` | canonical global-best PSO (prior PSO formulation), same decoder and budget |
| `ga`, `sa`, `rs` | genetic algorithm, simulated annealing, random search over the same genome |
| `qiskit` | Qiskit `optimization_level=3` (strict equivalence: permutation elision disabled) |
| `tket` | TKET `FullPeepholeOptimise` (+ `DefaultMappingPass` in hardware mode) |
| `pyzx` | PyZX `full_reduce` + extraction + basic optimisation |
| `hypso_*` | ablations (no variants / placement / schedule / memetic / guidance, relaxed categorical, SPSO-only, QPSO-only, static gbest, unseeded) |

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
