"""Stable interface to the six frozen Phase 6A circuits.

The definitions live only in ``evaluation/preflight/catalogue.py``, the
canonical frozen source. This module re-exposes them; it defines no circuit
of its own. Run code that imports it from the project root (for example
``python -m evaluation.check_catalogue``) so that ``evaluation`` is importable.

Every circuit is barrier-free, and instruction indices refer to the
operation lists of the canonical source.
"""

import numpy as np

from evaluation.preflight import catalogue as _catalogue

CATALOGUE_VERSION = "phase6a-catalogue-v1"
CIRCUIT_IDS = tuple(_catalogue.ORIGINALS)
CIRCUIT_NAMES = {
    "C1": "GHZ-3",
    "C2": "Bernstein-Vazirani, secret 1011",
    "C3": "Deutsch-Jozsa, f(x) = x0 xor x1 xor x2",
    "C4": "Grover-3, marked 101, 2 iterations",
    "C5": "QFT-3 on |5>",
    "C6": "Teleportation of ry(2pi/3)|0>, deferred measurement",
}
C4_INDEX_MAP = dict(_catalogue.C4_INDEX_MAP)


def _require(circuit_id):
    if circuit_id not in _catalogue.ORIGINALS:
        raise KeyError(f"unknown circuit {circuit_id!r}")


def circuit_operations(circuit_id):
    """Return the canonical operation list of ``circuit_id`` as a tuple."""
    _require(circuit_id)
    return tuple(_catalogue.ORIGINALS[circuit_id][2])


def circuit_shape(circuit_id):
    """Return ``(num_qubits, num_clbits)`` of ``circuit_id``."""
    _require(circuit_id)
    num_qubits, num_clbits, _ = _catalogue.ORIGINALS[circuit_id]
    return num_qubits, num_clbits


def build_circuit(circuit_id):
    """Return a new barrier-free ``QuantumCircuit`` for ``circuit_id``."""
    _require(circuit_id)
    return _catalogue.build_original(circuit_id)


def expected_distribution(circuit_id):
    """Return a copy of the hand-derived expected distribution, classical bit 0 rightmost."""
    _require(circuit_id)
    return dict(_catalogue.EXPECTED_DISTRIBUTIONS[circuit_id])


def expected_state(circuit_id):
    """Return the hand-derived pre-measurement statevector, defined up to global phase."""
    _require(circuit_id)
    num_qubits, amplitudes = _catalogue.expected_states()[circuit_id]
    state = np.zeros(2 ** num_qubits, dtype=complex)
    for index, value in amplitudes.items():
        state[index] = value
    return state
