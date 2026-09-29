# HyPSO-QCO v2 vs related work on the supplied benchmarks

Protocol and reproduction: [README.md](README.md).  Full generated
tables are in [REPORT_TABLES.md](REPORT_TABLES.md) (from
`python -m qcpso.bench.report_literature`).  They include the 1- and
5-minute GUOQ snapshots, depth, estimated success probability, runtimes
and the deviation of every output.

Setup:
* Every method optimises the same 10 IBM-Eagle-mapped circuits under the
  same contract:
  * equivalence on the same physical qubits;
  * two-qubit gates only on pairs already coupled in the input;
  * native ECR directions.
* The anytime optimisers (QUESO, GUOQ, HyPSO-QCO) get the same wall-clock
  budget: **15 minutes per circuit**, on the same 4-core machine.
* Qiskit and TKET run to completion.
* One seed per method and circuit.

## 1. Two-qubit (ECR) gate count, side by side

| circuit | input | Qiskit O3 | TKET† | QUESO | GUOQ | HyPSO-QCO v1 | **HyPSO-QCO v2** | v2 vs best other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 311 | 311 | 299 | 311 | 199 | 309 | **153** | −23.1 % (GUOQ) |
| heisenberg_8 | 420 | 420 | 420 | 420 | 326 | 420 | **276** | −15.3 % (GUOQ) |
| add_17 | 499 | 499 | 495 | 499 | 421 | 491 | **390** | −7.4 % (GUOQ) |
| qae_17 | 541 | 541 | 537 | 541 | 428 | 527 | **420** | −1.9 % (GUOQ) |
| qft_16 | 614 | 614 | 610 | 614 | 536 | 604 | **519** | −3.2 % (GUOQ) |
| hubbard_8 | 1,344 | 1,344 | 1,251 | 1,336 | 1,165 | 1,334 | **930** | −20.2 % (GUOQ) |
| hhl_8 | 2,377 | 2,377 | 2,365 | 2,377 | 500 | 2,375 | **337** | −32.6 % (GUOQ) |
| heisenberg_32 | 3,942 | 4,024‡ | 3,834 | 3,942 | 3,878 | 3,882 | **3,328** | −13.2 % (TKET) |
| grover_10 | 16,397 | 16,397 | 14,453 | 16,397 | 16,393 | 16,395 | **13,543** | −6.3 % (TKET) |
| hubbard_18 | 33,958 | 33,456‡ | 29,547 | 33,926 | 33,829 | 30,415 | **27,559** | −6.7 % (TKET) |
| **mean reduction vs input** | | −0.1 % | 4.1 % | 0.1 % | 20.2 % | 1.9 % | **31.3 %** | |

† TKET's connectivity-preserving passes (`FullPeepholeOptimise` would
couple uncoupled qubits).
‡ Qiskit needed an undirected coupling map for these two circuits.  Its
output has ECRs in non-native directions and relabels qubits, so it fails
the same-qubit equivalence check (Choi-MPS deviation 0.98 on
`heisenberg_32`).

HyPSO-QCO v2 has the fewest ECRs on **all 10 circuits**, against every
tool (10/0/0 each; one-sided Wilcoxon signed-rank p = 0.001, the minimum
for n = 10).

## 2. Total native gates and physical single-qubit gates

| circuit | total: TKET | QUESO | GUOQ | **v2** | physical 1q (sx+x): TKET | QUESO | GUOQ | **v2** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 1,402 | 1,337 | 1,170 | **808** | 511 | 469 | 413 | **291** |
| heisenberg_8 | 1,455 | **1,217** | 1,597 | 1,229 | 485 | **330** | 549 | 442 |
| add_17 | 2,203 | 2,108 | 1,980 | **1,662** | 806 | 766 | 682 | **606** |
| qae_17 | 2,368 | 2,301 | 2,057 | **1,860** | 873 | 836 | 706 | **686** |
| qft_16 | 2,651 | 2,691 | 2,568 | **2,144** | 969 | 999 | 891 | **768** |
| hubbard_8 | 5,174 | 6,204 | 4,972 | **3,898** | 1,889 | 2,320 | 1,747 | **1,373** |
| hhl_8 | 14,780 | 16,069 | 2,803 | **1,811** | 5,496 | 5,921 | 1,032 | **679** |
| heisenberg_32 | 14,100 | 14,544 | 14,700 | **12,657** | 5,142 | 5,305 | 5,375 | **4,547** |
| grover_10 | 57,497 | 74,687 | 73,279 | **48,187** | 20,737 | 28,182 | 27,236 | **14,932** |
| hubbard_18 | 112,902 | 131,273 | 131,025 | **105,965** | 41,731 | 48,653 | 48,581 | **38,453** |
| **mean reduction vs input** | 36.2 % | 33.7 % | 43.4 % | **55.6 %** | 30.5 % | 28.5 % | 39.5 % | **52.2 %** |

Qiskit O3 has 10.4 % fewer total gates on average; HyPSO-QCO v1 has 33.0 %.

* **Total gates:** HyPSO-QCO v2 has the fewest on 9 of 10 circuits.  On
  `heisenberg_8` QUESO has 12 fewer (1,217 vs 1,229), but keeps all 420
  ECRs (v2: 276).
* **Physical single-qubit gates:** fewest on 9 of 10 circuits.  QUESO has
  fewer on `heisenberg_8`.
* **Depth:** lowest on 9 of 10 circuits (QUESO: 302 vs 342 on
  `heisenberg_8`).

## 3. Compute-matched comparison (one resynthesis worker)

GUOQ's search is single-threaded.  HyPSO-QCO v2 normally resynthesises
blocks in 4 worker processes.  With **one** worker (same 15-minute budget,
the 7 circuits of up to 17 qubits):

| circuit | GUOQ: ECR / total | v2, 1 worker: ECR / total | v2, 4 workers: ECR / total |
|---|---|---|---|
| mult_8 | 199 / 1,170 | **164 / 865** | 153 / 808 |
| heisenberg_8 | 326 / 1,597 | **283 / 1,231** | 276 / 1,229 |
| add_17 | 421 / 1,980 | **407 / 1,792** | 390 / 1,662 |
| qae_17 | 428 / 2,057 | **427 / 2,027** | 420 / 1,860 |
| qft_16 | **536** / 2,568 | 541 / **2,296** | 519 / 2,144 |
| hubbard_8 | 1,165 / 4,972 | **968 / 4,065** | 930 / 3,898 |
| hhl_8 | 500 / 2,803 | **329 / 1,756** | 337 / 1,811 |

At matched compute, HyPSO-QCO v2:
* has **fewer ECRs than GUOQ on 6 of 7** circuits.  On `qft_16` GUOQ has
  5 fewer (536 vs 541), and on `qae_17` the margin is 1 ECR.
* has **fewer total gates on all 7**.

On six circuits, four workers reduce the ECR count by a further
1.6–6.7 %.  On `hhl_8` the 1-worker run is 2.4 % better (329 vs 337).

## 4. Ablation: what does the swarm phase contribute?

The configuration fixed before the runs ("v2") works as follows:
1. 25 % of the budget goes to the swarm phase.
2. The memetic phase then refines up to three distinct swarm elites.
3. Finally it deepens the best circuit with 4–5-qubit blocks.

The ablation "memetic only" instead evaluates just the strongest elite seed
(greedy ECR→CX conversion + TKET pass + greedy schedule).  It gives the
whole budget to the memetic phase.  Same 15-minute budget, 4 workers:

| circuit | v2 (swarm 25 % + memetic): ECR / total | memetic only: ECR / total |
|---|---|---|
| mult_8 | **153 / 808** | 156 / 818 |
| heisenberg_8 | 276 / 1,229 | **266 / 1,193** |
| add_17 | 390 / **1,662** | **389** / 1,677 |
| qae_17 | 420 / **1,860** | **413** / 1,890 |
| qft_16 | 519 / **2,144** | 519 / 2,202 |
| hubbard_8 | 930 / 3,898 | **915 / 3,646** |
| hhl_8 | 337 / 1,811 | **275 / 1,528** |
| mean ECR reduction vs input (7 circuits) | 37.3 % | **38.3 %** |

The three large circuits run without a swarm phase in both configurations
(large-circuit mode: one decode takes minutes).

**Honest reading.**  At a 15-minute budget the swarm phase does **not**
pay for its 25 % of the budget.
* In ECR count the memetic-only variant is better on 5 of 7 circuits,
  equal on 1 and worse on 1.  In total gates the two are split (4 / 3).
* The run logs show why: the last, *deepening* stage with 4–5-qubit blocks
  gives large late gains (for example `hhl_8` 315 → 270, `heisenberg_8`
  332 → 291).  With a swarm phase and three elites, this stage gets little
  time.
* The diversity of the swarm elites does matter in some cases (`mult_8`,
  and the spread between elites on `hhl_8`).  It matters less than extra
  resynthesis time.

Consequences:
1. The headline comparison (§1, §2) uses the configuration fixed before
   the runs.
2. The memetic-only configuration is even stronger against the related
   work, but it was selected after seeing these results.
3. The advantage over GUOQ, TKET, QUESO and Qiskit comes from the
   connectivity-preserving memetic resynthesis (contributions C9 and C10 in
   `docs/CONTRIBUTION_ASSESSMENT.md`), not from the particle swarm.
4. For already-mapped circuits at short budgets we recommend
   `--resynth-share 1.0` (memetic only).  In the other modes (`cliffordt`,
   `continuous`, `hardware`) the swarm remains the main search engine, as
   the earlier ablations show.

## 5. Verification

Every saved output was compared with its input by
`qcpso.bench.verify_literature` (all rows in
[verification.csv](verification.csv)):
* **Circuits with ≤ 20 used qubits:** random-state deviation with a shared
  global phase, simulated with Qiskit Aer.
* **`heisenberg_32` (32 used qubits):** exact Choi-state MPS miter.

| method | largest deviation over the checked outputs | class |
|---|---:|---|
| Qiskit O3 | 1.7e-10 | exact (but see ‡ above: the two fallback outputs fail the contract) |
| TKET | 3.5e-9 | numerically exact |
| QUESO | 3.8e-9 | numerically exact |
| GUOQ | **5.4e-6** (`qft_16`) | approximate on `qft_16`, otherwise ≤ 4.9e-7 |
| **HyPSO-QCO v2** (all configurations) | 5.7e-8 | numerically exact; `heisenberg_32`: 1.6e-10 |

**`hubbard_18`** (18 used qubits, but 105k–357k gates).  Its outputs are
larger than the statevector check handles.  HyPSO-QCO's output is verified
step by step, by the run-time checks below:
* every replaced block is checked exactly;
* every TKET block is checked by simulation (465 blocks, none rejected).

An end-to-end Choi-MPS check of the HyPSO-QCO output against the input is
running (`logs/mps_h18_final.log`).  The outputs of the other tools on
`hubbard_18` are not verified end to end.

**Safety nets.**  Two issues were found and fixed during this work (see
`superseded/README.md`):
1. **TKET's `SynthesiseTket` is not exact.**  Its single-qubit squashing
   dropped a small rotation (`rz(3.8e-4)`) after phase folding on
   `qae_17`.
2. **Unchecked decodes.**  An intermediate decode could therefore be
   inexact.  One ablation run inherited this (deviation 3.8e-4) and was
   caught by the final verification.

The final code:
* no longer uses `SynthesiseTket`;
* checks every TKET result by simulation;
* checks every replaced block and every accepted memetic round at run
  time.

**No step was rejected in the final runs.**  All HyPSO-QCO results in this
report come from the final code.

## 6. Where HyPSO-QCO v2 does *not* win, and caveats

* **Single-qubit counts on `heisenberg_8`.**  QUESO has fewer physical
  single-qubit gates (330 vs 442), total gates (1,217 vs 1,229) and depth.
  QUESO applies many single-qubit rewrite rules but removes no ECR.
* **Compute-matched `qft_16`.**  With one worker HyPSO-QCO has 5 more ECRs
  than GUOQ (541 vs 536).
* **Numerical exactness.**  The memetic phase and GUOQ use numerical
  synthesis.
  * HyPSO-QCO's outputs deviate by at most 5.7e-8.
  * GUOQ's 15-minute `qft_16` output deviates by 5.4e-6.
  * TKET, QUESO and Qiskit are exact up to rounding.
* **Budgets.**
  * All anytime tools had 15 minutes; GUOQ's paper uses 1 hour.  GUOQ was
    still improving on several circuits (`mult_8`: 275 → 231 → 199 at 1 /
    5 / 15 minutes).  Longer budgets may narrow the gap; this was not
    measured.
  * HyPSO-QCO overran the budget by up to 3.4 % on the large circuits: the
    deadline is checked between resynthesis blocks.
* **Seeds.**  One seed per method.  Re-running HyPSO-QCO after the code
  fixes changed its per-circuit ECR counts by −4 % to +4 %.  Every
  per-circuit margin over the best other tool is larger than that, except
  `qae_17` (1.9 %) and `qft_16` (3.2 %).
* **Other related work** could not be run under this contract.
  * **BQSKit O3:** did not finish `mult_8` within 35 minutes.
  * **PyZX and VOQC:** do not preserve connectivity.
  * **Quarl:** needs a trained GPU model.
  * **QALM, OAC and POPQC:** no public implementation for this gate set.
  * **Published numbers:** none exist for these exact files, so all tools
    were run here.
* **GUOQ modifications.**  GUOQ ran with a patch that makes its
  resynthesis connectivity-aware (`third_party/`).  Without it, GUOQ's
  output would not respect the device mapping.  The patch only restricts
  GUOQ.
