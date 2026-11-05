Mode: `ibm`, budget: 300 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | ga | sa |
|---|---|---|---|---|
| hubbard_8 | 8 | 1344 | **1340.3** | 1342.3 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| ga | 27.33 | 0.27 | 21.30 | 28.39 | 999.45 |
| sa | 24.87 | 0.12 | 12.96 | 26.39 | 680.05 |

Equivalence check: 6 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
