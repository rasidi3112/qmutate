# Freeze history

This directory is the historical audit trail of the Phase 6A code freeze. It keeps every superseded
freeze and every rejected freeze proposal byte-for-byte, together with the records written when each
one was archived, re-bound or rejected. Nothing here is modified or deleted after it is written
(`evaluation/PROTOCOL.md`, section 13).

The files in this directory are **not** the artefacts of the final experiment. The final, approved
freeze is the set of live files listed in `evaluation/code_freeze.json`, at their normal paths. This
README was added after the archives were complete. It is not part of any freeze record, and the freeze
tooling skips it: the seed-history check reads only JSON files and `seeds.json` here.

## The final freeze

| Live file | SHA-256 | State |
|---|---|---|
| `evaluation/code_freeze.json` | `e8961cd3ceda31055cc52bd824f0cb31a89872fc0315d82146f6ba3903c76292` | manifest, protocol revision 9 |
| `evaluation/code_freeze.lock.json` | `6d44fc5bf504ef3f1e442280fd89e1ec1c3678aaf9b658f3ba111f7ee239794d` | lock, status `approved` |
| `evaluation/seeds.json` | `15c2a225e3f880386976e75fd401b58a9c3f6630629a6c0c1f6babf92dbffdb3` | seeds |
| `evaluation/seeds.lock.json` | `5c4a17bc4f816bfd6211a0229a8e3536530c51835ff33cc2bc8c70f9ea8827fa` | binds the seeds to the manifest |

All six files in `evaluation/results/` record exactly these four hashes in their metadata
(`code_freeze_sha256`, `code_freeze_lock_sha256`, `seeds_sha256`, `seeds_lock_sha256`). None of
them records any other manifest or lock, including those archived here.

### Telling final artefacts from archived ones

- A file is part of the final freeze only if it is at its normal path outside this directory and its
  SHA-256 matches `evaluation/code_freeze.json`. The freeze check verifies this:

  ```bash
  VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_code_freeze --require-approved
  ```

- Every file under `evaluation/freeze_history/` other than this README is an archive copy or record. Archived copies of covered files
  carry the suffix `.orig` or `.rejected`, and in `v2*/` their original path has `/` replaced by `__`,
  so they cannot be imported or collected by the tests as they are.
- Archived manifests and locks are byte-identical copies, so their internal fields still name the
  live location (for example `"manifest": "evaluation/code_freeze.json"`). That field describes where
  the file was live when it was archived, not where the copy is now.
- A lock with `"status": "proposed"` was never approved. Each lock under a `rejected/` directory has
  this status.
- To check which freeze a results file used, compare its `metadata.code_freeze_sha256` with the live
  lock's `sha256` field.

## Layout

```text
freeze_history/
├── v1/                 freeze v1 (approved, superseded)
├── v2/                 first re-freeze cycle out of freeze v2
│   └── rejected/       freeze proposal v3 (protocol revision 7), rejected
├── v2-r2/              second re-freeze cycle out of freeze v2
│   └── rejected/       freeze proposal c9b67ef1… (protocol revision 8), rejected
└── v2-r3/              third re-freeze cycle out of freeze v2; its proposal is the final freeze
```

A history directory is named after the **outgoing** freeze, the one being replaced, not after the
proposal that replaces it (PROTOCOL section 13). This is why the three cycles that replaced freeze v2
are `v2`, `v2-r2` and `v2-r3`. Section 13 also requires a new directory for each cycle once a
directory holds a rejected proposal.

| Directory | Contents |
|---|---|
| `v1/` | Freeze v1: manifest `163fdd6f…` (protocol revision 6), its `approved` lock, the seeds lock that bound the seeds to v1, a copy of `seeds.json`, the v1 version of `tests/test_evaluation_harness.py` (`test_evaluation_harness.py.orig`) and `HISTORY.json`. |
| `v2/` | The outgoing freeze v2: manifest `7b980eb3…` (protocol revision 6), its `approved` lock `ea4f9a6d…` and its seeds lock `d49a3f5d…`. Also the v2 versions of the 10 files the next proposal changed (`.orig`), `ORIGINALS_INDEX.json`, `FREEZE_RETIREMENT.json`, `SEEDS_REBIND.json` and `SEEDS_BINDING.json`. |
| `v2/rejected/` | Freeze proposal v3: manifest `40788a9c…` (revision 7), its `proposed` lock, its re-bound seeds lock, the 10 proposed files (`.rejected`) and `FREEZE_REJECTION.json`. |
| `v2-r2/` | The same outgoing freeze v2 (byte-identical manifest, lock, seeds lock and 10 `.orig` files), with this cycle's `FREEZE_RETIREMENT.json` and `SEEDS_REBIND.json`. |
| `v2-r2/rejected/` | Freeze proposal `c9b67ef1…` (revision 8): its manifest, its `proposed` lock, re-bound seeds lock, 10 `.rejected` files and `FREEZE_REJECTION.json`. |
| `v2-r3/` | The same outgoing freeze v2 and 10 `.orig` files, with this cycle's `FREEZE_RETIREMENT.json` and `SEEDS_REBIND.json`. It has no `rejected/` directory. The proposal of this cycle, `e8961cd3…`, is the live approved freeze. |

## File types

| File | Meaning |
|---|---|
| `code_freeze.json`, `code_freeze.lock.json`, `seeds.lock.json` | Byte-identical copies of the live manifest, lock and seeds lock at the time of archiving. |
| `seeds.json` (only in `v1/`) | Byte-identical copy of the seed file. Its SHA-256 equals the live `evaluation/seeds.json`. |
| `<path with / as __>.orig` | The outgoing version of a covered file, kept so that a full rollback to the outgoing freeze stays possible (PROTOCOL section 13, step 0). Its hash matches the outgoing manifest. The archive shows that the content matches; it does not record when each copy was made. `v1/test_evaluation_harness.py.orig` does not follow this naming rule and keeps only the file name; its hash matches the v1 manifest. |
| `rejected/<path with / as __>.rejected` | The version of a covered file in a proposal that was rejected. Its hash matches the rejected manifest. |
| `rejected/` | A proposal set aside before approval. It holds the proposal's manifest, its `proposed` lock, its seeds lock, its `.rejected` files and `FREEZE_REJECTION.json`. `FREEZE_REJECTION.json` names the outgoing approved freeze that was restored, and the `.rejected` files still match the rejected manifest. |
| `HISTORY.json` (`v1/`) | Archive date, the SHA-256 of each other file in `v1/`, and the status at archiving. |
| `FREEZE_RETIREMENT.json` | The record that `check_code_freeze --retire` publishes: the outgoing manifest and lock hashes, the lock status and the retired protocol revision. In `v2-r2/` and `v2-r3/` it also lists the `.orig` hashes and the seeds hash. The `v2/` record has neither; there the `.orig` hashes are listed in `ORIGINALS_INDEX.json`. |
| `ORIGINALS_INDEX.json` (`v2/`) | Each changed covered file, its archive name and its SHA-256, plus the outgoing manifest hash. |
| `SEEDS_REBIND.json` | The record that `check_code_freeze --rebind-seeds` publishes: the previous and new manifest and seeds-lock hashes, the seeds hash and the slot-schema hash. |
| `FREEZE_REJECTION.json` | The record that `check_code_freeze --reject` publishes: the hashes of the rejected manifest, lock, seeds lock and files, and of the restored outgoing manifest, lock and seeds lock. |
| `SEEDS_BINDING.json` (`v2/`) | The record of the Route A′ deviation (below). |

There is no `SEEDS_RECORD.json` and no `failed/` directory. `SEEDS_RECORD.json` was introduced in
protocol revision 8 and is written only by `--record-seeds` for a first seed binding. The seeds were
first bound under freeze v1 (revision 6), before that file existed. A `failed/` directory would hold
leftover partial files from interrupted writes (PROTOCOL section 13); none were archived.

The freeze check reads this directory but does not hash it. The seed-history check reads every
`seeds_sha256` field in the JSON files here and every archived `seeds.json`. The partial-file check
looks for hidden `.partial` files. All `seeds_sha256` values in this directory, and the archived
`v1/seeds.json`, equal the SHA-256 of the live `evaluation/seeds.json`.

## Sequence supported by the records

The order below is not based on timestamps. Within a directory, the records are linked by hashes: each
record names the manifest it retired, re-bound, rejected or restored. The records do not link one cycle
to the next. The order of the three cycles follows from their directory names (PROTOCOL section 13),
from the protocol revisions of their proposals (7, 8 and 9) and from the change log at the top of
`evaluation/PROTOCOL.md`, which names the rejected proposal of each earlier cycle. Only two records
carry a date, `v1/HISTORY.json` (`archived_on`) and `v2/SEEDS_BINDING.json`
(`date`), both 2026-10-29. No record carries a time. File modification times are not evidence and were
not used.

1. **Freeze v1** (manifest `163fdd6f…`, revision 6) was approved; its archived lock has status
   `approved`. The seeds (`15c2a225…`) were bound to it by `v1/seeds.lock.json`.
2. **v1 to v2.** `v1/HISTORY.json` records v1 as superseded by a re-freeze for two post-seed harness
   test corrections (Route A). The v1 and v2 manifests differ only in the hash of
   `tests/test_evaluation_harness.py`; parameters, environments and every other file hash are equal.
   Comparing `v1/test_evaluation_harness.py.orig` with `v2/tests__test_evaluation_harness.py.orig`
   shows changes in two tests that had assumed `seeds.json` does not exist (one of them also assumed
   `evaluation/results/` does not exist).
3. **Freeze v2** (manifest `7b980eb3…`, revision 6) was approved; its archived lock `ea4f9a6d…` has
   status `approved`. Its seeds lock `d49a3f5d…` was written before approval (Route A′,
   `v2/SEEDS_BINDING.json`).
4. **Cycle `v2`.** Freeze v2 was retired, proposal v3 (`40788a9c…`, revision 7) was written, the seeds
   were re-bound to it, and the proposal was rejected. `FREEZE_REJECTION.json` records v2 as restored.
5. **Cycle `v2-r2`.** The same sequence with proposal `c9b67ef1…` (revision 8), which was also
   rejected and v2 restored.
6. **Cycle `v2-r3`.** Freeze v2 was retired again, proposal `e8961cd3…` (revision 9) was written, and
   the unchanged seeds were re-bound to it (`v2-r3/SEEDS_REBIND.json`, new seeds lock `5c4a17bc…`).
   This directory does not record the approval. That `e8961cd3…` is approved is shown by the live lock
   status `approved`, which the documented procedure sets only through `check_code_freeze --approve`
   once every check passes (PROTOCOL section 13), and by the external approval anchor described
   below.

The reasons for each rejection are not stored in these records. The change log at the top of
`evaluation/PROTOCOL.md` describes the audit findings fixed after each rejected proposal, and states
for revisions 7, 8 and 9 that no scientific decision changed. This directory does not verify that
statement.

## Route A and Route A′

These labels come from the records themselves. The repository defines them only as far as described
here.

**Route A** is named in `v1/HISTORY.json`: v1 was "superseded by a re-freeze for two post-seed harness
test corrections". The archive is consistent with corrections made after the seeds existed: the seeds
were bound to v1 (`v1/seeds.lock.json`), only `tests/test_evaluation_harness.py` changed between the v1
and v2 manifests, and the changed tests are the two that had assumed `seeds.json` does not exist. The
repository does not define the letter "A" further, does not name any alternative route, and does not
record the commands used for the v1 to v2 re-freeze. Revision 6, which was in force at the time, had
no documented re-freeze procedure for existing seeds (`evaluation/PROTOCOL.md`, changes from revision
6). `--retire` and `--rebind-seeds` were added in revision 7, and `--reject` in revision 8.

The two labels describe different things. Route A names the v1 to v2 re-freeze as a whole. Route A′
concerns one step within freeze v2: how its seeds lock was written. The records do not state how the
two labels relate beyond the shared letter.

**Route A′** (written "Route A-prime" in the record) is documented in `v2/SEEDS_BINDING.json`. That
record states:

- what was done: `seeds.json` was restored byte-identically from `freeze_history/v1`, and
  `seeds.lock.json` was written **before** `--approve` using the checker's own serialisation and
  hashing functions, instead of with `--record-seeds` after approval;
- why: so that no state with an approved freeze and no seeds ever existed;
- the deviation: the protocol wording at the time (section 10) names `--record-seeds` as the command
  that creates `seeds.lock.json`;
- the stated evidence: a rehearsal on scratch copies in which the documented order gave a
  byte-identical seeds lock and lock. The rehearsal itself is not archived; only this statement of its
  outcome is.

The hashes in `SEEDS_BINDING.json` are consistent with the archive. Its seeds-lock hash equals
`v2/seeds.lock.json` (`d49a3f5d…`), and its "expected after --approve" lock hash equals the archived
approved v2 lock (`ea4f9a6d…`). The proposed v2 lock that it lists (`b2184b57…`) is not archived and
cannot be checked. From revision 7 on, the documented `--rebind-seeds` replaced this manual step; each
of the three later cycles has a `SEEDS_REBIND.json` record.

## Relation to the final freeze

- All three cycles replaced the same outgoing freeze v2. Their copies of the v2 manifest, lock, seeds
  lock and `.orig` files are byte-identical.
- The final manifest `e8961cd3…` covers the same 42 files as every manifest here. It differs from v2
  in 10 of them: `evaluation/PROTOCOL.md`, `evaluation/protocol.lock.json`, `evaluation/analysis.py`,
  `evaluation/check_code_freeze.py`, `evaluation/check_protocol.py`, `evaluation/make_seeds.py`,
  `evaluation/run_study.py`, `evaluation/study_config.py`, `evaluation/suites.py` and
  `tests/test_evaluation_harness.py`. The two rejected proposals changed the same 10 files.
  `src/qmutate/`, the other tests, the catalogue and the preflight evidence have the same hashes in
  every manifest here and in the final one. Among the parameters, only `PROTOCOL_REVISION` (6 to 9) and
  `SEED_FILE_REVISIONS` (added, `[6, 7, 8, 9]`) differ between v2 and the final manifest.
- Every seeds hash recorded here, in the seeds locks, the records and the archived `v1/seeds.json`, is
  the same, `15c2a225…`, and the final seeds lock binds that same file to `e8961cd3…`. The archived
  manifests do not record a seeds hash; the `seeds.sha256` anchor was added in revision 9.
- The `.orig` and `.rejected` files show earlier and rejected versions of code and protocol text. They
  were not used for the pre-run or the formal run: each results file records the SHA-256 of the code
  it ran with (`metadata.code_sha256`), and those hashes equal the live files, not these copies.

## What this directory does not contain

- **The approval decisions.** No record here says who approved a freeze or when. An external approval
  note and record for `e8961cd3…` are kept outside the repository; only their SHA-256 values are
  published, in `evaluation/REPORT.md` section 2.1. Their contents are not part of this repository, and
  a reader with the repository alone cannot verify them.
- **Reasons for rejection.** See the change log in `evaluation/PROTOCOL.md`.
- **Logs** of the commands that wrote these files.
- **Results.** The study results are in `evaluation/results/`, and the preflight evidence in
  `evaluation/preflight/results/`.

`.DS_Store` files that macOS may create here are not part of the archive and are excluded by the
project's `.gitignore`.

## Checking the archive

Each archived file can be checked against the record that lists it. On macOS, for example:

```bash
shasum -a 256 evaluation/freeze_history/v1/seeds.json evaluation/seeds.json
shasum -a 256 evaluation/freeze_history/v2/*.orig
shasum -a 256 evaluation/freeze_history/v2/rejected/*.rejected
```

Compare the output with `v1/HISTORY.json`, `v2/ORIGINALS_INDEX.json` and
`v2/rejected/FREEZE_REJECTION.json`. The live freeze is checked with
`check_code_freeze --require-approved`, shown above. That check runs the seed-history check, which
reads this directory.
