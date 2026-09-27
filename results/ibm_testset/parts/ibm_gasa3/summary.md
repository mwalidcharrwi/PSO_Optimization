Mode: `ibm`, budget: 120 unique evaluations, seeds: 2

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | ga | sa |
|---|---|---|---|---|
| hhl_8 | 8 | 2377 | **2376** | 2377 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| ga | 15.26 | 0.04 | 2.85 | 15.42 | 779.04 |
| sa | 13.79 | 0.00 | 6.87 | 16.17 | 640.36 |

Equivalence check: 4 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
