"""Preflight validation of the Phase 6A circuits and fault catalogue.

Run from the project root with ``PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1``.
Writes ``results/validate-qiskit-<version>.json`` next to this script and
prints a summary. It runs no T1-T6 suite and samples nothing.
"""

import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit import Barrier, Measure
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Statevector

from qmutate import EquivalenceModel, check_equivalence, remove_instruction
from qmutate.equivalence import _ideal_distribution
from qmutate.mutation import _isolated_copy

from catalogue import (
    C4_INDEX_MAP, DIFFUSER, EXPECTED_DISTRIBUTIONS, FAULTS, FORMER_RESERVES, ORACLE, ORIGINALS, REDUNDANT_GROUPS,
    build, build_fault, build_original, expected_states, meas, h,
)

CLASSIFIER_ATOL = 1e-8
STATE_ATOL = 1e-8
AGREEMENT_TOL = 1e-9
PROBABILITY_FLOOR = 1e-15


def independent_distribution(circuit):
    """Return the exact classical-bit distribution using only ``Statevector`` and an explicit measurement map.

    Gates are simulated in order on a gates-only circuit. Measurements must be
    terminal: no gate may act on a qubit after it is measured. Measurements
    are then applied in circuit order to a classical register initialised to
    0, so a repeatedly written bit keeps the last written value and an
    unwritten bit stays 0. Keys put classical bit 0 rightmost.
    """
    gates = QuantumCircuit(circuit.num_qubits)
    writes = []
    measured = set()
    for instruction in circuit.data:
        qubits = [circuit.find_bit(q).index for q in instruction.qubits]
        if isinstance(instruction.operation, Measure):
            clbit = circuit.find_bit(instruction.clbits[0]).index
            writes.append((qubits[0], clbit))
            measured.add(qubits[0])
            continue
        if measured.intersection(qubits):
            raise ValueError("a gate acts on a measured qubit")
        gates.append(instruction.operation, qubits)
    probabilities = Statevector(gates).probabilities()
    width = circuit.num_clbits
    result = {}
    for basis, probability in enumerate(probabilities):
        if probability <= PROBABILITY_FLOOR:
            continue
        register = [0] * width
        for qubit, clbit in writes:
            register[clbit] = (basis >> qubit) & 1
        key = "".join(str(register[i]) for i in reversed(range(width)))
        result[key] = result.get(key, 0.0) + float(probability)
    return dict(sorted(result.items()))


def self_checks():
    """Check the independent mapping on hand-made cases with unwritten and repeated writes."""
    cases = []
    circuit = QuantumCircuit(2, 3)
    circuit.x(0)
    circuit.measure(0, 1)
    cases.append(("unwritten bits stay 0", circuit, {"010": 1.0}))
    circuit = QuantumCircuit(2, 2)
    circuit.x(0)
    circuit.measure(0, 0)
    circuit.measure(1, 0)
    cases.append(("last write wins", circuit, {"00": 1.0}))
    circuit = QuantumCircuit(2, 2)
    circuit.x(1)
    circuit.measure(0, 0)
    circuit.measure(1, 0)
    cases.append(("last write wins (to 1)", circuit, {"01": 1.0}))
    circuit = QuantumCircuit(1, 2)
    circuit.h(0)
    circuit.measure(0, 0)
    circuit.measure(0, 1)
    cases.append(("one qubit into two bits", circuit, {"00": 0.5, "11": 0.5}))
    return {name: tv(independent_distribution(c), expected) <= AGREEMENT_TOL for name, c, expected in cases}


def tv(first, second):
    """Return the total variation distance between two distributions."""
    return 0.5 * sum(abs(first.get(k, 0.0) - second.get(k, 0.0)) for k in set(first) | set(second))


def classifier_distribution(circuit):
    """Return qmutate's own exact distribution for comparison only."""
    return {k: v for k, v in sorted(_ideal_distribution(_isolated_copy(circuit)).items()) if v > PROBABILITY_FLOOR}


def signature(distribution):
    """Return a hashable rounded form of a distribution."""
    return tuple(sorted((k, round(v, 9)) for k, v in distribution.items() if v > 1e-12))


def unmeasured(circuit):
    """Return ``circuit`` with its final measurements removed."""
    return circuit.remove_final_measurements(inplace=False)


def same_instructions(first, second):
    """Return whether two circuits have equal instruction lists."""
    return list(first.data) == list(second.data)


def validate_originals(supported):
    """Validate each original circuit against its documented distribution and state."""
    results = {}
    for circuit_id in ORIGINALS:
        circuit = build_original(circuit_id)
        independent = independent_distribution(circuit)
        num_qubits, amplitudes = expected_states()[circuit_id]
        expected = np.zeros(2 ** num_qubits, dtype=complex)
        for index, value in amplitudes.items():
            expected[index] = value
        actual = Statevector(unmeasured(circuit)).data
        overlap = np.vdot(expected, actual)
        phase = overlap / abs(overlap)
        difference = float(np.max(np.abs(actual - phase * expected)))
        results[circuit_id] = {
            "instructions": len(circuit.data),
            "barriers": sum(isinstance(i.operation, Barrier) for i in circuit.data),
            "tv_independent_vs_documented": tv(independent, EXPECTED_DISTRIBUTIONS[circuit_id]),
            "tv_independent_vs_classifier": tv(independent, classifier_distribution(circuit)),
            "state_abs_overlap": float(abs(overlap)),
            "state_global_phase_rad": float(np.angle(phase)),
            "state_max_abs_difference_after_phase": difference,
            "state_within_tolerance": difference <= STATE_ATOL,
            "unsupported_gates": sorted({i.operation.name for i in circuit.data} - supported),
            "reproducible": same_instructions(circuit, build_original(circuit_id)),
        }
    return results


def validate_fault(fault, originals, supported):
    """Validate one fault against the catalogue, the classifier and the independent cross-check."""
    fault_id, circuit_id, category, tag, edits, predicted_class, predicted, measurement_only = fault
    original = originals[circuit_id]
    circuit = build_fault(fault)
    independent = independent_distribution(circuit)
    classifier = classifier_distribution(circuit)
    if predicted is None:
        predicted = EXPECTED_DISTRIBUTIONS[circuit_id]
    ideal = check_equivalence(original, circuit, model=EquivalenceModel.IDEAL_DISTRIBUTION, atol=CLASSIFIER_ATOL)
    unitary = check_equivalence(original, circuit, model=EquivalenceModel.UNITARY, atol=CLASSIFIER_ATOL)
    observed_class = {"equivalent": "EQ", "not_equivalent": "NE"}.get(ideal.verdict.value, "UNKNOWN")
    independent_class = "EQ" if tv(independent, independent_distribution(original)) <= CLASSIFIER_ATOL else "NE"
    entry = {
        "circuit": circuit_id,
        "category": category,
        "tag": tag,
        "former_reserve": fault_id in FORMER_RESERVES,
        "instructions": len(circuit.data),
        "barriers": sum(isinstance(i.operation, Barrier) for i in circuit.data),
        "predicted_class": predicted_class,
        "classifier_ideal_verdict": ideal.verdict.value,
        "classifier_ideal_tv_vs_original": ideal.total_variation,
        "classifier_unitary_verdict": unitary.verdict.value,
        "classifier_unitary_reason": unitary.reason.value if unitary.reason else None,
        "observed_class": observed_class,
        "independent_class": independent_class,
        "independent_tv_vs_original": tv(independent, independent_distribution(original)),
        "distribution_independent": independent,
        "distribution_catalogue": {k: v for k, v in sorted(predicted.items()) if v > PROBABILITY_FLOOR},
        "tv_independent_vs_catalogue": tv(independent, predicted),
        "tv_independent_vs_classifier": tv(independent, classifier),
        "measurement_only_catalogue": measurement_only,
        "measurement_only_structural": same_instructions(unmeasured(circuit), unmeasured(original)),
        "unsupported_gates": sorted({i.operation.name for i in circuit.data} - supported),
        "reproducible": same_instructions(circuit, build_fault(fault)),
    }
    if tag == "missing_gate":
        removals = [edit for edit in edits if edit[0] == "remove"]
        entry["single_removal_matches_remove_instruction"] = (
            len(edits) == 1 and len(removals) == 1
            and same_instructions(circuit, remove_instruction(original, removals[0][1]))
        )
    checks = [
        observed_class == predicted_class,
        independent_class == predicted_class,
        entry["tv_independent_vs_catalogue"] <= AGREEMENT_TOL,
        entry["tv_independent_vs_classifier"] <= AGREEMENT_TOL,
        entry["classifier_unitary_reason"] == "measurement",
        measurement_only == entry["measurement_only_structural"],
        not entry["unsupported_gates"],
        entry["barriers"] == 0,
        entry["reproducible"],
        entry.get("single_removal_matches_remove_instruction", True),
    ]
    entry["all_checks_pass"] = all(checks)
    entry["signature"] = signature(independent)
    return fault_id, entry


def count_table(faults, subset):
    """Return the per-circuit counts for the faults selected by ``subset``."""
    table = {}
    for circuit_id in ORIGINALS:
        entries = [e for e in faults.values() if e["circuit"] == circuit_id and subset(e)]
        not_equivalent = [e for e in entries if e["observed_class"] == "NE"]
        table[circuit_id] = {
            "faults": len(entries),
            "not_equivalent": len(not_equivalent),
            "equivalent": sum(e["observed_class"] == "EQ" for e in entries),
            "unknown": sum(e["observed_class"] == "UNKNOWN" for e in entries),
            "distinct_behaviours": len({(e["signature"], e["measurement_only_structural"]) for e in not_equivalent}),
            "distinct_distributions": len({e["signature"] for e in not_equivalent}),
        }
    table["total"] = {key: sum(row[key] for row in table.values()) for key in next(iter(table.values()))}
    return table


def main():
    """Run every preflight check and write the JSON record."""
    supported = set(BasicSimulator().target.operation_names)
    originals = {circuit_id: build_original(circuit_id) for circuit_id in ORIGINALS}
    c4_ops = ORIGINALS["C4"][2]
    blocks = {
        "initial H": h(0, 1, 2), "oracle 1": ORACLE, "diffuser 1": DIFFUSER, "oracle 2": ORACLE,
        "diffuser 2": DIFFUSER, "measurements": meas(3),
    }
    index_checks = {name: c4_ops[start:stop] == blocks[name] for name, (start, stop) in C4_INDEX_MAP.items()}
    with_barriers = QuantumCircuit(3, 3)
    for name, (start, stop) in C4_INDEX_MAP.items():
        for op_name, *args in c4_ops[start:stop]:
            getattr(with_barriers, op_name)(*args)
        if name != "measurements":
            with_barriers.barrier()
    index_checks["length"] = len(c4_ops)
    index_checks["with_barriers_instructions"] = len(with_barriers.data)
    index_checks["with_barriers_first_measurement"] = next(
        i for i, inst in enumerate(with_barriers.data) if isinstance(inst.operation, Measure)
    )
    index_checks["with_barriers_tv_vs_barrier_free"] = tv(
        independent_distribution(with_barriers), independent_distribution(originals["C4"])
    )
    faults = dict(validate_fault(fault, originals, supported) for fault in FAULTS)
    groups = {}
    for fault_id, entry in faults.items():
        if entry["observed_class"] == "NE":
            groups.setdefault((entry["circuit"], entry["signature"]), []).append(fault_id)
    observed_groups = sorted(tuple(sorted(v)) for v in groups.values() if len(v) > 1)
    record = {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "qiskit": qiskit.__version__,
            "numpy": np.__version__,
            "basic_simulator_backend_version": BasicSimulator().backend_version,
            "qmutate": version("qmutate"),
        },
        "tolerances": {
            "classifier_atol": CLASSIFIER_ATOL,
            "state_atol": STATE_ATOL,
            "agreement_tv": AGREEMENT_TOL,
        },
        "self_checks": self_checks(),
        "originals": validate_originals(supported),
        "c4_index_checks": index_checks,
        "faults": faults,
        "observed_redundant_groups": observed_groups,
        "catalogue_redundant_groups_match": observed_groups == sorted(tuple(sorted(g)) for g in REDUNDANT_GROUPS),
        "counts_all": count_table(faults, lambda e: True),
        "counts_without_missing_gate": count_table(faults, lambda e: e["tag"] != "missing_gate"),
    }
    for entry in faults.values():
        entry["signature"] = [list(item) for item in entry["signature"]]
    output = Path(__file__).resolve().parent / "results" / f"validate-qiskit-{qiskit.__version__}.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(record, indent=1) + "\n")
    failing = [fault_id for fault_id, entry in faults.items() if not entry["all_checks_pass"]]
    worst = max(max(e["tv_independent_vs_catalogue"], e["tv_independent_vs_classifier"]) for e in faults.values())
    print(json.dumps(record["environment"]))
    print("self checks:", record["self_checks"])
    for circuit_id, row in record["originals"].items():
        print(circuit_id, row)
    print("C4 index checks:", index_checks)
    print("faults:", len(faults), "failing:", failing)
    print("largest TV disagreement (independent vs catalogue or classifier):", worst)
    print("unitary verdicts:", sorted({(e["classifier_unitary_verdict"], e["classifier_unitary_reason"]) for e in faults.values()}))
    print("redundant groups match catalogue:", record["catalogue_redundant_groups_match"], observed_groups)
    print("counts_all:", json.dumps(record["counts_all"]))
    print("counts_without_missing_gate:", json.dumps(record["counts_without_missing_gate"]))
    print("written:", output.relative_to(Path.cwd()) if output.is_relative_to(Path.cwd()) else output.name)
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
