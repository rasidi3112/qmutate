"""Stable interface to the 70 frozen Phase 6A hand-written faults.

The definitions live only in ``evaluation/preflight/catalogue.py``, the
canonical frozen source. This module wraps each entry in a ``Fault`` record
and builds fault circuits from it; it defines no fault of its own and holds
no T2-T6 detection prediction.
"""

from dataclasses import dataclass

from evaluation.preflight import catalogue as _catalogue

D_NOT_EQUIVALENT = "D-NOT-EQUIVALENT"
D_EQUIVALENT = "D-EQUIVALENT"
_CLASS_NAMES = {_catalogue.NE: D_NOT_EQUIVALENT, _catalogue.EQ: D_EQUIVALENT}


@dataclass(frozen=True)
class Fault:
    """One frozen hand-written fault.

    Attributes:
        fault_id: Stable identifier such as ``"C4-F09"``.
        circuit_id: The circuit the fault applies to.
        category: Fault category from the catalogue.
        missing_gate: Whether the fault is tagged ``missing_gate``.
        expected_class: ``"D-NOT-EQUIVALENT"`` or ``"D-EQUIVALENT"``, as
            classified under IDEAL_DISTRIBUTION and confirmed in preflight.
        measurement_only: Whether the fault changes only measurements.
        former_reserve: Whether the fault was first proposed as a reserve.
        edits: The canonical edit list, applied to the circuit's operations.
    """

    fault_id: str
    circuit_id: str
    category: str
    missing_gate: bool
    expected_class: str
    measurement_only: bool
    former_reserve: bool
    edits: tuple


def _record(entry):
    fault_id, circuit_id, category, tag, edits, predicted_class, _, measurement_only = entry
    return Fault(
        fault_id=fault_id,
        circuit_id=circuit_id,
        category=category,
        missing_gate=tag == _catalogue.MG,
        expected_class=_CLASS_NAMES[predicted_class],
        measurement_only=measurement_only,
        former_reserve=fault_id in _catalogue.FORMER_RESERVES,
        edits=tuple(edits),
    )


FAULTS = tuple(_record(entry) for entry in _catalogue.FAULTS)
FAULT_IDS = tuple(fault.fault_id for fault in FAULTS)
_BY_ID = {fault.fault_id: fault for fault in FAULTS}
_ENTRIES = {entry[0]: entry for entry in _catalogue.FAULTS}

SEED_SENSITIVE = dict(_catalogue.SEED_SENSITIVE)
BORDERLINE = dict(_catalogue.BORDERLINE)
REDUNDANT_GROUPS = tuple(_catalogue.REDUNDANT_GROUPS)


def get_fault(fault_id):
    """Return the ``Fault`` record for ``fault_id``."""
    if fault_id not in _BY_ID:
        raise KeyError(f"unknown fault {fault_id!r}")
    return _BY_ID[fault_id]


def faults_for(circuit_id):
    """Return the faults of ``circuit_id`` in catalogue order."""
    return tuple(fault for fault in FAULTS if fault.circuit_id == circuit_id)


def fault_operations(fault_id):
    """Return the operation list of the fault circuit as a tuple."""
    get_fault(fault_id)
    entry = _ENTRIES[fault_id]
    return tuple(_catalogue.apply_edits(_catalogue.ORIGINALS[entry[1]][2], entry[4]))


def build_fault(fault_id):
    """Return a new barrier-free ``QuantumCircuit`` for ``fault_id``."""
    get_fault(fault_id)
    return _catalogue.build_fault(_ENTRIES[fault_id])
