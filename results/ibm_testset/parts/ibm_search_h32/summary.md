Mode: `ibm`, budget: 40 unique evaluations, seeds: 1

# Benchmark summary (objective: `twoq`, primary metric: `twoq`)

## Primary metric per circuit (mean over seeds; best in bold)

| circuit | qubits | lowered | spso | ga | sa |
|---|---|---|---|---|---|
| heisenberg_32 | 32 | 3942 | **3882** | **3882** | **3882** |

## All metrics of the reference method vs. lowered input

| circuit | gates | 2q gates | T | depth | time (s) |
|---|---|---|---|---|---|

## Average reduction w.r.t. the lowered input (%)

| method | gates | 2q gates | T | depth | mean time (s) |
|---|---|---|---|---|---|
| spso | 74.94 | 1.52 | - | 66.01 | 613.22 |
| ga | 74.91 | 1.52 | - | 66.02 | 620.89 |
| sa | 74.76 | 1.52 | - | 65.69 | 480.73 |

Equivalence check: 0 verified, 3 not checked (too large, or --no-verify), 0 FAILED.
