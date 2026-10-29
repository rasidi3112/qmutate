# Phase 6A preflight validation record

Status: validation complete; catalogue **not frozen**; formal Phase 6A study **not started**.
This record covers execution and exact-distribution checks only. No T1–T6 suite was run against any
mutant, and no mutation score, detection rate, correlation, p-value or seed-sensitivity result was
computed.

## Environments

| | Environment A | Environment B |
|---|---|---|
| Python | 3.11.14 | 3.11.14 |
| Qiskit | 2.6.1 | 2.0.3 |
| NumPy | 2.4.6 | 2.4.6 |
| BasicSimulator `backend_version` | 0.1 | 0.1 |
| qmutate | 0.1.0 (unmodified `src/`) | 0.1.0 (unmodified `src/`) |
| Platform | macOS 27.0 arm64 | macOS 27.0 arm64 |

## Entry points

Run from the project root, once per environment:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python evaluation/preflight/validate.py
PYTHONDONTWRITEBYTECODE=1 python evaluation/preflight/smoke.py
```

| File | Role |
|---|---|
| `catalogue.py` | Barrier-free circuit definitions, all 70 fault edits, catalogue predictions and labels |
| `validate.py` | Independent distribution cross-check, classifier comparison, structural checks, counts |
| `smoke.py` | BasicSimulator execution check only |
| `results/validate-qiskit-<version>.json` | Full record, including the complete distribution of every fault |
| `results/smoke-qiskit-<version>.json` | Execution status per circuit |

These scripts are validation tools, separate from the qmutate package; `src/` was not changed.

## Frozen-definition constraint: barrier-free circuits

All six circuits and all 70 faults contain no barriers (checked). Fault instruction indices refer to
the barrier-free operation lists in `catalogue.py`. C4 indices, verified exactly:

| C4 block | Indices |
|---|---|
| initial H | 0–2 |
| oracle 1 | 3–7 |
| diffuser 1 | 8–22 |
| oracle 2 | 23–27 |
| diffuser 2 | 28–42 |
| measurements | 43–45 |

Inserting a barrier after each C4 block gives 51 instructions and moves the first measurement to
index 48, so the documented indices would no longer hold; the ideal distribution is unchanged
(TV 0).

## Tolerances

| Check | Tolerance |
|---|---|
| Classifier verdict (`check_equivalence`, approved) | atol 1e-8 on total variation |
| Original statevector vs documented state, after global-phase alignment by overlap | max abs difference ≤ 1e-8 |
| Agreement between independent, classifier and catalogue distributions | TV ≤ 1e-9 |

## Independent cross-check method

`validate.py::independent_distribution` does not use qmutate. It simulates the gate instructions in
order with `qiskit.quantum_info.Statevector`, requires measurements to be terminal, and applies the
measurements in circuit order to a classical register initialised to 0, so a repeatedly written bit
keeps its last written value and an unwritten bit stays 0. Self-checks on hand-made circuits
(unwritten bits, last write wins in both directions, one qubit into two bits) all pass.

## Results

Identical on both environments.

**Original circuits.** All six match their documented distributions (TV ≤ 2.2e-15) and statevectors
(max difference after phase alignment ≤ 1.9e-15; aligned global phase 0, or 8e-16 rad for C5).
The independent and classifier distributions agree exactly (TV 0).

**Faults (70).** Every fault passes every check:

- the classifier's IDEAL_DISTRIBUTION class and the independent class equal the catalogue
  prediction;
- the independent distribution matches the catalogue (largest TV 2.9e-15) and the classifier
  (largest TV 0);
- UNITARY is `UNKNOWN (MEASUREMENT)` for every fault, as required by the current protocol;
- measurement-only faults identified structurally match the catalogue;
- every gate is in BasicSimulator's operation set, and every circuit is reproducible;
- every `missing_gate` fault is exactly `remove_instruction(original, index)`.

Distributions are bit-identical between Qiskit 2.6.1 and 2.0.3. The smallest not-equivalent TV is
0.04198 (C6-F05); every equivalent fault has TV 0. Discrepancies found: **none**.

**Smoke test.** BasicSimulator (`shots=16`, `seed_simulator=0`) ran all 6 originals and all
70 faults (76 circuits) without an exception on both environments. Counts were neither inspected
nor stored.

## Catalogue counts (C5-F12 and C6-F12 included)

Distinct behaviours are distinct pairs of (ideal distribution, measurement-only flag) among
D-NOT-EQUIVALENT faults; distinct distributions ignore the flag. These are three separate measures,
not minimums.

**All faults**

| Circuit | Faults | D-NOT-EQUIVALENT | D-EQUIVALENT | UNKNOWN | Distinct behaviours | Distinct distributions |
|---|---|---|---|---|---|---|
| C1 | 12 | 9 | 3 | 0 | 8 | 7 |
| C2 | 11 | 10 | 1 | 0 | 10 | 10 |
| C3 | 11 | 10 | 1 | 0 | 9 | 8 |
| C4 | 12 | 10 | 2 | 0 | 9 | 9 |
| C5 | 12 | 9 | 3 | 0 | 9 | 9 |
| C6 | 12 | 9 | 3 | 0 | 8 | 7 |
| **Total** | **70** | **57** | **13** | **0** | **53** | **50** |

**Subset without `missing_gate`** (reported separately; no minimum applies)

| Circuit | Faults | D-NOT-EQUIVALENT | D-EQUIVALENT | Distinct behaviours | Distinct distributions |
|---|---|---|---|---|---|
| C1 | 10 | 7 | 3 | 7 | 6 |
| C2 | 8 | 7 | 1 | 7 | 7 |
| C3 | 8 | 7 | 1 | 7 | 7 |
| C4 | 10 | 9 | 1 | 8 | 8 |
| C5 | 8 | 6 | 2 | 6 | 6 |
| C6 | 9 | 7 | 2 | 6 | 5 |
| **Total** | **53** | **43** | **10** | **41** | **39** |

UNITARY: all 70 faults `UNKNOWN (MEASUREMENT)`; no state-only classification is made.

## Labels carried forward (not verified here)

- Seed-sensitive: C1-F03 (T4, T5), C2-F06, C2-F08, C2-F09, C3-F06, C3-F08, C4-F09, C4-F10 (T2),
  C6-F05 (T4, T5).
- Borderline: C3-F09 (T3).
- Behaviourally redundant (identical distributions, confirmed): {C1-F05, C1-F07, C1-F11},
  {C3-F01, C3-F05}, {C3-F02, C3-F10}, {C4-F01, C4-F04}, {C6-F04, C6-F11}, {C6-F07, C6-F10}.
  Redundant faults are kept and are not independent evidence.

## Known limitations

- The independent cross-check is independent of qmutate's measurement mapping, not of Qiskit: both
  it and the classifier take probabilities from Qiskit `Statevector`.
- Catalogue distributions are hand derivations transcribed into `catalogue.py`; agreement shows
  the transcription and the circuits are consistent, not that the derivations were done
  independently twice.
- The smoke test shows only that execution completes; it says nothing about output correctness.
- T2–T6 predictions, including T6 state-difference predictions for D-EQUIVALENT faults, are not
  verified here; they belong to the formal study.
- `validate.py` reads qmutate's private `_ideal_distribution` for comparison only.
- Results are recorded for Qiskit 2.6.1 and 2.0.3 on one platform.
