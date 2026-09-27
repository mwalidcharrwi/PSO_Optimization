# Results on `test_circuits_new` (IBM Eagle native circuits)

**Input.**  Ten circuits (`add_17`, `grover_10`, `heisenberg_8/32`, `hhl_8`,
`hubbard_8/18`, `mult_8`, `qae_17`, `qft_16`), already transpiled for a
127-qubit IBM device: gate set {rz, sx, x, ecr}, every ECR on a coupled pair
in its native direction.

**Task.**  Re-optimise without changing the mapping (mode `ibm`).  Outputs
use only {rz, sx, x, ecr}, and every ECR stays on an original coupled pair in
the input's native direction; this was checked for every saved circuit.

**Methods** (same objective: ECR count, then total gates, then depth).
* *Qiskit O3*: `optimization_level=3` with basis {rz, sx, x, ecr}, the input's
  directed coupling map and a trivial layout.  For `heisenberg_32` and
  `hubbard_18` Qiskit raised a TranspilerError (it creates an ECR in the
  non-native direction and cannot flip it).  It was re-run with an
  undirected coupling map, a relaxation in Qiskit's favour.
* *greedy*: the deterministic HyPSO-QCO pipeline with default decisions (no swarm).
* *standard PSO*: canonical gbest PSO over the same genome and decoder.
* *HyPSO-QCO*: the proposed swarm.

**Budgets** (unique circuit evaluations per run).
* 300 evaluations, 3 seeds: `mult_8`, `heisenberg_8`, `add_17`, `qae_17`,
  `qft_16`, `hubbard_8`.
* 120 evaluations, 2 seeds: `hhl_8`.
* 40 evaluations, 1 seed: `heisenberg_32`.
* 16 evaluations, 1 seed: `grover_10`, `hubbard_18` (one decode takes
  2.5–9 minutes).
* Standard PSO was not run on the three largest circuits because of compute
  time.

**Verification.**  Every output of the 8 circuits with ≤ 20 active qubits is
verified equivalent to its input by statevector simulation on the active
qubits.  `heisenberg_32` and `hubbard_18` (31–32 active qubits) are too
large for simulation here, and QCEC did not finish within 2 h, so they are
*not formally verified*.  They were produced by the same sound passes that
are verified on the other 8 circuits and in the test suite.

**Files.**
* `optimized/<circuit>_hypso.qasm`: the best HyPSO-QCO circuit per benchmark.
* `results.csv`: every run.
* `summary.md`: generic statistics.
* `parts/`: raw per-process outputs.

## Headline

* **Two-qubit gates:** HyPSO-QCO never uses more ECRs than the input or
  Qiskit O3, and uses strictly fewer on 9/10 circuits.  The largest saving is
  `hubbard_18`: 33,958 → 30,415 ECRs (−10.4 %), where Qiskit O3 reaches
  33,456.
* **Total native gates:** −15 % to −75 % vs. the input on every circuit
  (median about −24 %).  Qiskit O3 re-optimisation changes the inputs by
  −62 % to +5 %.
* **Depth:** −15 % to −66 % vs. the input.
* **Swarm vs. no swarm:** HyPSO-QCO improves on its own deterministic
  pipeline (greedy) on every circuit in ECR count or total gates.
* **Versus standard PSO** on the 7 circuits where both ran: fewer or equal
  ECRs on 6/7 (`qae_17`: 530 vs 528.7 is the exception) and fewer total
  gates on 6/7 (`hubbard_8`: 5,956 vs 5,928 is the exception).

### Two-qubit (ECR) gate count (mean over seeds; best in bold)

| circuit | used qubits | input | Qiskit O3 | greedy (no swarm) | standard PSO | HyPSO-QCO | HyPSO vs input |
|---|---|---|---|---|---|---|---|
| mult_8 | 8 | 311 | 311 | 311 | 309.7 | **309** | −0.64 % |
| heisenberg_8 | 8 | 420 | **420** | **420** | **420** | **420** | −0.00 % |
| add_17 | 17 | 499 | 499 | 499 | 494 | **493.7** | −1.07 % |
| qae_17 | 17 | 541 | 541 | 541 | **528.7** | 530 | −2.03 % |
| qft_16 | 16 | 614 | 614 | 614 | 607.7 | **606.7** | −1.19 % |
| hubbard_8 | 8 | 1344 | 1344 | 1344 | 1338 | **1335.3** | −0.64 % |
| hhl_8 | 8 | 2377 | 2377 | 2377 | 2377 | **2376** | −0.04 % |
| heisenberg_32 | 32 | 3942 | 4024 | **3882** | – | **3882** | −1.52 % |
| grover_10 | 10 | 16397 | 16397 | 16397 | – | **16395** | −0.01 % |
| hubbard_18 | 31 | 33958 | 33456 | 30431 | – | **30415** | −10.43 % |

### Total native gate count (mean over seeds; best in bold)

| circuit | used qubits | input | Qiskit O3 | greedy (no swarm) | standard PSO | HyPSO-QCO | HyPSO vs input |
|---|---|---|---|---|---|---|---|
| mult_8 | 8 | 1898 | 1958 | 1532 | 1452.7 | **1427.7** | −24.78 % |
| heisenberg_8 | 8 | 2127 | 2127 | 1461 | 1348 | **1325.3** | −37.69 % |
| add_17 | 17 | 2812 | 2916 | 2268 | 2211 | **2196** | −21.91 % |
| qae_17 | 17 | 3033 | 3085 | 2467 | 2412 | **2398.7** | −20.91 % |
| qft_16 | 16 | 3444 | 3505 | 2752 | 2701.3 | **2668.3** | −22.52 % |
| hubbard_8 | 8 | 8125 | 8070 | 6144 | **5928** | 5956 | −26.70 % |
| hhl_8 | 8 | 18165 | 19083 | 15670 | 15412 | **15401.5** | −15.21 % |
| heisenberg_32 | 32 | 58848 | 22592 | 14855 | – | **14740** | −74.95 % |
| grover_10 | 10 | 93235 | 93315 | 73444 | – | **71485** | −23.33 % |
| hubbard_18 | 31 | 357535 | 153652 | 140941 | – | **135134** | −62.20 % |

### Circuit depth (mean over seeds; best in bold)

| circuit | used qubits | input | Qiskit O3 | greedy (no swarm) | standard PSO | HyPSO-QCO | HyPSO vs input |
|---|---|---|---|---|---|---|---|
| mult_8 | 8 | 1138 | 1173 | 869 | 854.7 | **840.7** | −26.13 % |
| heisenberg_8 | 8 | 529 | 529 | 386 | 362 | **360.3** | −31.88 % |
| add_17 | 17 | 1003 | 1026 | 745 | 734.3 | **730** | −27.22 % |
| qae_17 | 17 | 1066 | 1080 | 792 | **770.3** | 777 | −27.11 % |
| qft_16 | 16 | 1009 | 1025 | 727 | 719.7 | **716** | −29.04 % |
| hubbard_8 | 8 | 4400 | 4388 | 3245 | **3169.3** | 3176 | −27.82 % |
| hhl_8 | 8 | 10641 | 11175 | **8914** | 9017 | 9014.5 | −15.29 % |
| heisenberg_32 | 32 | 7143 | 3430 | 2457 | – | **2422** | −66.09 % |
| grover_10 | 10 | 43923 | 44073 | **33578** | – | 34216 | −22.10 % |
| hubbard_18 | 31 | 136644 | 64708 | 59671 | – | **57219** | −58.13 % |

### Runs, budgets and verification

| circuit | method | seeds | mean time (s) | equivalence |
|---|---|---|---|---|
| mult_8 | Qiskit O3 | 1 | 3 | verified |
| mult_8 | greedy (no swarm) | 1 | 1 | verified |
| mult_8 | standard PSO | 3 | 286 | verified |
| mult_8 | HyPSO-QCO | 3 | 305 | verified |
| heisenberg_8 | Qiskit O3 | 1 | 5 | verified |
| heisenberg_8 | greedy (no swarm) | 1 | 1 | verified |
| heisenberg_8 | standard PSO | 3 | 421 | verified |
| heisenberg_8 | HyPSO-QCO | 3 | 373 | verified |
| add_17 | Qiskit O3 | 1 | 6 | verified |
| add_17 | greedy (no swarm) | 1 | 1 | verified |
| add_17 | standard PSO | 3 | 813 | verified |
| add_17 | HyPSO-QCO | 3 | 636 | verified |
| qae_17 | Qiskit O3 | 1 | 6 | verified |
| qae_17 | greedy (no swarm) | 1 | 2 | verified |
| qae_17 | standard PSO | 3 | 624 | verified |
| qae_17 | HyPSO-QCO | 3 | 898 | verified |
| qft_16 | Qiskit O3 | 1 | 6 | verified |
| qft_16 | greedy (no swarm) | 1 | 2 | verified |
| qft_16 | standard PSO | 3 | 541 | verified |
| qft_16 | HyPSO-QCO | 3 | 745 | verified |
| hubbard_8 | Qiskit O3 | 1 | 11 | verified |
| hubbard_8 | greedy (no swarm) | 1 | 10 | verified |
| hubbard_8 | standard PSO | 3 | 1287 | verified |
| hubbard_8 | HyPSO-QCO | 3 | 1940 | verified |
| hhl_8 | Qiskit O3 | 1 | 20 | verified |
| hhl_8 | greedy (no swarm) | 1 | 7 | verified |
| hhl_8 | standard PSO | 2 | 813 | verified |
| hhl_8 | HyPSO-QCO | 2 | 837 | verified |
| heisenberg_32 | Qiskit O3 | 1 | 30 | unchecked |
| heisenberg_32 | greedy (no swarm) | 1 | 31 | unchecked |
| heisenberg_32 | HyPSO-QCO | 1 | 1320 | unchecked |
| grover_10 | Qiskit O3 | 1 | 257 | verified |
| grover_10 | greedy (no swarm) | 1 | 149 | verified |
| grover_10 | HyPSO-QCO | 1 | 2817 | verified |
| hubbard_18 | Qiskit O3 | 1 | 283 | unchecked |
| hubbard_18 | greedy (no swarm) | 1 | 549 | unchecked |
| hubbard_18 | HyPSO-QCO | 1 | 11219 | unchecked |
