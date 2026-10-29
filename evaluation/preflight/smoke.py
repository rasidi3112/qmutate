"""BasicSimulator execution smoke test for the Phase 6A circuits and faults.

This is an execution check only. It records whether ``BasicSimulator().run``
completes without an exception and reports success; it does not inspect or
store counts, apply any T1-T6 assertion, or record detection outcomes.

Run from the project root with ``PYTHONDONTWRITEBYTECODE=1``. Writes
``results/smoke-qiskit-<version>.json`` next to this script.
"""

import json
import sys
from pathlib import Path

import qiskit
from qiskit.providers.basic_provider import BasicSimulator

from catalogue import FAULTS, ORIGINALS, build_fault, build_original

SHOTS = 16
SEED = 0


def execute(circuit):
    """Return ``"ok"`` or the exception raised while running ``circuit``."""
    try:
        result = BasicSimulator().run(circuit, shots=SHOTS, seed_simulator=SEED).result()
    except Exception as error:
        return f"{type(error).__name__}: {error}"
    return "ok" if result.success else "result.success is False"


def main():
    """Run every circuit once and write the execution status record."""
    status = {}
    for circuit_id in ORIGINALS:
        status[circuit_id] = execute(build_original(circuit_id))
    for fault in FAULTS:
        status[fault[0]] = execute(build_fault(fault))
    failures = {name: outcome for name, outcome in status.items() if outcome != "ok"}
    record = {
        "qiskit": qiskit.__version__,
        "shots": SHOTS,
        "seed_simulator": SEED,
        "circuits_run": len(status),
        "failures": failures,
        "status": status,
    }
    output = Path(__file__).resolve().parent / "results" / f"smoke-qiskit-{qiskit.__version__}.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(record, indent=1) + "\n")
    print(f"qiskit {qiskit.__version__}: {len(status)} circuits run, {len(failures)} failures {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
