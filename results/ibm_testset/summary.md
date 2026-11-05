IBM-native test set (test_circuits_new), mode `ibm`

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | spso | qiskit | ga | sa |
|---|---|---|---|---|---|---|---|---|
| add_17 | 17 | 499 | 499 | **493.7** | 494 | 499 | 497.3 | 497.3 |
| heisenberg_8 | 8 | 420 | **420** | **420** | **420** | **420** | **420** | **420** |
| mult_8 | 8 | 311 | 311 | **309** | 309.7 | 311 | **309** | 310.3 |
| hubbard_8 | 8 | 1344 | 1344 | **1335.3** | 1338 | 1344 | 1340.3 | 1342.3 |
| qae_17 | 17 | 541 | 541 | 530 | **528.7** | 541 | 534.3 | 539.3 |
| qft_16 | 16 | 614 | 614 | **606.7** | 607.7 | 614 | 609.3 | 613.7 |
| heisenberg_32 | 32 | 3942 | **3882** | **3882** | **3882** | 4024 | **3882** | **3882** |
| hhl_8 | 8 | 2377 | 2377 | **2376** | 2377 | 2377 | **2376** | 2377 |
| grover_10 | 10 | 16397 | 16397 | **16395** | - | 16397 | - | - |
| hubbard_18 | 31 | 33958 | 30431 | **30415** | - | 33456 | - | - |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| add_17 | 2812 -> 2196.0 | 499 -> 493.7 | 59 -> 55.3 | 1003 -> 730.0 | 635.7 |
| heisenberg_8 | 2127 -> 1325.3 | 420 -> 420.0 | 0 -> 0.0 | 529 -> 360.3 | 373.0 |
| mult_8 | 1898 -> 1427.7 | 311 -> 309.0 | 36 -> 38.7 | 1138 -> 840.7 | 304.6 |
| hubbard_8 | 8125 -> 5956.0 | 1344 -> 1335.3 | 36 -> 28.3 | 4400 -> 3176.0 | 1939.9 |
| qae_17 | 3033 -> 2398.7 | 541 -> 530.0 | 38 -> 35.0 | 1066 -> 777.0 | 898.2 |
| qft_16 | 3444 -> 2668.3 | 614 -> 606.7 | 44 -> 30.0 | 1009 -> 716.0 | 744.6 |
| heisenberg_32 | 58848 -> 14740.0 | 3942 -> 3882.0 | 0 -> 0.0 | 7143 -> 2422.0 | 1320.1 |
| hhl_8 | 18165 -> 15401.5 | 2377 -> 2376.0 | 597 -> 582.0 | 10641 -> 9014.5 | 836.5 |
| grover_10 | 93235 -> 71485.0 | 16397 -> 16395.0 | 209 -> 306.0 | 43923 -> 34216.0 | 2817.5 |
| hubbard_18 | 357535 -> 135134.0 | 33958 -> 30415.0 | 0 -> 0.0 | 136644 -> 57219.0 | 11218.7 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 30.34 | 1.19 | 6.80 | 31.80 | 75.26 |
| hypso | 33.02 | 1.76 | 2.27 | 33.08 | 2108.88 |
| spso | 30.08 | 0.84 | 9.34 | 31.11 | 674.80 |
| qiskit | 10.38 | -0.06 | -8.36 | 9.13 | 62.56 |
| ga | 30.80 | 0.60 | 10.87 | 31.59 | 515.22 |
| sa | 29.44 | 0.32 | 10.43 | 30.67 | 379.99 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 8 | 2 | 0 | 0.57 | 0.00391 |
| spso | 5 | 2 | 1 | 0.05 | 0.141 |
| qiskit | 9 | 1 | 0 | 1.83 | 0.00195 |
| ga | 4 | 4 | 0 | 0.29 | 0.0625 |
| sa | 6 | 2 | 0 | 0.58 | 0.0156 |

## Friedman test and average ranks (lower is better)

Friedman: chi2 = 27.343, p = 4.89e-05

| method | average rank |
|---|---|
| hypso | 1.81 |
| spso | 2.62 |
| ga | 2.75 |
| sa | 3.81 |
| greedy | 4.81 |
| qiskit | 5.19 |

Equivalence check: 97 verified, 9 not checked (too large, or --no-verify), 0 FAILED.
