# Phase 6A evaluation protocol

| | |
|---|---|
| Protocol revision | **9** |
| Status | Written before any T1–T6 assertion is run. The formal experiment starts only after explicit mentor approval. |
| Catalogue | `phase6a-catalogue-v1` (`CATALOGUE_FREEZE.md`, `manifest.json`), frozen |
| Parameters | `evaluation/study_config.py` holds every numeric parameter and the seed schema stated here |
| Integrity | `evaluation/protocol.lock.json` records this file's SHA-256; every results file records the revision and hash |

This protocol consolidates the approved Phase 6A plan and every later mentor decision; where they
differ, the later decision applies.

Constraints: no change to `src/qmutate`, its API, report schema version 1 or the existing tests; no
Git repository or commits; no `#` comments in evaluation code; a library bug found during the study
is reported, not fixed inside Phase 6.

**Changes from revision 8** (fixes for findings F1 and F2 of the adversarial audit of the freeze
proposal of cycle `v2-r2`, which was rejected before approval; no scientific decision changed):

- 13 (F1): removing the seed files together with every seed history record made the seeds read as
  "not generated yet", so `make_seeds` would have passed its gate. A manifest written while seeds
  exist now records their SHA-256 (`seeds.sha256`), which ties them to the lock reported to the
  mentor. `--write` refuses if recorded seeds are missing, invalid or not the recorded file. The
  remaining limit, removal of every piece of evidence, is stated in section 13.
- 10 and 13 (F2): `make_seeds` wrote `seeds.json` directly, so an interruption could leave an empty or
  truncated file, which `--record-seeds` would then bind permanently. The seed file is now written
  through a synced, validated partial file and a hard link, and the directory is synced. The freeze
  check, `--write`, `--rebind-seeds` and `--record-seeds` accept `seeds.json` only if it is a valid
  seed file. Recovery from an interrupted generation is documented.
- 10: seed files of revisions 6 to 9 are accepted.
- The rejected proposal of cycle `v2-r2` (revision 8) is kept in `evaluation/freeze_history/v2-r2/rejected/`.

**Changes from revision 7** (fixes found by the read-only audit of freeze proposal v3, which was
rejected before approval; no scientific decision changed):

- 13: a missing or replaced `seeds.json` or `seeds.lock.json` could read as "seeds not generated yet",
  which approval, `make_seeds` and the study gate accepted. The freeze check now compares the live
  seed files with the **seed history** recorded under `evaluation/freeze_history/`, and
  `--record-seeds` records the first binding there (`SEEDS_RECORD.json`).
- 13: the freeze tool and `run_study` never remove a partial file. A leftover partial file is refused,
  the freeze check reports it, and the recovery keeps it as evidence in a `failed/` directory.
- 13: the code-freeze lock is validated explicitly (exactly `manifest`, `sha256` and `status`, and
  `manifest` naming `evaluation/code_freeze.json`). A lock or manifest of the wrong JSON type is a
  failed check, not an exception.
- 13: each `check_code_freeze` action runs on its own, so one invocation can no longer write and
  approve a freeze. Approval also requires both environments of section 14.
- 13: `--retire` refuses until the outgoing version of every changed covered file is archived as
  `.orig` (step 0). The new `--reject` sets a proposed freeze aside and makes the outgoing approved
  freeze live again. Full rollback, history directories and recovery for every failure state are
  documented.
- 10: seed files of revisions 6, 7 and 8 are accepted.
- Freeze proposal v3 (revision 7) is kept in `evaluation/freeze_history/v2/rejected/`.

**Changes from revision 6** (clarifies a real re-freeze gap; no scientific decision changed):

- 13: revision 6 did not define how to re-freeze once seeds exist. The only documented seed binding,
  `--record-seeds`, requires an approved freeze, so a re-freeze had to remove `seeds.json` and pass
  through an approved state without seeds, in which `make_seeds` would pass its gate. Revision 7
  adds an explicit, fail-closed re-freeze procedure. `--retire` archives the outgoing freeze, and
  `--rebind-seeds` re-binds the unchanged seeds before approval. `seeds.json` stays in place
  throughout.
- 10: the seed file records the protocol revision under which it was generated. Seed files of
  revisions 6 and 7 are accepted, because the slot schema is identical; a protocol revision never
  causes seeds to be regenerated.
- The pre-run record fix made with this revision (section 3 counts and the section 13 rule "every
  seed used") changes no protocol text.

**Changes from revision 5** (code freeze; no scientific decision changed):

- 13: a mandatory code-freeze check runs before any readiness or study execution, and before
  `make_seeds`. It requires an approved, fully passing freeze. The manifest is verified through a
  separate lock, with no self-referential hash, and seeds are bound to it by a seeds lock. Protected
  output paths are distinguished from content-hashed files.
- 13 and 16: every documented command sets `VECLIB_MAXIMUM_THREADS=1`. The setting is recorded in the
  freeze environment and in every results file's metadata, and the freeze check fails without it.
- 10: `make_seeds.py` refuses to run unless the code freeze is approved and verifies.

**Changes from revision 4** (independent review; no scientific decision changed):

- Appendix A: the 1e-10 slack is documented as a **heuristic engineering margin, not a proven
  floating-point error bound**. Two numerical assumptions behind the guarantee are stated.
- 13: output files are named by mode (`pre-run-*.json` or `run-*.json`) and written atomically. Every
  results file records SHA-256 hashes of the evaluation code, the qmutate source, the harness tests,
  `CATALOGUE_FREEZE.md` and `pyproject.toml`, and the post-run check compares them. Protected files,
  hash coverage and exit statuses are listed.
- Implementation corrected to match sections 4 and 5.4: suite tolerances are read from
  `study_config`, and the matched-suite baseline computes no p-values.
- 13 and 16: the driver refuses to start unless qmutate is imported from this project's
  `src/qmutate`, and every command sets `PYTHONPATH=src`. The temporary Qiskit 2.0.3 environment
  holds an outdated installed copy of qmutate.

**Changes from revision 3** (final pre-run audit):

- 5.4: the deduplicated result is described as a sensitivity analysis based on **approximate** state
  equivalence. The claim that T2–T5 pass/fail probabilities are equal is withdrawn. The approved
  matched-suite baseline is named as such.
- 5.4 and appendix A: the T6 grouping condition gets a full derivation, including phase alignment,
  tolerances, the comparison against the original circuit's state, and an explicit floating-point
  slack of 1e-10.
- 3: the 100,000-shot check is a readiness check only. It is kept apart from suite outcomes and never
  used for tuning. Pre-run exceptions are recorded as failed checks.
- 4 and 11: approved T1 semantics. T1 is invalid for a circuit whose original fails the execution
  check. A mutant or fault whose execution raises while the original passes counts as detected by T1.
- 13: the driver re-runs the integrity checks after the study and refuses to write if anything
  changed. Oracle exceptions in RQ3 are recorded.

Earlier revisions:
- **Revision 3:** suite-by-suite deduplication scope; T1 exception handling; pre-run stage contents; RQ4
  undefined scores; H3/H4 decidability; integrity checks and entry points.
- **Revision 2:** T1 shots and seed; seed reuse and execution order; RQ4 scope; exclusion of the T6
  UNITARY score; deduplication analysis; INCONCLUSIVE limitation; determinism rules; counts.

## 1. Research questions and hypotheses

| RQ | Question | Hypothesis |
|---|---|---|
| RQ1 | Does the adjusted removal mutation score rank suites the way their real-fault detection rate does? | H1 (7.6) |
| RQ2 | How much of each removal-mutant set is equivalent, `UNKNOWN` or skipped, and how far does adjustment move the score? | descriptive |
| RQ3 | How do T5's scores compare empirically with `distribution_oracle`'s? | H3: \|Δ_c\| ≤ 0.1 for at least 4 of 6 circuits |
| RQ4 | How stable are removal-mutant mutation scores of sampling suites when only the seed changes? | H4: range ≤ 0.1 for every circuit and sampling suite |

Each hypothesis is *supported*, *not supported* or *undecidable*. An unsupported hypothesis is a
research result, not an implementation failure; acceptance (section 15) does not depend on any
hypothesis outcome.

## 2. Layout

| Path | Role | State |
|---|---|---|
| `evaluation/preflight/catalogue.py` | Canonical frozen circuits, faults and hand-derived expected values | frozen |
| `evaluation/preflight/` (other files) | Preflight validation evidence | preserved, never rerun or written |
| `evaluation/circuits.py`, `evaluation/faults.py` | Stable interfaces over the canonical source | present |
| `evaluation/manifest.json`, `evaluation/check_catalogue.py`, `evaluation/CATALOGUE_FREEZE.md` | Freeze record and structural checks | present |
| `evaluation/PROTOCOL.md`, `evaluation/protocol.lock.json`, `evaluation/study_config.py`, `evaluation/check_protocol.py` | Protocol, its lock, its parameters and consistency checks | present |
| `evaluation/suites.py` | T1–T6 as oracles `oracle(circuit) -> None` | present |
| `evaluation/analysis.py` | Detection rates, groups, deduplicated rates, τ statistics, p-values, hypothesis rules | present |
| `evaluation/make_seeds.py` | Seed generation, once | present |
| `evaluation/seeds.json` | All seeds | generated at the formal run |
| `evaluation/run_study.py` | Single entry point for pre-run checks, runs and statistics | present |
| `evaluation/results/`, `evaluation/REPORT.md` | Results and report | after the run |
| `tests/test_evaluation_harness.py` | Harness tests on synthetic circuits only | present |

Hand-derived expected values stay in the canonical source and are exposed by `circuits.py`; T2 modes,
T3 supports and T4 marginals are derived from them in `study_config.py`, not restated.

## 3. Circuits and pre-run checks

The six circuits, the bit convention (qᵢ → cᵢ, keys c_{m−1}…c₀, statevector index k = Σqᵢ2ⁱ) and
the hand-derived expected distributions and states are those of the frozen catalogue. All circuits
are barrier-free.

Before any suite assertion, `run_study.py --pre-run-checks` performs, for each circuit:

| Source | Role | Rule |
|---|---|---|
| (a) hand derivation | reference, independent of the circuit code | — |
| (b) Qiskit `Statevector` with the study's own measurement mapping | built circuit produces (a) | largest probability difference ≤ 1e-12; state equals (a) up to global phase within 1e-12 |
| (c) qmutate `_ideal_distribution` (read-only) | qmutate's mapping agrees | largest probability difference ≤ 1e-12 |
| (d) 100,000 BasicSimulator shots, seed `pre_run/<circuit>` | partly independent statistical check | no outcome with p = 0 observed; TV(p̂, p) ≤ ε(100000, 2^m, 10⁻⁶): 0.01249 (k = 8), 0.01444 (k = 16) |

then classifies every fault (section 5.2) and computes the behaviour-equivalence groups of section
5.4. A failed pre-run check stops the study before any suite runs. An exception raised inside a
check is recorded with its type and counts as a failed check. `--pre-run-checks` stops after this
stage and writes its own results file.

The 100,000-shot check (d) is a **readiness check only**. Its counts are recorded in the pre-run
record and kept apart from every suite outcome. They are never used to tune circuits, faults,
thresholds or suites. A failure stops the study for mentor review; it never triggers an adjustment.

## 4. Test suites

Each suite is an oracle `oracle(circuit)`: it returns normally to pass and raises `AssertionError` to
fail. Sampling uses `qmutate.sample_counts` (BasicSimulator, no transpilation) with the suite's
primary seed (section 10).

| Suite | Check | Shots |
|---|---|---|
| T1 run | Execution completes and every count key has `num_clbits` bits. Checks execution and key format only, **not quantum correctness**. Inside the T1 oracle, an exception raised while BasicSimulator executes the circuit becomes an `AssertionError`. So a removal mutant or fault whose execution raises, while the original passes, is **detected** by T1 (the runner records `KILLED`, not `ERROR`). If the original itself fails, T1 is **invalid** for that circuit (section 11). | 16, fixed recorded seed |
| T2 mode | The expected mode is the **unique** most frequent outcome; a maximum shared by several outcomes fails | 1,000 |
| T3 support | Every observed outcome lies in the expected support | 100 |
| T4 marginal | \|p̂(bit = 1) − P_exp(bit = 1)\| ≤ 0.05 for the fixed bit below, with exact fractions | 4,000 |
| T5 distribution | TV(p̂, p_exp) ≤ 0.05 with exact fractions (all expected distributions are rational) | 8,000 |
| T6 state | `Statevector` of the circuit with final measurements removed equals the expected state up to global phase, max abs difference ≤ 1e-8 | none |

**Applicability matrix** (fixed; `study_config.APPLICABILITY`):

| Circuit | T1 | T2 | T3 | T4 bit, P_exp(1) | T5 | T6 | Suites |
|---|---|---|---|---|---|---|---|
| C1 | ✓ | ✗ two equal modes | ✓ {000, 111} | c₀, 1/2 | ✓ | ✓ | 5 |
| C2 | ✓ | ✓ `1011` | ✓ {1011} | c₀, 1 | ✓ | ✓ | 6 |
| C3 | ✓ | ✓ `111` | ✓ {111} | c₀, 1 | ✓ | ✓ | 6 |
| C4 | ✓ | ✓ `101` | ✗ full support | c₁, 1/32 | ✓ | ✓ | 5 |
| C5 | ✓ | ✗ uniform | ✗ full support | c₀, 1/2 | ✓ | ✓ | 4 |
| C6 | ✓ | ✗ four equal modes | ✗ full support | c₂, 3/4 | ✓ | ✓ | 4 |

**Invalid original suite.** Each applicable suite is first run on its original circuit with its
primary seed. If it fails or raises, the suite is excluded for that circuit, the exception is
recorded, it is reported as a protocol deviation, and nothing is tuned. No removal-mutant run or
fault evaluation is performed for an excluded suite. A `BaselineFailedError` from
`run_removal_mutants` is handled the same way.

## 5. Fault classification and real-fault detection

### 5.1 Catalogue counts (confirmed)

**70 faults; 57 D-NOT-EQUIVALENT; 13 D-EQUIVALENT; 17 `missing_gate`; 43 D-NOT-EQUIVALENT faults without
`missing_gate`.**

| Measure | C1 | C2 | C3 | C4 | C5 | C6 | Total |
|---|---|---|---|---|---|---|---|
| Faults | 12 | 11 | 11 | 12 | 12 | 12 | 70 |
| D-NOT-EQUIVALENT | 9 | 10 | 10 | 10 | 9 | 9 | 57 |
| D-EQUIVALENT | 3 | 1 | 1 | 2 | 3 | 3 | 13 |
| `missing_gate` | 2 | 3 | 3 | 2 | 4 | 3 | 17 |
| D-NOT-EQUIVALENT without `missing_gate` | 7 | 7 | 7 | 9 | 6 | 7 | 43 |

### 5.2 Classification

| Class | Rule | Effect |
|---|---|---|
| Invalid | Fault fails to build; or the pre-run execution check (BasicSimulator, 16 shots, seed `pre_run/<circuit>`, counts discarded) raises; or the exact model raises | excluded from every denominator, listed with the stage and error type (none in preflight) |
| D-EQUIVALENT | `check_equivalence(original, fault, IDEAL_DISTRIBUTION, atol=1e-8)` is `EQUIVALENT` | excluded from F_c |
| D-UNKNOWN | that check is `UNKNOWN` | excluded, reported with its reason, protocol deviation (none in preflight) |
| D-NOT-EQUIVALENT | that check is `NOT_EQUIVALENT` | forms F_c |

The classification is recomputed in the run and must equal `manifest.json`; any difference is a
reported deviation, and the recomputed class is used.

**UNITARY.** The circuits contain measurements, so `check_equivalence` under UNITARY returns
`UNKNOWN (MEASUREMENT)` for every fault and is recorded as such. Measurements are never removed
automatically to construct a unitary comparison, and no state-only classification is made.

### 5.3 Primary detection rate

Outcome of suite s on fault f ∈ F_c: *detected* (`AssertionError`), *undetected* (normal return) or
*error* (any other exception, recorded with its type). Faults are evaluated in catalogue order.

DR(s, c) = detected / (|F_c| − errors(s, c)) as an exact `Fraction`; undefined when the denominator
is 0. If errors(s, c) > 0, a sensitivity value counting errors as undetected is also reported.

Every RQ1 result is computed for two fault sets: F_c, and F_c without `missing_gate` faults. No
minimum applies to the second set. The **primary analysis always uses every fault in F_c**; nothing
in section 5.4 replaces or alters it.

### 5.4 Behaviour-equivalence groups (deduplication sensitivity, defined before the run)

Sharing an output distribution is **not** enough to treat two faults as interchangeable: a
measurement-mapping fault has the same pre-measurement state as the original, so T6 sees it
differently from a gate fault with the same distribution, and two gate faults with the same
distribution can still have different pre-measurement states.

**Definition.** Within one circuit and one fault set, two D-NOT-EQUIVALENT faults f and g are
*behaviour-equivalent* if and only if both hold:

1. **identical measurement map:** the ordered lists of (qubit index, classical-bit index) of their
   measurement instructions are equal; and
2. **identical pre-measurement state up to global phase:** with ψ_f and ψ_g the `Statevector` of each
   circuit with final measurements removed, started from |0…0⟩, and e^{iφ} = ⟨ψ_g|ψ_f⟩/|⟨ψ_g|ψ_f⟩|,
   max_k |ψ_f[k] − e^{iφ}ψ_g[k]| ≤ 1e-8.

**What the relation does and does not establish, suite by suite** (revision 4). The relation is
**approximate state equivalence**: states equal within the numerical tolerance 1e-8 after phase
alignment, not exactly equal. It implies that the members' ideal output distributions are close
(within √N·1e-8 in total variation, by inequality (A2) of appendix A). It does **not** imply equal distributions. It says nothing
about how a circuit's instruction list executes. The deduplicated result is therefore a
**sensitivity analysis based on approximate state equivalence**, not a claim that group members are
interchangeable.

| Suite | What (1) and (2) establish | Use in the deduplication analysis |
|---|---|---|
| T1 | Nothing. T1 depends on how BasicSimulator executes the instruction list, not on the state. | **Excluded.** T1 is excluded from the deduplication sensitivity analysis. |
| T2–T5 | Only that the members' ideal output distributions are close. **No claim is made that their pass/fail probabilities are equal.** A fixed-threshold test applied to slightly different distributions can have different pass probabilities, and realised seeded outcomes can differ. | Included as an approximate-equivalence sensitivity analysis. The representative's outcome stands for the group. Every member's outcome is recorded, and any disagreement is reported. |
| T6 | An identical deterministic outcome (detected), under the condition proved in appendix A. | Grouped only for groups that meet the condition (below). Otherwise the members are singletons for T6. |

**T6 grouping condition** (appendix A). The group's shared measurement map equals the original
circuit's map, and every member's IDEAL total variation against the original exceeds
√N·(1e-8 + 1e-12) + 1e-10, with N = 2ⁿ. The condition uses only the classification computed before
the run and the pre-run tolerance. It never uses a fault's comparison with the expected state, and
groups are not changed after suite outcomes exist.

**Scope of the deduplication sensitivity analysis.** It uses the suites T2–T6 that apply to the
circuit. **T1 is excluded from the deduplication sensitivity analysis.** Its τ statistics are shown
next to the approved **matched-suite baseline**: the primary detection rates restricted to the same
suites. The only difference between the two is then deduplication. The baseline has no p-values and
is not used for H1. The primary all-fault analysis and H1 are never changed by deduplication.

**Groups.** Groups are the connected components of this relation. They are computed in the pre-run
stage from the circuits and their classification alone, before any suite assertion, using the frozen
1e-8 global-phase-aligned state tolerance. Every pairwise comparison is recorded. Groups are never
changed after detection results exist. A
component is used as a group only if every pair in it satisfies (1) and (2); otherwise its faults are
left as singletons and the case is reported. Faults in no group are singletons. Groups are formed
separately for each fault set, after the `missing_gate` filter.

**Predicted groups** (hand reasoning; confirmed or corrected at pre-run, and the computed groups are
used):

| Group | Reason |
|---|---|
| {C1-F05, C1-F07} | `cx(2,1)` acts with control q₂ = \|0⟩, so it is the identity on that state; same state as removing `cx(1,2)` |
| {C6-F04, C6-F11} | both leave q₂ in (√3/2)\|0⟩ + ½\|1⟩ with q₀, q₁ in \|+⟩ |

Predicted **not** grouped despite identical distributions: C1-F11 (different measurement map),
C3-F02 / C3-F10 and C6-F07 / C6-F10 (different measurement maps), C3-F01 / C3-F05 (helper qubit in
\|−⟩ vs \|+⟩), C4-F01 / C4-F04 (sign of the marked amplitude differs). Predicted group counts:
C1 8, C2 10, C3 10, C4 10, C5 9, C6 8 (55) for F_c; C1 7, C2 7, C3 7, C4 9, C5 6, C6 6 (42) without
`missing_gate`.

Both predicted groups use the original measurement map. Their preflight IDEAL TV is 0.5, far above
√8·(1e-8 + 1e-12) + 1e-10 ≈ 2.84e-8, so both are also predicted to be T6 groups.

**Deduplicated detection rate.** For each group G, its representative r(G) is the member with the
lowest fault ID (approved). For suite s, the groups used are the T6 groups when s = T6 and the
behaviour-equivalence groups otherwise. With 𝒢(c) those groups for circuit c in the fault set,

DR_dedup(s, c) = #{G : r(G) detected} / (|𝒢(c)| − #{G : r(G) error})

as an exact `Fraction`, undefined when the denominator is 0. For every group with more than one
member, the report lists each member's outcome and flags any disagreement; a disagreement never
changes DR_dedup or the primary analysis.

**Descriptive measures** (reported alongside, not used for grouping): distinct ideal distributions,
and distinct pairs of (ideal distribution, measurement-only flag), within F_c. Preflight values:
distinct distributions 7, 10, 8, 9, 9, 7 (50); distinct (distribution, measurement-only) classes 8,
10, 9, 9, 9, 8 (53).

## 6. Mutation metrics

- Removal mutants: `run_removal_mutants(circuit, suite, allow_barrier=True)` with the default
  `allow_measure=False`, so measurements are skipped (`NOT_RUN`).
- **Primary score:** from `classify_report(circuit, report, model=IDEAL_DISTRIBUTION)`, the exact
  `Fraction(killed, adjusted_eligible)` with `adjusted_eligible = killed + survived −
  equivalent_survived` from `ClassifiedReport.metrics()`; undefined when `adjusted_eligible` is 0, in
  which case the suite is left out of that circuit's τ and reported.
- **Secondary:** the unadjusted score `Fraction(killed, killed + survived)`.
- **Excluded:** a secondary T6 score adjusted under UNITARY. With measurements present every UNITARY
  verdict is `UNKNOWN (MEASUREMENT)`, and building measurement-free copies would change the approved
  classification protocol, so this score is not computed. The UNITARY verdict counts of removal
  mutants are still recorded as returned.
- **RQ2:** per circuit and suite: generated, skipped by reason, killed, survived, errors, IDEAL
  verdict counts (equivalent, not equivalent, unknown by reason), and base-to-adjusted change.

## 7. Kendall τ_b

### 7.1 Data points
For circuit c, each usable suite s gives (x_s, y_s) = (primary adjusted score, DR(s, c)), both exact
fractions; a suite counts only if both are defined. n_c is the number of data points.

### 7.2 Pairs within a circuit
For each unordered pair {i, j}: tied in x if xᵢ = xⱼ, tied in y if yᵢ = yⱼ (possibly both);
concordant if (xᵢ − xⱼ)(yᵢ − yⱼ) > 0, discordant if < 0. n₀ = n_c(n_c − 1)/2; n₁ = pairs tied in x;
n₂ = pairs tied in y; n_C, n_D; U_x = n₀ − n₁; U_y = n₀ − n₂.

### 7.3 Per circuit
τ_b(c) = (n_C − n_D) / √(U_x · U_y); undefined, with reason, when n_c < 2, U_x = 0 (score constant),
U_y = 0 (detection rate constant), or both.

### 7.4 Primary pooled statistic
P = circuits with n_c ≥ 2.

τ_pooled = Σ_{c∈P} (n_C(c) − n_D(c)) / √( Σ_{c∈P} U_x(c) · Σ_{c∈P} U_y(c) )

Pairs only within a circuit. Undefined if P is empty or either sum is 0; always in [−1, 1]. A circuit
with constant x (or y) adds only to the y-sum (or x-sum), pulling τ_pooled towards 0; a circuit with
both constant has no effect and is listed.

### 7.5 Sensitivity over defined circuits
τ*_pooled,def: the same formula over D ⊆ P, the circuits with defined τ_b(c); undefined if D is
empty. Any disagreement with τ_pooled about reaching 0.5 is stated. Not used for H1.

### 7.6 H1 rule
Judged separately on both fault sets, with the primary detection rates only. **Supported:** τ_pooled
defined and ≥ 0.5, **and** τ_b(c) defined and > 0 for at least 4 of 6 circuits. **Not supported:**
τ_pooled defined but a condition fails. **Undecidable:** only when τ_pooled is undefined. An
undefined τ_b(c) counts as not positive and never makes H1 undecidable by itself.

### 7.7 Deduplication sensitivity analysis
Sections 7.1–7.5 and 8 are repeated for both fault sets over the suites in scope (T2–T6 where
applicable; T1 excluded), with y_s = DR_dedup(s, c) and the deduplication permutation seeds. The same
statistics without p-values are computed for the matched-suite baseline: the same suites with the
primary DR(s, c). These results are reported in a separate table labelled "deduplication sensitivity".
They **never replace the primary results and do not affect H1**: H1 is computed from the primary
data points alone. Every difference between the deduplicated values and the baseline values is
listed.

## 8. Permutation p-values (descriptive only)

Detection rates are permuted only within a circuit, each suite keeping its score; U_x and U_y are
invariant, so comparisons are made exactly on the integer numerator Σ(n_C − n_D).

- **Per circuit (c ∈ D):** p_c = #{permutations among all n_c! orderings with recomputed τ_b ≥
  observed} / n_c!; identical orderings from tied y counted separately; ties in the upper tail;
  one-sided for positive association.
- **Pooled (τ_pooled over P; τ*_pooled,def over D):** B = 100,000 Monte Carlo permutations, each
  shuffling every circuit's detection rates independently with `random.Random(seed)`, seed slot
  `permutation/<analysis>/<fault set>/<statistic>`; b = #{recomputed ≥ observed};
  p = (b + 1)/(B + 1).
- No p-value for an undefined statistic. p-values never decide H1, are labelled "descriptive,
  one-sided (positive association)", and the word "significant" is not used.

**Reporting per fault set and analysis:** a per-circuit table (n_c, n₀, n₁, n₂, n_C, n_D, U_x, U_y,
τ_b or "undefined" with reason, membership of P and D, p_c with numerator and n_c!); τ_pooled with b,
B, seed slot and constant-value contributions; τ*_pooled,def likewise; circuits with n_c < 2; and,
for the primary analysis, H1 status with a note that p-values did not affect it.

## 9. RQ3 and RQ4

**RQ3.** `distribution_oracle(circuit, shots=shots_for_threshold(0.05, num_clbits),
seed=<oracle/circuit>, delta=family_delta(0.05, g + 2))`, g = number of generated removal
candidates, run with `run_removal_mutants` over the same mutants. Report Δ_c = score(T5) −
score(oracle) (both primary adjusted) and a 2×2 killed/survived table per circuit with agreement rate
and one-sided kills. `WITHIN_TOLERANCE` and `INCONCLUSIVE` both count as survived, as the library
defines. **Limitation:** the existing run data do not expose the verdict of a survived mutant
(`MutantResult` stores only the candidate, outcome and error type, and the oracle returns `None` for
both verdicts), so the two are **not** reported separately, and no extra samples are drawn to
separate them. Neither T5 nor the oracle is described as a bound on the other.

- The 2×2 table covers generated mutants where both outcomes are killed or survived; mutants with an
  error in either run are counted separately.
- Δ_c is undefined if either score is undefined, if T5 was excluded, or if the oracle's baseline
  failed.
- H3: *undecidable* if fewer than 4 Δ_c are defined; otherwise *supported* if at least 4 defined
  \|Δ_c\| ≤ 0.1, else *not supported*.

**RQ4.** For every circuit and applicable sampling suite (T2–T5), the removal-mutant run and its
IDEAL classification are repeated with each of the 20 seeds `rq4/<circuit>/<suite>/01…20`, giving 20
adjusted mutation scores; report their minimum, maximum and range. A seed for which the suite fails
its original circuit gives an undefined score for that seed, which is recorded. The range is defined
when at least 2 scores are defined. A suite excluded in the primary run is skipped and reported.

H4: *not supported* if any defined range exceeds 0.1; otherwise *undecidable* if any range is
undefined; otherwise *supported*.

**RQ4 measures only the seed sensitivity of removal-mutant mutation scores; it does not measure the
seed sensitivity of fault detection rates**, which are computed with the primary seed only.

## 10. Seeds and execution order

**Seed slots** are fixed by `study_config.seed_slots()` (404 slots, in this order):

| Slots | Count |
|---|---|
| `primary/<circuit>/<suite>` for each applicable T1–T5 | 24 |
| `rq4/<circuit>/<suite>/01…20` for each applicable T2–T5 | 360 |
| `oracle/<circuit>` | 6 |
| `pre_run/<circuit>` | 6 |
| `permutation/<analysis>/<fault set>/<statistic>` | 8 |

`make_seeds.py` fills every slot once with `secrets.randbits(63)` in this order, writes `seeds.json`
(protocol revision plus the ordered slots) and refuses to run if `seeds.json` exists or the code
freeze (section 13) is not approved and verified. It writes the bytes to an exclusively created
`.seeds.json.partial`, flushes and syncs it, reads it back, validates it as a seed file, hard-links it
to `seeds.json` and syncs the directory. An interruption therefore leaves either no `seeds.json` or a
complete, valid one. A partial file left by an interruption is kept and refuses the next run (recovery
in section 13). Its hash is then bound to the freeze by
`check_code_freeze --record-seeds`, which creates `seeds.lock.json` and records the binding in the
seed history (`evaluation/freeze_history/SEEDS_RECORD.json`). It runs before
any suite assertion, in the first environment only; both environments use the same file. Seeds are
never regenerated or replaced after results exist (assumption A3).

The seed file records the protocol revision under which it was generated (`protocol_revision`).
`run_study.py` accepts seed files whose revision is in `study_config.SEED_FILE_REVISIONS` = (6, 7, 8, 9).
These revisions share the same 404-slot schema, which the seeds lock binds through
`seed_slot_schema_sha256`. A new protocol revision never causes seeds to be regenerated. On a
re-freeze, the existing seeds are re-bound as described in section 13.

**Primary seed reuse.** Suite s on circuit c uses `primary/c/s` for the original-suite check, for
every removal mutant (through `run_removal_mutants`, which also re-checks the original) and for every
fault of c. T6 needs no seed.

**Execution order** (recorded in the results file as an ordered list of stage, circuit, suite and
target):

1. Integrity checks (section 13).
2. Pre-run stage, before any suite assertion:
   - pre-run checks for C1…C6;
   - fault classification, including the execution check, for every fault in catalogue order;
   - behaviour-equivalence groups and T6 groups for C1…C6.
3. For each circuit C1…C6 and each applicable suite in order T1…T6:
   - the original-suite check;
   - `run_removal_mutants`, with candidates in index order, followed by its classification (IDEAL,
     then UNITARY);
   - the D-NOT-EQUIVALENT faults in catalogue order.
4. RQ3 oracle runs for C1…C6.
5. RQ4 runs for each circuit, sampling suite and seed, in slot order.
6. Statistics for F_c, then F_c without `missing_gate`. Within each: the primary analysis, then the
   deduplication sensitivity analysis, then the matched-suite baseline.

## 11. Errors, invalid suites, UNKNOWN and inconclusive results

| Situation | Handling |
|---|---|
| Suite fails or raises on its original circuit (including `BaselineFailedError`) | suite excluded for that circuit; no mutant or fault run for it; deviation recorded |
| Suite raises a non-`AssertionError` on a removal mutant | `ERROR`; excluded from the score as in qmutate; counted |
| Suite raises a non-`AssertionError` on a fault | *error*; excluded from DR and DR_dedup denominators; sensitivity DR with errors as undetected |
| Fault classified `UNKNOWN` under IDEAL | D-UNKNOWN; excluded; deviation |
| Removal mutant classified `UNKNOWN` under IDEAL | stays in the denominator (qmutate adjusts only for `EQUIVALENT`); counted by reason |
| Any UNITARY verdict | recorded as returned (`UNKNOWN (MEASUREMENT)`); used for nothing |
| `distribution_oracle` `INCONCLUSIVE` or `WITHIN_TOLERANCE` | survived; not separable (limitation in section 9); no resampling |
| Original circuit raises during T1's execution | T1 fails on the original, so **T1 is invalid** for that circuit: excluded and reported as a deviation |
| Removal mutant or fault raises during T1's execution while the original passes | **detected** by T1 (`AssertionError` inside the oracle; the runner records `KILLED`) |
| Fault raises in the pre-run execution check | classified Invalid (stage `execution`); excluded from every denominator and never given to any suite |
| A pre-run check raises | recorded with its error type as a failed check; the study stops before any suite runs |
| `distribution_oracle` raises during RQ3 (other than a baseline failure) | recorded with its error type; Δ_c undefined; deviation |
| RQ4 seed whose original-suite check fails | undefined score for that seed; recorded |
| T1–T6 | fixed-rule assertions with no inconclusive state |
| Pre-run or integrity check fails | study stops before any suite assertion |
| Library bug | stop and report; no fix inside Phase 6 |

## 12. Cases noted before the run

Preliminary notes only. They are not hypotheses, are not measured by RQ4, and are never used to
change anything; observed outcomes are reported as they occur.

- **Seed-sensitive (preliminary):** C1-F03 (T4, T5); C2-F06, C2-F08, C2-F09, C3-F06, C3-F08 (T2 exact
  ties); C4-F09, C4-F10 (T2); C6-F05 (T4, T5).
- **Borderline:** C3-F09 under T3 (100 shots): q = (2 − √3)/4, detection 1 − (1 − q)¹⁰⁰ = 0.999026.
- **Not detectable by T6 by construction:** the measurement-mapping faults C1-F11, C2-F10, C3-F10,
  C4-F06, C5-F08 and C6-F10.

## 13. Determinism, integrity and evidence protection

- **Integrity checks at start.** `run_study.py` refuses to start, writes nothing and exits with
  status 2 unless all of these hold:
  - the mandatory **code-freeze check** passes (next point);
  - every `check_catalogue` check passes;
  - every `check_protocol` consistency check passes, including that `PROTOCOL.md` matches
    `protocol.lock.json`;
  - `seeds.json` exists, its revision is in `study_config.SEED_FILE_REVISIONS`, its slots equal `study_config.seed_slots()` in
    order, and every seed is an integer in [0, 2⁶³);
  - the output path is acceptable (next point);
  - the running `qmutate` package was imported from this project's `src/qmutate`. This matters
    because the temporary Qiskit 2.0.3 environment contains an outdated, non-editable installed copy
    of qmutate, so every command must run with `PYTHONPATH=src`.
- **Code-freeze check** (`evaluation/check_code_freeze.py`, `verify(require_approved=True)`). It
  **fails closed**: any failed or missing check, or any exception, refuses the start. It checks that:
  - no leftover partial file of a freeze artefact or of `seeds.json` exists, live or under
    `evaluation/freeze_history/` outside a `failed/` directory;
  - `code_freeze.json` and `code_freeze.lock.json` exist and are JSON objects of the expected shape;
    the lock has exactly the fields `manifest`, `sha256` and `status`, its `manifest` names
    `evaluation/code_freeze.json`, and the manifest's SHA-256 equals the lock;
  - the lock status is `approved`;
  - the set of covered files is unchanged (none added or removed), and every covered file's
    SHA-256 is unchanged;
  - every project module actually imported by the entry points is covered;
  - the runtime parameters equal the recorded ones;
  - `VECLIB_MAXIMUM_THREADS=1` is set;
  - the running environment equals its recorded entry (versions, `RECORD` hashes of key packages,
    qmutate import location, environment variables);
  - if `seeds.json` or `seeds.lock.json` exists, both exist, and the seeds lock matches the seed
    file, the slot schema and the manifest's SHA-256;
  - the **seed history** matches: every `seeds_sha256` recorded in a JSON file under
    `evaluation/freeze_history/` and every archived `seeds.json` (hidden files and `failed/`
    directories excepted) names one SHA-256, equal to `seeds.json` and to the seeds lock's
    `seeds_sha256`. An unreadable history file fails;
  - if the manifest records a seeds SHA-256 (`seeds.sha256`), `seeds.json` exists and has it;
  - if `seeds.json` exists, it is a valid seed file: its slots equal `study_config.seed_slots()` in
    order, every seed is an integer in [0, 2⁶³), and its revision is accepted. An empty, truncated or
    malformed file fails;
  - "seeds not generated yet" passes only when no seeds were ever recorded, neither in the seed
    history nor in the manifest.

  The checker is imported only inside the driver's check function, so there is no import cycle. The
  driver always calls it; a test-only parameter can substitute it, but `main` never passes it.
- **How the manifest's own integrity is verified.** The manifest never contains its own hash or its
  lock's hash. Its SHA-256 is stored in `code_freeze.lock.json` together with its status. The lock is
  the trust anchor: its content is reported to the mentor at approval and recorded in every results
  file. Changing the manifest breaks the lock comparison. Changing the lock changes the recorded lock
  hash, and the lock status can only become `approved` through `--approve` when every check passes.
  Seeds generated after approval are bound by `seeds.lock.json`, so the approved manifest never
  changes. A new freeze is started with `check_code_freeze --retire` (see "Re-freeze when seeds already
  exist" below) and needs mentor approval of the new hashes.
- **Each freeze action runs on its own.** `--write`, `--add-environment`, `--approve`,
  `--record-seeds`, `--retire <H>`, `--rebind-seeds <H>` and `--reject <H>` are never combined in one
  invocation, and `--require-approved` is accepted only without an action; anything else, including an
  unknown argument, is refused with exit status 1. `--approve` refuses unless every check passes and
  the manifest records both environments of section 14 (`qiskit-2.0.3` and `qiskit-2.6.1`).
- **History directories.** Each cycle that retires a freeze has its own history directory `<H>`
  inside `evaluation/freeze_history/`, named after the outgoing freeze: `v2` for the first re-freeze
  out of freeze v2, then `v2-r2`, `v2-r3`, … for later cycles out of the same outgoing freeze. A new
  directory is required whenever `<H>` holds a rejected cycle (`<H>/rejected/`). `--retire` and
  `--rebind-seeds` refuse such a directory, because its `FREEZE_RETIREMENT.json`, `SEEDS_REBIND.json`
  and `.orig` files belong to the rejected cycle and are never overwritten. A covered file is archived
  under its path with `/` replaced by `__`, plus `.orig` for the outgoing version or `.rejected` for a
  rejected version. Nothing in a history directory is ever modified or deleted. Recovery only adds
  files, or moves evidence into a `failed/` subdirectory, which the checks ignore.
- **Re-freeze when seeds already exist** (revisions 7 to 9). This applies when covered files must
  change after seeds were generated. Every command uses the documented environment variables.

  | Step | Command (environment) | Effect | State if it stops here |
  |---|---|---|---|
  | 0 | — | Before a covered file is changed, copy its outgoing version into `<H>` as `<archive name>.orig`, with its SHA-256 checked against the outgoing manifest. Then make and test the changes. | The gate refuses: covered hashes changed. |
  | 1 | `check_code_freeze --retire <H>` (first) | Refuses unless every covered file that changed or is missing has its `.orig` with the outgoing hash. Publishes byte-identical copies of the live manifest and lock and a `FREEZE_RETIREMENT.json` record (with the `.orig` hashes and the seeds hash) into `<H>`. Then it removes the live lock, then the live manifest. | The gate refuses: no live manifest, or a manifest without its lock. |
  | 2 | `check_code_freeze --write` (first) | Writes the new manifest, recording the SHA-256 of the existing seeds as `seeds.sha256`, and a `proposed` lock. It refuses, writing nothing, if seeds are recorded in the seed history but `seeds.json` is missing, invalid or not the recorded file. | The gate refuses: not approved, and the seeds lock is bound to the old manifest. |
  | 3 | `check_code_freeze --add-environment` (second) | Adds the second environment. Seed binding checks are ignored here, since seeds are re-bound in step 4; the seed history check is not. It refuses once the seeds lock is bound to the current manifest, because the binding would break. | as step 2 |
  | 4 | `check_code_freeze --rebind-seeds <H>` (first) | Re-binds the existing seeds (conditions below). Publishes the old seeds lock and a `SEEDS_REBIND.json` record into `<H>`, then replaces the live seeds lock with `os.replace`. `seeds.json` is never written. | Before the replacement: the old lock is live and the gate refuses. After it: proposed and fully bound, so the gate refuses until approval. |
  | 5 | `check_code_freeze` (both); `check_catalogue`; `check_protocol`; tests | Read-only verification. Report every new hash to the mentor. | proposed |
  | 6 | `check_code_freeze --approve` (first), only after mentor approval | Refuses unless every check passes and both environments are recorded. The lock becomes `approved`. | approved, seeds present and bound; `make_seeds` refuses because `seeds.json` exists and the seed history records it |

  **`--rebind-seeds` conditions.** It refuses, writing nothing, unless all of these hold:
  - `<H>` holds no rejected cycle;
  - the live lock is a valid lock of the live manifest and is `proposed`;
  - every freeze check other than the seed binding checks passes, including the seed history and the
    absence of leftover partial files;
  - `seeds.json` and `seeds.lock.json` both exist;
  - the existing seeds lock has exactly the three seeds-lock fields;
  - its `seeds_sha256` equals the SHA-256 of `seeds.json`;
  - its slot schema equals the new manifest's;
  - it is bound to the manifest archived in `<H>`, whose archived lock is a valid `approved` lock.

  An existing archive file with other content, or a leftover partial file, is refused and left for
  inspection. A conflicting `SEEDS_REBIND.json` is detected only after the old seeds lock has been
  archived; that archive is a byte-identical copy and is harmless.
- **Rejecting a proposed freeze.** A proposed freeze that the mentor does not approve is set aside, never
  edited:

  | Step | Command (environment) | Effect | State if it stops here |
  |---|---|---|---|
  | R0 | — | Copy the proposed version of each covered file whose hash differs from the outgoing manifest into `<H>/rejected/` as `<archive name>.rejected`. The copy is taken while the covered files still hold the proposed versions; it may be staged elsewhere first and placed later, because R1 checks every copy's SHA-256 against the proposed manifest. | proposed; the gate refuses |
  | R1 | `check_code_freeze --reject <H>` (first) | Refuses, writing nothing, unless: the live lock is a valid `proposed` lock of the live manifest; `<H>` holds the outgoing approved freeze and its matching `FREEZE_RETIREMENT.json`; every `.rejected` copy of R0 exists with the proposed manifest's hash; `seeds.json` matches its lock; and the live seeds lock is either the outgoing one or the re-bound one recorded in `SEEDS_REBIND.json`. Then it publishes the live manifest, lock and seeds lock with a `FREEZE_REJECTION.json` record into `<H>/rejected/`. Only then does it remove the live lock and then the live manifest, put the outgoing seeds lock back with `os.replace`, and publish the outgoing manifest and, last, the outgoing lock. `seeds.json` and covered files are never touched. | Every intermediate state fails the freeze check. When R1 completes, the outgoing approved freeze is live again. The gate still refuses until every covered file matches it. |
  | R2a | — (full rollback) | Copy every `<H>/<archive name>.orig` back to its path, each checked against the restored manifest. Then run `check_code_freeze --require-approved` in both environments, which must pass. The outgoing approved freeze is then in force again, unchanged. | approved outgoing freeze |
  | R2b | — (new cycle) | Change the covered files, then start a new cycle at step 0 with a new `<H′>`. The `.orig` copies may be taken from `<H>`, since the outgoing freeze is the same. | as step 0 |

- **Seed history.** The seed history is every `seeds_sha256` recorded in a JSON file under
  `evaluation/freeze_history/` (`SEEDS_RECORD.json`, archived seeds locks, `FREEZE_RETIREMENT.json`,
  `SEEDS_REBIND.json`, `FREEZE_REJECTION.json`), together with every archived `seeds.json`. Once
  anything is recorded, a missing, replaced or inconsistent `seeds.json` or `seeds.lock.json` fails the
  freeze check, so approval, `make_seeds` and the study gate all refuse. `--record-seeds` is the first
  binding only. It refuses when seeds are already recorded anywhere except in its own identical
  `SEEDS_RECORD.json`, which it accepts so that an interrupted first binding can be completed.
- **Seed anchor in the manifest.** A manifest written while seeds exist records their SHA-256
  (`seeds.sha256`); `--add-environment` keeps it. The manifest's SHA-256 is in the lock, and the
  lock's SHA-256 is reported to the mentor and recorded in every results file. Removing or replacing
  `seeds.json`, its lock and every seed history record therefore still fails the freeze check, and the
  state never reads as "seeds not generated yet".
- **Seed file content.** No check accepts a `seeds.json` that is not a valid seed file, so an empty,
  truncated or malformed file can never be bound by `--record-seeds`, re-bound, anchored or used.
- **Guarantees and limits.**
  - Each file that `--retire`, `--rebind-seeds`, `--reject` and `--record-seeds` creates is published
    by exclusive creation of a partial file and a hard link, so it is either complete or absent. The
    replacements of a live file (the seeds lock, and the manifest and lock in `--add-environment` and
    `--approve`) use `os.replace`, which is atomic within one POSIX file system.
  - The steps as a whole are **not** atomic. Instead, every intermediate state fails the freeze check,
    and repeating an interrupted step resumes it:
    - `--retire` accepts identical archives and finishes a run that stopped after removing the lock;
    - `--rebind-seeds` accepts an identical archived lock and record, and reports a completed re-bind
      after the replacement;
    - `--reject` resumes from its record, step by step.
  - Only `make_seeds` syncs a directory (after linking `seeds.json`). The freeze tool does not, so after
    a power loss a freeze file just published or replaced may be missing or old. The freeze check
    then fails, and the step is repeated.
  - The tools never remove a partial file, except the partial name of a file they have just linked
    successfully (it is then the same file). After a crash between that link and the removal, a
    partial file identical to the published file remains, and the freeze check reports it.
  - **Limit of the seed guarantee.** The checks detect a missing or replaced seed file as long as one
    piece of evidence remains unaltered: the manifest's `seeds.sha256`, a seed history record, or the
    seeds lock.
    They cannot detect the removal of **every** piece of evidence: the live manifest and lock,
    `seeds.json`, its lock and the whole seed history. After such a removal, a new `--write` sees a
    project in which seeds were never generated. The same holds before the first re-freeze, when no
    manifest records the seeds yet. Only an external, trusted anchor detects this: the lock's SHA-256
    and the seeds' SHA-256 reported to the mentor and recorded in results metadata. A new freeze
    always has a new lock hash, so it cannot pass for the one the mentor approved.
- **Recovery by state.** Never edit, regenerate or delete seeds, archives or partial files.

  | State or refusal | Recovery |
  |---|---|
  | A refusal names a leftover `.partial` file, or the check "no leftover partial freeze files" fails | Do not delete it. Record its SHA-256 and size, and compare it with the file it was meant to create or replace. Then move it, keeping its name, into `<H>/failed/` (or `evaluation/freeze_history/failed/` when no cycle is open), and repeat the interrupted command. |
  | `--retire` refuses: step 0 is incomplete | Copy each missing outgoing version into `<H>` as `.orig` from a byte-identical source whose SHA-256 equals the outgoing manifest's. If no such source exists, stop and report: a full rollback would no longer be possible. |
  | `--retire`, `--rebind-seeds` or `--reject` was interrupted | Repeat the same command with the same `<H>`. |
  | `--write` was interrupted: a manifest exists without a lock | Move the new manifest into `<H>/failed/` and repeat `--write`. |
  | `--add-environment` was interrupted: the manifest and the lock disagree | Move the live manifest and lock into `<H>/failed/`, then repeat from step 2. |
  | `--approve` was interrupted | The lock is either still `proposed` or `approved` (`os.replace`). Inspect it, and repeat `--approve` only under the mentor approval already given. |
  | `--record-seeds` was interrupted after `SEEDS_RECORD.json` | Repeat `--record-seeds`; it accepts its own identical record. |
  | `make_seeds` was interrupted: `.seeds.json.partial` exists | No seed was recorded or used, because `seeds.json` does not exist or is complete. Record the partial file's SHA-256 and size, and move it into `evaluation/freeze_history/failed/`. If `seeds.json` is absent, repeat `make_seeds`; if it is present, it is complete, so continue with `--record-seeds`. |
  | `seeds.json` is not a valid seed file and was never recorded (no seeds lock, no seed history, no manifest anchor) | No result can have used it. Move it into `evaluation/freeze_history/failed/` and repeat `make_seeds`. If it was recorded anywhere, stop and report. |
  | `--write` refuses because recorded seeds are missing, invalid or not the recorded file | Restore `seeds.json` byte-identically, as for a failed seed history check. Never write a manifest without the recorded seeds. |
  | The seed history check fails, or `--rebind-seeds` refuses because the seeds or their lock changed | Stop and report. Never treat the state as "seeds not generated yet". The only legitimate recovery restores byte-identical files: `seeds.json` from an archived copy whose SHA-256 equals the seed history (for example `freeze_history/v1/seeds.json`); the seeds lock from `<H>/seeds.lock.json` before a re-bind (then repeat `--rebind-seeds`), or from a byte-identical copy whose SHA-256 equals `new_seeds_lock_sha256` in `SEEDS_REBIND.json` after one. |
  | `--reject` refuses | Nothing was written to the live paths. If R0 copies are missing and the covered files still hold the proposed versions, make them and repeat. Otherwise, stop and report. |
  | `<H>` holds a rejected cycle and `--retire` or `--rebind-seeds` refuses | Use a new history directory (R2b). |
  | The proposed freeze is rejected and no further change is wanted | `--reject <H>`, then the full rollback (R2a). |
- **Thread setting.** All documented commands set `VECLIB_MAXIMUM_THREADS=1` (Apple Accelerate). The
  value is recorded in the freeze environment and in every results file's metadata. It must be set
  when the process starts; the freeze check refuses otherwise.
- **Output.** `run_study.py` writes only the file given by `--out`. It must be a new `.json` file
  directly inside `evaluation/results/`, outside every protected path (`study_config.PROTECTED_PATHS`,
  which include `evaluation/preflight/` and `seeds.json`).
  - It must be named `pre-run-*.json` with `--pre-run-checks` and `run-*.json` otherwise, so a
    readiness result can never take a formal result's name.
  - The bytes are written to an exclusively created hidden `.<name>.partial` file, which is flushed and
    synced, then hard-linked to the output name. The link fails if the name exists. So the output
    either does not exist or is complete, and an existing file is never overwritten even in a race.
    The partial name is removed only after a successful link. A leftover partial file is refused and
    kept as evidence; the run is repeated with a new output name.
- **Output format.** JSON with sorted keys, exact fractions as `"p/q"` strings, no timestamps and no
  absolute paths.
- **Raw data kept:**
  - every suite's outcome on the original, every removal mutant and every fault, with error types;
  - every classification verdict and reason;
  - every exact score fraction;
  - every seed used;
  - the full execution order.
- **Seeds.** `make_seeds.py` creates `seeds.json` exclusively (`FileExistsError` if it or a partial
  file exists), through a synced and validated partial file and a hard link (section 10). The slot list
  and order are deterministic; only the values come from `secrets.randbits(63)`.
- **Metadata in every results file:**
  - the mode;
  - the protocol revision, with the SHA-256 of `PROTOCOL.md` and of `protocol.lock.json`;
  - the catalogue version, with the SHA-256 of the canonical source and of `manifest.json`;
  - the SHA-256 of `seeds.json`;
  - `code_sha256`: the SHA-256 of every `evaluation/**/*.py`, every `src/qmutate/*.py`,
    `tests/test_evaluation_harness.py`, `evaluation/CATALOGUE_FREEZE.md` and `pyproject.toml`;
  - the SHA-256 of `code_freeze.json`, `code_freeze.lock.json` and `seeds.lock.json`;
  - the Python, Qiskit, NumPy, BasicSimulator and qmutate versions, and `VECLIB_MAXIMUM_THREADS`;
  - every parameter;
  - the execution order (in the body).
- **After the run.** The driver repeats every integrity check and recomputes the whole metadata
  block, including every hash above. If anything changed during the run, it refuses to write and
  exits with status 4. The pre-run stage and the full run never write any file other than the new
  output (and its temporary partial file).
- **Exit statuses:**
  - 0: written and complete;
  - 2: refused to start, or an `argparse` usage error; nothing run or written;
  - 3: written, but stopped by a failed pre-run check;
  - 4: run, but not written because integrity changed;
  - 1: an uncaught exception; nothing written.
- **Protected output paths versus content-hashed files.** These are two different lists.
  - **Protected output paths** (`study_config.PROTECTED_PATHS`) can never be the target of a
    `run_study` output:
    - `evaluation/preflight/`;
    - `manifest.json`, `CATALOGUE_FREEZE.md`, `PROTOCOL.md` and `protocol.lock.json`;
    - `seeds.json`;
    - `code_freeze.json`, `code_freeze.lock.json` and `seeds.lock.json`.

    Every writer also refuses to overwrite: `run_study` and `make_seeds` create files exclusively, and
    the freeze tool's `--write` refuses if a manifest or lock exists.
  - **Content-hashed files** are listed in `code_freeze.json` (`covers` and `files_sha256`): every
    `evaluation/*.py` and `evaluation/preflight/*.py`, every `src/qmutate/*.py` and `py.typed`, all
    tests, `PROTOCOL.md`, `protocol.lock.json`, the catalogue files, the preflight evidence and
    `pyproject.toml`.
  - Three files are verified **without** a manifest content hash: `code_freeze.json` (through the
    lock), `code_freeze.lock.json` (the trust anchor) and `seeds.json` (through `seeds.lock.json` and
    the seed history). `evaluation/freeze_history/` is not hashed; it is read by the seed history and
    partial-file checks.
- **What each check covers:**

  | File | Hash or check | Covers |
  |---|---|---|
  | `evaluation/preflight/catalogue.py` | `manifest.json` (checked by `check_catalogue`), plus metadata | the frozen circuits, faults and expected values |
  | `evaluation/manifest.json` | regenerated and compared by `check_catalogue`, plus metadata | IDs, classes, tags and operation fingerprints |
  | `evaluation/preflight/` evidence (7 files) | `manifest.json` (`check_catalogue`) | preflight scripts and results |
  | `evaluation/PROTOCOL.md` | `protocol.lock.json` (`check_protocol`), plus metadata | this protocol |
  | `evaluation/protocol.lock.json` | metadata | the lock itself |
  | `evaluation/seeds.json` | slot and range validation at start, plus metadata | every seed |
  | `evaluation/CATALOGUE_FREEZE.md` | metadata (`code_sha256`) | the freeze record |
  | evaluation code, qmutate source, harness tests, `pyproject.toml` | `code_freeze.json` (freeze check), plus metadata (`code_sha256`) | the code that produced the results |
  | `evaluation/code_freeze.json` | `code_freeze.lock.json` (freeze check), plus metadata | the covered hashes, parameters and environments |
  | `evaluation/code_freeze.lock.json` | reported at approval, plus metadata | the trust anchor |
  | `evaluation/seeds.lock.json` | freeze check, plus metadata | the binding of `seeds.json` to the manifest |

  With the freeze check, every content-hashed file is checked against its approved value at start
  and again after the run.
- **Repeated runs.** Two runs in the same environment, written to two different files, must be
  byte-identical (`cmp`). Cross-version rules are in section 14.
- **Protocol changes** require mentor approval, a new revision number, and an updated lock; results
  produced under an earlier revision are kept and labelled with it.

## 14. Reproducibility across environments

Runs on Qiskit 2.6.1 and 2.0.3 with the same `seeds.json`. Required to match exactly: pre-run checks
(a)–(c), behaviour-equivalence groups, fault classes, equivalence verdicts, T1 and T6 outcomes. Not
required to match: sampled counts, T2–T5 and oracle outcomes, and everything derived from them;
differences are tabulated. `REPORT.md` gives the commands to rebuild the Qiskit 2.0.3 environment
without changing `pyproject.toml`.

## 15. Acceptance criteria (independent of hypothesis outcomes)

1. Pre-run checks pass for all six circuits, or each failure is reported and the study stopped.
2. The catalogue was frozen before any experiment, and `check_catalogue` and `check_protocol` pass
   before and after the run.
3. Every applicable suite was checked on its original circuit; deviations reported.
4. Results and `REPORT.md` contain every metric of sections 5–9 for both fault sets, the
   deduplication sensitivity analysis, all exclusions, and each hypothesis's status.
5. Same-environment reproducibility passes on both Qiskit versions; the cross-version comparison is
   reported.
6. Harness tests pass, and the 632 existing tests pass from unchanged files on both versions.
7. A diff review shows changes only under `evaluation/`, in `tests/test_evaluation_harness.py`, and,
   if approved, one README link; no change to `src/qmutate` or existing tests; no `#` comments; no
   Git.

## 16. Intended commands for the formal run (not to be run before approval)

From the project root, first environment. Every Python command sets
`VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1`.

```bash
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_code_freeze --require-approved
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_catalogue
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_protocol
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.make_seeds
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_code_freeze --record-seeds
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.run_study --pre-run-checks --out evaluation/results/pre-run-qiskit-2.6.1.json
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.run_study --out evaluation/results/run-qiskit-2.6.1-a.json
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.run_study --out evaluation/results/run-qiskit-2.6.1-b.json
cmp evaluation/results/run-qiskit-2.6.1-a.json evaluation/results/run-qiskit-2.6.1-b.json
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -W default -m pytest -p no:cacheprovider -q --no-header tests
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_code_freeze --require-approved
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_catalogue
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_protocol
```

The Qiskit 2.0.3 environment repeats every command except `make_seeds` and `--record-seeds`, with
`2.0.3` in the output names. `PYTHONPATH=src` and `VECLIB_MAXIMUM_THREADS=1` are required in both
environments; the driver refuses without them (section 13). The freeze is approved, with
`check_code_freeze --approve`, only after mentor approval of its hashes.

## Appendix A. T6 grouping guarantee (derivation)

**Notation.**
- N = 2ⁿ for an n-qubit circuit.
- ψ is a fault's state, ψ_o is the original circuit's state, and φ is the hand-derived expected state.
- ψ and ψ_o are `Statevector`s of the circuits with final measurements removed, started from |0…0⟩.
  All three are unit vectors.
- T6 computes o = ⟨φ|ψ⟩ and the phase e^{iθ*} = o/|o| (or 1 when o = 0). Its difference is
  d = max_k |ψ_k − e^{iθ*}φ_k|, and it detects the fault when d > τ₆ = 1e-8.

**(A1) Lower bound.** For unit vectors u, v and every phase θ:

max_k |u_k − e^{iθ}v_k| ≥ TV(|u|², |v|²)/√N, where TV(|u|², |v|²) = ½ Σ_k ||u_k|² − |v_k|²|.

*Proof.*
- ||u_k|² − |v_k|²| = ||u_k| − |v_k||·(|u_k| + |v_k|) ≤ |u_k − e^{iθ}v_k|·(|u_k| + |v_k|), because
  ||a| − |b|| ≤ |a − b| and |e^{iθ}v_k| = |v_k|.
- With m the maximum, Σ_k ||u_k|² − |v_k|²| ≤ m·Σ_k(|u_k| + |v_k|) ≤ m·2√N, by Cauchy–Schwarz and
  ‖u‖ = ‖v‖ = 1.
- Divide by 2. ∎

The bound holds for every θ, so it holds whatever phase T6 chooses.

**(A2) Upper bound.** The same computation gives TV(|u|², |v|²) ≤ √N·max_k |u_k − e^{iθ}v_k|. This is
the basis of the statement in section 5.4 that grouped faults have close distributions.

**(A3) Measurement maps.** A measurement map defines a function f from basis index to classical
outcome: last write wins, and unwritten bits are 0. The classical distribution is
P_u(x) = Σ_{k: f(k) = x} |u_k|². For two states measured through the same f,
TV(P_u, P_v) ≤ TV(|u|², |v|²), by the triangle inequality within each preimage of f.

**(A4) Comparison with the original circuit.** Pre-run check (b) guarantees
ε = max_k |ψ_o,k − e^{iα}φ_k| ≤ 1e-12 for its overlap phase α.

**Derivation.** Take θ' = θ* − α. For every k:

|ψ_k − e^{iθ*}φ_k| ≥ |ψ_k − e^{iθ'}ψ_o,k| − |ψ_o,k − e^{iα}φ_k|.

Since max_k(a_k − b_k) ≥ max_k a_k − max_k b_k:

d ≥ max_k |ψ_k − e^{iθ'}ψ_o,k| − ε ≥ TV(|ψ|², |ψ_o|²)/√N − 1e-12 ≥ TV_cl/√N − 1e-12,

using (A1) and then (A3). Here TV_cl is the IDEAL total variation between the fault and the
original, as reported by `check_equivalence`. (A3) applies only when the fault's measurement map
equals the original's. Hence:

**If the fault's map equals the original's and TV_cl > √N·(τ₆ + 1e-12), then d > τ₆, and T6 detects
the fault.**

**Floating point (limitation).** The derivation is exact for exact unit vectors. In the
implementation, TV_cl, d and the states are computed in double precision, and two numerical
assumptions are made:

1. The vectors are unit vectors to within rounding.
2. The state used by the classifier for TV_cl and the state used by T6 are the same gate sequence
   simulated twice. `check_equivalence` uses a gates-only copy; T6 uses
   `remove_final_measurements`. In exact arithmetic these are equal.

No formal floating-point error analysis has been done. The added slack of 1e-10 is a **heuristic
engineering margin, not a proven floating-point error bound**. It is chosen to be about five orders
of magnitude above the double-precision rounding expected for N ≤ 32 and the short gate sequences
here (of order 1e-15). In the study the margin is not close to binding: both predicted T6 groups
have TV_cl = 0.5, against bounds below 6e-8. The condition actually used is:

TV_cl > √N·(1e-8 + 1e-12) + 1e-10

| Circuits | n | Bound |
|---|---|---|
| C1, C4, C5, C6 | 3 | 2.8387e-8 |
| C3 | 4 | 4.0104e-8 |
| C2 | 5 | 5.6674e-8 |

**Scope.**
- The guarantee needs three things:
  1. the group's measurement map equals the original circuit's;
  2. pre-run check (b) passed;
  3. TV_cl comes from the pre-run classification.
- Without (1) it fails. A measurement-mapping fault can have TV_cl = 1 and T6 difference 0.
- It never uses a fault's comparison with the expected state.
- When every member of a group satisfies it, every member is detected by T6, so the T6 outcomes in
  the group are identical.

**Sharpness.** (A1) is attained to first order by two-outcome states perturbed by a small angle, so
no tighter general constant is claimed.

**Tests.** The harness tests check (A1), (A2) and (A3) numerically on seeded random states with
random phases and maps. They also check the tightness example, the strict boundary of the
condition, and that T6 detects a synthetic fault whose TV is just above the bound.
