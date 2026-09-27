Mode: `ibm`, budget: 600 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | qiskit |
|---|---|---|---|
| heisenberg_32 | 32 | 3942 | **4024** |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| qiskit | 61.61 | -2.08 | - | 51.98 | 29.63 |

Equivalence check: 0 verified, 1 not checked (too large, or --no-verify), 0 FAILED.
