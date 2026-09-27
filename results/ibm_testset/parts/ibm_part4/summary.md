Mode: `ibm`, budget: 16 unique evaluations, seeds: 1

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | qiskit |
|---|---|---|---|---|---|
| grover_10 | 10 | 16397 | 16397 | **16395** | 16397 |
| hubbard_18 | 31 | 33958 | 30431 | **30415** | - |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| grover_10 | 93235 -> 71485.0 | 16397 -> 16395.0 | 209 -> 306.0 | 43923 -> 34216.0 | 2817.5 |
| hubbard_18 | 357535 -> 135134.0 | 33958 -> 30415.0 | 0 -> 0.0 | 136644 -> 57219.0 | 11218.7 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 40.90 | 5.19 | 0.00 | 39.94 | 349.10 |
| hypso | 42.77 | 5.22 | -46.41 | 40.11 | 7018.09 |
| qiskit | -0.09 | 0.00 | -7.66 | -0.34 | 256.56 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 2 | 0 | 0 | 0.03 | 0.25 |
| qiskit | 1 | 0 | 0 | 0.01 | 0.5 |

Equivalence check: 3 verified, 2 not checked (too large, or --no-verify), 0 FAILED.
