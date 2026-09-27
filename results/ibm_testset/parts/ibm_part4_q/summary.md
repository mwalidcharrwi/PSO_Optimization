Mode: `ibm`, budget: 600 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | qiskit |
|---|---|---|---|
| hubbard_18 | 31 | 33958 | **33456** |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| qiskit | 57.02 | 1.48 | - | 52.64 | 282.84 |

Equivalence check: 0 verified, 1 not checked (too large, or --no-verify), 0 FAILED.
