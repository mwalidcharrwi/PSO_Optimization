# Superseded HyPSO-QCO v2 runs

These runs (main, 1-worker and memetic-only configurations) used a TKET pass
that included `SynthesiseTket`.  Later analysis showed that TKET's
single-qubit squashing can drop small rotations: `rz(3.8e-4)` next to
Clifford gates, after phase folding on `qae_17`.  Some *intermediate*
decodes of the swarm phase were therefore only approximately equivalent.

Every final output verified here is numerically exact (deviation <= 4.2e-8;
see `verification.csv`) except `ablation/qae_17`.  That run started its
memetic phase from such an inexact decode, and its deviation is 3.8e-4.

The code was fixed:
* the TKET pass now uses only `KAKDecomposition` + `CliffordSimp` and is
  checked numerically;
* the memetic phase now verifies every accepted round and every replaced
  block.

All HyPSO-QCO configurations were re-run with the fixed code; see the parent
folder.  These files are kept for transparency only and are not used in the
report.
