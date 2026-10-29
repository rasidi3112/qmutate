# Phase 6A evaluation report

| | |
|---|---|
| Study | Phase 6A: removal-mutant scores versus real-fault detection for qmutate 0.1.0 |
| Protocol | `evaluation/PROTOCOL.md`, revision 9 (SHA-256 `784694584a2cbed26bb201c6106fee86593fd25548d709768269bfa803447ce4`) |
| Catalogue | `phase6a-catalogue-v1` (`evaluation/manifest.json`, `evaluation/CATALOGUE_FREEZE.md`) |
| Code freeze | manifest `e8961cd3ceda31055cc52bd824f0cb31a89872fc0315d82146f6ba3903c76292`, lock `6d44fc5bf504ef3f1e442280fd89e1ec1c3678aaf9b658f3ba111f7ee239794d` (approved) |
| Seeds | `seeds.json` `15c2a225e3f880386976e75fd401b58a9c3f6630629a6c0c1f6babf92dbffdb3`, `seeds.lock.json` `5c4a17bc4f816bfd6211a0229a8e3536530c51835ff33cc2bc8c70f9ea8827fa` |
| Formal results | `evaluation/results/` (section 3.3) |
| Report status | Written after the formal run from the existing artefacts only, then corrected after a read-only review against the same artefacts. No experiment was re-run to produce or correct it. |

**How to read this report.** Paragraphs labelled **Observed** state values read from the results
files, exactly as recorded. Paragraphs labelled **Interpretation** are readings of those values; they
are bounded by the limitations in section 11 and are not results in themselves. Fractions are exact;
the decimal in parentheses is rounded to four places. Every table in sections 4–9 was generated from
`evaluation/results/run-qiskit-2.6.1-a.json`. Its body is identical to the Qiskit 2.0.3 results
(section 9).

## 1. Purpose and scope

The study asks whether qmutate's removal mutation score tells anything about how well a test suite
detects faults in quantum circuits. It uses six circuits (C1–C6) and a frozen catalogue of 70 faults
written by hand for this study (`evaluation/CATALOGUE_FREEZE.md`). It compares six fixed test suites
(T1–T6) on them. The protocol calls these catalogue faults "real faults" to distinguish them from the
removal mutants that qmutate generates automatically. This report uses "real faults" and "real-fault
detection" only in that sense; the catalogue does not claim that its faults reproduce bugs observed in
practice. The four research questions
and their hypotheses, as approved (PROTOCOL.md section 1):

| RQ | Question | Hypothesis |
|---|---|---|
| RQ1 | Does the adjusted removal mutation score rank suites the way their real-fault detection rate does? | H1 (PROTOCOL 7.6) |
| RQ2 | How much of each removal-mutant set is equivalent, `UNKNOWN` or skipped, and how far does adjustment move the score? | descriptive |
| RQ3 | How do T5's scores compare empirically with `distribution_oracle`'s? | H3: \|Δ_c\| ≤ 0.1 for at least 4 of 6 circuits |
| RQ4 | How stable are removal-mutant mutation scores of sampling suites when only the seed changes? | H4: range ≤ 0.1 for every circuit and sampling suite |

Each hypothesis is *supported*, *not supported* or *undecidable* under a fixed rule. The protocol
states that an unsupported hypothesis is a research result, not an implementation failure.

**Scope.** One mutation operator, removal of one top-level instruction, run with
`allow_barrier=True` and `allow_measure=False` (PROTOCOL section 6). The study covers six small circuits
(at most 2³ measured outcomes for C1, C3, C4, C5 and C6, and 2⁴ for C2) and noiseless simulation with
Qiskit's `BasicSimulator`. Equivalence uses the exact IDEAL output-distribution model. It runs on
Qiskit 2.6.1 and 2.0.3, Python 3.11.14, on macOS arm64.

## 2. Provenance and integrity

### 2.1 Approved artefacts

| File | SHA-256 | Role |
|---|---|---|
| `evaluation/code_freeze.json` | `e8961cd3ceda31055cc52bd824f0cb31a89872fc0315d82146f6ba3903c76292` | manifest: 42 covered files, parameters, both environments, seed anchor |
| `evaluation/code_freeze.lock.json` | `6d44fc5bf504ef3f1e442280fd89e1ec1c3678aaf9b658f3ba111f7ee239794d` | trust anchor, status `approved` |
| `evaluation/seeds.json` | `15c2a225e3f880386976e75fd401b58a9c3f6630629a6c0c1f6babf92dbffdb3` | 404 seeds (file revision 6) |
| `evaluation/seeds.lock.json` | `5c4a17bc4f816bfd6211a0229a8e3536530c51835ff33cc2bc8c70f9ea8827fa` | binds the seeds to the manifest |
| `evaluation/PROTOCOL.md` | `784694584a2cbed26bb201c6106fee86593fd25548d709768269bfa803447ce4` | protocol revision 9 |
| `evaluation/protocol.lock.json` | `dd8fb03f0ff94443dbfc83c1850955c90f4f9cfba718476e9164a906d5ed001f` | protocol lock |

An approval note and a verified approval record are stored outside the project directory as an
external anchor: note SHA-256 `b61dd413169ae48cf1254eb9e23343da87ad7446d670918aefbe54cd4b8c9333`,
record SHA-256 `cc002575a21c224169fa7da2b5309818b84cc00d4bf58b8aeb994c407c56eb92`. They are not part
of the repository. Their hashes are listed so that the retained copies can be checked against them; a
reader with the repository alone cannot verify them.

### 2.2 Freeze history

| Freeze | Manifest | Status | Archive |
|---|---|---|---|
| v1 | `163fdd6f…` | approved, superseded | `evaluation/freeze_history/v1/` |
| v2 | `7b980eb3…` | approved, superseded; its seeds lock was written before approval (Route A′ deviation, recorded in `freeze_history/v2/SEEDS_BINDING.json`) | `evaluation/freeze_history/v2/` |
| v3 (protocol revision 7) | `40788a9c…` | proposed, rejected before approval | `evaluation/freeze_history/v2/rejected/` |
| cycle v2-r2 (revision 8) | `c9b67ef1…` | proposed, rejected before approval | `evaluation/freeze_history/v2-r2/rejected/` |
| **cycle v2-r3 (revision 9)** | **`e8961cd3…`** | **approved; used for the pre-run and the formal run** | outgoing v2 archived in `evaluation/freeze_history/v2-r3/` |

Revisions 7–9 changed the integrity tooling (re-freeze, rejection, seed history, lock validation and
partial-file handling), the completeness of the pre-run records written by `run_study` (sampled counts
and seeds, revision 7), how `run_study` and `make_seeds` write their files (revisions 8 and 9), and the
protocol text. The PROTOCOL.md change log states for each that no scientific decision changed.
`seeds.json` was generated once, under revision 6, and was never regenerated. Revision 9 accepts seed
files of revisions 6–9 (PROTOCOL section 10). The names `v2-r2` and `v2-r3` are history directories
for the second and third re-freeze cycles out of freeze v2 (PROTOCOL section 13).

### 2.3 Integrity at the time of writing

These were verified read-only while this report was prepared:
- all hashes above;
- the lock is `approved` and bound to the manifest;
- the seeds lock is bound to the manifest, `seeds.json` and the slot schema;
- all 42 covered files match their frozen hashes;
- each results file's metadata (freeze, lock, seeds, seeds lock, protocol and 24 code hashes) equals
  the live files;
- `check_code_freeze --require-approved` passes 23/23, `check_catalogue` 109/109 and
  `check_protocol` 79/79 in both environments.

This report is not covered by the freeze: it is outside the manifest's file globs and outside the
results' `code_sha256`. Before it was added, a copy of the project containing a placeholder report
passed every checker and all 803 tests in both environments. After it was added, the project itself
passed the same checks and tests. Adding the report therefore does not change the approved state.

## 3. Environments, execution and reproduction

### 3.1 Environments

| Environment | Python | NumPy | BasicSimulator | Platform | VECLIB_MAXIMUM_THREADS | qmutate | SciPy* | rustworkx* | BLAS* | Installed qmutate copy* |
|---|---|---|---|---|---|---|---|---|---|---|
| Qiskit 2.6.1 | 3.11.14 | 2.4.6 | 0.1 | macOS-27.0-arm64-arm-64bit | 1 | 0.1.0 | 1.17.1 | 0.18.1 | accelerate | editable |
| Qiskit 2.0.3 | 3.11.14 | 2.4.6 | 0.1 | macOS-27.0-arm64-arm-64bit | 1 | 0.1.0 | 1.17.1 | 0.18.1 | accelerate | non-editable |

\* from the environment entry of `evaluation/code_freeze.json`; the other columns from the results metadata.

In both environments every command set `VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src
PYTHONDONTWRITEBYTECODE=1`, and qmutate was imported from `src/qmutate` (recorded as
`qmutate_imported_from: src/qmutate` in the frozen environment entries).

### 3.2 What was run (PROTOCOL section 16)

Each environment ran, in order:
1. `check_code_freeze --require-approved`, `check_catalogue`, `check_protocol`;
2. `run_study --out …-a.json`, then `run_study --out …-b.json`;
3. `cmp` of the two outputs;
4. the test suite (`pytest -W default`);
5. the three checks again.

According to the run logs, every step exited with status 0. Those logs were written to a temporary
directory outside the project and are not archived with it (finding R8), so this statement cannot be checked from
the repository. The evidence that can be checked is in the results files themselves: no deviation, not
stopped, byte-identical a and b files, and the hashes in section 3.3. Three steps of the section 16
list were not executed:
- `make_seeds` and `check_code_freeze --record-seeds` are first-binding steps. The seeds already
  existed and were bound, so both would have refused, and seeds are never regenerated.
- The pre-run (`--pre-run-checks`) had already been run under the same approved freeze, in both
  environments, before the formal run. Its outputs are listed below.

The results record no deviation (`"deviations": []`) and no stop (`"stopped": null`).

### 3.3 Results files

| File | SHA-256 | Content |
|---|---|---|
| `evaluation/results/pre-run-qiskit-2.6.1.json` | `a1f378f70b13049b7a7d6caf017d66e830b3a2db7b33fcb601a7111823a9ae8a` | pre-run stage, Qiskit 2.6.1 |
| `evaluation/results/pre-run-qiskit-2.0.3.json` | `785b870cefbe7c1d987ba0a7eaf595d1d0147839bffc7f70d5b1266243f0922d` | pre-run stage, Qiskit 2.0.3 |
| `evaluation/results/run-qiskit-2.6.1-a.json`, `-b.json` | `94d3e531a43b7a579bde4d2275627453ec6b2f94be71e7f732c0a5f9fef4f66c` (both) | formal run, Qiskit 2.6.1 |
| `evaluation/results/run-qiskit-2.0.3-a.json`, `-b.json` | `6cd3568e0ca474d37a0beb19544748a78c3d86076abd847aa5562e51e26a576d` (both) | formal run, Qiskit 2.0.3 |

### 3.4 Rebuilding the environments

The project environment (Qiskit 2.6.1) is the editable install of `pyproject.toml` (README,
Installation). The Qiskit 2.0.3 environment was a separate virtual environment that did not change
`pyproject.toml`. It was created in a temporary directory outside the project, which does not persist. Its exact
package set is recorded in the manifest (`environments.qiskit-2.0.3.all_distributions`). These
commands reproduce that package set. They were verified to install exactly the recorded 19
distributions and versions:

```bash
uv venv --python 3.11.14 /path/to/venv-qiskit-2.0.3
VIRTUAL_ENV=/path/to/venv-qiskit-2.0.3 uv pip install "qiskit==2.0.3" "numpy==2.4.6" "scipy==1.17.1" "rustworkx==0.18.1" "symengine==0.13.0" "sympy==1.14.0" "dill==0.4.1" "stevedore==5.9.1" "mpmath==1.3.0" "python-dateutil==3.0.0" "six==1.17.0" "tzdata==2026.5" "typing_extensions==4.16.0" "pytest==9.1.1" "pluggy==1.7.0" "iniconfig==2.3.1" "packaging==26.3" "pygments==2.21.0"
VIRTUAL_ENV=/path/to/venv-qiskit-2.0.3 uv pip install --no-deps .
```

Run the last command from the project root. It installs a non-editable copy of qmutate, which is
needed because `qmutate.__version__` reads the installed package metadata; code is still imported
from `src/qmutate` through `PYTHONPATH=src`. In verification, this step installed from a
byte-identical copy of the project so that the project directory itself stayed untouched.

**Warning: known limit (finding R2, section 11).** A rebuilt environment passes the tests (803/803),
`check_catalogue` (109/109) and `check_protocol` (79/79). In that environment,
`check_code_freeze --require-approved` **fails** with one failed check, "environment qiskit-2.0.3
unchanged" (22/23). The study's start-up gate uses the same check, so `run_study` would refuse to start
there (not run in that environment). The cause is how the environment is
fingerprinted, not a change of any package version: every recorded version matches.

The frozen environment entry includes the SHA-256 of each key package's `RECORD` file. The `RECORD`
files of `numpy`, `dill` and `sympy` list console scripts whose content includes the virtual
environment's absolute path. In the original environments the path is in the script's first
(shebang) line; in the rebuilt one the first line is `#!/bin/sh` and the path is in the following
`exec` line. Either way, these hashes differ for an environment at another location.

The Qiskit 2.6.1 environment has the same property for `numpy` and `dill` (its `f2py` script starts
with a shebang that contains the absolute path of the project's `.venv`). Its package versions are
recorded in `environments.qiskit-2.6.1.all_distributions`; a pinned rebuild analogous to the one above
has not been verified.

## 4. Configuration, seeds and pre-run

**Suites** (PROTOCOL section 4): T1 run (16 shots, checks execution and key format only); T2 unique
mode (1,000 shots); T3 support (100); T4 one marginal within 0.05 (4,000); T5 total variation within
0.05 (8,000); T6 statevector up to global phase within 1e-8 (no shots). Applicability, shots and seed
slots, as run:

| Circuit | Suite | Shots | Seed slot | Original circuit | Excluded |
|---|---|---|---|---|---|
| C1 | T1 | 16 | `primary/C1/T1` | pass | no |
| C1 | T3 | 100 | `primary/C1/T3` | pass | no |
| C1 | T4 | 4000 | `primary/C1/T4` | pass | no |
| C1 | T5 | 8000 | `primary/C1/T5` | pass | no |
| C1 | T6 | none | `primary/C1/T6` | pass | no |
| C2 | T1 | 16 | `primary/C2/T1` | pass | no |
| C2 | T2 | 1000 | `primary/C2/T2` | pass | no |
| C2 | T3 | 100 | `primary/C2/T3` | pass | no |
| C2 | T4 | 4000 | `primary/C2/T4` | pass | no |
| C2 | T5 | 8000 | `primary/C2/T5` | pass | no |
| C2 | T6 | none | `primary/C2/T6` | pass | no |
| C3 | T1 | 16 | `primary/C3/T1` | pass | no |
| C3 | T2 | 1000 | `primary/C3/T2` | pass | no |
| C3 | T3 | 100 | `primary/C3/T3` | pass | no |
| C3 | T4 | 4000 | `primary/C3/T4` | pass | no |
| C3 | T5 | 8000 | `primary/C3/T5` | pass | no |
| C3 | T6 | none | `primary/C3/T6` | pass | no |
| C4 | T1 | 16 | `primary/C4/T1` | pass | no |
| C4 | T2 | 1000 | `primary/C4/T2` | pass | no |
| C4 | T4 | 4000 | `primary/C4/T4` | pass | no |
| C4 | T5 | 8000 | `primary/C4/T5` | pass | no |
| C4 | T6 | none | `primary/C4/T6` | pass | no |
| C5 | T1 | 16 | `primary/C5/T1` | pass | no |
| C5 | T4 | 4000 | `primary/C5/T4` | pass | no |
| C5 | T5 | 8000 | `primary/C5/T5` | pass | no |
| C5 | T6 | none | `primary/C5/T6` | pass | no |
| C6 | T1 | 16 | `primary/C6/T1` | pass | no |
| C6 | T4 | 4000 | `primary/C6/T4` | pass | no |
| C6 | T5 | 8000 | `primary/C6/T5` | pass | no |
| C6 | T6 | none | `primary/C6/T6` | pass | no |

Every applicable suite passed its original circuit, so no suite was excluded (PROTOCOL sections 4
and 11).

**Seeds** (PROTOCOL section 10): 404 slots, each filled once by `secrets.randbits(63)`:
- 24 primary;
- 360 RQ4;
- 6 oracle;
- 6 pre-run;
- 8 permutation.

The values are in `evaluation/seeds.json` and are repeated in the results (`seed` fields). Pooled
permutation p-values use B = 100,000 Monte Carlo permutations (`study_config.PERMUTATIONS`). Every other
parameter is in `evaluation/study_config.py` and in the manifest's `parameters`.

**Pre-run checks** (PROTOCOL section 3). **Observed:** all six circuits passed:

| Circuit | Result | (b) max prob. diff. | (b) state diff. | (c) max prob. diff. | (d) TV, 100,000 shots | (d) ε | (d) outcomes outside support | (d) seed slot |
|---|---|---|---|---|---|---|---|---|
| C1 | pass | 1.1e-16 | 0.0e+00 | 1.1e-16 | 201/100000 (0.0020) | 0.01249 | 0 | pre_run/C1 |
| C2 | pass | 1.4e-15 | 4.4e-16 | 1.4e-15 | 0 (0.0000) | 0.01444 | 0 | pre_run/C2 |
| C3 | pass | 1.1e-15 | 3.3e-16 | 1.1e-15 | 0 (0.0000) | 0.01249 | 0 | pre_run/C3 |
| C4 | pass | 4.0e-15 | 1.9e-15 | 4.0e-15 | 363/400000 (0.0009) | 0.01249 | 0 | pre_run/C4 |
| C5 | pass | 5.6e-17 | 6.5e-16 | 5.6e-17 | 77/20000 (0.0039) | 0.01249 | 0 | pre_run/C5 |
| C6 | pass | 8.3e-17 | 5.6e-17 | 8.3e-17 | 289/100000 (0.0029) | 0.01249 | 0 | pre_run/C6 |

**Fault classification** (PROTOCOL 5.1–5.2). **Observed:** the recomputed classes equal
`manifest.json` for all 70 faults. No fault was Invalid or D-UNKNOWN.

| Circuit | Faults | D-NOT-EQUIVALENT | D-EQUIVALENT | D-UNKNOWN | Invalid | `missing_gate` | D-NOT-EQ. without `missing_gate` | Class equals manifest |
|---|---|---|---|---|---|---|---|---|
| C1 | 12 | 9 | 3 | 0 | 0 | 2 | 7 | 12 |
| C2 | 11 | 10 | 1 | 0 | 0 | 3 | 7 | 11 |
| C3 | 11 | 10 | 1 | 0 | 0 | 3 | 7 | 11 |
| C4 | 12 | 10 | 2 | 0 | 0 | 2 | 9 | 12 |
| C5 | 12 | 9 | 3 | 0 | 0 | 4 | 6 | 12 |
| C6 | 12 | 9 | 3 | 0 | 0 | 3 | 7 | 12 |
| Total | 70 | 57 | 13 | 0 | 0 | 17 | 43 | 70 |

## 5. RQ2: removal-mutant sets, equivalence and adjustment

**Observed** (per circuit and suite, from `ClassifiedReport.metrics()` under the IDEAL model):

| Circuit | Suite | Candidates | Executed | Not run | Killed | Survived | Errors | IDEAL equivalent | Equivalent killed/survived/error | IDEAL not equivalent | IDEAL unknown | Unadjusted score | Adjusted score (primary) | Change |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | T1 | 6 | 3 | 3 | 0 | 3 | 0 | 0 | 0/0/0 | 3 | 0 | 0 (0.0000) | 0 (0.0000) | 0 |
| C1 | T3 | 6 | 3 | 3 | 2 | 1 | 0 | 0 | 0/0/0 | 3 | 0 | 2/3 (0.6667) | 2/3 (0.6667) | 0 |
| C1 | T4 | 6 | 3 | 3 | 1 | 2 | 0 | 0 | 0/0/0 | 3 | 0 | 1/3 (0.3333) | 1/3 (0.3333) | 0 |
| C1 | T5 | 6 | 3 | 3 | 3 | 0 | 0 | 0 | 0/0/0 | 3 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C1 | T6 | 6 | 3 | 3 | 3 | 0 | 0 | 0 | 0/0/0 | 3 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C2 | T1 | 17 | 13 | 4 | 0 | 13 | 0 | 0 | 0/0/0 | 13 | 0 | 0 (0.0000) | 0 (0.0000) | 0 |
| C2 | T2 | 17 | 13 | 4 | 11 | 2 | 0 | 0 | 0/0/0 | 13 | 0 | 11/13 (0.8462) | 11/13 (0.8462) | 0 |
| C2 | T3 | 17 | 13 | 4 | 13 | 0 | 0 | 0 | 0/0/0 | 13 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C2 | T4 | 17 | 13 | 4 | 5 | 8 | 0 | 0 | 0/0/0 | 13 | 0 | 5/13 (0.3846) | 5/13 (0.3846) | 0 |
| C2 | T5 | 17 | 13 | 4 | 13 | 0 | 0 | 0 | 0/0/0 | 13 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C2 | T6 | 17 | 13 | 4 | 13 | 0 | 0 | 0 | 0/0/0 | 13 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C3 | T1 | 14 | 11 | 3 | 0 | 11 | 0 | 0 | 0/0/0 | 11 | 0 | 0 (0.0000) | 0 (0.0000) | 0 |
| C3 | T2 | 14 | 11 | 3 | 11 | 0 | 0 | 0 | 0/0/0 | 11 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C3 | T3 | 14 | 11 | 3 | 11 | 0 | 0 | 0 | 0/0/0 | 11 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C3 | T4 | 14 | 11 | 3 | 5 | 6 | 0 | 0 | 0/0/0 | 11 | 0 | 5/11 (0.4545) | 5/11 (0.4545) | 0 |
| C3 | T5 | 14 | 11 | 3 | 11 | 0 | 0 | 0 | 0/0/0 | 11 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C3 | T6 | 14 | 11 | 3 | 11 | 0 | 0 | 0 | 0/0/0 | 11 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| C4 | T1 | 46 | 43 | 3 | 0 | 43 | 0 | 4 | 0/4/0 | 39 | 0 | 0 (0.0000) | 0 (0.0000) | 0 |
| C4 | T2 | 46 | 43 | 3 | 19 | 24 | 0 | 4 | 0/4/0 | 39 | 0 | 19/43 (0.4419) | 19/39 (0.4872) | +76/1677 |
| C4 | T4 | 46 | 43 | 3 | 33 | 10 | 0 | 4 | 0/4/0 | 39 | 0 | 33/43 (0.7674) | 11/13 (0.8462) | +44/559 |
| C4 | T5 | 46 | 43 | 3 | 39 | 4 | 0 | 4 | 0/4/0 | 39 | 0 | 39/43 (0.9070) | 1 (1.0000) | +4/43 |
| C4 | T6 | 46 | 43 | 3 | 42 | 1 | 0 | 4 | 3/1/0 | 39 | 0 | 42/43 (0.9767) | 1 (1.0000) | +1/43 |
| C5 | T1 | 12 | 9 | 3 | 0 | 9 | 0 | 6 | 0/6/0 | 3 | 0 | 0 (0.0000) | 0 (0.0000) | 0 |
| C5 | T4 | 12 | 9 | 3 | 1 | 8 | 0 | 6 | 0/6/0 | 3 | 0 | 1/9 (0.1111) | 1/3 (0.3333) | +2/9 |
| C5 | T5 | 12 | 9 | 3 | 3 | 6 | 0 | 6 | 0/6/0 | 3 | 0 | 1/3 (0.3333) | 1 (1.0000) | +2/3 |
| C5 | T6 | 12 | 9 | 3 | 8 | 1 | 0 | 6 | 5/1/0 | 3 | 0 | 8/9 (0.8889) | 1 (1.0000) | +1/9 |
| C6 | T1 | 10 | 7 | 3 | 0 | 7 | 0 | 1 | 0/1/0 | 6 | 0 | 0 (0.0000) | 0 (0.0000) | 0 |
| C6 | T4 | 10 | 7 | 3 | 4 | 3 | 0 | 1 | 0/1/0 | 6 | 0 | 4/7 (0.5714) | 2/3 (0.6667) | +2/21 |
| C6 | T5 | 10 | 7 | 3 | 6 | 1 | 0 | 1 | 0/1/0 | 6 | 0 | 6/7 (0.8571) | 1 (1.0000) | +1/7 |
| C6 | T6 | 10 | 7 | 3 | 7 | 0 | 0 | 1 | 1/0/0 | 6 | 0 | 1 (1.0000) | 1 (1.0000) | 0 |
| Total |  | 534 | 438 | 96 | 275 | 163 | 0 | 48 | 9/39/0 | 390 | 0 |  |  |  |

**Evaluations versus distinct mutants.** Each row counts the removal mutants of one circuit as run
by one suite. The same mutants are run once per applicable suite, so the **Total** row counts
**mutant–suite evaluations**, not distinct mutants. Each mutant's IDEAL verdict is identical in every
suite of its circuit.

| Count | Mutant–suite evaluations (Total row) | Distinct mutants |
|---|---|---|
| Candidates (top-level instructions) | 534 | 105 (C1 6, C2 17, C3 14, C4 46, C5 12, C6 10) |
| Executed (generated) | 438 | 86 (3, 13, 11, 43, 9, 7) |
| Not run (`measure`) | 96 | 19 (3, 4, 3, 3, 3, 3) |
| IDEAL equivalent | 48 | 11 (C4 4, C5 6, C6 1) |
| IDEAL not equivalent | 390 | 75 |

For example, 534 = 6×5 + 17×6 + 14×6 + 46×5 + 12×4 + 10×4 (candidates × applicable suites), and
48 = 4×5 + 6×4 + 1×4.

**Denominator consistency.** Each check below holds for all 30 circuit–suite pairs:
- the outcomes add up to the candidates, giving 534 = 438 executed + 96 not run evaluations;
- the IDEAL verdicts cover exactly the executed mutants, giving 438 = 48 equivalent + 390 not
  equivalent + 0 unknown evaluations;
- the 96 not-run evaluations have no verdict;
- `adjusted_eligible = killed + survived − equivalent_survived`;
- both scores equal their counts;
- equivalent killed + survived + error equals the equivalent count.

No removal mutant raised an error, and no IDEAL verdict was `unknown`. All 438 UNITARY verdicts
(evaluations) are `unknown` with reason `measurement`, recorded as the protocol prescribes (section 6)
and used for nothing.

**Observed:** adjustment changed 9 of the 30 primary scores, all upwards (C4 T2, T4, T5, T6; C5 T4,
T5, T6; C6 T4, T5). The largest changes were +2/3 (C5/T5) and +2/9 (C5/T4). All 96 skipped
evaluations, 19 distinct candidates, are `measure` instructions. The results record them as `not_run`
but do not store the skip reason (finding R1).

**Interpretation:** an IDEAL-equivalent removal mutant is one whose output distribution equals the
original's within the tolerance. Here these are 11 of the 86 distinct executed mutants, all in C4, C5
and C6 (48 of the 438 mutant–suite evaluations). Equivalent survivors lower the unadjusted score. The
protocol defines the adjusted score, which removes equivalent survivors from the denominator, as the
primary score (PROTOCOL section 6). T1 kills no removal mutant in any circuit, which is consistent
with T1 checking only execution and key format.

## 6. RQ1: mutation score versus real-fault detection (H1)

Data points: x = primary adjusted mutation score, y = DR(s, c) = detected / (|F_c| − errors)
(PROTOCOL 7.1, 5.3). No fault outcome was an error. Within a circuit, every suite uses the same fault
denominator. τ_b is computed per circuit, and the pooled statistic sums pair counts within circuits
only (PROTOCOL 7.2–7.4).

### 6.1 Fault set F_c (all 57 D-NOT-EQUIVALENT faults)

**Observed data points:**

| Circuit | Suite | x: adjusted mutation score | Detected / denominator | y: DR(s, c) | Fault errors |
|---|---|---|---|---|---|
| C1 | T1 | 0 (0.0000) | 0/9 | 0 (0.0000) | 0 |
| C1 | T3 | 2/3 (0.6667) | 5/9 | 5/9 (0.5556) | 0 |
| C1 | T4 | 1/3 (0.3333) | 4/9 | 4/9 (0.4444) | 0 |
| C1 | T5 | 1 (1.0000) | 8/9 | 8/9 (0.8889) | 0 |
| C1 | T6 | 1 (1.0000) | 8/9 | 8/9 (0.8889) | 0 |
| C2 | T1 | 0 (0.0000) | 0/10 | 0 (0.0000) | 0 |
| C2 | T2 | 11/13 (0.8462) | 9/10 | 9/10 (0.9000) | 0 |
| C2 | T3 | 1 (1.0000) | 10/10 | 1 (1.0000) | 0 |
| C2 | T4 | 5/13 (0.3846) | 4/10 | 2/5 (0.4000) | 0 |
| C2 | T5 | 1 (1.0000) | 10/10 | 1 (1.0000) | 0 |
| C2 | T6 | 1 (1.0000) | 9/10 | 9/10 (0.9000) | 0 |
| C3 | T1 | 0 (0.0000) | 0/10 | 0 (0.0000) | 0 |
| C3 | T2 | 1 (1.0000) | 9/10 | 9/10 (0.9000) | 0 |
| C3 | T3 | 1 (1.0000) | 10/10 | 1 (1.0000) | 0 |
| C3 | T4 | 5/11 (0.4545) | 5/10 | 1/2 (0.5000) | 0 |
| C3 | T5 | 1 (1.0000) | 10/10 | 1 (1.0000) | 0 |
| C3 | T6 | 1 (1.0000) | 9/10 | 9/10 (0.9000) | 0 |
| C4 | T1 | 0 (0.0000) | 0/10 | 0 (0.0000) | 0 |
| C4 | T2 | 19/39 (0.4872) | 5/10 | 1/2 (0.5000) | 0 |
| C4 | T4 | 11/13 (0.8462) | 9/10 | 9/10 (0.9000) | 0 |
| C4 | T5 | 1 (1.0000) | 10/10 | 1 (1.0000) | 0 |
| C4 | T6 | 1 (1.0000) | 9/10 | 9/10 (0.9000) | 0 |
| C5 | T1 | 0 (0.0000) | 0/9 | 0 (0.0000) | 0 |
| C5 | T4 | 1/3 (0.3333) | 2/9 | 2/9 (0.2222) | 0 |
| C5 | T5 | 1 (1.0000) | 9/9 | 1 (1.0000) | 0 |
| C5 | T6 | 1 (1.0000) | 8/9 | 8/9 (0.8889) | 0 |
| C6 | T1 | 0 (0.0000) | 0/9 | 0 (0.0000) | 0 |
| C6 | T4 | 2/3 (0.6667) | 7/9 | 7/9 (0.7778) | 0 |
| C6 | T5 | 1 (1.0000) | 8/9 | 8/9 (0.8889) | 0 |
| C6 | T6 | 1 (1.0000) | 8/9 | 8/9 (0.8889) | 0 |

**Observed per-circuit statistics:**

| Circuit | n_c | n₀ | n₁ (x ties) | n₂ (y ties) | n_C | n_D | U_x | U_y | τ_b(c) | In P | In D | p_c (descriptive, one-sided) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 5 | 10 | 1 | 1 | 9 | 0 | 9 | 9 | 1.0000 | yes | yes | 2/120 = 1/60 (0.0167) |
| C2 | 6 | 15 | 3 | 2 | 11 | 0 | 12 | 13 | 0.8807 | yes | yes | 12/720 = 1/60 (0.0167) |
| C3 | 6 | 15 | 6 | 2 | 9 | 0 | 9 | 13 | 0.8321 | yes | yes | 24/720 = 1/30 (0.0333) |
| C4 | 5 | 10 | 1 | 1 | 8 | 0 | 9 | 9 | 0.8889 | yes | yes | 4/120 = 1/30 (0.0333) |
| C5 | 4 | 6 | 1 | 0 | 5 | 0 | 5 | 6 | 0.9129 | yes | yes | 2/24 = 1/12 (0.0833) |
| C6 | 4 | 6 | 1 | 1 | 5 | 0 | 5 | 5 | 1.0000 | yes | yes | 2/24 = 1/12 (0.0833) |

**Observed pooled statistics:**

| Statistic | Circuits | Σ(n_C − n_D) | ΣU_x | ΣU_y | Value | Monte Carlo | p (descriptive) | Seed slot |
|---|---|---|---|---|---|---|---|---|
| τ_pooled (over P) | C1, C2, C3, C4, C5, C6 | 47 | 49 | 55 | 0.9054 | b = 0, B = 100000 | 1/100001 (0.0000) | `permutation/primary/all/tau_pooled` |
| τ*_pooled,def (over D) | C1, C2, C3, C4, C5, C6 | 47 | 49 | 55 | 0.9054 | b = 0, B = 100000 | 1/100001 (0.0000) | `permutation/primary/all/tau_pooled_def` |

**H1 (F_c): supported.** τ_pooled = 47/√(49·55) = 0.9054 ≥ 0.5, and τ_b(c) is defined and positive in
6 of 6 circuits (the rule needs 4).

### 6.2 Fault set F_c without `missing_gate` (43 faults)

**Observed data points:**

| Circuit | Suite | x: adjusted mutation score | Detected / denominator | y: DR(s, c) | Fault errors |
|---|---|---|---|---|---|
| C1 | T1 | 0 (0.0000) | 0/7 | 0 (0.0000) | 0 |
| C1 | T3 | 2/3 (0.6667) | 4/7 | 4/7 (0.5714) | 0 |
| C1 | T4 | 1/3 (0.3333) | 3/7 | 3/7 (0.4286) | 0 |
| C1 | T5 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |
| C1 | T6 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |
| C2 | T1 | 0 (0.0000) | 0/7 | 0 (0.0000) | 0 |
| C2 | T2 | 11/13 (0.8462) | 7/7 | 1 (1.0000) | 0 |
| C2 | T3 | 1 (1.0000) | 7/7 | 1 (1.0000) | 0 |
| C2 | T4 | 5/13 (0.3846) | 3/7 | 3/7 (0.4286) | 0 |
| C2 | T5 | 1 (1.0000) | 7/7 | 1 (1.0000) | 0 |
| C2 | T6 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |
| C3 | T1 | 0 (0.0000) | 0/7 | 0 (0.0000) | 0 |
| C3 | T2 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |
| C3 | T3 | 1 (1.0000) | 7/7 | 1 (1.0000) | 0 |
| C3 | T4 | 5/11 (0.4545) | 3/7 | 3/7 (0.4286) | 0 |
| C3 | T5 | 1 (1.0000) | 7/7 | 1 (1.0000) | 0 |
| C3 | T6 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |
| C4 | T1 | 0 (0.0000) | 0/9 | 0 (0.0000) | 0 |
| C4 | T2 | 19/39 (0.4872) | 5/9 | 5/9 (0.5556) | 0 |
| C4 | T4 | 11/13 (0.8462) | 8/9 | 8/9 (0.8889) | 0 |
| C4 | T5 | 1 (1.0000) | 9/9 | 1 (1.0000) | 0 |
| C4 | T6 | 1 (1.0000) | 8/9 | 8/9 (0.8889) | 0 |
| C5 | T1 | 0 (0.0000) | 0/6 | 0 (0.0000) | 0 |
| C5 | T4 | 1/3 (0.3333) | 1/6 | 1/6 (0.1667) | 0 |
| C5 | T5 | 1 (1.0000) | 6/6 | 1 (1.0000) | 0 |
| C5 | T6 | 1 (1.0000) | 5/6 | 5/6 (0.8333) | 0 |
| C6 | T1 | 0 (0.0000) | 0/7 | 0 (0.0000) | 0 |
| C6 | T4 | 2/3 (0.6667) | 6/7 | 6/7 (0.8571) | 0 |
| C6 | T5 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |
| C6 | T6 | 1 (1.0000) | 6/7 | 6/7 (0.8571) | 0 |

**Observed per-circuit statistics:**

| Circuit | n_c | n₀ | n₁ (x ties) | n₂ (y ties) | n_C | n_D | U_x | U_y | τ_b(c) | In P | In D | p_c (descriptive, one-sided) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 5 | 10 | 1 | 1 | 9 | 0 | 9 | 9 | 1.0000 | yes | yes | 2/120 = 1/60 (0.0167) |
| C2 | 6 | 15 | 3 | 3 | 9 | 1 | 12 | 12 | 0.6667 | yes | yes | 48/720 = 1/15 (0.0667) |
| C3 | 6 | 15 | 6 | 2 | 9 | 0 | 9 | 13 | 0.8321 | yes | yes | 24/720 = 1/30 (0.0333) |
| C4 | 5 | 10 | 1 | 1 | 8 | 0 | 9 | 9 | 0.8889 | yes | yes | 4/120 = 1/30 (0.0333) |
| C5 | 4 | 6 | 1 | 0 | 5 | 0 | 5 | 6 | 0.9129 | yes | yes | 2/24 = 1/12 (0.0833) |
| C6 | 4 | 6 | 1 | 3 | 3 | 0 | 5 | 3 | 0.7746 | yes | yes | 6/24 = 1/4 (0.2500) |

**Observed pooled statistics:**

| Statistic | Circuits | Σ(n_C − n_D) | ΣU_x | ΣU_y | Value | Monte Carlo | p (descriptive) | Seed slot |
|---|---|---|---|---|---|---|---|---|
| τ_pooled (over P) | C1, C2, C3, C4, C5, C6 | 42 | 49 | 52 | 0.8321 | b = 0, B = 100000 | 1/100001 (0.0000) | `permutation/primary/without_missing_gate/tau_pooled` |
| τ*_pooled,def (over D) | C1, C2, C3, C4, C5, C6 | 42 | 49 | 52 | 0.8321 | b = 0, B = 100000 | 1/100001 (0.0000) | `permutation/primary/without_missing_gate/tau_pooled_def` |

**H1 (without `missing_gate`): supported.** τ_pooled = 42/√(49·52) = 0.8321 ≥ 0.5, and τ_b(c) is
positive in 6 of 6 circuits.

### 6.3 Deduplication sensitivity analysis (PROTOCOL 5.4 and 7.7; does not affect H1)

**Observed groups.** The computed groups equal the protocol's predictions: 55 groups for F_c and 42
without `missing_gate`, with the multi-member groups {C1-F05, C1-F07} and {C6-F04, C6-F11}. Both are
also T6 groups. No component was an anomaly, and no group member's outcome disagreed with its
representative's.

F_c, groups:

| Circuit | Groups | Multi-member groups | T6 groups | Multi-member T6 groups | Anomalies |
|---|---|---|---|---|---|
| C1 | 8 | {C1-F05, C1-F07} | 8 | {C1-F05, C1-F07} | 0 |
| C2 | 10 | none | 10 | none | 0 |
| C3 | 10 | none | 10 | none | 0 |
| C4 | 10 | none | 10 | none | 0 |
| C5 | 9 | none | 9 | none | 0 |
| C6 | 8 | {C6-F04, C6-F11} | 8 | {C6-F04, C6-F11} | 0 |

F_c, deduplicated detection rates (suites T2–T6; T1 excluded):

| Circuit | Suite | Detected groups / groups | DR_dedup | DR (matched-suite baseline) | Dedup vs baseline |
|---|---|---|---|---|---|
| C1 | T3 | 4/8 | 1/2 (0.5000) | 5/9 (0.5556) | differs |
| C1 | T4 | 4/8 | 1/2 (0.5000) | 4/9 (0.4444) | differs |
| C1 | T5 | 7/8 | 7/8 (0.8750) | 8/9 (0.8889) | differs |
| C1 | T6 | 7/8 | 7/8 (0.8750) | 8/9 (0.8889) | differs |
| C2 | T2 | 9/10 | 9/10 (0.9000) | 9/10 (0.9000) | same |
| C2 | T3 | 10/10 | 1 (1.0000) | 1 (1.0000) | same |
| C2 | T4 | 4/10 | 2/5 (0.4000) | 2/5 (0.4000) | same |
| C2 | T5 | 10/10 | 1 (1.0000) | 1 (1.0000) | same |
| C2 | T6 | 9/10 | 9/10 (0.9000) | 9/10 (0.9000) | same |
| C3 | T2 | 9/10 | 9/10 (0.9000) | 9/10 (0.9000) | same |
| C3 | T3 | 10/10 | 1 (1.0000) | 1 (1.0000) | same |
| C3 | T4 | 5/10 | 1/2 (0.5000) | 1/2 (0.5000) | same |
| C3 | T5 | 10/10 | 1 (1.0000) | 1 (1.0000) | same |
| C3 | T6 | 9/10 | 9/10 (0.9000) | 9/10 (0.9000) | same |
| C4 | T2 | 5/10 | 1/2 (0.5000) | 1/2 (0.5000) | same |
| C4 | T4 | 9/10 | 9/10 (0.9000) | 9/10 (0.9000) | same |
| C4 | T5 | 10/10 | 1 (1.0000) | 1 (1.0000) | same |
| C4 | T6 | 9/10 | 9/10 (0.9000) | 9/10 (0.9000) | same |
| C5 | T4 | 2/9 | 2/9 (0.2222) | 2/9 (0.2222) | same |
| C5 | T5 | 9/9 | 1 (1.0000) | 1 (1.0000) | same |
| C5 | T6 | 8/9 | 8/9 (0.8889) | 8/9 (0.8889) | same |
| C6 | T4 | 6/8 | 3/4 (0.7500) | 7/9 (0.7778) | differs |
| C6 | T5 | 7/8 | 7/8 (0.8750) | 8/9 (0.8889) | differs |
| C6 | T6 | 7/8 | 7/8 (0.8750) | 8/9 (0.8889) | differs |

F_c, τ with deduplicated rates versus the matched-suite baseline:

| Circuit | n (T2–T6) | τ_b with DR_dedup | p_c numerator/n! | τ_b matched-suite baseline (no p-value) |
|---|---|---|---|---|
| C1 | 4 | 0.8944 | 4/24 | 1.0000 |
| C2 | 5 | 0.8018 | 12/120 | 0.8018 |
| C3 | 5 | 0.7071 | 24/120 | 0.7071 |
| C4 | 4 | 0.8000 | 4/24 | 0.8000 |
| C5 | 3 | 0.8165 | 2/6 | 0.8165 |
| C6 | 3 | 1.0000 | 2/6 | 1.0000 |

| Statistic | Deduplicated | Monte Carlo (descriptive) | Seed slot | Matched-suite baseline |
|---|---|---|---|---|
| tau_pooled | 0.8033 | b = 10, B = 100000, p = 1/9091 (0.0001) | `permutation/dedup_sensitivity/all/tau_pooled` | 0.8262 |
| tau_pooled_def | 0.8033 | b = 9, B = 100000, p = 10/100001 (0.0001) | `permutation/dedup_sensitivity/all/tau_pooled_def` | 0.8262 |

Without `missing_gate`, groups:

| Circuit | Groups | Multi-member groups | T6 groups | Multi-member T6 groups | Anomalies |
|---|---|---|---|---|---|
| C1 | 7 | none | 7 | none | 0 |
| C2 | 7 | none | 7 | none | 0 |
| C3 | 7 | none | 7 | none | 0 |
| C4 | 9 | none | 9 | none | 0 |
| C5 | 6 | none | 6 | none | 0 |
| C6 | 6 | {C6-F04, C6-F11} | 6 | {C6-F04, C6-F11} | 0 |

Without `missing_gate`, deduplicated detection rates:

| Circuit | Suite | Detected groups / groups | DR_dedup | DR (matched-suite baseline) | Dedup vs baseline |
|---|---|---|---|---|---|
| C1 | T3 | 4/7 | 4/7 (0.5714) | 4/7 (0.5714) | same |
| C1 | T4 | 3/7 | 3/7 (0.4286) | 3/7 (0.4286) | same |
| C1 | T5 | 6/7 | 6/7 (0.8571) | 6/7 (0.8571) | same |
| C1 | T6 | 6/7 | 6/7 (0.8571) | 6/7 (0.8571) | same |
| C2 | T2 | 7/7 | 1 (1.0000) | 1 (1.0000) | same |
| C2 | T3 | 7/7 | 1 (1.0000) | 1 (1.0000) | same |
| C2 | T4 | 3/7 | 3/7 (0.4286) | 3/7 (0.4286) | same |
| C2 | T5 | 7/7 | 1 (1.0000) | 1 (1.0000) | same |
| C2 | T6 | 6/7 | 6/7 (0.8571) | 6/7 (0.8571) | same |
| C3 | T2 | 6/7 | 6/7 (0.8571) | 6/7 (0.8571) | same |
| C3 | T3 | 7/7 | 1 (1.0000) | 1 (1.0000) | same |
| C3 | T4 | 3/7 | 3/7 (0.4286) | 3/7 (0.4286) | same |
| C3 | T5 | 7/7 | 1 (1.0000) | 1 (1.0000) | same |
| C3 | T6 | 6/7 | 6/7 (0.8571) | 6/7 (0.8571) | same |
| C4 | T2 | 5/9 | 5/9 (0.5556) | 5/9 (0.5556) | same |
| C4 | T4 | 8/9 | 8/9 (0.8889) | 8/9 (0.8889) | same |
| C4 | T5 | 9/9 | 1 (1.0000) | 1 (1.0000) | same |
| C4 | T6 | 8/9 | 8/9 (0.8889) | 8/9 (0.8889) | same |
| C5 | T4 | 1/6 | 1/6 (0.1667) | 1/6 (0.1667) | same |
| C5 | T5 | 6/6 | 1 (1.0000) | 1 (1.0000) | same |
| C5 | T6 | 5/6 | 5/6 (0.8333) | 5/6 (0.8333) | same |
| C6 | T4 | 5/6 | 5/6 (0.8333) | 6/7 (0.8571) | differs |
| C6 | T5 | 5/6 | 5/6 (0.8333) | 6/7 (0.8571) | differs |
| C6 | T6 | 5/6 | 5/6 (0.8333) | 6/7 (0.8571) | differs |

Without `missing_gate`, τ with deduplicated rates versus the matched-suite baseline:

| Circuit | n (T2–T6) | τ_b with DR_dedup | p_c numerator/n! | τ_b matched-suite baseline (no p-value) |
|---|---|---|---|---|
| C1 | 4 | 1.0000 | 2/24 | 1.0000 |
| C2 | 5 | 0.4286 | 30/120 | 0.4286 |
| C3 | 5 | 0.7071 | 24/120 | 0.7071 |
| C4 | 4 | 0.8000 | 4/24 | 0.8000 |
| C5 | 3 | 0.8165 | 2/6 | 0.8165 |
| C6 | 3 | undefined (detection rate constant) | none | undefined (detection rate constant) |

| Statistic | Deduplicated | Monte Carlo (descriptive) | Seed slot | Matched-suite baseline |
|---|---|---|---|---|
| tau_pooled | 0.6803 | b = 104, B = 100000, p = 105/100001 (0.0010) | `permutation/dedup_sensitivity/without_missing_gate/tau_pooled` | 0.6803 |
| tau_pooled_def | 0.7093 | b = 75, B = 100000, p = 76/100001 (0.0008) | `permutation/dedup_sensitivity/without_missing_gate/tau_pooled_def` | 0.7093 |

**Observed:** deduplication changes detection rates only where a multi-member group exists. That is
C1 and C6 for F_c, and C6 alone without `missing_gate`. With F_c, τ_pooled falls from 0.8262
(baseline) to 0.8033 (deduplicated). Without `missing_gate`, the deduplicated and baseline values are
equal (0.6803, and 0.7093 over D). The results record `affects_h1: false` for both fault sets.

### 6.4 Interpreting τ_b and the p-values

**Interpretation:**
- **Small samples and ties.** Each circuit contributes 4 to 6 points, one per applicable suite. Many
  points share x = 1: T5 and T6 in every circuit, T3 in C2 and C3, and T2 in C3. This gives many ties
  in x (n₁ up to 6 of 15 pairs for C3). With so few points, small changes in the pair counts move
  τ_b(c) visibly. For C2, removing the `missing_gate` faults changes (n_C, n_D, n₂) from (11, 0, 2) to
  (9, 1, 3), and τ_b from 0.8807 to 0.6667.
- **The T1 point.** T1 gives (x, y) = (0, 0) in every circuit, so it is concordant with every suite
  that has x > 0 and y > 0. Part of the positive association therefore comes from the T1 point, which
  is lowest on both measures. The matched-suite baseline (T2–T6 only, as defined in PROTOCOL 5.4)
  gives τ_pooled = 0.8262 for F_c and 0.6803 without `missing_gate`. Both are lower than the primary
  values and still at least 0.5. The protocol does not use the baseline for H1, and it is reported
  here only as context.
- **Dependent observations.** Within a circuit, all suites are evaluated on the same removal mutants
  and the same faults, and x and y are computed on the same circuit. The points are therefore not
  independent samples. The permutation p-values test only the null hypothesis that detection rates
  are exchangeable across suites within each circuit. They are **descriptive, one-sided (positive
  association)**, uncorrected for multiplicity, and they did not affect any hypothesis
  (`p_values_affect_hypotheses: false`).
- **Resolution of the p-values.** Per circuit, p_c is a count over all n_c! orderings, so its
  smallest possible value is limited, for example 1/24 for 4 points. Ties raise it further (C5 and C6:
  1/12). For the pooled statistic, b = 0 of B = 100,000 gives p = 1/100,001: no permutation reached
  the observed numerator. This is a bound set by B, not an exact tail probability.
- **What H1 "supported" means.** The approved decision rule was met for both fault sets. Within this
  catalogue and these suites, ranking suites by adjusted removal score and ranking them by
  catalogue-fault detection rate are strongly concordant (τ_pooled 0.9054 and 0.8321). This holds
  subject to the small samples, ties, the T1 point and the dependence described above. It does not show
  a causal relation, nor that the association holds for other circuits, faults, operators or suites.

## 7. RQ3: T5 versus `distribution_oracle` (H3)

The oracle uses shots `shots_for_threshold(0.05, num_clbits)`, seed `oracle/<circuit>` and
δ = `family_delta(0.05, g + 2)` (PROTOCOL section 9). It is run over the same removal mutants as T5.
Δ_c = score(T5) − score(oracle), both primary adjusted. The results field `delta` is the oracle's δ,
not Δ_c (finding R5).

**Observed:**

| Circuit | Generated mutants g | Oracle shots | Oracle δ = family_delta(0.05, g+2) | Oracle seed slot | T5 adjusted score | Oracle adjusted score | Δ_c | Both killed | Both survived | T5 only | Oracle only | With error | Agreement |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 3 | 12908 | 0.010000 | `oracle/C1` | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | 3 | 0 | 0 | 0 | 0 | 1 (1.0000) |
| C2 | 13 | 19088 | 0.003333 | `oracle/C2` | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | 13 | 0 | 0 | 0 | 0 | 1 (1.0000) |
| C3 | 11 | 12908 | 0.003846 | `oracle/C3` | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | 11 | 0 | 0 | 0 | 0 | 1 (1.0000) |
| C4 | 43 | 12908 | 0.001111 | `oracle/C4` | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | 39 | 4 | 0 | 0 | 0 | 1 (1.0000) |
| C5 | 9 | 12908 | 0.004545 | `oracle/C5` | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | 3 | 6 | 0 | 0 | 0 | 1 (1.0000) |
| C6 | 7 | 12908 | 0.005556 | `oracle/C6` | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | 6 | 1 | 0 | 0 | 0 | 1 (1.0000) |

**H3: supported.** Δ_c is defined for all 6 circuits, and |Δ_c| = 0 ≤ 0.1 in all 6 (the rule needs 4).

**Observed:** in every circuit, T5 and the oracle produced identical outcomes for every removal
mutant. Every survivor under either is an IDEAL-equivalent mutant: 4 in C4, 6 in C5 and 1 in C6, equal
to the equivalent survivors in section 5. Both adjusted scores are therefore 1 in every circuit.

**Interpretation:** H3 is supported **only within this catalogue and protocol**. At these shot
counts, both T5 and the oracle detected every non-equivalent removal mutant of these six circuits, so
the comparison cannot separate them. The result says nothing about circuits with more classical bits,
smaller distribution changes, other shot budgets or other mutation operators. Neither suite is a
bound on the other (PROTOCOL section 9). As the protocol states, the results do not record whether an
oracle survivor was `WITHIN_TOLERANCE` or `INCONCLUSIVE`.

## 8. RQ4: seed sensitivity of removal-mutant scores (H4)

For every circuit and applicable sampling suite (T2–T5), the removal-mutant run and its IDEAL
classification were repeated with the 20 seeds `rq4/<circuit>/<suite>/01…20`, none of which is the
primary seed. RQ4 measures the seed sensitivity of mutation scores only, **not** of fault detection
rates (PROTOCOL section 9).

**Observed:**

| Circuit/suite | Defined scores | Minimum | Maximum | Range | > 0.1 | Scores (value × seeds) | Seed slots |
|---|---|---|---|---|---|---|---|
| C1/T3 | 20 | 2/3 (0.6667) | 2/3 (0.6667) | 0 (0.0000) | no | all 20 = 2/3 | `rq4/C1/T3/01…20` |
| C1/T4 | 20 | 1/3 (0.3333) | 1/3 (0.3333) | 0 (0.0000) | no | all 20 = 1/3 | `rq4/C1/T4/01…20` |
| C1/T5 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C1/T5/01…20` |
| C2/T2 | 20 | 6/13 (0.4615) | 11/13 (0.8462) | 5/13 (0.3846) | yes | 6/13×11, 11/13×9 | `rq4/C2/T2/01…20` |
| C2/T3 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C2/T3/01…20` |
| C2/T4 | 20 | 5/13 (0.3846) | 5/13 (0.3846) | 0 (0.0000) | no | all 20 = 5/13 | `rq4/C2/T4/01…20` |
| C2/T5 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C2/T5/01…20` |
| C3/T2 | 20 | 4/11 (0.3636) | 1 (1.0000) | 7/11 (0.6364) | yes | 4/11×10, 1/1×10 | `rq4/C3/T2/01…20` |
| C3/T3 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C3/T3/01…20` |
| C3/T4 | 20 | 5/11 (0.4545) | 5/11 (0.4545) | 0 (0.0000) | no | all 20 = 5/11 | `rq4/C3/T4/01…20` |
| C3/T5 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C3/T5/01…20` |
| C4/T2 | 20 | 19/39 (0.4872) | 7/13 (0.5385) | 2/39 (0.0513) | no | 19/39×4, 20/39×4, 7/13×12 | `rq4/C4/T2/01…20` |
| C4/T4 | 20 | 11/13 (0.8462) | 11/13 (0.8462) | 0 (0.0000) | no | all 20 = 11/13 | `rq4/C4/T4/01…20` |
| C4/T5 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C4/T5/01…20` |
| C5/T4 | 20 | 1/3 (0.3333) | 1/3 (0.3333) | 0 (0.0000) | no | all 20 = 1/3 | `rq4/C5/T4/01…20` |
| C5/T5 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C5/T5/01…20` |
| C6/T4 | 20 | 2/3 (0.6667) | 2/3 (0.6667) | 0 (0.0000) | no | all 20 = 2/3 | `rq4/C6/T4/01…20` |
| C6/T5 | 20 | 1 (1.0000) | 1 (1.0000) | 0 (0.0000) | no | all 20 = 1/1 | `rq4/C6/T5/01…20` |

**H4: not supported.** Two ranges exceed 0.1: C2/T2 = 5/13 (0.3846) and C3/T2 = 7/11 (0.6364). All 18
ranges are defined, and every seed gave a defined score.

**Observed variation.** The variation comes only from T2 (unique mode): from removals of `h` gates in
C2 and C3, and of `h` and `ccx` gates in C4:
- **C2/T2:** 9 mutants change outcome across the 20 seeds. Their outcomes follow exactly two joint
  patterns, occurring for 11 and 9 seeds, and these give the scores 6/13 and 11/13.
- **C3/T2:** 7 mutants change outcome together. They are all killed for 10 seeds and all survive for
  10, giving 1 and 4/11.
- **C4/T2:** 5 mutants vary (3 `h`, 2 `ccx`), giving a range of 2/39.

The primary-seed scores (C2/T2 11/13, C3/T2 1, C4/T2 19/39) are each one of the values seen across
the 20 RQ4 seeds. Every other circuit–suite pair gave the same score for all 20 seeds.

**Additional exact computation** (made during the review of this report; not stored in the results
files). The ideal output distribution of each varying T2 mutant was computed from the circuits with
`run_study.independent_distribution`, deterministically, without sampling and without running a suite.
In all 21 varying mutants (9 in C2, 7 in C3, 5 in C4), the expected mode is **exactly tied** with
at least one other outcome:
- two outcomes at 1/2 each in C2 and C3;
- four outcomes at 1/4 for the three `h` removals in C4;
- all eight outcomes at 1/8 for the two `ccx` removals in C4.

**Interpretation:** H4 not being supported is a **research result about T2, not a software
failure**. For a mutant whose expected mode is exactly tied, a unique-mode check passes or fails
depending on which tied outcome is sampled most often, which is consistent with the observed seed
dependence. In C2 and C3 the varying mutants change outcome together across seeds (two joint
patterns). This is consistent with each run reusing one seed for every call (PROTOCOL section 10),
although the results do not isolate that mechanism. A single-seed T2 mutation score for C2 or C3
should therefore not be read as a stable property of the suite. The other sampling suites gave the
same score for all 20 seeds on these circuits.

## 9. Cross-environment comparison (PROTOCOL section 14)

**Observed:**
- Same environment: runs a and b are byte-identical in each environment (`cmp`, equal SHA-256).
- Across environments: the result bodies (everything except `metadata`) are **identical**, 0
  differing values. The only metadata difference is `environment.qiskit`. Everything that must match
  exactly matched: pre-run checks (a)–(c), behaviour-equivalence groups, fault classes, equivalence
  verdicts, and T1 and T6 outcomes.
- The values that may differ (sampled counts, T2–T5 and oracle outcomes, and everything derived from
  them) were also identical. There is therefore no difference to tabulate.

**Interpretation:** with identical seeds, NumPy 2.4.6 and `BasicSimulator` 0.1, both Qiskit versions
produced the same samples here. The README states that seeded counts are not promised to be identical
across versions, so this agreement is an observation for this pair of versions, not a guarantee.

## 10. Hypothesis summary

| Hypothesis | Fault set | Rule (protocol) | Observed basis | Status |
|---|---|---|---|---|
| H1 | F_c | τ_pooled ≥ 0.5 and τ_b(c) > 0 in ≥ 4 circuits (7.6) | τ_pooled 0.9054; 6/6 positive | supported |
| H1 | without `missing_gate` | same | τ_pooled 0.8321; 6/6 positive | supported |
| H3 | — | \|Δ_c\| ≤ 0.1 in ≥ 4 of ≥ 4 defined (9) | Δ_c = 0 in 6/6 | supported |
| H4 | — | every defined range ≤ 0.1 (9) | C2/T2 5/13 and C3/T2 7/11 exceed 0.1 | not supported |

RQ2 is descriptive (section 5). These statuses follow the frozen decision rules. They are not proofs
that the hypotheses are true, and a status is not confirmed merely because the software ran without
error.

## 11. Limitations, generalisation and findings

**Limitations of the study design.**
- **Small and specific population:** six small circuits, 70 hand-written faults (57 non-equivalent)
  and six fixed suites. The results do not generalise beyond this catalogue, its circuits, the
  removal operator, noiseless `BasicSimulator` simulation and the measured-outcome sizes used here.
- **RQ1:**
  - 4–6 dependent points per circuit;
  - heavy ties;
  - the structural (0, 0) point of T1;
  - descriptive p-values only;
  - one primary seed per suite for fault detection, whose seed sensitivity was not measured
    (PROTOCOL section 9).
- **RQ3:** both suites scored 1 everywhere, so their ability to discriminate between suites is not
  tested by this catalogue. Survivor verdicts are not separable.
- **RQ4:** 20 seeds per pair. A range is a coarse summary, and the variation concentrates in T2.
- **Seed sensitivity of single-run values:** any value from a T2 run on C2 or C3 depends strongly on
  the seed (section 8). The fault detection rates in section 6 use the primary seed only.
- **Execution evidence:** the formal-run logs are not archived with the project (finding R8). The
  results files, their hashes and the byte-identical a/b pairs are the verifiable record.
- **Additional computation:** the exact mode ties in section 8 come from a deterministic computation
  made during review, not from the results files.
- **PROTOCOL section 12 notes** (preliminary, not hypotheses). These are the observed outcomes for
  the faults the protocol flagged before the run:

| Fault | Suite | Observed outcome (primary seed) |
|---|---|---|
| C1-F03 | T4 | detected |
| C1-F03 | T5 | undetected |
| C2-F06 | T2 | undetected |
| C2-F08 | T2 | detected |
| C2-F09 | T2 | detected |
| C3-F06 | T2 | detected |
| C3-F08 | T2 | detected |
| C4-F09 | T2 | undetected |
| C4-F10 | T2 | detected |
| C6-F05 | T4 | undetected |
| C6-F05 | T5 | undetected |
| C3-F09 | T3 | detected |
| C1-F11 | T6 | undetected |
| C2-F10 | T6 | undetected |
| C3-F10 | T6 | undetected |
| C4-F06 | T6 | undetected |
| C5-F08 | T6 | undetected |
| C6-F10 | T6 | undetected |

**Findings: protocol versus artefacts** (documented, not corrected):

| ID | Finding | Effect |
|---|---|---|
| R1 | PROTOCOL section 6 asks RQ2 to report "skipped by reason". The results store `not_run` without a `skip_reason`. All 96 skipped candidates are `measure` instructions, run with `allow_measure=False`, so the reason is `measurement_not_allowed` by inference, not by record. | RQ2 skip reasons are inferred. |
| R2 | The frozen environment fingerprint includes `RECORD` hashes that depend on the virtual environment's absolute path: the console scripts of `numpy`, `dill` and `sympy` contain that path, in the shebang line or in an `exec` line after `#!/bin/sh`. The original Qiskit 2.0.3 environment lived in a temporary directory outside the project. A rebuilt environment reproduces every package version and passes the tests and two checkers, but `check_code_freeze --require-approved` fails on "environment qiskit-2.0.3 unchanged" (22/23). | The approved freeze gate, and therefore `run_study`, refuses in a rebuilt Qiskit 2.0.3 environment unless its scripts produce identical `RECORD` hashes (same absolute path and script form), which was not verified. Re-validating a rebuilt environment needs a new approved environment entry. The results themselves can still be verified (section 12). |
| R8 | The logs of the formal run (exit statuses of every section 16 step) were written outside the project and are not archived with it. | The statement in section 3.2 that every step exited with status 0 cannot be checked from the repository; the results files, their hashes and the a/b identity can. |
| R3 | `qmutate.__version__` reads installed package metadata, so `import qmutate` fails when the source is used only through `PYTHONPATH=src`. | Every environment needs an installed copy of qmutate (section 3.4). |
| R4 | Section 16 steps `make_seeds` and `--record-seeds` were not executed (first-binding steps), and the pre-run was not repeated (already run under the same freeze). | None on the results (section 3.2). |
| R5 | In `rq3`, the field `delta` is the oracle's δ = `family_delta(0.05, g + 2)`; Δ_c is `delta_c`. | Naming only. |
| R6 | The results files carry `protocol_revision` (9) but no separate schema-version field. | The format is defined by PROTOCOL section 13 at revision 9. |
| R7 | PROTOCOL section 15 criterion 7 allows one README link to this study, if approved. None has been added. | Pending decision. |

## 12. Re-running the analysis from the artefacts

None of the following runs an experiment, samples a study circuit or writes a file in the project.
**Do not run `run_study`, `make_seeds` or any `check_code_freeze` action** (`--write`, `--approve`,
…) for this purpose. Run the commands from the project root in an environment set up as in section
3.4.

1. Verify the artefacts against section 2.1 and section 3.3:

```bash
shasum -a 256 evaluation/code_freeze.json evaluation/code_freeze.lock.json evaluation/seeds.json evaluation/seeds.lock.json evaluation/PROTOCOL.md evaluation/protocol.lock.json evaluation/results/*.json
```

2. Run the read-only checks. In the project environment (Qiskit 2.6.1) all three pass. In a rebuilt
   Qiskit 2.0.3 environment (section 3.4), `check_code_freeze --require-approved` is expected to
   **fail** with exactly one failed check, "environment qiskit-2.0.3 unchanged" (finding R2), while the
   other two pass; any other failure is a real integrity problem.

```bash
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_code_freeze --require-approved
```

```bash
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_catalogue
```

```bash
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_protocol
```

3. Recompute every statistic and hypothesis status from a results file with the study's own
   `evaluation.analysis` functions. Save the following script **outside the project directory**, for
   example as `/tmp/recompute.py`, and run it from the project root:

```bash
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src:. PYTHONDONTWRITEBYTECODE=1 python /tmp/recompute.py
```

```python
import json
from fractions import Fraction

from evaluation import analysis, make_seeds, study_config

RESULTS = "evaluation/results/run-qiskit-2.6.1-a.json"
doc = json.load(open(RESULTS))
seeds = make_seeds.load_seeds("evaluation/seeds.json", study_config.seed_slots(), study_config.SEED_FILE_REVISIONS)
classes, suites, groups = doc["fault_classification"], doc["suites"], doc["behaviour_groups"]


def plain(value):
    return json.loads(json.dumps(value, default=lambda v: f"{v.numerator}/{v.denominator}"
                                 if isinstance(v, Fraction) else sorted(v)))


for fault_set in study_config.FAULT_SETS:
    primary, dedup, baseline = {}, {}, {}
    for cid, circuit_suites in suites.items():
        selected = [f for f, r in classes.items() if f.startswith(cid + "-") and r["class"] == "D-NOT-EQUIVALENT"
                    and (fault_set == "all" or not r["missing_gate"])]
        primary[cid], dedup[cid], baseline[cid] = [], [], []
        for suite, entry in circuit_suites.items():
            if entry["excluded"]:
                continue
            outcomes = {f: entry["faults"][f]["outcome"] for f in selected}
            score = None if entry["scores"]["adjusted_score"] is None else Fraction(entry["scores"]["adjusted_score"])
            rate = analysis.detection_rate(outcomes)["rate"]
            if score is not None and rate is not None:
                primary[cid].append((score, rate))
            if suite in study_config.DEDUP_SUITES:
                key = "t6_groups" if suite == "T6" else "groups"
                rate_dedup = analysis.dedup_detection_rate([tuple(g) for g in groups[cid][fault_set][key]], outcomes)["rate"]
                if score is not None and rate_dedup is not None:
                    dedup[cid].append((score, rate_dedup))
                if score is not None and rate is not None:
                    baseline[cid].append((score, rate))
    result = analysis.fault_set_statistics(
        primary, dedup, baseline,
        {s: seeds[f"permutation/primary/{fault_set}/{s}"] for s in study_config.POOLED_STATISTICS},
        {s: seeds[f"permutation/dedup_sensitivity/{fault_set}/{s}"] for s in study_config.POOLED_STATISTICS},
        study_config.PERMUTATIONS)
    recorded = doc["statistics"][fault_set]
    same = all(plain(result[k]) == recorded[k] for k in ("primary", "h1", "dedup_sensitivity"))
    print(f"{fault_set}: H1 {result['h1']}, tau_pooled {result['primary']['tau_pooled']['value']:.4f}; "
          f"recomputed statistics equal the results file: {same}")
h3 = analysis.h3_status({c: None if r["delta_c"] is None else Fraction(r["delta_c"]) for c, r in doc["rq3"].items()})
h4 = analysis.h4_status({k: None if r["range"] is None else Fraction(r["range"]) for k, r in doc["rq4"].items()})
print(f"H3 {h3} (recorded {doc['hypotheses']['H3']}); H4 {h4} (recorded {doc['hypotheses']['H4']})")
```

Expected output (verified on the Qiskit 2.6.1 environment; it takes a few seconds):

```text
all: H1 supported, tau_pooled 0.9054; recomputed statistics equal the results file: True
without_missing_gate: H1 supported, tau_pooled 0.8321; recomputed statistics equal the results file: True
H3 supported (recorded supported); H4 not supported (recorded not supported)
```

The script rebuilds the data points from the recorded suite scores, fault outcomes, classes and
groups. It reruns the exact statistics and seeded permutations of PROTOCOL sections 7–9, and compares
them with the recorded `statistics`. Set `RESULTS` to the Qiskit 2.0.3 file to check that run.

## 13. File references

| Path | Content |
|---|---|
| `evaluation/PROTOCOL.md`, `evaluation/protocol.lock.json` | approved protocol, revision 9 |
| `evaluation/manifest.json`, `evaluation/CATALOGUE_FREEZE.md`, `evaluation/preflight/` | frozen catalogue and preflight evidence |
| `evaluation/code_freeze.json`, `evaluation/code_freeze.lock.json` | approved code freeze |
| `evaluation/seeds.json`, `evaluation/seeds.lock.json` | seeds and their binding |
| `evaluation/freeze_history/` | archived and rejected freezes, retirement, rejection and re-bind records |
| `evaluation/results/pre-run-qiskit-*.json` | pre-run stage results |
| `evaluation/results/run-qiskit-*-{a,b}.json` | formal results: `pre_run`, `fault_classification`, `behaviour_groups`, `suites`, `rq3`, `rq4`, `statistics`, `hypotheses`, `execution_order`, `deviations`, `metadata` |
| `evaluation/study_config.py`, `evaluation/run_study.py`, `evaluation/analysis.py`, `evaluation/suites.py` | parameters, driver, statistics, suites |
