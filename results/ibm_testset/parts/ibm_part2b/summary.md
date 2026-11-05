Mode: `ibm`, budget: 300 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | spso | qiskit |
|---|---|---|---|---|---|---|
| qae_17 | 17 | 541 | 541 | 530 | **528.7** | 541 |
| qft_16 | 16 | 614 | 614 | **606.7** | 607.7 | 614 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| qae_17 | 3033 -> 2398.7 | 541 -> 530.0 | 38 -> 35.0 | 1066 -> 777.0 | 898.2 |
| qft_16 | 3444 -> 2668.3 | 614 -> 606.7 | 44 -> 30.0 | 1009 -> 716.0 | 744.6 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 19.38 | 0.00 | 15.91 | 26.83 | 1.91 |
| hypso | 21.72 | 1.61 | 19.86 | 28.07 | 821.39 |
| spso | 21.02 | 1.66 | 19.48 | 28.21 | 582.64 |
| qiskit | -1.74 | 0.00 | -13.40 | -1.45 | 6.06 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 2 | 0 | 0 | 1.61 | 0.25 |
| spso | 1 | 0 | 1 | -0.04 | 0.75 |
| qiskit | 2 | 0 | 0 | 1.61 | 0.25 |

## Friedman test and average ranks (lower is better)

Friedman: chi2 = 5.333, p = 0.149

| method | average rank |
|---|---|
| hypso | 1.50 |
| spso | 1.50 |
| greedy | 3.50 |
| qiskit | 3.50 |

Equivalence check: 16 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
