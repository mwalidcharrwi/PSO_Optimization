# Novel research directions for PSO-based quantum circuit optimisation

This document lists the research contributions that the proposed framework
makes possible.  Items marked **implemented** are part of HyPSO-QCO in this
repository (and can be switched off for ablation studies).  Items marked
**open** are directions the codebase is structured to support next.  Each
item states the hypothesis and how to evaluate it with `qcpso.bench.run`.

## A. Contributions implemented in HyPSO-QCO

| # | Contribution | Hypothesis | Evidence / ablation |
|---|---|---|---|
| A1 | **Equivalence-by-construction search space**: particles encode decisions of a sound optimisation program, not circuits | Removes fidelity penalties and makes PSO scale from ~5 to thousands of qubits×gates | every result is verified; runs on circuits with >1000 gates |
| A2 | **BFS-enumerated decomposition-variant library** (108 + 12 CCZ networks × polarity × T placement; 2-qubit gate orientations) | Joint choice of decompositions creates cancellations that greedy polarity choice misses | `hypso_novar` |
| A3 | **Free rotation placement** in path-sum phase folding | Moving merged phases out of CNOT sandwiches unlocks CNOT cancellations | `hypso_noplace` |
| A4 | **Pass-schedule genes** (phase-ordering) | Different pass orders reach different local optima | `hypso_nosched` |
| A5 | **Provenance-aligned genome** (semantic parity tags) | Keeps gene meaning stable across particles, so social learning transfers decisions correctly | compare with positional encoding (open A5b) |
| A6 | **Categorical PSO** for nominal decisions + hybrid SPSO/QPSO for continuous genes | Probability-vector dynamics fit nominal variables better than continuous relaxation | `hypso_relaxed`, `hypso_spso`, `hypso_qpso` |
| A7 | **Provenance-guided memetic search** (credit assignment from surviving gates, adjacent-site moves) | Concentrating moves on poorly optimised regions speeds up convergence | `hypso_unguided`, `hypso_nomemetic` |
| A8 | **Elitist seeding with the deterministic compiler** | Guarantees the result is never worse than greedy, so the swarm is a safe drop-in | `hypso_noseed` |
| A9 | **Hardware co-optimisation** (random-key layout + router hyper-parameters + nearest-neighbour Toffoli networks in one swarm) | Decomposition and layout interact; optimising them jointly lowers SWAP overhead | `--mode hardware` vs Qiskit/TKET and greedy SABRE |
| A10 | **Swarm instantiation** for 2-qubit block resynthesis (inner PSO + Levenberg–Marquardt with exact Jacobian) | A global swarm stage avoids local minima of pure gradient instantiation | `passes/kak.py` |
| A11 | **Two-timescale genome** (lazy placement genes refined only by local search) | Fine-grained genes should refine, not define, solutions | `hypso_eager` |
| A12 | **Adaptive operator selection** in the memetic search (probability matching) | Which neighbourhood pays off is circuit-family dependent | compare fixed move mix (git history) |

## B. Open directions (the next papers)

1. **Multi-objective PSO (MOPSO) with a Pareto archive.**  Optimise
   (CNOT, T, depth, estimated fidelity) at the same time with crowding-distance
   leaders.  *Evaluation:* hyper-volume against the single-objective runs.
   *Hook:* `pipeline.OBJECTIVES`; the engine already compares generic costs.
2. **Noise-aware objectives from calibration data.**  Replace uniform error
   rates in `fidelity_cost` with per-edge CNOT errors and T1/T2; add them to
   the hardware genome so the layout avoids bad couplers.
3. **Relative-phase Toffoli variants** (Maslov 2016) for compute–uncompute
   pairs.  The swarm decides which Toffoli pairs can use 4-T relative-phase
   versions.  This needs a matching analysis pass to stay sound.
4. **CNOT-network resynthesis passes** (Gray-synth / PMH / Steiner-Gauss)
   for {CNOT, Rz} regions, with the parity ordering and the Steiner-tree
   root choice as genes.  This is especially useful in hardware mode.
5. **3-qubit block resynthesis** (QSearch/LEAP-style) using the swarm
   instantiation of `passes/kak.py`, generalised to 3-qubit templates.  The
   CNOT structure would be a categorical gene.
6. **ZX-calculus rewrite scheduling**: expose the order and targets of local
   complementation / pivoting / phase-gadget fusion as genes, then extract
   with CNOT-aware heuristics.  This combines ZX-level T-count with low CNOT
   count.
7. **Surrogate-assisted PSO**: a GNN or gradient-boosted model trained
   online on (genome → cost) pairs pre-screens particles, cutting the number
   of full decodes for million-gate circuits.
8. **Windowed / incremental evaluation**: because the cost is roughly
   additive over regions, re-decode only the window affected by a changed
   site.  This would allow orders of magnitude more evaluations per second.
9. **Transfer and warm-starting** across circuit families: variant
   statistics learned on `gf2^4_mult` seed the probability vectors for
   `gf2^8_mult`.
10. **Island-model multi-swarm on HPC** with elite migration.  The
    process-pool evaluation already parallelises within a swarm.
11. **Fault-tolerant cost models**: T-depth, magic-state factory footprint
    and lattice-surgery routing as objectives in `cliffordt` mode.
12. **Dynamic circuits**: mid-circuit measurement and classical feed-forward
    (measurement-based uncomputation of Toffolis, Gidney 2018) as additional
    variants.
13. **Pulse-level co-optimisation**: genes for native-gate choice (CX vs ECR
    vs √iSWAP) and calibrated pulse-duration costs.
14. **Theory and landscape analysis**: fitness–distance correlation,
    neutrality and epistasis between adjacent sites.  This would explain why
    adjacent-site moves help and guide the choice of topology.
15. **Positional vs provenance encodings (A5b)**: a controlled study that
    replaces semantic tags with positional indices, quantifying the
    gene-meaning drift that provenance alignment removes.

## C. Suggested experimental protocol for the paper

* Benchmarks: the Nam et al. suite (`.qc`), RevLib (`.real`), QASMBench
  (`.qasm`), plus hardware runs on IBM Tokyo / heavy-hex devices.
* Baselines: greedy (the deterministic core), Qiskit O3, TKET
  FullPeepholeOptimise, PyZX, standard PSO (prior formulation), GA, SA and
  random search under the **same evaluation budget and decoder**.  The
  method of the reference paper can be added as another strategy in
  `qcpso/pso/baselines.py`.
* Report mean ± std over ≥ 5 seeds, per-circuit wins/ties/losses, one-sided
  Wilcoxon signed-rank tests and Friedman average ranks (produced
  automatically in `summary.md`), convergence curves (`convergence.json`)
  and the ablation table.
* Verify every output circuit (automatic for ≤ 20 logical / 22 physical
  qubits).
