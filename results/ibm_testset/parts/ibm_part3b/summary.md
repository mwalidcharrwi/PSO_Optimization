Mode: `ibm`, budget: 120 unique evaluations, seeds: 2

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | greedy | hypso | spso | qiskit |
|---|---|---|---|---|---|---|
| hhl_8 | 8 | 2377 | 2377 | **2376** | 2377 | 2377 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|
| hhl_8 | 18165 -> 15401.5 | 2377 -> 2376.0 | 597 -> 582.0 | 10641 -> 9014.5 | 836.5 |

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| greedy | 13.74 | 0.00 | 6.87 | 16.23 | 6.62 |
| hypso | 15.21 | 0.04 | 2.51 | 15.29 | 836.54 |
| spso | 15.16 | 0.00 | 3.77 | 15.26 | 813.12 |
| qiskit | -5.05 | 0.00 | 0.00 | -5.02 | 20.13 |

## `hypso` vs. each method on `twoq` (per-circuit means)

| method | wins | ties | losses | mean improvement (%) | Wilcoxon p (one-sided) |
|---|---|---|---|---|---|
| greedy | 1 | 0 | 0 | 0.04 | 0.5 |
| spso | 1 | 0 | 0 | 0.04 | 0.5 |
| qiskit | 1 | 0 | 0 | 0.04 | 0.5 |

Equivalence check: 6 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
