Mode: `cliffordt`, budget: 600 unique evaluations, seeds: 3

# Benchmark summary (objective: `gates`, primary metric: `gates`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | hypso | hypso_novar | hypso_place | hypso_place_eager | hypso_nosched | hypso_nomemetic | hypso_unguided | hypso_relaxed | hypso_spso | hypso_qpso | hypso_gbest | hypso_noseed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tof_10 | 19 | 255 | **175.7** | 215 | 178.3 | 177.7 | **175.7** | 176.3 | 177 | 179.7 | 177.7 | 177.7 | 177.7 | 178.3 |
| barenco_tof_5 | 9 | 180 | 100 | 140 | 103.3 | 100 | 100 | 100.7 | **98.7** | 102 | 101.3 | 101.3 | 100.7 | 101.3 |
| barenco_tof_10 | 19 | 480 | **268** | 365 | 270 | 272 | 270 | 269.3 | 269.3 | 276.7 | 268.7 | 268.7 | 270 | 271.3 |
| vbe_adder_3 | 10 | 162 | 81.7 | 101 | 85 | 83 | 81 | **79.7** | 81.7 | 83.7 | 81 | 81 | 80.3 | 83 |
| cuccaro_adder_8 | 18 | 273 | 195.7 | 233 | 196.3 | 195 | 195 | **194.3** | 195 | 196.3 | 196.3 | 196.3 | 195 | 195 |
| gf2^5_mult | 15 | 540 | 258.7 | 311 | 259 | 256.3 | 257.7 | **254.7** | 260.7 | 264.3 | 256.3 | 256.3 | 255 | 257 |

## All metrics of the reference method vs. lowered input

| circuit | gates | cx | T | depth | time (s) |
|---|---|---|---|---|---|
| tof_10 | 255 -> 175.7 | 102 -> 70.7 | 119 -> 71.0 | 180 -> 119.0 | 3.3 |
| barenco_tof_5 | 180 -> 100.0 | 72 -> 45.3 | 84 -> 40.0 | 129 -> 87.0 | 3.3 |
| barenco_tof_10 | 480 -> 268.0 | 192 -> 131.3 | 224 -> 100.0 | 339 -> 226.0 | 8.6 |
| vbe_adder_3 | 162 -> 81.7 | 72 -> 42.7 | 70 -> 24.0 | 93 -> 48.0 | 2.9 |
| cuccaro_adder_8 | 273 -> 195.7 | 129 -> 99.7 | 112 -> 64.0 | 202 -> 185.0 | 3.6 |
| gf2^5_mult | 540 -> 258.7 | 216 -> 152.0 | 252 -> 90.0 | 326 -> 178.0 | 7.2 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | cx | T | depth | mean time (s) |
|---|---|---|---|---|---|
| hypso | 41.62 | 32.08 | 53.49 | 33.66 | 4.81 |
| hypso_novar | 26.10 | 14.56 | 53.49 | 20.91 | 4.90 |
| hypso_place | 40.68 | 29.83 | 53.49 | 33.72 | 5.22 |
| hypso_place_eager | 41.33 | 31.24 | 53.49 | 33.26 | 5.16 |
| hypso_nosched | 41.69 | 31.99 | 53.49 | 33.54 | 4.65 |
| hypso_nomemetic | 41.88 | 32.53 | 53.49 | 33.00 | 4.80 |
| hypso_unguided | 41.59 | 32.14 | 53.49 | 33.33 | 4.67 |
| hypso_relaxed | 40.45 | 29.50 | 53.49 | 31.61 | 5.08 |
| hypso_spso | 41.45 | 31.49 | 53.49 | 33.59 | 5.17 |
| hypso_qpso | 41.45 | 31.49 | 53.49 | 33.59 | 4.64 |
| hypso_gbest | 41.65 | 31.80 | 53.49 | 34.07 | 4.43 |
| hypso_noseed | 41.16 | 30.78 | 53.49 | 33.23 | 4.42 |

## `hypso` vs. each method on `gates` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| hypso_novar | 6 | 0 | 0 | 20.91 | 0.0156 |
| hypso_place | 6 | 0 | 0 | 1.64 | 0.0156 |
| hypso_place_eager | 3 | 1 | 2 | 0.49 | 0.312 |
| hypso_nosched | 1 | 2 | 3 | -0.14 | 0.688 |
| hypso_nomemetic | 3 | 0 | 3 | -0.54 | 0.797 |
| hypso_unguided | 3 | 1 | 2 | 0.05 | 0.219 |
| hypso_relaxed | 6 | 0 | 0 | 2.03 | 0.0156 |
| hypso_spso | 4 | 0 | 2 | 0.22 | 0.25 |
| hypso_qpso | 4 | 0 | 2 | 0.22 | 0.25 |
| hypso_gbest | 3 | 0 | 3 | -0.15 | 0.469 |
| hypso_noseed | 4 | 0 | 2 | 0.78 | 0.156 |

## Friedman test and average ranks (lower is better)

Friedman: chi2 = 41.425, p = 2.04e-05

| method | average rank |
|---|---|
| hypso_nomemetic | 2.67 |
| hypso_nosched | 4.42 |
| hypso | 4.50 |
| hypso_gbest | 4.50 |
| hypso_unguided | 5.00 |
| hypso_spso | 5.75 |
| hypso_qpso | 5.75 |
| hypso_place_eager | 6.00 |
| hypso_noseed | 7.50 |
| hypso_place | 9.50 |
| hypso_relaxed | 10.42 |
| hypso_novar | 12.00 |

Equivalence check: 0 verified, 216 not checked (too large, or --no-verify), 0 FAILED.
