# Honest assessment of the contribution of HyPSO-QCO

This document separates what is new from what is standard, what the
experiments show from what they do not, and which parts of the observed
improvements are actually due to particle swarm optimisation.  All numbers
come from the result files in `results/`.

## 1. What is new (method level)

Claims of novelty are relative to the literature reviewed in
[RELATED_WORK.md](RELATED_WORK.md).  An exhaustive novelty search was not
possible, so treat them as "not found in the reviewed work".

| # | Contribution | Status |
|---|---|---|
| C1 | **PSO over compilation decisions instead of over circuits.**  Each particle encodes decisions of a sound optimisation program, so every candidate is exactly equivalent to the input.  Prior PSO work encodes gates directly and relies on fidelity-based fitness, which limits it to a few qubits. | Implemented; scales to 357k-gate circuits; all outputs verified |
| C2 | **Decomposition-variant library as search variables**: all 108 minimal 6-CNOT and 12 nearest-neighbour 8-CNOT CCZ networks (BFS), T polarity and placement, 2-qubit gate orientations, and 16 exact ECR→CNOT Clifford lowerings | Implemented; **the largest measured effect of the swarm** (ablation below) |
| C3 | **Categorical (probability-vector) PSO** for nominal decisions, combined with SPSO/QPSO for continuous genes | Implemented; significant in the ablation |
| C4 | Provenance-aligned genes (semantic tags) and a provenance-guided memetic local search with adaptive operator selection | Implemented; **no measurable effect** at the tested budgets |
| C5 | Free placement of folded rotations (sound by a path-sum argument), as lazy genes | Implemented; **hurts at the tested budgets**, so it is opt-in |
| C6 | Hardware co-optimisation: random-key layout, router hyper-parameters and nearest-neighbour Toffoli networks in one swarm | Implemented; beats Qiskit/TKET, statistically tied with GA/SA |
| C7 | IBM-native re-synthesis: greedy choice among the 64 exact Clifford wrappings of each CNOT→ECR conversion, plus minimal {rz, sx, x} runs | Implemented; **deterministic, not PSO**; responsible for most of the gate reduction on the supplied benchmarks |
| C8 | Verification tooling: exact Choi-state MPS "alternating miter" for 30+ qubit circuits.  This is an MPS realisation of alternating equivalence checking, not a new idea in itself | Implemented; verified the two 31–32-qubit outputs where QCEC did not finish |

## 2. Where the improvements come from

### 2.1 Supplied benchmarks (`test_circuits_new`, IBM-native, fixed mapping)

Stage-by-stage analysis (`results/ibm_testset/breakdown.json`); S4 is the
HyPSO mean over seeds.

| circuit | ECR: input → S1 → S3 → S4 | gates: input → S1 → S3 → S4 |
|---|---|---|
| mult_8 | 311 → 311 → 311 → 309.0 | 1898 → 1546 → 1532 → 1427.7 |
| heisenberg_8 | 420 → 420 → 420 → 420.0 | 2127 → 1449 → 1461 → 1325.3 |
| add_17 | 499 → 499 → 499 → 493.7 | 2812 → 2275 → 2268 → 2196.0 |
| qae_17 | 541 → 541 → 541 → 530.0 | 3033 → 2466 → 2467 → 2398.7 |
| qft_16 | 614 → 614 → 614 → 606.7 | 3444 → 2741 → 2752 → 2668.3 |
| hubbard_8 | 1344 → 1344 → 1344 → 1335.3 | 8125 → 6222 → 6144 → 5956.0 |
| hhl_8 | 2377 → 2377 → 2377 → 2376.0 | 18165 → 16107 → 15670 → 15401.5 |
| heisenberg_32 | 3942 → 3942 → 3882 → 3882.0 | 58848 → 14540 → 14855 → 14740.0 |
| grover_10 | 16397 → 16397 → 16397 → 16395.0 | 93235 → 74623 → 73444 → 71485.0 |
| hubbard_18 | 33958 → 33926 → 30431 → 30415.0 | 357535 → 131273 → 140926 → 135134.0 |

Stages:
* S1: native re-synthesis only (C7).
* S2: plus rewrite passes (omitted from the table).
* S3: plus 2-qubit block resynthesis; this is the deterministic "greedy" pipeline.
* S4: plus the swarm.

* **Native re-synthesis (S1, deterministic, no PSO)** gives most of the
  total-gate reduction: median −20.2 % (−11 % to −75 %).
* **The deterministic ECR reductions** come only from 2-qubit block
  resynthesis, on the two Trotter circuits: `hubbard_18` −10.4 % and
  `heisenberg_32` −1.5 %.  On the other 8 circuits the deterministic
  pipeline does not change the ECR count at all.
* **The swarm (S3 → S4)** adds a further median **−3.1 % gates** (−0.8 % to
  −9.3 %) and a median **−0.35 % ECRs** (0 to −2.0 %).  It lowers the ECR
  count below the deterministic pipeline on 8 of 10 circuits, by 1–16 ECRs
  (means).  On 7 of them it is the only component that reduces the ECR
  count at all.
* The inputs contain a lot of removable single-qubit overhead: Qiskit O3
  itself removes 57–62 % of the gates of `heisenberg_32` and `hubbard_18`.
  The large percentage reductions therefore partly reflect the inputs.

### 2.2 Built-in suites (logical circuits; `results/cliffordt`, `continuous`, `hardware_tokyo`, `ablation`)

* Versus external optimisers: HyPSO-QCO beats Qiskit O3, TKET and PyZX on
  every Clifford+T circuit (18/18; 28.8 %, 37.1 % and 41.8 % fewer gates;
  p ≤ 1e-4).  In continuous mode it beats them on all but the two QFT
  circuits (TKET is better by 2 CNOTs).  On IBM Tokyo it uses 15.8 % fewer
  CNOTs than Qiskit and 19.9 % fewer than TKET.
* **Most of this advantage over external tools is again due to the
  decision space and the sound passes (C1, C2), not to PSO specifically.**
  The deterministic greedy pipeline alone already beats Qiskit, TKET and
  PyZX on most circuits.
* The ablation (6 Toffoli-heavy circuits, 600 evaluations, 3 seeds):
  * without decomposition-variant genes: −20.9 % worse (6/6, p = 0.016);
  * categorical PSO replaced by a continuous relaxation: −2.0 % worse (6/6, p = 0.016);
  * with placement genes: −1.6 % worse (6/6, p = 0.016), hence opt-in;
  * memetic search, schedule genes, provenance guidance, topology,
    SPSO/QPSO choice and elitist seeding: all within ±1 %, not significant.

## 3. Is PSO the right search strategy?  (same genome, decoder and budget)

| comparison | Clifford+T (18) | continuous (11) | IBM Tokyo (8) | supplied set |
|---|---|---|---|---|
| HyPSO vs standard PSO | better, p = 0.002 | better, p = 0.004 | better, p = 0.004 | trend (ECR p = 0.14, gates p = 0.07) |
| HyPSO vs GA | better, p = 0.008 | better, p = 0.047 | tie, p = 0.41 | ECR trend (p = 0.06); GA fewer gates |
| HyPSO vs SA | tie, p = 0.36 | tie (trend), p = 0.063 | tie, p = 0.20 | better (ECR p = 0.016, gates p = 0.004) |
| average rank of HyPSO | 1st (tied with SA) | 1st | 1st (tied with GA) | – |

Honest reading:
* The proposed swarm is **clearly and consistently better than the
  canonical PSO used by prior work**.  That is the main PSO-specific
  contribution, mostly through categorical PSO and elitist seeding.
* It is **at least as good as GA and SA on the primary metric** and ranks
  first or tied first everywhere.  But no single baseline is beaten
  significantly in every setting: SA ties on the built-in suites, GA ties
  on hardware and on the supplied set (where GA finds slightly fewer
  gates).  A strong claim that PSO beats all metaheuristics is not
  supported.  The robust claims are "better than canonical PSO" and
  "never significantly worse than GA/SA".

### 3.1 GA / SA on the supplied benchmarks

Per-circuit means (ECR / total gates); `grover_10` and `hubbard_18` were not
run with the baselines because of compute time.

| circuit | HyPSO-QCO | standard PSO | GA | SA |
|---|---|---|---|---|
| mult_8 | 309.0 / 1428 | 309.7 / 1453 | 309.0 / 1419 | 310.3 / 1464 |
| heisenberg_8 | 420.0 / 1325 | 420.0 / 1348 | 420.0 / 1325 | 420.0 / 1371 |
| add_17 | 493.7 / 2196 | 494.0 / 2211 | 497.3 / 2184 | 497.3 / 2218 |
| qae_17 | 530.0 / 2399 | 528.7 / 2412 | 534.3 / 2393 | 539.3 / 2401 |
| qft_16 | 606.7 / 2668 | 607.7 / 2701 | 609.3 / 2668 | 613.7 / 2698 |
| hubbard_8 | 1335.3 / 5956 | 1338.0 / 5928 | 1340.3 / 5905 | 1342.3 / 6105 |
| hhl_8 | 2376.0 / 15402 | 2377.0 / 15412 | 2376.0 / 15392 | 2377.0 / 15660 |
| heisenberg_32 | 3882 / 14740 | 3882 / 14746 | 3882 / 14765 | 3882 / 14851 |

| HyPSO vs | ECR (primary): W/T/L, one-sided Wilcoxon p | total gates: W/T/L, p |
|---|---|---|
| standard PSO | 5/2/1, p = 0.14 | 7/0/1, p = 0.074 |
| GA | 4/4/0, p = 0.063 | **1/0/7**, p = 0.95 (GA ≈ 0.3 % fewer gates) |
| SA | 6/2/0, **p = 0.016** | 8/0/0, **p = 0.004** |

On the supplied circuits HyPSO is never worse than GA or SA on the primary
metric and is significantly better than SA.  It is **not** significantly
better than GA or standard PSO at 3 seeds, and GA reaches slightly fewer
total gates.  The differences between the searches (≤ 2 %) are small
compared with the gain from the formulation itself (≈ 20 %).

## 4. Limitations and threats to validity

1. **No comparison with state-of-the-art superoptimisers** (GUOQ, Quarl,
   QUESO, Quartz, VOQC, BQSKit).  They may reach larger reductions.  All
   claims are relative to Qiskit, TKET and PyZX and to PSO/GA/SA/random
   search on the same decoder.
2. The built-in suites are programmatic reconstructions of standard
   families, not the original benchmark files (for example the Nam et al.
   `.qc` files).
3. Few seeds (3; 1–2 on the largest supplied circuits) and small budgets on
   the largest circuits (16–40 evaluations).
4. **Runtime.**  HyPSO-QCO needs minutes to hours (3.1 h for `hubbard_18`),
   versus seconds to minutes for Qiskit.  Most of the gain on the supplied
   circuits is available from the deterministic pipeline in seconds (S1/S3).
5. The paper referred to in the original task was never provided, so no
   comparison with its method is possible.
6. For `heisenberg_32` and `hubbard_18`, Qiskit O3 fails with the directed
   coupling map and was run with an undirected map, a relaxation in
   Qiskit's favour.
7. Two proposed components (C4 guidance, C5 placement) showed no benefit.
   They are kept for completeness, and placement is disabled by default.

## 5. Bottom line

The strongest, best-supported contribution is the **formulation**:
searching exactly-equivalent compilation decisions (C1), including a rich,
systematically enumerated decomposition-variant space (C2), with a PSO
adapted to nominal variables (C3).  This formulation scales to real,
hardware-compiled circuits and yields verified improvements over industrial
optimisers.  On the supplied IBM-native circuits, most of the gate reduction
comes from the deterministic native re-synthesis (C7).  The swarm
consistently adds a further few percent of gates.  On 7 of the 10 circuits
it is the only component that reduces the two-qubit gate count at all.
