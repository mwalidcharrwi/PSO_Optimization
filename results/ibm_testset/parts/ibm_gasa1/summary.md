Mode: `ibm`, budget: 300 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | ga | sa |
|---|---|---|---|---|
| add_17 | 17 | 499 | **497.3** | **497.3** |
| heisenberg_8 | 8 | 420 | **420** | **420** |
| mult_8 | 8 | 311 | **309** | 310.3 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| ga | 28.42 | 0.33 | 4.06 | 28.96 | 269.18 |
| sa | 26.52 | 0.18 | 2.10 | 27.39 | 213.07 |

Equivalence check: 18 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
