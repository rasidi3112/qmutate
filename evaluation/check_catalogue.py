"""Structural checks of the frozen Phase 6A catalogue and its manifest.

Run from the project root:

    PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_catalogue
    PYTHONDONTWRITEBYTECODE=1 python -m evaluation.check_catalogue --write-manifest

The checks build circuits but never simulate, sample or classify them, and
run no T1-T6 suite. ``--write-manifest`` regenerates ``manifest.json`` from
the canonical source; it is used once, at freeze time.
"""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from qiskit.circuit import Barrier

from evaluation import circuits, faults
from evaluation.preflight import catalogue

ROOT = Path(__file__).resolve().parent
CANONICAL_SOURCE = ROOT / "preflight" / "catalogue.py"
MANIFEST = ROOT / "manifest.json"
EVIDENCE = (
    "preflight/PREFLIGHT.md",
    "preflight/validate.py",
    "preflight/smoke.py",
    "preflight/results/validate-qiskit-2.6.1.json",
    "preflight/results/validate-qiskit-2.0.3.json",
    "preflight/results/smoke-qiskit-2.6.1.json",
    "preflight/results/smoke-qiskit-2.0.3.json",
)
FAULT_ID = re.compile(r"^C[1-6]-F\d{2}$")


def sha256(path):
    """Return the SHA-256 hex digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(operations):
    """Return a SHA-256 digest of a canonical JSON form of an operation list."""
    text = json.dumps([list(op) for op in operations], separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def build_manifest():
    """Return the manifest generated from the canonical source."""
    circuit_rows = []
    for circuit_id in circuits.CIRCUIT_IDS:
        num_qubits, num_clbits = circuits.circuit_shape(circuit_id)
        operations = circuits.circuit_operations(circuit_id)
        circuit_rows.append({
            "id": circuit_id,
            "name": circuits.CIRCUIT_NAMES[circuit_id],
            "num_qubits": num_qubits,
            "num_clbits": num_clbits,
            "instructions": len(operations),
            "operations_sha256": fingerprint(operations),
        })
    fault_rows = []
    for fault in faults.FAULTS:
        operations = faults.fault_operations(fault.fault_id)
        fault_rows.append({
            "id": fault.fault_id,
            "circuit": fault.circuit_id,
            "category": fault.category,
            "tag": "missing_gate" if fault.missing_gate else "other",
            "expected_class": fault.expected_class,
            "measurement_only": fault.measurement_only,
            "former_reserve": fault.former_reserve,
            "instructions": len(operations),
            "operations_sha256": fingerprint(operations),
        })
    classes = Counter(row["expected_class"] for row in fault_rows)
    return {
        "catalogue_version": circuits.CATALOGUE_VERSION,
        "canonical_source": {"path": "evaluation/preflight/catalogue.py", "sha256": sha256(CANONICAL_SOURCE)},
        "constraints": {
            "barrier_free": True,
            "instruction_indices_refer_to": "barrier-free operation lists in the canonical source",
            "c4_index_map": {name: [start, stop - 1] for name, (start, stop) in circuits.C4_INDEX_MAP.items()},
        },
        "counts": {
            "circuits": len(circuit_rows),
            "faults": len(fault_rows),
            "D-NOT-EQUIVALENT": classes[faults.D_NOT_EQUIVALENT],
            "D-EQUIVALENT": classes[faults.D_EQUIVALENT],
            "missing_gate": sum(row["tag"] == "missing_gate" for row in fault_rows),
        },
        "circuits": circuit_rows,
        "faults": fault_rows,
        "preflight_evidence_sha256": {name: sha256(ROOT / name) for name in EVIDENCE},
    }


def run_checks(manifest):
    """Return a list of ``(check, passed, detail)`` tuples."""
    results = []

    def check(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    stored = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else None
    check("manifest exists", stored is not None)
    if stored is not None:
        check("canonical source unchanged since freeze",
              stored["canonical_source"]["sha256"] == manifest["canonical_source"]["sha256"])
        check("manifest matches regenerated manifest", stored == manifest)
    check("six circuits C1-C6", circuits.CIRCUIT_IDS == ("C1", "C2", "C3", "C4", "C5", "C6"))
    check("70 unique fault ids", len(faults.FAULT_IDS) == 70 == len(set(faults.FAULT_IDS)))
    check("fault ids well formed and prefixed by their circuit",
          all(FAULT_ID.match(f.fault_id) and f.fault_id.startswith(f.circuit_id + "-") for f in faults.FAULTS))
    per_circuit = Counter(f.circuit_id for f in faults.FAULTS)
    check("8-12 faults per circuit", all(8 <= per_circuit[c] <= 12 for c in circuits.CIRCUIT_IDS), dict(per_circuit))
    counts = manifest["counts"]
    check("57 D-NOT-EQUIVALENT and 13 D-EQUIVALENT",
          counts["D-NOT-EQUIVALENT"] == 57 and counts["D-EQUIVALENT"] == 13, counts)
    check("both former reserves included", {f.fault_id for f in faults.FAULTS if f.former_reserve} == {"C5-F12", "C6-F12"})

    for circuit_id in circuits.CIRCUIT_IDS:
        built = circuits.build_circuit(circuit_id)
        direct = catalogue.build_original(circuit_id)
        check(f"{circuit_id} interface matches canonical build", list(built.data) == list(direct.data))
        check(f"{circuit_id} barrier-free", not any(isinstance(i.operation, Barrier) for i in built.data))
        check(f"{circuit_id} instruction count", len(built.data) == len(circuits.circuit_operations(circuit_id)))
    operations = circuits.circuit_operations("C4")
    blocks = {
        "initial H": catalogue.h(0, 1, 2), "oracle 1": catalogue.ORACLE, "diffuser 1": catalogue.DIFFUSER,
        "oracle 2": catalogue.ORACLE, "diffuser 2": catalogue.DIFFUSER, "measurements": catalogue.meas(3),
    }
    check("C4 index map", all(list(operations[a:b]) == blocks[n] for n, (a, b) in circuits.C4_INDEX_MAP.items())
          and len(operations) == 46)

    entries = {entry[0]: entry for entry in catalogue.FAULTS}
    for fault in faults.FAULTS:
        built = faults.build_fault(fault.fault_id)
        direct = catalogue.build_fault(entries[fault.fault_id])
        same = list(built.data) == list(direct.data)
        barrier_free = not any(isinstance(i.operation, Barrier) for i in built.data)
        check(f"{fault.fault_id} interface matches canonical build and is barrier-free", same and barrier_free)

    for version in ("2.6.1", "2.0.3"):
        record = json.loads((ROOT / f"preflight/results/validate-qiskit-{version}.json").read_text())
        recorded = record["faults"]
        check(f"preflight {version}: same 70 fault ids", set(recorded) == set(faults.FAULT_IDS))
        check(f"preflight {version}: all checks passed", all(e["all_checks_pass"] for e in recorded.values()))
        check(f"preflight {version}: instruction counts match",
              all(recorded[f.fault_id]["instructions"] == len(faults.fault_operations(f.fault_id)) for f in faults.FAULTS)
              and all(record["originals"][c]["instructions"] == len(circuits.circuit_operations(c))
                      for c in circuits.CIRCUIT_IDS))
        mapping = {"NE": faults.D_NOT_EQUIVALENT, "EQ": faults.D_EQUIVALENT}
        check(f"preflight {version}: observed classes equal expected classes",
              all(mapping.get(recorded[f.fault_id]["observed_class"]) == f.expected_class for f in faults.FAULTS))
        smoke = json.loads((ROOT / f"preflight/results/smoke-qiskit-{version}.json").read_text())
        check(f"preflight smoke {version}: 76 circuits, no failures",
              smoke["circuits_run"] == 76 and not smoke["failures"]
              and set(smoke["status"]) == set(circuits.CIRCUIT_IDS) | set(faults.FAULT_IDS))
    if stored is not None:
        check("preflight evidence unchanged since freeze",
              stored["preflight_evidence_sha256"] == manifest["preflight_evidence_sha256"])
    return results


def main(argv):
    """Write the manifest if requested, then run every check."""
    manifest = build_manifest()
    if "--write-manifest" in argv:
        MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
        print(f"wrote {MANIFEST.relative_to(ROOT.parent)}")
    results = run_checks(manifest)
    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        if not passed or not name.startswith(("C1-", "C2-", "C3-", "C4-", "C5-", "C6-")):
            print(f"{'PASS' if passed else 'FAIL'}  {name}{'  ' + str(detail) if detail else ''}")
    fault_checks = [r for r in results if r[0].startswith(("C1-", "C2-", "C3-", "C4-", "C5-", "C6-"))]
    print(f"per-fault checks: {sum(r[1] for r in fault_checks)}/{len(fault_checks)} passed")
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
