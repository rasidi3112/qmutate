"""Generate ``evaluation/seeds.json`` once (protocol revision 9, section 10).

Run from the project root:

    PYTHONDONTWRITEBYTECODE=1 python -m evaluation.make_seeds

Slots are filled in the fixed order of ``study_config.seed_slots()`` with
``secrets.randbits(63)``. The file is created exclusively: if it exists the
script stops without writing anything. The bytes are written to a synced partial file,
validated, and only then hard-linked to ``seeds.json``, so an interruption leaves either
no seed file or a complete, valid one.
"""

import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

from evaluation import study_config

PROJECT = Path(__file__).resolve().parent.parent
SEED_BITS = 63


def seed_document(slots, revision, randbits=secrets.randbits):
    """Return the seed file content for ``slots``, in slot order."""
    return {
        "protocol_revision": revision,
        "seed_bits": SEED_BITS,
        "seeds": [{"slot": slot, "seed": randbits(SEED_BITS)} for slot in slots],
    }


def serialize(document):
    """Return the exact bytes written for a seed document."""
    return (json.dumps(document, indent=1) + "\n").encode()


def _sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_seeds(path, slots, revision, randbits=secrets.randbits):
    """Create ``path`` with a new seed document; raise ``FileExistsError`` if it or a partial file exists.

    The bytes go to an exclusively created hidden partial file next to ``path``. It is
    flushed and synced, read back and validated against ``slots`` and ``revision``, and
    only then hard-linked to ``path``; the directory is synced after the link. An
    interruption therefore leaves either no ``path`` or a complete, valid one. The partial
    name is removed only after a successful link, when it names the same file. A partial
    file left by an interruption is kept as evidence and refuses the next run.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} already exists; seeds are never regenerated")
    partial = path.with_name(f".{path.name}.partial")
    data = serialize(seed_document(slots, revision, randbits))
    try:
        handle = open(partial, "xb")
    except FileExistsError as error:
        raise FileExistsError(f"leftover partial file {partial.name} is kept as evidence; follow the protocol's "
                              "recovery for an interrupted seed generation") from error
    with handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if partial.read_bytes() != data:
        raise ValueError(f"{partial.name} does not hold the bytes just written")
    load_seeds(partial, slots, revision)
    os.link(partial, path)
    _sync_directory(path.parent)
    partial.unlink()
    return hashlib.sha256(data).hexdigest()


def load_seeds(path, slots, revision):
    """Return ``{slot: seed}`` from ``path`` after validating it against ``slots``.

    ``revision`` is one accepted protocol revision or a tuple of them; the seed file records
    the revision under which it was generated.
    """
    accepted = (revision,) if isinstance(revision, int) else tuple(revision)
    document = json.loads(Path(path).read_text())
    if document.get("protocol_revision") not in accepted:
        raise ValueError(f"seed file revision {document.get('protocol_revision')} is not one of {accepted}")
    entries = document.get("seeds")
    if not isinstance(entries, list) or [e.get("slot") for e in entries] != list(slots):
        raise ValueError("seed slots differ from the protocol's slot list or order")
    for entry in entries:
        seed = entry.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** SEED_BITS:
            raise ValueError(f"seed for {entry.get('slot')} is not an integer in [0, 2**{SEED_BITS})")
    return {entry["slot"]: entry["seed"] for entry in entries}


def main(freeze_checks=None):
    """Write the study's seed file, refusing to overwrite or to run without an approved code freeze."""
    if freeze_checks is None:
        from evaluation import check_code_freeze

        freeze_checks = lambda: check_code_freeze.verify(require_approved=True)
    try:
        results = freeze_checks()
    except Exception as error:
        results = [(f"code freeze check raised {type(error).__name__}", False, "")]
    failed = [name for name, passed, _ in results if not passed]
    if failed or not results:
        print("refusing: the code freeze is not approved or does not verify")
        for name in failed:
            print(f"  {name}")
        return 1
    path = PROJECT / study_config.SEEDS_FILE
    try:
        digest = write_seeds(path, study_config.seed_slots(), study_config.PROTOCOL_REVISION)
    except FileExistsError as error:
        print(error)
        return 1
    print(f"wrote {study_config.SEEDS_FILE} with {len(study_config.seed_slots())} seeds, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
