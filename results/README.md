# Benchmark results

Every folder holds `results.csv` (one row per circuit × method × seed),
`summary.md` (tables and statistics) and `convergence.json` (best-so-far
traces of the search methods; git-ignored because of its size).  All
numbers were produced by the code in this repository with the commands
below.

| folder | mode | suite | budget (unique evaluations) | seeds |
|---|---|---|---|---|
| `cliffordt/` | {H, X, Rz, CNOT}, objective `gates` | built-in `small` (18 circuits) | 600 | 3 |
| `continuous/` | {U3, CNOT}, objective `cx` | built-in `continuous` (11 circuits) | 300 | 3 |
| `hardware_tokyo/` | IBM Tokyo (20 qubits), objective `cx` | built-in `hardware` (8 circuits) | 200 | 3 |
| `ablation/` | {H, X, Rz, CNOT}, objective `gates` | built-in `ablation` (6 Toffoli-heavy circuits) | 600 | 3 |

```bash
python -m qcpso bench --suite small --mode cliffordt --methods greedy,hypso,spso,ga,sa,rs,qiskit,tket,pyzx \
    --budget 600 --seeds 3 --out results/cliffordt
python -m qcpso bench --suite continuous --mode continuous --methods greedy,hypso,spso,ga,sa,rs,qiskit,tket,pyzx \
    --budget 300 --seeds 3 --out results/continuous
python -m qcpso bench --suite hardware --mode hardware --device ibm_tokyo \
    --methods greedy,hypso,spso,ga,sa,rs,qiskit,tket --budget 200 --seeds 3 --out results/hardware_tokyo
python -m qcpso bench --suite ablation --mode cliffordt --no-verify --budget 600 --seeds 3 --out results/ablation \
    --methods hypso,hypso_novar,hypso_place,hypso_place_eager,hypso_nosched,hypso_nomemetic,hypso_unguided,hypso_relaxed,hypso_spso,hypso_qpso,hypso_gbest,hypso_noseed
```

Protocol notes

* The *lowered* column is the input decomposed with default choices
  (Toffoli = 15 gates: 2 H, 7 T/T†, 6 CNOT).  In hardware mode it is the
  unrouted logical circuit.
* `spso`, `ga`, `sa`, `rs` use the **same decoder, genome and budget** as
  `hypso`; only the search strategy differs.  `spso` is the canonical
  unseeded gbest PSO (the formulation used in prior PSO-for-circuits work).
  `ga`, `sa` and `rs` are seeded like HyPSO.
* External tools get the undecomposed input and are held to the same
  strict-equivalence contract: Qiskit's `ElidePermutations` and TKET's
  implicit wire swaps are disabled.  Their outputs are counted in the same
  gate set; single-qubit runs are fused in continuous mode.
* Every output of the main experiments is checked for equivalence by
  simulation (with initial/final layouts in hardware mode).  The ablation
  run skips verification for speed; all its circuits come from the same
  sound passes.
* Statistics: per-circuit means over seeds, one-sided Wilcoxon signed-rank
  tests (HyPSO < method), Friedman test and average ranks.
* The built-in suites are programmatic reconstructions of standard
  families (tof_n, barenco_tof_n, VBE/Cuccaro adders, GF(2^n) multipliers,
  QFT, QAOA, random Clifford+T).  They are not the original benchmark files.
