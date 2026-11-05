Mode: `ibm`, budget: 300 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | spso | qiskit |
|---|---|---|---|---|---|---|
| add_17 | 17 | 499 | 499 | **493.7** | 494 | 499 |
| heisenberg_8 | 8 | 420 | **420** | **420** | **420** | **420** |
| mult_8 | 8 | 311 | 311 | **309** | 309.7 | 311 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| add_17 | 2812 -> 2196.0 | 499 -> 493.7 | 59 -> 55.3 | 1003 -> 730.0 | 635.7 |
| heisenberg_8 | 2127 -> 1325.3 | 420 -> 420.0 | 0 -> 0.0 | 529 -> 360.3 | 373.0 |
| mult_8 | 1898 -> 1427.7 | 311 -> 309.0 | 36 -> 38.7 | 1138 -> 840.7 | 304.6 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 23.31 | 0.00 | -1.08 | 25.46 | 1.06 |
| hypso | 28.13 | 0.57 | -0.60 | 28.41 | 437.75 |
| spso | 27.15 | 0.48 | 0.64 | 27.75 | 506.52 |
| qiskit | -2.29 | 0.00 | -12.03 | -1.79 | 4.56 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 2 | 1 | 0 | 0.57 | 0.25 |
| spso | 2 | 1 | 0 | 0.09 | 0.25 |
| qiskit | 2 | 1 | 0 | 0.57 | 0.25 |

## Friedman test and average ranks (lower is better)

Friedman: chi2 = 6.000, p = 0.112

| method | average rank |
|---|---|
| hypso | 1.50 |
| spso | 2.17 |
| greedy | 3.17 |
| qiskit | 3.17 |

Equivalence check: 24 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
