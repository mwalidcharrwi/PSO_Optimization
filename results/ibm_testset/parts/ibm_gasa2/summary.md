Mode: `ibm`, budget: 300 unique evaluations, seeds: 3

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | ga | sa |
|---|---|---|---|---|
| qae_17 | 17 | 541 | **534.3** | 539.3 |
| qft_16 | 16 | 614 | **609.3** | 613.7 |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| ga | 21.81 | 1.00 | 16.47 | 27.99 | 457.42 |
| sa | 21.25 | 0.18 | 19.26 | 27.49 | 299.79 |

Equivalence check: 12 verified, 0 not checked (too large, or --no-verify), 0 FAILED.
