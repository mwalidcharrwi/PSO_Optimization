# Results on `test_circuits_new` (IBM Eagle native circuits)

**Input.**  Ten circuits (`add_17`, `grover_10`, `heisenberg_8/32`, `hhl_8`,
`hubbard_8/18`, `mult_8`, `qae_17`, `qft_16`), already transpiled for a
127-qubit IBM device: gate set {rz, sx, x, ecr}, every ECR on a coupled pair
in its native direction.

**Task.**  Re-optimise without changing the mapping (mode `ibm`).  Outputs
use only {rz, sx, x, ecr}, and every ECR stays on an original coupled pair in
the input's native direction; this was checked for every saved circuit.

**Methods** (same objective: ECR count, then total gates, then depth).
* The inputs were transpiled by Qiskit at optimisation level 3, so the
  input column is the Qiskit O3 result; Qiskit O3 is not a separate
  baseline.
* *greedy*: the deterministic HyPSO-QCO pipeline with default decisions (no swarm).
* *standard PSO*: canonical gbest PSO over the same genome and decoder.
* *GA*, *SA*: genetic algorithm and simulated annealing over the same genome,
  decoder and budget (seeded like HyPSO).
* *HyPSO-QCO*: the proposed swarm.

**Budgets** (unique circuit evaluations per run).
* 300 evaluations, 3 seeds: `mult_8`, `heisenberg_8`, `add_17`, `qae_17`,
  `qft_16`, `hubbard_8`.
* 120 evaluations, 2 seeds: `hhl_8`.
* 40 evaluations, 1 seed: `heisenberg_32`.
* 16 evaluations, 1 seed: `grover_10`, `hubbard_18` (one decode takes
  2.5–9 minutes).
* Standard PSO, GA and SA were run on every circuit except `grover_10` and
  `hubbard_18`, which were skipped because of compute time.

**Verification.**  All 10 HyPSO-QCO outputs are verified equivalent to their
inputs.
* The 8 circuits with ≤ 20 active qubits use statevector simulation on the
  active qubits; every run of every method was checked.
* `heisenberg_32` and `hubbard_18` (31–32 active qubits) use a Choi-state
  MPS "alternating miter" (`qcpso/bench/mps_verify.py`), with no truncation:
  * `heisenberg_32`: |tr(U_in U_opt^†)|/2^n = 1 − 7e-15, peak bond 8, 42 s.
  * `hubbard_18`: 1 − 4.4e-11, peak bond 256, 18 min.

  As a sensitivity check, deleting one gate gives 2e-10, and changing one
  rotation by 1e-3 rad deviates by 1.3e-7, far above the observed values.
  Details are in `verification_large.json`.  QCEC did not finish within 2 h
  on these two circuits.

**Files.**
* `optimized/<circuit>_hypso.qasm`: the best HyPSO-QCO circuit per benchmark.
* `results.csv`: every run.
* `summary.md`: generic statistics.
* `parts/`: raw per-process outputs.

## Headline

* **Two-qubit gates:** HyPSO-QCO never uses more ECRs than the input (the
  Qiskit O3 transpilation), and uses strictly fewer on 9/10 circuits.  The
  largest saving is `hubbard_18`: 33,958 → 30,415 ECRs (−10.4 %).
* **Total native gates:** −15 % to −75 % vs. the input on every circuit
  (median about −24 %).  **Depth:** −15 % to −66 %.
* **Where the gain comes from** (`breakdown.json`,
  [docs/CONTRIBUTION_ASSESSMENT.md](../../docs/CONTRIBUTION_ASSESSMENT.md)):
  * the deterministic native re-synthesis alone gives a median −20 % of gates;
  * the swarm adds a median −3.1 % gates and −0.35 % ECRs on top of the full
    deterministic pipeline;
  * on 7/10 circuits the swarm is the only component that reduces the ECR
    count at all.
* **Search strategies** (same genome, decoder and budget; primary metric
  ECR, per-circuit means):
  * vs. SA: fewer or equal ECRs on 8/8 (6 wins, p = 0.016) and fewer gates
    on 8/8 (p = 0.004);
  * vs. GA: fewer or equal ECRs on 8/8 (4 wins, p = 0.06, not significant),
    but GA finds about 0.3 % fewer total gates on 7/8;
  * vs. standard PSO: fewer or equal ECRs on 7/8 (p = 0.14) and fewer gates
    on 7/8 (p = 0.07), neither significant at 3 seeds.

### Two-qubit (ECR) gate count (mean over seeds; best in bold)

| circuit | used qubits | input | greedy (no swarm) | standard PSO | GA | SA | HyPSO-QCO | HyPSO vs input |
|---|---|---|---|---|---|---|---|---|
| mult_8 | 8 | 311 | 311 | 309.7 | **309** | 310.3 | **309** | −0.64 % |
| heisenberg_8 | 8 | 420 | **420** | **420** | **420** | **420** | **420** | −0.00 % |
| add_17 | 17 | 499 | 499 | 494 | 497.3 | 497.3 | **493.7** | −1.07 % |
| qae_17 | 17 | 541 | 541 | **528.7** | 534.3 | 539.3 | 530 | −2.03 % |
| qft_16 | 16 | 614 | 614 | 607.7 | 609.3 | 613.7 | **606.7** | −1.19 % |
| hubbard_8 | 8 | 1344 | 1344 | 1338 | 1340.3 | 1342.3 | **1335.3** | −0.64 % |
| hhl_8 | 8 | 2377 | 2377 | 2377 | **2376** | 2377 | **2376** | −0.04 % |
| heisenberg_32 | 32 | 3942 | **3882** | **3882** | **3882** | **3882** | **3882** | −1.52 % |
| grover_10 | 10 | 16397 | 16397 | – | – | – | **16395** | −0.01 % |
| hubbard_18 | 31 | 33958 | 30431 | – | – | – | **30415** | −10.43 % |

### Total native gate count (mean over seeds; best in bold)

| circuit | used qubits | input | greedy (no swarm) | standard PSO | GA | SA | HyPSO-QCO | HyPSO vs input |
|---|---|---|---|---|---|---|---|---|
| mult_8 | 8 | 1898 | 1532 | 1452.7 | **1419.3** | 1463.7 | 1427.7 | −24.78 % |
| heisenberg_8 | 8 | 2127 | 1461 | 1348 | **1324.7** | 1371 | 1325.3 | −37.69 % |
| add_17 | 17 | 2812 | 2268 | 2211 | **2184.3** | 2217.7 | 2196 | −21.91 % |
| qae_17 | 17 | 3033 | 2467 | 2412 | **2393.3** | 2400.7 | 2398.7 | −20.91 % |
| qft_16 | 16 | 3444 | 2752 | 2701.3 | **2668** | 2698.3 | 2668.3 | −22.52 % |
| hubbard_8 | 8 | 8125 | 6144 | 5928 | **5904.7** | 6104.7 | 5956 | −26.70 % |
| hhl_8 | 8 | 18165 | 15670 | 15412 | **15392.5** | 15659.5 | 15401.5 | −15.21 % |
| heisenberg_32 | 32 | 58848 | 14855 | 14746 | 14765 | 14851 | **14740** | −74.95 % |
| grover_10 | 10 | 93235 | 73444 | – | – | – | **71485** | −23.33 % |
| hubbard_18 | 31 | 357535 | 140941 | – | – | – | **135134** | −62.20 % |

### Circuit depth (mean over seeds; best in bold)

| circuit | used qubits | input | greedy (no swarm) | standard PSO | GA | SA | HyPSO-QCO | HyPSO vs input |
|---|---|---|---|---|---|---|---|---|
| mult_8 | 8 | 1138 | 869 | 854.7 | **833.7** | 845.7 | 840.7 | −26.13 % |
| heisenberg_8 | 8 | 529 | 386 | 362 | **359** | 372.7 | 360.3 | −31.88 % |
| add_17 | 17 | 1003 | 745 | 734.3 | **722** | 733 | 730 | −27.22 % |
| qae_17 | 17 | 1066 | 792 | **770.3** | 777.3 | 779.7 | 777 | −27.11 % |
| qft_16 | 16 | 1009 | 727 | 719.7 | 717.3 | 725.3 | **716** | −29.04 % |
| hubbard_8 | 8 | 4400 | 3245 | 3169.3 | **3151** | 3238.7 | 3176 | −27.82 % |
| hhl_8 | 8 | 10641 | **8914** | 9017 | 9000 | 8920 | 9014.5 | −15.29 % |
| heisenberg_32 | 32 | 7143 | 2457 | 2428 | 2427 | 2451 | **2422** | −66.09 % |
| grover_10 | 10 | 43923 | **33578** | – | – | – | 34216 | −22.10 % |
| hubbard_18 | 31 | 136644 | 59671 | – | – | – | **57219** | −58.13 % |

### Runs, budgets and verification

| circuit | method | seeds | mean time (s) | equivalence |
|---|---|---|---|---|
| mult_8 | greedy (no swarm) | 1 | 1 | verified |
| mult_8 | standard PSO | 3 | 286 | verified |
| mult_8 | GA | 3 | 188 | verified |
| mult_8 | SA | 3 | 144 | verified |
| mult_8 | HyPSO-QCO | 3 | 305 | verified |
| heisenberg_8 | greedy (no swarm) | 1 | 1 | verified |
| heisenberg_8 | standard PSO | 3 | 421 | verified |
| heisenberg_8 | GA | 3 | 222 | verified |
| heisenberg_8 | SA | 3 | 201 | verified |
| heisenberg_8 | HyPSO-QCO | 3 | 373 | verified |
| add_17 | greedy (no swarm) | 1 | 1 | verified |
| add_17 | standard PSO | 3 | 813 | verified |
| add_17 | GA | 3 | 398 | verified |
| add_17 | SA | 3 | 294 | verified |
| add_17 | HyPSO-QCO | 3 | 636 | verified |
| qae_17 | greedy (no swarm) | 1 | 2 | verified |
| qae_17 | standard PSO | 3 | 624 | verified |
| qae_17 | GA | 3 | 492 | verified |
| qae_17 | SA | 3 | 261 | verified |
| qae_17 | HyPSO-QCO | 3 | 898 | verified |
| qft_16 | greedy (no swarm) | 1 | 2 | verified |
| qft_16 | standard PSO | 3 | 541 | verified |
| qft_16 | GA | 3 | 422 | verified |
| qft_16 | SA | 3 | 339 | verified |
| qft_16 | HyPSO-QCO | 3 | 745 | verified |
| hubbard_8 | greedy (no swarm) | 1 | 10 | verified |
| hubbard_8 | standard PSO | 3 | 1287 | verified |
| hubbard_8 | GA | 3 | 999 | verified |
| hubbard_8 | SA | 3 | 680 | verified |
| hubbard_8 | HyPSO-QCO | 3 | 1940 | verified |
| hhl_8 | greedy (no swarm) | 1 | 7 | verified |
| hhl_8 | standard PSO | 2 | 813 | verified |
| hhl_8 | GA | 2 | 779 | verified |
| hhl_8 | SA | 2 | 640 | verified |
| hhl_8 | HyPSO-QCO | 2 | 837 | verified |
| heisenberg_32 | greedy (no swarm) | 1 | 31 | unchecked |
| heisenberg_32 | standard PSO | 1 | 613 | unchecked |
| heisenberg_32 | GA | 1 | 621 | unchecked |
| heisenberg_32 | SA | 1 | 481 | unchecked |
| heisenberg_32 | HyPSO-QCO | 1 | 1320 | unchecked |
| grover_10 | greedy (no swarm) | 1 | 149 | verified |
| grover_10 | HyPSO-QCO | 1 | 2817 | verified |
| hubbard_18 | greedy (no swarm) | 1 | 549 | unchecked |
| hubbard_18 | HyPSO-QCO | 1 | 11219 | unchecked |

