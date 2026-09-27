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

## 7. Complexity

One evaluation = lowering + a constant number of linear-time passes (the
commutation scans are bounded by wire length), i.e. roughly
O(|C| · w), where w is a small window factor.  KAK resynthesis is
memoised per block unitary.  Memory is O(|C| + S·D) for S particles and D
genes (D ≈ 3·#Toffolis + #rotations (capped) + slots + n_phys + 4).

## 8. Using the framework

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
