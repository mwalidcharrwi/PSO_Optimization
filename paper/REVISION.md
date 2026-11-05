# Revision of the DAC paper: replacement text, tables and figures

All numbers below come from `results/ibm_revision` (revision runs) and
`results/ibm_literature` (TKET, QUESO and the original runs), via

    python -m qcpso.bench.report_revision > results/ibm_revision/REPORT_TABLES.md
    PYTHONPATH=. python paper/rev_figs.py

Placeholders of the form ⟨…⟩ are filled in after the last runs.

## 0. What changed, item by item

| reviewer item | done | where |
|---|---|---|
| BQSKit deletion baseline, same budget and cores, all ten circuits | yes | V (Tools), Table I, VI-A |
| GUOQ 60 min on all ten circuits | yes | Table I, VI-B, Fig. 4 |
| three seeds for both tools on the seven smaller circuits, mean ± sd | yes | Table I, VI-A, VII |
| two GUOQ runs in parallel | yes (two jobs, ≈ 2 cores each) | V (Protocol) |
| resynthesis-only pre-specified; post-hoc caveat removed | yes | V (Protocol), VI-D |
| TKET → GUOQ on the three large circuits | yes | Table I, VI-B |
| Z-slot sparsification off, once per small circuit | yes | VI-D |
| IBM AI synthesis passes | ⟨run / sentence⟩ | V (Tools), VI-A |
| N for Proposition 1(c) | yes | IV-D, VI-F |
| larger figure fonts | yes (all figures drawn at printed size, 8 pt) | `paper/figures_rev/` |
| anytime plot instead of part of the RQ3 text | yes | VI-C, Fig. 4 |

## 1. Abstract (replace from "On ten circuits …" to the end)

> On ten circuits transpiled by Qiskit at optimisation level 3 for a
> 127-qubit IBM Eagle device (1,898 to 357,535 gates), HyPSO-QCO, in a
> resynthesis-only configuration fixed before the runs, used the fewest
> two-qubit (ECR) gates of all evaluated tools on every circuit within
> 15 minutes. Over three seeds, it removed 33.4% of the ECR gates on
> average, against 21.5% for GUOQ with a four times longer budget of
> 60 minutes, 8.9% for BQSKit's deletion-only workflow, 4.1% for TKET and
> 0.1% for QUESO (one-sided Wilcoxon p = 0.001 against each). Its worst
> seed beat GUOQ's best run on each of the seven smaller circuits, it passed
> GUOQ's 60-minute result after a median of 1.2 minutes, and every checked
> output was numerically exact (deviation at most ⟨D⟩).

## 2. Introduction

**Replace** "Second, it must scale: … in 35 minutes." **by**

> Second, it must scale: GUOQ reduced the ECR count of our two largest
> benchmarks (93,235 and 357,535 gates) by at most 0.4% in 15 minutes and
> 0.7% in 60 minutes, and BQSKit's deletion-only workflow deleted at most
> 0.9% of their remaining CNOT gates.

**Replace** the third contribution by

> • Evaluation under one contract (Section VI). On ten circuits transpiled by
> Qiskit O3 for IBM Eagle, with up to 357,535 gates, HyPSO-QCO used the
> fewest ECR gates of TKET, QUESO, BQSKit and GUOQ on every circuit
> (Fig. 1), over three seeds, against GUOQ with a four times longer budget
> and against TKET followed by GUOQ, and produced numerically exact outputs.
> Ablations locate the gains in the memetic phase on mapped circuits and in
> the variant search on logical circuits.

**Fig. 1:** `paper/figures_rev/rev_fig1_mean_reduction.pdf` (column width,
drawn at printed size). Caption:

> Fig. 1. Mean reduction beyond Qiskit O3 over the ten IBM Eagle benchmarks
> (15 min per circuit for the anytime tools; GUOQ also with 60 min;
> HyPSO-QCO and GUOQ: mean of three seeds on the seven smaller circuits).
> HyPSO-QCO used the fewest ECR gates on all ten circuits (one-sided
> Wilcoxon p = 0.001 against each tool).

## 3. Section II-B, Related Work (one sentence added at the end of "Numerical resynthesis")

> We compare against BQSKit's deletion-only workflow, the closest baseline,
> under the same budget and cores.

## 4. Section IV-D, after "so N accepted block replacements contribute less than N·10⁻¹⁰"

**Add**

> In our runs, N ranged from 39 (add_17) to 1,209 (grover_10), and the
> re-simulated block errors sum to at most 2.2 × 10⁻⁸ for every output.
> In large mode, the seed's 111 and 465 TKET blocks (heisenberg_32,
> hubbard_18) add 3.5 × 10⁻¹¹ and 9.2 × 10⁻¹¹ (computed exactly from the
> saved blocks).

## 5. Section V, Experimental Setup

**Tools — replace** "BQSKit [11] at optimisation level 3 did not finish
mult_8 in 35 minutes;" **by**

> BQSKit [11] (1.2.1) ran its deletion-only workflow (partitioning,
> ScanningGateRemovalPass per block, unfolding) on four workers with the
> same 15-minute budget. It sweeps the circuit while the gate count falls
> and, at a fixed point, grows the blocks from three to four and five
> qubits, so the whole budget is used. Its acceptance threshold bounds a
> block's Hilbert–Schmidt cost, which grows with the square of the operator
> error: at the default 10⁻⁸, its output for heisenberg_8 deviated by
> 1.4 × 10⁻⁴ (402 ECR gates). We therefore used 10⁻¹⁵, the tightest value
> above rounding (399 ECR gates, deviation 3.5 × 10⁻⁸), and instantiation
> level 1, which beat level 2 in a pilot on mult_8 (221 against 246 ECR
> gates). BQSKit needs fused single-qubit gates to re-instantiate, so it
> received the circuit after HyPSO-QCO's exact final stage (optimal
> two-qubit resynthesis, cancellation and U3 fusion), which alone removes
> 0–12% of the CNOTs (hubbard_18: 33,958 to 29,903) and can only favour
> BQSKit. On hhl_8, its first 3,000-gate chunk did not finish one sweep in
> 15 minutes, so it ran with 500-gate chunks. Deleting gates cannot couple
> new pairs, so its outputs satisfy the contract.
> ⟨IBM AI sentence⟩ BQSKit's level-3 flow did not finish mult_8 in
> 35 minutes; PyZX and VOQC do not preserve connectivity, and Quarl needs a
> trained GPU model.

**IBM AI sentence (if the run gives usable numbers):**

> IBM's AI synthesis passes [21], [22] (qiskit-ibm-transpiler 0.18, local
> models) re-synthesised Clifford, linear-function and permutation blocks
> after IBM's collection passes, with a coupling map restricted to the
> input's coupled pairs; its Pauli-network synthesis is excluded, because
> its local output was not equivalent to its input (mult_8: 67 CNOTs
> instead of 311).

**TKET → GUOQ, add after the GUOQ sentence:**

> On the three large circuits, we also ran GUOQ on TKET's output for the
> rest of the 15 minutes (TKET→GUOQ).

**Configurations and protocol — replace the paragraph by**

> Configurations and protocol. Before these runs, we fixed resynthesis only
> as the configuration for mapped circuits: phase 2 receives the whole
> budget T = 900 s with four workers and starts from the strongest
> deterministic seed (above 50,000 gates, this is large mode, unchanged).
> HyPSO-QCO and GUOQ ran with three seeds on the seven smaller circuits and
> one seed on the three large ones; GUOQ also ran for 60 minutes, its
> authors' budget, on all ten circuits, and its first seed's 15-minute
> result is the 15-minute snapshot of that run. All runs used one four-core
> container (Intel Xeon, 2.8 GHz, 15 GB): HyPSO-QCO and BQSKit ran alone with
> four workers, and GUOQ, whose search is single-threaded, ran two jobs at a
> time with about two cores each. Every anytime tool had 15 minutes per
> circuit, which for HyPSO-QCO includes decoding and native conversion; TKET
> ran to completion (2–244 s). The 1-worker and full (swarm) configurations
> of Section VI-B and VI-D ran with seed 0.

**Verification — unchanged**, add at the end:

> GUOQ's and BQSKit's outputs were checked in the same way.

## 6. Table I (replace)

LaTeX: `paper/tables_rev.tex` (generated). Content (ECR / total native
gates; mean ± sd of the ECR count over three seeds where given; generated
by `python -m qcpso.bench.report_revision --latex paper/tables_rev.tex`):

| circuit | q | input (Qiskit O3) | TKET | QUESO | BQSKit del. | GUOQ 15 min | GUOQ 60 min | TKET→GUOQ | HyPSO-QCO | margin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 8 | 311 / 1,898 | 299 / 1,402 | 311 / 1,337 | 221 / 956 | 200 ± 8 / 1,210 | 191 / 1,192 | -- | **155 ± 2** / **796** | 18.8% |
| heisenberg_8 | 8 | 420 / 2,127 | 420 / 1,455 | 420 / **1,217** | 399 / 1,270 | 326 ± 9 / 1,606 | 322 / 1,652 | -- | **265 ± 8** / 1,229 | 17.7% |
| add_17 | 17 | 499 / 2,812 | 495 / 2,203 | 499 / 2,108 | 470 / 1,891 | 415 ± 4 / 1,987 | 414 / 1,907 | -- | **391 ± 2** / **1,676** | 5.5% |
| qae_17 | 17 | 541 / 3,033 | 537 / 2,368 | 541 / 2,301 | 501 / 2,063 | 430 ± 7 / 2,093 | 436 / 2,143 | -- | **416 ± 1** / **1,785** | 3.3% |
| qft_16 | 16 | 614 / 3,444 | 610 / 2,651 | 614 / 2,691 | 583 / 2,253 | 532 ± 4 / 2,494 | 529 / 2,447 | -- | **514 ± 7** / **2,149** | 2.9% |
| hubbard_8 | 8 | 1,344 / 8,125 | 1,251 / 5,174 | 1,336 / 6,204 | 1,243 / 5,057 | 1,138 ± 8 / 4,760 | 1,130 / 4,654 | -- | **852 ± 38** / **3,336** | 24.6% |
| hhl_8 | 8 | 2,377 / 18,165 | 2,365 / 14,780 | 2,377 / 16,069 | 2,150 / 13,316 | 475 ± 16 / 2,805 | 468 / 2,742 | -- | **291 ± 8** / **1,618** | 37.7% |
| heisenberg_32 | 32 | 3,942 / 58,848 | 3,834 / 14,100 | 3,942 / 14,544 | 3,808 / 14,495 | 3,805 / 14,438 | 3,719 / 13,923 | 3,741 / 14,175 | **3,325** / **12,678** | 10.6% |
| grover_10 | 10 | 16,397 / 93,235 | 14,453 / 57,497 | 16,397 / 74,687 | 15,860 / 56,549 | 16,392 / 72,828 | 16,380 / 71,699 | 14,445 / 56,972 | **12,163** / **54,671** | 15.8% |
| hubbard_18 | 31 | 33,958 / 357,535 | 29,547 / 112,902 | 33,926 / 131,273 | 29,690 / 129,229 | 33,829 / 131,019 | 33,727 / 130,582 | 29,543 / 112,898 | **27,224** / **104,737** | 7.8% |
| mean reduction |  | -- | 4.1% / 36.2% | 0.1% / 33.7% | 8.9% / 43.2% | 20.8% / 43.5% | 21.5% / 44.1% | 10.0% / 61.1% (3) | 33.4% / 56.0% | 14.5% |

Margin: ECR reduction of HyPSO-QCO (mean) relative to the best other result on
the circuit at any budget (mean 14.5%).

Caption:

> TABLE I. ECR / total native gate count after re-optimisation (15 min per
> circuit for the anytime tools, GUOQ also 60 min; mean ± sd of the ECR count
> over three seeds on the seven smaller circuits, one seed on the large
> ones; T→G: TKET followed by GUOQ; fewest ECR gates and fewest total gates
> in bold). The input is Qiskit O3's transpilation for a 127-qubit IBM Eagle
> device; q: used qubits. Margin: ECR reduction of HyPSO-QCO relative to the
> best other result on the circuit at any budget. HyPSO-QCO won on all ten
> circuits against each tool in ECR gates (one-sided Wilcoxon p = 0.001).

## 7. Section VI, Results

### A. RQ1: Comparison with Related Tools (replace the first paragraph)

> HyPSO-QCO used the fewest ECR gates on all ten circuits (Table I).
> Beyond Qiskit O3, it removed 33.4% of the ECR gates on average (three
> seeds on the seven smaller circuits), against 20.8% for GUOQ (three
> seeds), 8.9% for BQSKit's deletion-only workflow, 4.1% for TKET and 0.1%
> for QUESO (geometric-mean ECR ratio 0.601, against 0.736 for GUOQ), and
> won on all ten circuits against each tool (p = 0.001). The seed-to-seed
> standard deviation was at most 4.5% of the mean (hubbard_8), and on each
> of the seven smaller circuits even HyPSO-QCO's worst seed used fewer ECR
> gates than GUOQ's best run of any length (closest: qft_16, 521 against
> 529). Its margin over the best other tool at 15 minutes ranged from 3.3%
> (qae_17) to 38.7% (hhl_8), 15.2% on average, and over the ten circuits it
> removed 14,807 ECR gates, against 6,592 for TKET, 5,478 for BQSKit, 2,860
> for GUOQ and 40 for QUESO.

Second paragraph ("It also led in total gates …"): keep, with the numbers
of Table I (HyPSO-QCO: 56.0% total gates, 52.5% physical single-qubit gates;
on heisenberg_8, QUESO still has fewer total gates, 1,217 against 1,229).

Third paragraph (large circuits): replace the numbers:

> … In large mode, HyPSO-QCO's seed applies the checked block-wise TKET pass
> and ends close to TKET; the memetic phase then removed the rest, so
> HyPSO-QCO used 7.9–15.8% fewer ECR gates than TKET and 7.8–15.8% fewer
> than TKET followed by GUOQ on the three largest circuits.

BQSKit paragraph (new, after the large-circuit paragraph):

> BQSKit's deletion-only workflow, the closest baseline to our memetic
> phase, removed 8.9% of the ECR gates on average; HyPSO-QCO used 27.1%
> fewer on average and won on all ten circuits (p = 0.001). With blocks of
> up to five qubits, it deleted 4.4–27.1% of the CNOTs that remained after
> its exact preprocessing on the six smaller circuits it could sweep
> repeatedly and 1.3% on heisenberg_32, but fewer than 1% on grover_10 and
> hubbard_18 and 5.2% on hhl_8, where one sweep with three-qubit blocks did
> not finish in 15 minutes. Deletion alone thus leaves much of the redundancy that
> HyPSO-QCO's exact start, warm-started fits and Z-slot sparsification
> remove.

Success-probability sentence (replace):

> Its outputs had the highest estimated success probability (Eq. (2)) on
> every circuit: from 0.0959 to 0.313 on mult_8 (GUOQ: 0.220 in 15 and
> 0.235 in 60 minutes), from 4.08 × 10⁻⁵ to 1.87 × 10⁻³ on hubbard_8
> (GUOQ: 2.38 × 10⁻⁴ in 60 minutes) and from 1.09 × 10⁻⁸ to 0.111 on
> hhl_8 (GUOQ: 0.0291 in 60 minutes).

### B. RQ2: Longer Budgets, Combined Baselines and Matched Compute (replace)

> A four times longer budget did not close the gap. In 60 minutes, GUOQ's
> mean ECR reduction rose from 20.8% to 21.5%, and HyPSO-QCO's 15-minute
> result still used fewer ECR gates on all ten circuits (Fig. 3(a); margin
> 2.9–37.7%, 16.8% on average, p = 0.001). Running GUOQ on TKET's output
> helped on the large circuits, where TKET is strong (grover_10: 14,445
> against 16,392 ECR gates), but HyPSO-QCO remained 7.8–15.8% ahead. Matched
> to GUOQ's single search thread, the full configuration with one worker
> beat GUOQ's 15-minute run of the first submission on six of seven
> circuits (mean ECR reduction 35.1% against 28.6%).

Fig. 3(a): `paper/figures_rev/rev_fig3a_vs_guoq.pdf`, caption:

> Fig. 3. (a) ECR gates fewer than GUOQ for HyPSO-QCO (15 min, mean of
> three seeds on the seven smaller circuits; error bars: sd), relative to
> GUOQ's 15-minute mean and its 60-minute run.

(Keep Fig. 3(b), the phase breakdown of the full configuration, if space
allows; otherwise drop it and keep the RQ4 numbers in the text.)

### C. RQ3: Anytime Behaviour (replace text and add Fig. 4)

> Fig. 4 shows the best ECR count over time. HyPSO-QCO's resynthesis
> removed most of its reduction in the first minutes and passed GUOQ's
> final 60-minute result after 0.4–4.0 minutes (median 1.2 over the 21
> runs), while GUOQ improved slowly and had nearly converged after
> 15 minutes (20.8% at 15 and 21.5% at 60 minutes). BQSKit's deletion
> stalled after its first sweeps on most circuits, and growing its blocks
> to four and five qubits gained a few more percent.

Fig. 4: `paper/figures_rev/rev_fig_anytime.pdf` (column width). Caption:

> Fig. 4. ECR gates left over wall-clock time, mean over the seven smaller
> circuits (HyPSO-QCO and GUOQ: mean of three seeds; dotted: GUOQ's
> 60-minute run). TKET runs in seconds.

(`rev_fig_anytime_per_circuit.pdf`, full width, is available for the
artifact appendix.)

### D. RQ4: Where the Improvement Comes From (replace the second paragraph and the Z-slot sentence)

> At a 15-minute budget, the swarm did not pay for itself on mapped
> circuits, which is why resynthesis only is the configuration for them.
> The full configuration of our first submission, with a swarm phase for
> 25% of the budget, lost to it on eight of ten circuits (mean ECR margin
> 3.8%, p = 0.005): the swarm lowers the starting point (mult_8: 311 to
> 280), but resynthesis alone passes that point within a minute.
>
> Z-slot sparsification. Without it (one seed, seven smaller circuits), the
> ECR count changed by −1.9% to +4.7%, but the outputs had 13.5–58.7% more
> physical single-qubit gates (sparsification removed 23.6% of them on
> average, and 23.2% of all gates).

(Delete: "As we identified this configuration after the runs, the headline
numbers use the configuration fixed beforehand; for mapped circuits at short
budgets, we recommend resynthesis only." and "Z-slot sparsification was not
ablated in isolation; the indirect evidence is …".)

### F. RQ6: Correctness (replace the first paragraph)

> Every checked HyPSO-QCO output was numerically exact: over the
> ⟨31⟩ revision outputs, the largest deviation was ⟨D⟩ (⟨circuit⟩), and
> heisenberg_32, checked with the MPS miter, deviated by ⟨⟩. TKET and
> QUESO were numerically exact too, and so was BQSKit with its tightened
> threshold (⟨⟩). GUOQ's outputs were approximate on ⟨heisenberg_8, hhl_8
> and, after TKET, grover_10⟩ (up to ⟨⟩); we kept them, which can only
> favour GUOQ. Behind each HyPSO-QCO output lie N = ⟨39–1,209⟩ accepted
> block replacements, whose re-simulated errors sum to at most 2.2 × 10⁻⁸,
> so Proposition 1(c) bounds the deviation of the unchecked hubbard_18
> output by ⟨1.3 × 10⁻⁸ + TKET blocks⟩.

Second paragraph (hubbard_18 not checked end to end, development defects):
keep.

## 8. Section VII, Threats to Validity (replace)

> Threats to validity. HyPSO-QCO and GUOQ ran three seeds on the seven
> smaller circuits; the three large circuits have one seed per tool. The
> seed-to-seed sd of HyPSO-QCO was at most 4.5% of the mean, and its worst
> seed beat GUOQ's best run on every smaller circuit, but the margins on
> qae_17 and qft_16 (about 3%) are small. GUOQ was patched to respect the
> mapping and QUESO used its authors' total-gate objective; GUOQ ran two
> jobs at a time while HyPSO-QCO and BQSKit ran alone, and the 1-worker run
> addresses the compute difference. BQSKit used a tighter acceptance
> threshold than its default, without which its outputs are not equivalent
> to their inputs. All benchmarks come from one device family and one
> transpiler, success probabilities are model estimates, and equivalence is
> established numerically, not symbolically.

## 9. Section VIII, Conclusion (replace the last two sentences)

> … it used the fewest ECR gates of all evaluated tools on every circuit,
> over three seeds and against GUOQ with four times its budget. Other
> devices and runs on hardware are the next steps. Code, circuits, outputs
> and logs are available at https://anonymous.4open.science/r/hypso-qco-dac27.

## 10. Figures

All revised figures are drawn at their printed width (column 3.5 in, full
7.16 in) in a Times-metric serif at 8 pt (ticks and legends 7.5 pt), so no
scaling in LaTeX is needed (`\includegraphics{…}` without `width=`):

| figure | file | width |
|---|---|---|
| Fig. 1 | `rev_fig1_mean_reduction.pdf` | column |
| Fig. 3(a) | `rev_fig3a_vs_guoq.pdf` | column |
| Fig. 4 | `rev_fig_anytime.pdf` | column |
| (appendix) | `rev_fig_anytime_per_circuit.pdf` | full |
