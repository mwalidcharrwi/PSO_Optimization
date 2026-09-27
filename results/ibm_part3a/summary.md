Mode: `ibm`, budget: 40 unique evaluations, seeds: 1

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso |
|---|---|---|---|---|
| heisenberg_32 | 32 | 3942 | **3882** | **3882** |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| heisenberg_32 | 58848 -> 14740.0 | 3942 -> 3882.0 | 0 -> 0.0 | 7143 -> 2422.0 | 1320.1 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 74.76 | 1.52 | - | 65.60 | 31.01 |
| hypso | 74.95 | 1.52 | - | 66.09 | 1320.12 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 0 | 1 | 0 | 0.00 | 1 |

Equivalence check: 0 verified, 2 not checked (too large, or --no-verify), 0 FAILED.
