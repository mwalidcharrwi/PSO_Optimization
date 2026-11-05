# HyPSO-QCO vs related work on the supplied benchmarks (`test_circuits_new`)

The tables and the discussion are in [REPORT.md](REPORT.md).  This file
describes the protocol.

## Inputs and contract

The ten supplied circuits are 127-qubit, IBM-Eagle-mapped circuits in the
native gate set {rz, sx, x, ecr}.  Every method has to return a circuit that:

1. is equivalent to the input on the **same physical qubits**, with no
   relabelling and no final permutation;
2. uses two-qubit gates **only on qubit pairs already coupled in the input**,
   with ECRs in the input's native directions;
3. is written in {rz, sx, x, ecr}.

Tools that work with CNOTs get the input converted *exactly* to
{rz, sx, x, cx} (`qcpso.native.to_cx`).  Their output is converted back
with the same exact lowering that HyPSO-QCO uses (`qcpso.native.to_native`).
ECR counts are therefore equal to their CNOT counts, and the single-qubit
counts are measured the same way for every method.

## Methods

| folder | method | budget | notes |
|---|---|---|---|
| `deterministic/` | (Qiskit 2.x `optimization_level=3`) | – | **not part of the comparison**: the supplied circuits were produced by Qiskit's level-3 transpiler, so the input already is the Qiskit O3 result.  The re-run outputs are kept in `deterministic/` for reference only and are excluded from all reports, tables and figures |
| `deterministic/` | TKET, connectivity-preserving | – | fixed point of `SynthesiseTket`, `KAKDecomposition(allow_swaps=False)` and `CliffordSimp(allow_swaps=False)` |
| `queso/` | QUESO (PLDI'23) | 900 s | GUOQ binary, `-opt TOTAL -search BEAM -temp 0 -q 8000 -resynth NONE --preserve-mapping` |
| `guoq/` | GUOQ (ASPLOS'25) | 900 s, snapshots 60 s / 300 s | `-g IBMN -opt TWO_Q -resynth BQSKIT --preserve-mapping`; coupling-aware BQSKit resynthesis (patch in `third_party/`) |
| `hypso/` | **HyPSO-QCO v2** | 900 s | `HyPSOConfig(mode="ibm", time_limit=900)`, 4 resynthesis workers, seed 0 |
| `hypso_w1/` | HyPSO-QCO v2, 1 worker | 900 s | compute-matched with GUOQ's single search thread |
| `ablation/` | v2 without the swarm phase | 900 s | memetic phase from the strongest elite seed only |
| (`results/ibm_testset`) | HyPSO-QCO v1 | 16–600 evaluations | previous version, re-measured from its saved outputs |

## Machine and budgets

All runs used the same 4-core container (15 GB RAM, `OMP_NUM_THREADS=1`).

* GUOQ and QUESO ran concurrently with each other and with the
  deterministic baselines.  GUOQ's search is single-threaded, with a
  separate BQSKit resynthesis server, so it uses at most about 2 cores.
* HyPSO-QCO's runs ran alone.
* The single-worker variant is included so that the comparison with GUOQ
  can also be read at matched compute.
* Budgets are wall-clock budgets, including HyPSO-QCO's decoding and
  conversion to native form.

## Verification

Every saved output is compared with its input (`qcpso.bench.verify_literature`):

* **≤ 20 used qubits:** random-state test with a shared global phase.
* **> 20 used qubits:** Choi-state MPS miter (`qcpso.bench.mps_verify`).

The **deviation** is reported in three classes: < 1e-9 exact, < 1e-6
numerically exact, otherwise approximate.

* GUOQ, BQSKit and the memetic phase of HyPSO-QCO use numerical synthesis,
  so their outputs are only numerically exact.
* GUOQ's error budget (ε = 1e-8 per resynthesis, up to 100 resynthesised
  blocks) can accumulate beyond 1e-6: for example, 5.4e-6 on `qft_16`.

## Reproduce

```bash
export PYTHONPATH=. OMP_NUM_THREADS=1 GUOQ_DIR=/path/to/patched/guoq     # see third_party/README.md
python -m qcpso.bench.compare_ibm --out results/ibm_literature/guoq  --methods guoq  --time-limit 900 --snapshots 60,300 --port 8091
python -m qcpso.bench.compare_ibm --out results/ibm_literature/queso --methods queso --time-limit 900 --snapshots 60,300
python -m qcpso.bench.compare_ibm --out results/ibm_literature/deterministic --methods tket_mp
scripts/run_ibm_literature.sh                                   # HyPSO-QCO v2, 1-worker variant, ablation
python -m qcpso.bench.verify_literature results/ibm_literature --large
python -m qcpso.bench.report_literature results/ibm_literature > results/ibm_literature/REPORT_TABLES.md
```

Optimised circuits: `*/optimized/<circuit>__<method>__s<seed>.qasm`.
