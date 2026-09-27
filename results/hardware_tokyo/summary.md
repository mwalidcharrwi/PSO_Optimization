Mode: `hardware`, budget: 200 unique evaluations, seeds: 3

Device: `ibm_tokyo`.  The `lowered` column is the *unrouted* logical circuit (no connectivity constraint); all other columns are routed, connectivity-respecting circuits verified with their initial/final layouts.

# Benchmark summary (objective: `cx`, primary metric: `cx`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | spso | ga | sa | rs | qiskit | tket |
|---|---|---|---|---|---|---|---|---|---|---|
| tof_4 | 7 | 30 | 24 | **22** | 31.3 | **22** | 23.3 | 24 | 30 | 30 |
| barenco_tof_4 | 7 | 48 | 42 | **35.7** | 50.7 | 36.7 | 38.7 | 42 | 48 | 46 |
| vbe_adder_3 | 10 | 72 | 62 | **51** | 78.3 | 53 | 51.7 | 62 | 58 | 58 |
| cuccaro_adder_4 | 10 | 65 | 49 | 45.7 | 78.7 | **45** | 48 | 49 | 65 | 61 |
| gf2^3_mult | 9 | 72 | 84 | 82.3 | 95.3 | 80.7 | **78.3** | 84 | 102 | 105 |
| qft_6 | 6 | 39 | 46 | 45.3 | 47.3 | **44.7** | 45.7 | 46 | 45 | 49 |
| qft_8 | 8 | 68 | 87 | 82.3 | 95.3 | **82** | **82** | 87 | 84 | 102 |
| qaoa_10_p1 | 10 | 30 | 33 | **31.7** | 41 | 33 | **31.7** | 33 | 36 | 42 |

## All metrics of the reference method vs. lowered input

| circuit | gates | cx | T | depth | time (s) |
|---|---|---|---|---|---|
| tof_4 | 75 -> 49.0 | 30 -> 22.0 | 35 -> 17.0 | 54 -> 38.3 | 3.1 |
| barenco_tof_4 | 120 -> 71.7 | 48 -> 35.7 | 56 -> 23.7 | 87 -> 63.7 | 5.8 |
| vbe_adder_3 | 162 -> 88.7 | 72 -> 51.0 | 70 -> 23.0 | 93 -> 58.0 | 8.4 |
| cuccaro_adder_4 | 137 -> 93.7 | 65 -> 45.7 | 56 -> 20.0 | 102 -> 81.7 | 7.8 |
| gf2^3_mult | 180 -> 136.0 | 72 -> 82.3 | 84 -> 31.7 | 91 -> 85.3 | 9.2 |
| qft_6 | 90 -> 72.3 | 39 -> 45.3 | 15 -> 5.3 | 41 -> 44.7 | 3.7 |
| qft_8 | 160 -> 125.3 | 68 -> 82.3 | 21 -> 8.0 | 57 -> 82.7 | 8.4 |
| qaoa_10_p1 | 85 -> 66.7 | 30 -> 31.7 | 0 -> 0.0 | 31 -> 33.0 | 3.8 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | cx | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 24.36 | -0.19 | 60.37 | 1.67 | 0.27 |
| hypso | 29.89 | 6.76 | 61.32 | 7.40 | 6.29 |
| spso | 14.48 | -21.31 | 60.05 | -8.54 | 7.26 |
| ga | 29.45 | 6.29 | 61.32 | 3.26 | 5.44 |
| sa | 29.13 | 5.50 | 60.24 | 4.62 | 4.79 |
| rs | 24.36 | -0.19 | 60.37 | 1.67 | 7.03 |
| qiskit | 4.06 | -10.14 | 7.09 | -12.73 | 0.03 |
| tket | 6.81 | -16.46 | 32.45 | -21.10 | 1.16 |

## `hypso` vs. each method on `cx` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 8 | 0 | 0 | 7.60 | 0.00391 |
| spso | 8 | 0 | 0 | 23.81 | 0.00391 |
| ga | 3 | 1 | 4 | 0.64 | 0.406 |
| sa | 5 | 1 | 2 | 1.86 | 0.203 |
| rs | 8 | 0 | 0 | 7.60 | 0.00391 |
| qiskit | 7 | 0 | 1 | 15.84 | 0.00781 |
| tket | 8 | 0 | 0 | 19.91 | 0.00391 |

## Friedman test and average ranks (lower is better)

Friedman: chi2 = 44.123, p = 2.02e-07

| method | average rank |
|---|---|
| hypso | 2.00 |
| ga | 2.00 |
| sa | 2.38 |
| greedy | 4.94 |
| rs | 4.94 |
| qiskit | 5.50 |
| tket | 6.88 |
| spso | 7.38 |

Equivalence check: 144 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
