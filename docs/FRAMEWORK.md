# HyPSO-QCO — Hybrid, Provenance-aligned Particle Swarm Optimisation for Quantum Circuit Optimisation

## 1. Problem statement

Given a quantum circuit *C* (OpenQASM 2, `.qc` or RevLib `.real`) and a
target gate set, find a circuit *C′* with *U(C′) = e^{iφ} U(C)* that
minimises a cost *f(C′)*: lexicographic `(gates, cx, T, depth)`, `(cx, gates,
depth)`, `(T, cx, gates, depth)`, `depth`, or an estimated-infidelity cost
`−log Π(1−ε_g)`.

Three targets are supported:

| mode | gate set | typical use |
|---|---|---|
| `cliffordt` | {H, X, Rz(θ), CNOT} (Nam gate set; T-count reported) | fault-tolerant / Clifford+T benchmarks |
| `continuous` | {U3, CNOT} (single-qubit runs fused) | NISQ devices, arbitrary rotations |
| `hardware` | {U3, CNOT} on a coupling graph (initial/final layouts) | device-constrained compilation |
| `ibm` | IBM native {rz, sx, x, ecr}, **fixed** existing mapping | re-optimising circuits that are already transpiled for an IBM device |

## 2. Key idea: search the space of *compilation decisions*, not circuits

Prior PSO approaches place gates and qubit indices directly in the particle
position.  Most candidates are then **not equivalent** to the target, the
fitness is an (exponentially expensive) fidelity estimate, and the
approach stays limited to a handful of qubits.

HyPSO-QCO instead wraps a **semantics-preserving optimisation program**
whose free decisions are exposed as a genome.  Every particle decodes to a
circuit that is *exactly* equivalent to the input ("equivalence by
construction"); the equivalence is additionally checked numerically for
every reported result.  Because decoding costs roughly linear time in the
circuit size, the swarm scales to circuits with thousands of gates.

```
  input circuit ──► lowering with variants ──► pass schedule ──► clean-up fix point ──► [routing] ──► finish ──► C′
                        ▲                          ▲                  ▲                    ▲
                    variant genes            schedule genes     placement genes      hardware genes
```

## 3. Genome (all genes in [0,1))

| segment | per | cardinality | decoding |
|---|---|---|---|
| **variant** | multi-variant gate instance ("site") | categorical | factor tuple of the site (see 3.1) |
| **placement** (opt-in, `use_placement=True`) | rotation, keyed by semantic tag | continuous, *lazy* | `<0.5` keep the standard location, else relative position among all availability points (4) |
| **schedule** | slot (default 6) | categorical over {skip, cancel, fold, hred, fold+cancel, kak} | pass sequence, followed by the clean-up fix point |
| **hardware** | physical qubit + 4 router genes | continuous keys + categorical | random-key layout; SABRE look-ahead size, weight, decay, tie-break seed |

### 3.1 Decomposition-variant library

* **CCZ / Toffoli** (factors `network × polarity × placement`).  The CCZ
  phase polynomial is `π·abc = π/4·(a+b+c−a⊕b−a⊕c−b⊕c+a⊕b⊕c)`.  A
  breadth-first search over CNOT sequences (state = linear map ∈ GL(3,2) ×
  set of visited parities) enumerates **all 108 minimal 6-CNOT networks**
  that expose the four multi-variable parities (all-to-all connectivity) and
  the **12 minimal 8-CNOT nearest-neighbour networks** (3 choices of middle
  qubit × 4), used in hardware mode.  Since CCZ is self-inverse, every T can
  be swapped with T† (*polarity*), and each T can be placed at the first or
  last occurrence of its parity (*placement*).  All 480 Toffoli variants
  are verified in the test-suite.
* **CZ** (H pair on either qubit), **SWAP** (CNOT orientation), **CP/CU1,
  CRZ** (accumulator qubit × early/late single-qubit phases), **RZZ/RXX/RZX**
  (accumulator), **CSWAP** (orientation, plus its inner Toffoli as a site).
* Multi-controlled X/Z/U gates use Barenco et al. constructions with
  *borrowed (dirty)* ancillas when available and a square-root recursion
  otherwise; their internal Toffolis are sites of their own.

### 3.2 Provenance alignment (why social learning works)

Standard encodings suffer from *gene-meaning drift*: when a particle
changes one decision, the positions of all later decisions shift, so
copying a gene from the global best copies a *different* decision.  In
HyPSO-QCO every emitted gate carries a provenance tag = key path `(index of
the input gate, …, semantic role)`.  Rotations produced by a CCZ template
are tagged with their **parity term** (e.g. `(17, 'p', 3)` = "the a⊕b phase
of input gate 17"), which is identical in all 432 variants of that Toffoli.
Variant genes are keyed by site key paths, placement genes by these
semantic tags, so gene *i* means the same decision in every particle.

## 4. Sound rewrite passes

| pass | description | soundness |
|---|---|---|
| `cancel` | slide each gate along its wire(s) over provably commuting gates to its inverse or a mergeable rotation | commutation test: gates commute if on every shared qubit both are Z-type or both X-type (proof in `passes/commutation.py`) |
| `fold` | **global path-sum phase folding with free placement** | see below |
| `hred` | Nam et al. Hadamard reduction rules (H S H → S† H S†, H⊗H·CX·H⊗H → reversed CX, target-side H S CX S† H → S† CX S) | verified numerically |
| `kak` | collect maximal 2-qubit blocks, compute the optimal CNOT count with the Shende–Markov–Bullock invariants, and resynthesise with **swarm instantiation** (inner PSO + Levenberg–Marquardt) when it saves CNOTs | numerical to machine precision, checked |
| `fuse` | fuse single-qubit runs into one U3 / Rz / X | exact |

**Phase folding with free placement.**  Sweep the circuit keeping, per
wire, an affine Boolean function of path variables: CNOT/X/SWAP act
linearly, diagonal gates leave values unchanged, every other gate
assigns a fresh path variable.  An Rz(θ) on a wire holding `ℓ ⊕ c`
multiplies the amplitude of every path by `exp(iθ(2(ℓ⊕c)−1)/2)`.
Amplitudes of all paths are products of such factors, so all rotations
with the same linear part ℓ can be merged into one rotation of angle
Σ(−1)^{c_i}θ_i, which can be realised at **any** point of the circuit where
some wire carries ℓ (with sign (−1)^{c}).  HyPSO-QCO enumerates these
*availability points* (positions of the original rotations and both ends of
every interval during which a wire holds ℓ) and lets the placement gene
choose; a rotation stuck between two otherwise-cancelling CNOTs can thus be
moved away.  Rotations on constant wires are global phases and removed.

*Ablation finding:* free placement is sound and occasionally helps (e.g.
GF(2^n) multipliers at 2000 evaluations), but across the ablation suite it
did not pay off at the tested budgets, even with lazy genes.  It is
therefore **opt-in**; by default the first-occurrence placement is used.

The clean-up fix point iterates `cancel → fold → cancel → hred → fold →
cancel` until the size stops decreasing.  All passes preserve the coupling
graph, so they are also applied after routing.

## 5. The swarm

### 5.1 Mixed-variable dynamics

*Continuous genes* (placement, layout keys) — hybrid of constriction PSO and
quantum-behaved PSO, chosen per particle and iteration with probability
`p_qpso = 0.5`:

```
SPSO:  v ← χ [ v + c1 r1 (p_i − x) + c2 r2 (l_i − x) ],  x ← x + clip(v, ±v_max)
QPSO:  x ← φ p_i + (1−φ) l_i ± β |m − x| ln(1/u),        β: 1.0 → 0.5
```

with χ = 0.7298, c1 = c2 = 1.49618, m the mean personal best and l_i the
neighbourhood best.

(In the logical modes with placement disabled, the default, every gene is
categorical, so only the categorical rule below is active; the continuous
rule drives the hardware layout keys and the optional placement genes.)

*Categorical genes* (decomposition variants, pass slots, router settings)
are **nominal**, so each particle holds a probability vector π over the k
categories of each gene (categorical PSO):

```
w ← χ [ w + c1 r1 (e(p_i) − π) + c2 r2 (e(l_i) − π) ],   π ← normalise(max(π + w, 0))
gene ~ (1 − ε) π + ε/k,     ε = ε_floor + turbulence
```

where `e(·)` is the one-hot vector of the personal/neighbourhood best
category.

### 5.2 Search control

* **Dynamic topology** — von Neumann lbest for the first half of the budget
  (diversity), gbest afterwards (convergence).
* **Elitist seeding** — one particle is the default decision vector, i.e. the
  deterministic compiler.  The swarm therefore can never return a circuit
  worse than the greedy optimiser it wraps.
* **Opposition-based initialisation** for half of the random particles.
* **Adaptive turbulence** that doubles with stagnation; **partial restarts**
  of the worst half after `patience` stagnant iterations.
* **Two-timescale genome** — placement genes are *lazy*: every particle
  starts with the standard placement, and these genes are neither randomised
  nor mutated by turbulence.  They change only when the local search finds
  a useful relocation, which then spreads through the swarm socially.  This
  keeps hundreds of fine-grained continuous genes from diluting the global
  search, which the ablation showed to happen with eager placement genes.
* **Provenance-guided memetic search** on the global best every iteration.
  The best circuit is decoded, and for every site the fraction of its gates
  that survived optimisation is computed from the provenance tags.  Moves
  are sampled proportionally to this *residual*: single-factor changes,
  whole-site resampling, and joint moves of two **adjacent sites** (sites
  acting on a common qubit), which capture the pairwise interactions that
  dominate cancellation between neighbouring gates.  Lazy genes use
  relocate/restore moves, and layout genes use "move a logical qubit to a
  neighbouring physical qubit" moves.
* **Adaptive operator selection** — the move types (layout, lazy, site,
  whole-site, adjacent pair, generic) are chosen by probability matching
  (Thierens 2005).  Each type's decayed reward is 1 for a strict improvement
  and 0.1 for a neutral move, with a 5% floor per type.  The search thus
  learns, per circuit, which neighbourhoods pay off; for example, placement
  moves help GF(2^n) multipliers but not Barenco ladders.
* **Memoisation** — phenotypes (decoded decisions) are cached; the budget is
  counted in *unique* evaluations.  Parallel evaluation uses a process pool.

### 5.3 Pseudo-code

```
HyPSO-QCO(C, budget):
  sites ← variant sites of C (provenance keys);  tags ← semantic rotation tags
  genome layout ← [variant | placement | schedule | hardware]
  swarm ← {default decisions} ∪ random ∪ opposite(random)
  evaluate swarm; set pbest, gbest
  while evaluations < budget:
      topology ← von Neumann if progress < ½ else gbest
      for each particle i:
          continuous genes ← SPSO or QPSO move towards (pbest_i, lbest_i)
          categorical genes ← sample from categorical-PSO probability vectors
          turbulence
      evaluate swarm (decode → sound passes → cost), update pbest/gbest
      gbest ← provenance-guided local search(gbest)
      on stagnation: restart worst particles, raise turbulence
  return decode(gbest)   (verified equivalent)
```

## 6. Hardware co-optimisation

The logical program (variants, placement, schedule) is followed by SABRE
routing from the layout decoded from random keys (sort the n_phys keys;
logical qubit i ↦ the i-th physical qubit).  Router look-ahead size,
look-ahead weight, decay and tie-breaking are genes as well.  SWAPs are
oriented so that one of their CNOTs cancels an adjacent CNOT, then all
(connectivity-preserving) passes and 2-qubit resynthesis run on the
physical circuit.  The three best distinct SabreLayout (bidirectional, 20 trials) layouts
are used as elite seeds.  Because nearest-neighbour Toffoli networks are in the variant
library, the swarm can pick, per Toffoli, a network matching the layout it
is co-evolving.  Results are verified with initial/final layouts and
|0⟩ ancillas (`hardware/verify.py`).

## 7. IBM-native mode (already-mapped circuits)

Circuits exported by an IBM transpiler are already laid out and routed:
every ECR acts on a coupled pair, in the device's native direction.  The
`ibm` mode optimises them without touching the mapping.

1. `ecr` is an IR gate.  The QASM reader uses it natively (instead of
   inlining the file's `rzx`-based definition into 4 CNOTs) once the
   definition is checked to be equivalent.  It also aliases
   Qiskit-exported ECR variants such as `ecr_140451863465232`.
2. **ECR lowering variants.**  A search over the 24 × 24 single-qubit
   Cliffords finds 64 exact identities ECR = (P⊗Q)·CX·(R⊗S) per CNOT
   orientation.  The 8 cheapest per orientation form a (2 × 8) variant site
   for every ECR of the input, so the swarm decides how each ECR is exposed
   to the CNOT-level passes.
3. The usual sound passes and the 2-qubit resynthesis run on the same
   coupled pairs, so connectivity is preserved by construction.
4. **Native re-synthesis.**  Every CNOT is converted back to one ECR in the
   native direction of its pair.  Among the 64 exact Clifford wrappings, the
   one minimising the native cost of the two pending single-qubit runs is
   chosen greedily.  Each run is then written with the fewest {rz, sx, x}
   gates (1, 3 or 5; closed-form cost).
5. Objective: `twoq` = (#ECR, #gates, depth).  Equivalence is checked on the
   used qubits by simulation (≤ 20 qubits) or with MQT QCEC
   (`qcpso/bench/qcec_verify.py`) for larger circuits.

## 7b. HyPSO-QCO v2: swarm + memetic, connectivity-preserving resynthesis (ibm mode)

The comparison with related work on the supplied circuits
(`results/ibm_literature`) showed that the v1 pipeline removed few ECRs.
TKET's Clifford rewrite rules and GUOQ's resynthesis removed far more.
v2 keeps the swarm over compilation decisions and adds a **memetic phase**:
connectivity-preserving numerical resynthesis, applied to the swarm's elites
and tuned for anytime use under a wall-clock budget *T*.

**Phase 1 — swarm (25 % of *T*).**
* Genome: ECR lowering variants (§7), plus a *lowering-mode* gene (per-ECR
  variants, or the exact greedy ECR→CX conversion `native.to_cx`), plus pass
  schedule genes.
* The pass library now also contains `tket`: the fixed point of TKET's
  `KAKDecomposition` and `CliffordSimp`, both with `allow_swaps=False`
  (`passes/tket_bridge.py`).
  * These passes never create a new qubit interaction.
  * TKET's `SynthesiseTket` is deliberately excluded: its single-qubit
    squashing dropped a small rotation `rz(3.8e-4)` on `qae_17`, a
    3.8e-4 error.
  * Every TKET result is **checked by simulation** and discarded if it
    deviates by more than 1e-9.
    * Circuits with ≤ 20 used qubits are checked whole, in 6,000-gate
      chunks when large.
    * Wider circuits are processed inside convex blocks of ≤ 10 qubits,
      each checked separately.  On `hubbard_18`, 465 blocks were checked
      and none was rejected.
  * The decoder applies `tket` only to exact circuits, before any
    numerically synthesised block.
* Three elite seeds: the greedy schedule; greedy ECR→CX conversion + TKET +
  greedy schedule; variant lowering + TKET + greedy schedule.
* Evaluation batches respect the phase deadline.
* In time-limited runs on circuits with more than 50,000 gates, one decode
  takes minutes, so the swarm phase is skipped and the strongest seed starts
  phase 2.

**Phase 2 — memetic resynthesis (remaining time, `memetic.py`,
`passes/resynth.py`).**  Each *round*:

1. **Partition** the current {1q, CX} circuit into convex blocks of at most
   *k* qubits (*k* = 3, 4 or 5).  A greedy scan keeps every qubit "open" in
   at most one block and merges open blocks only while the union fits.
   * Variations expose different blocks in later rounds: forward or
     reverse scan, random forced cuts, and block size.
   * Blocks are re-inserted by contracting the DAG and topologically
     re-linearising it.  This is correct for either scan direction, and a
     non-convex block would show up as a cycle.
2. **Resynthesise each block by CNOT deletion.**
   * Template: V(x) = L_m…L_1 L_0, where L_0 is a layer of U3 gates and each
     L_j is (U3⊗U3)·CX_j over the block's own CNOT skeleton.  Only existing
     CNOTs are ever deleted, so the device mapping is preserved by
     construction.
   * The exact initial parameters come from folding every single-qubit run
     into the U3 slot after the preceding CNOT on its qubit.
   * Deletion is tried CNOT by CNOT in two sweeps (backward, then forward),
     keeping every success.  After each deletion the parameters are
     re-instantiated by Levenberg–Marquardt with an analytic, vectorised
     Jacobian.
   * The solver starts from the previous solution (the "warm start").  It
     aborts on stagnation: successful runs converge in about 11 iterations
     (median), and failures stall.
   * A deletion is accepted if ‖V(x) − e^{iφ}U‖_F < 1e-10.
   * Deletions that would violate a lower bound are skipped.  The bound:
     one CNOT at most doubles the operator Schmidt rank across a
     single-qubit cut.
   * *Long 3-qubit blocks* (more than 20 CNOTs) are first refitted to a
     generic alternating 20-CNOT template on the block's two coupled pairs.
     This took `hhl_8` from 2,377 to 507 CNOTs in 36 s instead of 860 s.
   * *Deep* strategy: two random restarts per deletion, plus deletion of
     CNOT pairs on the same qubit pair (an odd number of CNOTs across a cut
     can never be non-entangling).
3. **Z-slot sparsification.**  Each U3 slot of a resynthesised block is
   tentatively restricted to an Rz and the rest re-instantiated from the
   warm start.  Rz is virtual on IBM hardware.  On `mult_8` this removed
   28 % of the physical single-qubit gates.
4. **Exact clean-up passes**, then accept the round if the CNOT count did
   not increase.

Other features of phase 2:
* Block results are memoised by the block's gate list, so repeated
  partitions are cheap.  Blocks are processed largest first in a process
  pool.
* The next strategy is chosen by adaptive operator selection: probability
  matching on CNOTs saved per second, over the 12 (direction, cuts, size,
  restarts) strategies.
* The phase first refines up to three distinct swarm elites, each until it
  stalls (every strategy has failed twice in a row).  It then *deepens* the
  best circuit with blocks of up to 5 qubits until *T* expires.
* The swarm's diversity therefore pays off here: different starting
  representations lead to different local optima (for example `mult_8`:
  173 CNOTs from one seed, 161 from the swarm's elite).

**Soundness.**
* Phase 1 is exact.  Its only external pass (TKET) is checked by
  simulation, as described above.
* Phase 2 is numerically exact per block (Frobenius residual < 1e-10).
* Two run-time safety nets guard phase 2:
  1. every replaced block's emitted gate list is re-simulated and compared
     with the original block (tolerance 1e-8);
  2. for circuits with ≤ 20 used qubits, every accepted memetic round is
     checked against its predecessor by a random-state test (tolerance 1e-7).
* A rejected step is logged and skipped.  No step was rejected in the final
  runs.
* The contraction-based rebuild makes block replacement correct for any
  convex block.
* Every output is re-verified independently afterwards: statevector
  simulation for ≤ 20 used qubits, and the Choi-state MPS miter for larger
  circuits where it converges.

## 8. Complexity

One evaluation = lowering + a constant number of linear-time passes (the
commutation scans are bounded by wire length), i.e. roughly
O(|C| · w), where w is a small window factor.  KAK resynthesis is
memoised per block unitary.  Memory is O(|C| + S·D) for S particles and D
genes (D ≈ 3·#Toffolis + #rotations (capped) + slots + n_phys + 4).

## 9. Using the framework

```python
from qcpso.io import load, save_qasm
from qcpso.framework import optimize, HyPSOConfig
from qcpso.pso.engine import PSOParams

circ = load("benchmarks/barenco_tof_5.qasm")
res = optimize(circ, HyPSOConfig(mode="cliffordt", pso=PSOParams(max_evals=1000, seed=0)))
print(res.summary())
save_qasm(res.circuit, "barenco_tof_5.opt.qasm")
```

```
python -m qcpso optimize in.qasm -o out.qasm --mode continuous --budget 1000
python -m qcpso optimize in.qasm --mode hardware --device ibm_tokyo
python -m qcpso bench --suite path/to/benchmarks --mode cliffordt --seeds 5 --budget 1000
```

Ablation switches (runner method names): `hypso_novar`, `hypso_noplace`,
`hypso_nosched`, `hypso_nomemetic`, `hypso_unguided`, `hypso_eager` (placement genes not lazy),
`hypso_ls4` (smaller local search), `hypso_relaxed`
(continuous relaxation instead of categorical PSO), `hypso_spso`,
`hypso_qpso`, `hypso_gbest`, `hypso_noseed`.
