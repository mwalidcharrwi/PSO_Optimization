# Related work: quantum circuit optimisation and particle swarm optimisation

This survey positions **HyPSO-QCO** (see [FRAMEWORK.md](FRAMEWORK.md)) with respect to
five bodies of work: (1) rule-based and phase-polynomial circuit optimisers,
(2) ZX-calculus methods, (3) search-, learning- and synthesis-based
optimisers, (4) qubit mapping/routing, and (5) swarm / evolutionary
computation applied to quantum circuits.  The last section distils the
research gaps that motivate the proposed framework.

> Note: the paper referenced in the task description was not attached to the
> conversation, so this survey is built from the open literature.  Once the
> paper is provided, its method can be added as an explicit baseline (the
> `qcpso.pso.baselines` module is designed for that).

---

## 1. Rule-based, peephole and phase-polynomial optimisation

| Work | Idea | Relevance to HyPSO-QCO |
|---|---|---|
| Maslov, Dueck, Miller & Negrevergne, *Quantum circuit simplification and level compaction*, IEEE TCAD 2008 | Template/peephole rewriting with commutation | Our commutation-aware cancellation pass follows this line |
| Abdessaied, Soeken & Drechsler, *Quantum circuit optimization by Hadamard gate reduction*, RC 2014 | Rules that remove Hadamards | Used in our H-reduction pass |
| Nam, Ross, Su, Childs & Maslov, *Automated optimization of large quantum circuits with continuous parameters*, npj QI 2018 | Hadamard reduction, single/two-qubit cancellation with commutation, rotation merging over {CNOT, Rz} sub-circuits; **Toffoli polarity chosen greedily**; standard benchmark suite | Our deterministic core ("greedy") is Nam-style; HyPSO turns the greedy choices (Toffoli polarity, networks, rotation placement, pass order) into a *global* search |
| Amy, Maslov & Mosca, *Polynomial-time T-depth optimization via matroid partitioning* (Tpar), IEEE TCAD 2014 | Phase polynomials, phase folding | Our phase folding generalises it to the *path-sum* view with **free placement** |
| Amy & Mosca, *T-count optimization and Reed–Muller codes*, IEEE TIT 2019; Heyfron & Campbell, *An efficient quantum compiler that reduces T count* (TODD), QST 2018 | T-count minimisation via coding theory | Orthogonal; could be added as a pass |
| Amy, Azimzadeh & Mosca, *On the CNOT-complexity of CNOT-phase circuits* (Gray-synth), QST 2018; Patel, Markov & Hayes, *Optimal synthesis of linear reversible circuits* (PMH), QIC 2008 | CNOT-network re-synthesis | Candidate future pass (see RESEARCH_DIRECTIONS) |
| Amy, *Towards large-scale functional verification of universal quantum circuits* (path sums / Feynman), QPL 2018 | Path-sum representation | Justifies the soundness of our global phase folding |
| Iten, Moyard, Metger, Sutter & Woerner, *Exact and practical pattern matching for quantum circuit optimization*, ACM TQC 2022 | Template matching (in Qiskit) | Rule-based baseline family |
| Hietala, Rand, Hung, Wu & Hicks, *A verified optimizer for quantum circuits* (VOQC), POPL 2021 | Formally verified Nam-style passes | Motivates our equivalence-by-construction design |
| Sivarajah et al., *t\|ket⟩: a retargetable compiler for NISQ devices*, QST 2020; Javadi-Abhari et al., *Quantum computing with Qiskit*, 2024 | Industrial compilers (FullPeepholeOptimise, O3) | Used as baselines (`qcpso.bench.external`) |
| Maslov, *Advantages of using relative-phase Toffoli gates…*, PRA 2016; Amy, Maslov, Mosca & Roetteler, *A meet-in-the-middle algorithm…*, IEEE TCAD 2013 | Alternative Toffoli decompositions (T-depth, relative phase) | Our BFS-enumerated variant library is a systematic extension |

**Gap.** Every rule-based optimiser makes *local, greedy, order-dependent*
decisions (which decomposition, where a merged rotation goes, which pass
runs first).  Nam et al. already observed that the Toffoli polarity matters
and fixed it greedily; nobody searches these coupled decisions *jointly*.

## 2. ZX-calculus

* Duncan, Kissinger, Perdrix & van de Wetering, *Graph-theoretic simplification of quantum circuits with the ZX-calculus*, Quantum 2020.
* Kissinger & van de Wetering, *Reducing the number of non-Clifford gates in quantum circuits*, PRA 2020; *PyZX*, QPL 2019.
* Riu et al., *Reinforcement learning based quantum circuit optimization via ZX-calculus*, Quantum 2025.
* *Quantum circuit optimization based on dynamic grouping and ZX-calculus for reducing 2-qubit gate count*, arXiv:2507.14434 (2025).

ZX methods reach excellent T-counts but circuit *extraction* often inflates
the CNOT count (reproduced by our PyZX baseline).  HyPSO-QCO reaches the same
T-count through phase folding while keeping the circuit structure, which
avoids the extraction penalty.

## 3. Search-, learning- and synthesis-based optimisation

| Work | Search space / method |
|---|---|
| Xu et al., *Quartz: superoptimization of quantum circuits*, PLDI 2022 | Automatically generated rewrite rules + cost-based backtracking search |
| Xu, Molavi, Pick, Tannu & Albarghouthi, *Synthesizing quantum-circuit optimizers* (QUESO), PLDI 2023 | Synthesised rewrite rules, beam search |
| Xu, Molavi, Tannu & Albarghouthi, *Optimizing quantum circuits, fast and slow* (GUOQ), ASPLOS 2025 | Simulated-annealing-like random walk over rewrite rules + unitary resynthesis |
| Li et al., *Quarl: a learning-based quantum circuit optimizer*, OOPSLA 2024 | Reinforcement learning over rewrites |
| Wagner, Xu, Liu, Jia & Acar, *QALM: escaping local minima via interleaved exploration and exploitation*, arXiv:2606.16221 (2026) | Interleaves search with rule-based optimisation |
| *Local optimization of quantum circuits* (extended version), arXiv:2502.19526 (2025) | Local (windowed) optimisation of large circuits |
| Fösel, Niu, Marquardt & Li, *Quantum circuit optimization with deep reinforcement learning*, arXiv:2103.07585 | RL agents applying local transformations |
| Ruiz et al., *Quantum circuit optimization with AlphaTensor*, Nature Machine Intelligence 2025 | T-count via tensor decomposition + RL |
| Kremer et al., *Practical and efficient quantum circuit synthesis and transpiling with RL*, arXiv:2405.13196 | RL synthesis/routing |
| Shende, Markov & Bullock, *Minimal universal two-qubit CNOT-based circuits*, PRA 2004; Vatan & Williams, PRA 2004 | Optimal 2-qubit CNOT counts (used in our KAK pass) |
| Davis et al., *Towards optimal topology aware quantum circuit synthesis* (QSearch), QCE 2020; Younis et al., *QFAST*, QCE 2021; Smith et al., *LEAP*, ACM TQC 2023 | Numerical instantiation-based synthesis (BQSKit) |

**Pass-order / compiler autotuning.** Quetschlich, Burgholzer & Wille,
*Compiler optimization for quantum computing using reinforcement learning*,
DAC 2023; *Reinforcement learning for adaptive composition of quantum circuit
optimisation passes*, arXiv:2601.21629; *QuTuner*, arXiv:2607.04586;
*TuniQ*, arXiv:2605.11375; *MQSS-Selector*, arXiv:2609.30104.  These tune
*which passes run*, but not the decisions *inside* passes (decomposition
variants, rotation placement) nor the hardware layout jointly.

**Gap.** Superoptimisers search the circuit space with local moves
(annealing, beam search, RL).  They must re-verify or rely on verified rules,
and their moves are myopic.  Population-based, *socially learning* search
over *compilation decisions* has not been explored.

## 4. Qubit mapping and routing

* Siraichi et al., *Qubit allocation*, CGO 2018.
* Zulehner, Paler & Wille, *An efficient methodology for mapping quantum circuits to the IBM QX architectures*, IEEE TCAD 2019.
* Li, Ding & Xie, *Tackling the qubit mapping problem for NISQ-era quantum devices* (SABRE), ASPLOS 2019; Zou et al., *LightSABRE*, arXiv:2409.08368.
* Cowtan et al., *On the qubit routing problem*, TQC 2019.
* Tan & Cong, *Optimal layout synthesis for quantum computing* (OLSQ), ICCAD 2020.
* Zhou, Li & Feng, *Quantum circuit transformation based on simulated annealing and heuristic search*, IEEE TCAD 2020.
* Liu et al., *Tackling the qubit mapping problem with permutation-aware synthesis*, arXiv:2305.02939.
* *Quantum circuit mapping based on discrete particle swarm optimization and deep reinforcement learning*, Swarm and Evolutionary Computation, 2025: discrete PSO (sorting selection) for the **initial layout** + DDQN gate scheduling.

**Gap.** Layout, routing heuristics and gate decomposition are optimised in
separate stages.  The decomposition of a Toffoli fixes which qubit pairs
interact; choosing it *together with* the layout (e.g. a nearest-neighbour
8-CNOT network when the three qubits lie on a line) has not been
co-optimised by a single swarm.

## 5. Swarm and evolutionary computation for quantum circuits

**PSO foundations.** Kennedy & Eberhart, ICNN 1995; Shi & Eberhart
(inertia weight), 1998; Clerc & Kennedy (constriction), IEEE TEVC 2002;
Kennedy & Eberhart (binary PSO), 1997; Kennedy & Mendes (neighbourhood
topologies), CEC 2002; Sun, Feng & Xu (quantum-behaved PSO), CEC 2004; Liang
et al. (CLPSO), IEEE TEVC 2006; Zhan et al. (adaptive PSO), IEEE TSMC-B
2009; Chen et al. (set-based PSO for discrete problems), IEEE TEVC 2010;
Strasser et al. (integer & categorical PSO), GECCO 2016; Tizhoosh
(opposition-based learning), 2005; O'Neill & Brabazon (grammatical swarm),
Natural Computing 2006.

**PSO / swarms applied to quantum circuits.**

| Work | Encoding | Scale / limitation |
|---|---|---|
| Hidayat & Cheah, *Particle Swarm Optimization for Quantum Circuit Synthesis: Performance Analysis and Insights*, arXiv:2507.02898 (2025) | Circuit gates/qubits encoded directly as particle coordinates; fitness = task success (MaxOne); compares inertia/learning factors and a GA | Few qubits, fidelity-based fitness, synthesis of small circuits |
| *Advanced swarm intelligence algorithms in quantum circuit design*, Int. J. Parallel, Emergent & Distributed Systems 40(1), 2025; *iSOMA swarm intelligence algorithm in synthesis of quantum computing circuits*, Applied Soft Computing 2023 | iSOMA, DE, PSO, GWO, ACO on parameterised circuits (Friedman/Nemenyi comparison) | Small parameterised circuits |
| *Quantum program synthesis: swarm algorithms and benchmarks*, EuroGP 2019 | Swarm algorithms for program synthesis | Small programs |
| Datta, Sengupta et al., *PSO-based reversible circuit synthesis using mixed control Toffoli gates*, J. Low Power Electronics 2013; *Reversible logic circuit synthesis using GA and PSO*, IEEE 2012 | Toffoli networks encoded as particles | Reversible (classical) functions, small n |
| *Quantum circuit mapping based on DPSO and DRL*, SWEVO 2025 | Permutation (layout) | Mapping only |
| Williams & Gray 1998; Spector et al. 1999; Lukac & Perkowski 2002 | GA/GP evolving circuits | Small circuits |
| PSO/swarms for variational circuits (VQE/QAOA parameter training) | Continuous angles | Parameter training, not gate optimisation |

**Gap.** Existing PSO approaches (i) search the *circuit space directly*,
so candidates are generally *not* equivalent to the target and the fitness
is a fidelity estimate that needs exponential simulation, limiting them to
a handful of qubits; (ii) use a *continuous relaxation* of inherently
nominal decisions; (iii) have no mechanism to align genes across particles
when the decoded structure changes; and (iv) optimise one stage (synthesis
**or** layout) in isolation.

## 6. Research gaps addressed by HyPSO-QCO

| # | Gap in the literature | HyPSO-QCO answer |
|---|---|---|
| G1 | PSO for circuits searches circuit space → approximate, tiny circuits | **Equivalence-by-construction**: particles encode decisions of a sound optimisation program; every candidate is exactly equivalent (verified), and circuits with thousands of gates are optimised |
| G2 | Greedy, order-dependent decisions in rule-based optimisers | Joint swarm search over **decomposition variants, rotation placement and pass schedule** |
| G3 | Unordered decisions modelled with continuous relaxations | **Categorical (probability-vector) PSO** for nominal genes + hybrid SPSO/QPSO for continuous genes |
| G4 | Social learning breaks when gene semantics shift between particles | **Provenance-aligned genome**: genes keyed by input-gate provenance and *semantic role* (e.g. "parity a⊕b of Toffoli 17") |
| G5 | Blind mutation in large decision spaces | **Provenance-guided memetic search**: credit assignment from the decoded circuit (which sites' gates survived) |
| G6 | Decomposition, layout and routing optimised in isolation | **Hardware co-optimisation** of Toffoli networks (incl. nearest-neighbour variants), random-key layout and router hyper-parameters in one swarm |
| G7 | Fixed placement of merged phases | **Free rotation placement** proven sound through the path-sum argument |
| G8 | Numerical resynthesis gets stuck in local minima | **Swarm instantiation** (PSO + Levenberg–Marquardt) for block resynthesis |
