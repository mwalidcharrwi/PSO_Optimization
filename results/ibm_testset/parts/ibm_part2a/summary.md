Mode: `ibm`, budget: 300 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | spso | qiskit |
|---|---|---|---|---|---|---|
| hubbard_8 | 8 | 1344 | 1344 | **1335.3** | 1338 | 1344 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| hubbard_8 | 8125 -> 5956.0 | 1344 -> 1335.3 | 36 -> 28.3 | 4400 -> 3176.0 | 1939.9 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 24.38 | 0.00 | 11.11 | 26.25 | 9.73 |
| hypso | 26.70 | 0.64 | 21.30 | 27.82 | 1939.90 |
| spso | 27.04 | 0.45 | 12.04 | 27.97 | 1287.18 |
| qiskit | 0.68 | 0.00 | 0.00 | 0.27 | 10.64 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 1 | 0 | 0 | 0.64 | 0.5 |
| spso | 1 | 0 | 0 | 0.20 | 0.5 |
| qiskit | 1 | 0 | 0 | 0.64 | 0.5 |

Equivalence check: 8 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
