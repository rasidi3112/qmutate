import dataclasses
import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Clbit, ClassicalRegister, Gate, Parameter, QuantumRegister, Qubit
from qiskit.circuit.library import Initialize
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Operator, random_unitary

from qmutate import (
    AdjustedMetrics,
    ClassifiedReport,
    EquivalenceModel,
    EquivalenceResult,
    EquivalenceVerdict,
    MutantOutcome,
    MutantResult,
    RunReport,
    UnknownReason,
    check_equivalence,
    classify_report,
    remove_instruction,
    run_removal_mutants,
)
from qmutate.equivalence import _ideal_distribution

UNITARY = EquivalenceModel.UNITARY
DISTRIBUTION = EquivalenceModel.IDEAL_DISTRIBUTION
EQUIVALENT = EquivalenceVerdict.EQUIVALENT
NOT_EQUIVALENT = EquivalenceVerdict.NOT_EQUIVALENT
UNKNOWN = EquivalenceVerdict.UNKNOWN


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


def assert_unknown(result: EquivalenceResult, reason: UnknownReason) -> None:
    assert result.verdict is UNKNOWN
    assert result.reason is reason
    assert result.max_difference is None
    assert result.total_variation is None


def test_circuits_differing_only_by_global_phase_are_equivalent():
    original = QuantumCircuit(1, global_phase=0.3)
    original.h(0)
    mutant = QuantumCircuit(1)
    mutant.h(0)

    result = check_equivalence(original, mutant, model=UNITARY)

    assert result.verdict is EQUIVALENT
    assert result.max_difference <= 1e-15
    assert result.reason is None
    assert result.total_variation is None


def test_removing_rz_two_pi_is_equivalent_up_to_global_phase():
    original = QuantumCircuit(1)
    original.rz(2 * math.pi, 0)

    result = check_equivalence(original, remove_instruction(original, 0), model=UNITARY)

    assert result.verdict is EQUIVALENT
    assert result.max_difference < 1e-12


@pytest.mark.parametrize(("theta", "verdict"), [(1e-3, NOT_EQUIVALENT), (1e-10, EQUIVALENT)])
def test_rz_removal_difference_matches_hand_computed_value(theta, verdict):
    original = QuantumCircuit(1)
    original.rz(theta, 0)

    result = check_equivalence(original, remove_instruction(original, 0), model=UNITARY)

    assert result.max_difference == pytest.approx(2 * math.sin(theta / 4), rel=1e-6)
    assert result.verdict is verdict


def test_atol_boundary_is_inclusive_of_the_computed_difference():
    original = QuantumCircuit(1)
    original.rz(1e-3, 0)
    mutant = remove_instruction(original, 0)
    difference = 2 * math.sin(1e-3 / 4)

    above = check_equivalence(original, mutant, model=UNITARY, atol=difference * 1.01)
    below = check_equivalence(original, mutant, model=UNITARY, atol=difference * 0.99)

    assert above.verdict is EQUIVALENT
    assert below.verdict is NOT_EQUIVALENT


def test_zero_trace_uses_zero_phase():
    original = QuantumCircuit(1)
    original.x(0)

    result = check_equivalence(original, remove_instruction(original, 0), model=UNITARY)

    assert result.max_difference == pytest.approx(1.0, abs=1e-12)
    assert result.verdict is NOT_EQUIVALENT


def test_trace_aligned_difference_is_not_the_minimum_over_phases():
    """Documents that max_difference uses the trace-aligned phase, which for
    CP(pi) gives 2 although the phase pi/2 achieves sqrt(2)."""
    original = QuantumCircuit(2)
    original.cp(math.pi, 0, 1)
    mutant = remove_instruction(original, 0)

    result = check_equivalence(original, mutant, model=UNITARY)
    u, v = Operator(original).data, Operator(mutant).data

    assert result.max_difference == pytest.approx(2.0, abs=1e-12)
    assert float(np.max(np.abs(u - 1j * v))) == pytest.approx(math.sqrt(2), abs=1e-12)


@pytest.mark.parametrize("removed", ["barrier", "delay"])
def test_removing_barrier_or_delay_is_unitary_equivalent(removed):
    original = QuantumCircuit(2)
    original.h(0)
    if removed == "barrier":
        original.barrier()
    else:
        original.delay(100, 0)
    original.cx(0, 1)

    result = check_equivalence(
        original, remove_instruction(original, 1, allow_barrier=True), model=UNITARY
    )

    assert result.verdict is EQUIVALENT
    assert result.max_difference <= 1e-15


def test_removing_a_gate_that_changes_the_unitary_is_not_equivalent():
    original = QuantumCircuit(1)
    original.h(0)
    original.z(0)

    result = check_equivalence(original, remove_instruction(original, 1), model=UNITARY)

    assert result.verdict is NOT_EQUIVALENT


def best_phase_difference(u, v) -> float:
    def difference(phase: float) -> float:
        return float(np.max(np.abs(u - np.exp(1j * phase) * v)))

    grid = np.linspace(-math.pi, math.pi, 2001)
    values = [difference(phase) for phase in grid]
    best = int(np.argmin(values))
    low, high = grid[max(best - 1, 0)], grid[min(best + 1, len(grid) - 1)]
    ratio = (math.sqrt(5) - 1) / 2
    for _ in range(80):
        left = high - ratio * (high - low)
        right = low + ratio * (high - low)
        if difference(left) <= difference(right):
            high = right
        else:
            low = left
    return min(values[best], difference((low + high) / 2))


def nearby_unitary(v, seed: int):
    rng = np.random.default_rng(seed)
    size = v.shape[0]
    hermitian = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    hermitian = (hermitian + hermitian.conj().T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(hermitian)
    epsilon = 10 ** rng.uniform(-5, -1)
    perturbation = eigenvectors @ np.diag(np.exp(1j * epsilon * eigenvalues)) @ eigenvectors.conj().T
    return np.exp(1j * rng.uniform(0, 2 * math.pi)) * v @ perturbation


@pytest.mark.parametrize("num_qubits", [1, 2, 3])
def test_documented_bound_holds_against_numerically_minimised_phase(num_qubits):
    """The bound max_difference <= min(2, 2**n * m, (1 + 2 * 2**(n/2)) * m) is
    proven; this test only checks it on seeded random cases. The numerical
    minimum found here is never below the true minimum, so the check cannot
    fail because of the search."""
    for seed in range(12):
        v = random_unitary(2**num_qubits, seed=seed).data
        u = nearby_unitary(v, seed)
        original = QuantumCircuit(num_qubits)
        original.unitary(u, range(num_qubits))
        mutant = QuantumCircuit(num_qubits)
        mutant.unitary(v, range(num_qubits))

        result = check_equivalence(original, mutant, model=UNITARY, atol=0.0)
        best = best_phase_difference(Operator(original).data, Operator(mutant).data)
        bound = min(2.0, 2**num_qubits * best, (1 + 2 * 2 ** (num_qubits / 2)) * best)

        assert result.max_difference <= bound + 1e-12


def unitary_unknown_cases():
    measured = QuantumCircuit(1, 1)
    measured.h(0)
    measured.measure(0, 0)
    reset = QuantumCircuit(1)
    reset.reset(0)
    control_flow = QuantumCircuit(1, 1)
    with control_flow.if_test((control_flow.clbits[0], 1)):
        control_flow.x(0)
    composite_body = QuantumCircuit(1)
    composite_body.h(0)
    non_gate = QuantumCircuit(1)
    non_gate.append(composite_body.to_instruction(), [0])
    unbound = QuantumCircuit(1)
    unbound.rx(Parameter("theta"), 0)
    phase_parameter = QuantumCircuit(1, global_phase=Parameter("phi"))
    phase_parameter.h(0)
    return [
        (measured, UnknownReason.MEASUREMENT),
        (reset, UnknownReason.RESET),
        (control_flow, UnknownReason.CONTROL_FLOW),
        (non_gate, UnknownReason.NON_GATE_INSTRUCTION),
        (unbound, UnknownReason.UNBOUND_PARAMETERS),
        (phase_parameter, UnknownReason.UNBOUND_PARAMETERS),
    ]


@pytest.mark.parametrize(
    ("circuit", "reason"),
    unitary_unknown_cases(),
    ids=["measurement", "reset", "control-flow", "non-gate", "unbound", "global-phase-parameter"],
)
def test_unitary_unknown_reasons(circuit, reason):
    assert_unknown(check_equivalence(circuit, circuit.copy(), model=UNITARY), reason)


def test_too_many_qubits_is_unknown():
    circuit = QuantumCircuit(2)
    circuit.h(0)

    assert_unknown(
        check_equivalence(circuit, circuit.copy(), model=UNITARY, max_qubits=1),
        UnknownReason.TOO_MANY_QUBITS,
    )
    assert check_equivalence(circuit, circuit.copy(), model=UNITARY, max_qubits=2).verdict is EQUIVALENT


def test_original_reason_is_reported_before_mutant_reason():
    original = QuantumCircuit(1, 1)
    original.reset(0)
    mutant = QuantumCircuit(1, 1)
    mutant.measure(0, 0)

    assert_unknown(check_equivalence(original, mutant, model=UNITARY), UnknownReason.RESET)
    assert_unknown(check_equivalence(mutant, original, model=UNITARY), UnknownReason.MEASUREMENT)


def simulated_key(circuit: QuantumCircuit) -> str:
    counts = BasicSimulator().run(circuit, shots=16, seed_simulator=3).result().get_counts()
    assert len(counts) == 1
    return next(iter(counts)).replace(" ", "")


def ordering_cases():
    cases = {}
    permuted = QuantumCircuit(2, 2)
    permuted.x(0)
    permuted.measure(0, 1)
    permuted.measure(1, 0)
    cases["permuted"] = (permuted, "10")
    qr = QuantumRegister(3, "q")
    a = ClassicalRegister(1, "a")
    b = ClassicalRegister(2, "b")
    two_registers = QuantumCircuit(qr, a, b)
    two_registers.x(0)
    two_registers.x(2)
    two_registers.measure(0, b[1])
    two_registers.measure(2, a[0])
    cases["registers-a-b"] = (two_registers, "101")
    reversed_registers = QuantumCircuit(QuantumRegister(3, "q"), ClassicalRegister(2, "b"), ClassicalRegister(1, "a"))
    reversed_registers.x(0)
    reversed_registers.x(2)
    reversed_registers.measure(0, reversed_registers.cregs[0][1])
    reversed_registers.measure(2, reversed_registers.cregs[1][0])
    cases["registers-b-a"] = (reversed_registers, "110")
    unmeasured = QuantumCircuit(2, 3)
    unmeasured.x(1)
    unmeasured.measure(1, 2)
    cases["unmeasured-bits"] = (unmeasured, "100")
    repeated = QuantumCircuit(1, 2)
    repeated.x(0)
    repeated.measure(0, 0)
    repeated.measure(0, 1)
    cases["same-qubit-two-bits"] = (repeated, "11")
    overwritten = QuantumCircuit(2, 1)
    overwritten.x(0)
    overwritten.measure(0, 0)
    overwritten.measure(1, 0)
    cases["last-write-wins"] = (overwritten, "0")
    other_qubit = QuantumCircuit(2, 1)
    other_qubit.x(0)
    other_qubit.measure(0, 0)
    other_qubit.x(1)
    cases["gate-on-other-qubit"] = (other_qubit, "1")
    return cases


@pytest.mark.parametrize("name", list(ordering_cases()))
def test_distribution_bit_ordering_matches_simulator(name):
    circuit, expected_key = ordering_cases()[name]

    distribution = _ideal_distribution(circuit)

    assert list(distribution) == [expected_key]
    assert distribution[expected_key] == pytest.approx(1.0, abs=1e-12)
    assert simulated_key(circuit) == expected_key
    assert check_equivalence(circuit, circuit.copy(), model=DISTRIBUTION).verdict is EQUIVALENT


def test_permuted_measurement_is_compared_by_classical_bit():
    swapped = QuantumCircuit(2, 2)
    swapped.x(1)
    swapped.measure(1, 1)
    swapped.measure(0, 0)
    direct = QuantumCircuit(2, 2)
    direct.x(0)
    direct.measure(0, 0)
    direct.measure(1, 1)
    permuted = ordering_cases()["permuted"][0]

    same = check_equivalence(permuted, swapped, model=DISTRIBUTION)
    different = check_equivalence(permuted, direct, model=DISTRIBUTION)

    assert same.verdict is EQUIVALENT
    assert different.verdict is NOT_EQUIVALENT
    assert different.total_variation == pytest.approx(1.0)
    assert different.max_difference == pytest.approx(1.0)


def test_removing_h_before_measurement_changes_the_distribution():
    original = QuantumCircuit(1, 1)
    original.h(0)
    original.measure(0, 0)

    result = check_equivalence(original, remove_instruction(original, 0), model=DISTRIBUTION)

    assert result.verdict is NOT_EQUIVALENT
    assert result.max_difference == pytest.approx(0.5)
    assert result.total_variation == pytest.approx(0.5)


def test_removing_z_before_measurement_is_distribution_equivalent_only():
    measured = QuantumCircuit(1, 1)
    measured.h(0)
    measured.z(0)
    measured.measure(0, 0)
    unmeasured = QuantumCircuit(1)
    unmeasured.h(0)
    unmeasured.z(0)

    distribution = check_equivalence(measured, remove_instruction(measured, 1), model=DISTRIBUTION)
    unitary = check_equivalence(unmeasured, remove_instruction(unmeasured, 1), model=UNITARY)

    assert distribution.verdict is EQUIVALENT
    assert distribution.total_variation <= 1e-12
    assert unitary.verdict is NOT_EQUIVALENT


def test_removing_one_measurement_leaves_its_bit_at_zero():
    original = QuantumCircuit(2, 2)
    original.x(0)
    original.measure(0, 0)
    original.measure(1, 1)

    result = check_equivalence(
        original, remove_instruction(original, 1, allow_measure=True), model=DISTRIBUTION
    )

    assert result.verdict is NOT_EQUIVALENT
    assert result.total_variation == pytest.approx(1.0)


def test_removing_the_only_measurement_is_unknown():
    original = QuantumCircuit(1, 1)
    original.x(0)
    original.measure(0, 0)

    result = check_equivalence(
        original, remove_instruction(original, 1, allow_measure=True), model=DISTRIBUTION
    )

    assert_unknown(result, UnknownReason.NO_MEASUREMENTS)


def distribution_unknown_cases():
    mid = QuantumCircuit(1, 1)
    mid.measure(0, 0)
    mid.h(0)
    reset = QuantumCircuit(1, 1)
    reset.reset(0)
    reset.measure(0, 0)
    control_flow = QuantumCircuit(1, 1)
    control_flow.measure(0, 0)
    with control_flow.if_test((control_flow.clbits[0], 1)):
        control_flow.x(0)
    non_gate = QuantumCircuit(1, 1)
    non_gate.append(Initialize([0, 1]), [0])
    non_gate.measure(0, 0)
    unbound = QuantumCircuit(1, 1)
    unbound.rx(Parameter("theta"), 0)
    unbound.measure(0, 0)
    no_measurements = QuantumCircuit(1, 1)
    no_measurements.h(0)
    loose = QuantumCircuit(QuantumRegister(1, "q"), ClassicalRegister(1, "c"))
    loose.add_bits([Clbit()])
    loose.measure(0, 0)
    return [
        (mid, UnknownReason.MID_CIRCUIT_MEASUREMENT),
        (reset, UnknownReason.RESET),
        (control_flow, UnknownReason.CONTROL_FLOW),
        (non_gate, UnknownReason.NON_GATE_INSTRUCTION),
        (unbound, UnknownReason.UNBOUND_PARAMETERS),
        (no_measurements, UnknownReason.NO_MEASUREMENTS),
        (loose, UnknownReason.CLBITS_OUTSIDE_REGISTERS),
    ]


@pytest.mark.parametrize(
    ("circuit", "reason"),
    distribution_unknown_cases(),
    ids=["mid-circuit", "reset", "control-flow", "non-gate", "unbound", "no-measurements", "loose-clbit"],
)
def test_distribution_unknown_reasons(circuit, reason):
    assert_unknown(check_equivalence(circuit, circuit.copy(), model=DISTRIBUTION), reason)


def test_clbits_outside_registers_on_the_mutant_are_unknown():
    original = QuantumCircuit(QuantumRegister(1, "q"), ClassicalRegister(2, "c"))
    original.measure(0, 0)
    mutant = QuantumCircuit(QuantumRegister(1, "q"), ClassicalRegister(1, "c"))
    mutant.add_bits([Clbit()])
    mutant.measure(0, 0)

    assert_unknown(
        check_equivalence(original, mutant, model=DISTRIBUTION),
        UnknownReason.CLBITS_OUTSIDE_REGISTERS,
    )


def test_measurements_followed_only_by_measure_barrier_or_delay_are_supported():
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.measure(0, 0)
    circuit.barrier()
    circuit.delay(50, 0)
    circuit.measure(0, 1)
    circuit.x(1)

    result = check_equivalence(circuit, circuit.copy(), model=DISTRIBUTION)

    assert result.verdict is EQUIVALENT
    assert _ideal_distribution(circuit) == pytest.approx({"00": 0.5, "11": 0.5})


def test_rounding_noise_in_identical_circuits_stays_equivalent():
    circuit = QuantumCircuit(3)
    circuit.ry(0.7, 0)
    circuit.cx(0, 1)
    circuit.rx(1.3, 2)
    circuit.measure_all()

    result = check_equivalence(circuit, circuit.copy(), model=DISTRIBUTION)

    assert result.verdict is EQUIVALENT
    assert result.total_variation < 1e-12


def test_total_variation_is_at_least_max_difference():
    original = QuantumCircuit(2, 2)
    original.ry(0.4, 0)
    original.h(1)
    original.cx(0, 1)
    original.measure([0, 1], [0, 1])

    for index in range(3):
        result = check_equivalence(original, remove_instruction(original, index), model=DISTRIBUTION)
        assert result.total_variation >= result.max_difference - 1e-15


def test_distribution_verdict_uses_total_variation_not_max_difference():
    """Removing ry(theta) on one qubit next to two uniform qubits changes 8
    outcome probabilities by sin(theta/2)**2 / 4 each, so total_variation is
    4 * max_difference and an atol between the two must give NOT_EQUIVALENT."""
    original = QuantumCircuit(3, 3)
    original.ry(0.3, 0)
    original.h(1)
    original.h(2)
    original.measure([0, 1, 2], [0, 1, 2])
    mutant = remove_instruction(original, 0)
    shift = math.sin(0.15) ** 2

    probe = check_equivalence(original, mutant, model=DISTRIBUTION)
    result = check_equivalence(original, mutant, model=DISTRIBUTION, atol=2 * probe.max_difference)

    assert probe.max_difference == pytest.approx(shift / 4)
    assert probe.total_variation == pytest.approx(shift)
    assert result.verdict is NOT_EQUIVALENT


def test_identical_circuits_are_equivalent_with_zero_tolerance():
    circuit = QuantumCircuit(1, 1)
    circuit.x(0)
    circuit.measure(0, 0)
    unitary = QuantumCircuit(1)
    unitary.x(0)

    assert check_equivalence(circuit, circuit.copy(), model=DISTRIBUTION, atol=0).verdict is EQUIVALENT
    assert check_equivalence(unitary, unitary.copy(), model=UNITARY, atol=0.0).verdict is EQUIVALENT


@pytest.mark.parametrize(("model", "num_qubits"), [(UNITARY, 11), (DISTRIBUTION, 17)])
def test_default_qubit_caps(model, num_qubits):
    circuit = QuantumCircuit(num_qubits, 1)
    circuit.measure(0, 0)

    assert_unknown(
        check_equivalence(circuit, circuit.copy(), model=model), UnknownReason.TOO_MANY_QUBITS
    )
    smaller = check_equivalence(circuit, circuit.copy(), model=model, max_qubits=num_qubits)
    assert smaller.reason is not UnknownReason.TOO_MANY_QUBITS


def test_too_many_qubits_in_distribution_model_is_unknown():
    circuit = QuantumCircuit(3, 1)
    circuit.measure(0, 0)

    assert_unknown(
        check_equivalence(circuit, circuit.copy(), model=DISTRIBUTION, max_qubits=2),
        UnknownReason.TOO_MANY_QUBITS,
    )


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"model": "unitary"}, TypeError, "model"),
        ({"model": UNITARY, "atol": True}, TypeError, "atol"),
        ({"model": UNITARY, "atol": "1e-8"}, TypeError, "atol"),
        ({"model": UNITARY, "atol": -1e-9}, ValueError, "atol"),
        ({"model": UNITARY, "atol": math.nan}, ValueError, "atol"),
        ({"model": UNITARY, "atol": math.inf}, ValueError, "atol"),
        ({"model": UNITARY, "max_qubits": True}, TypeError, "max_qubits"),
        ({"model": UNITARY, "max_qubits": 1.5}, TypeError, "max_qubits"),
        ({"model": UNITARY, "max_qubits": 0}, ValueError, "max_qubits"),
    ],
)
def test_invalid_options_are_rejected(kwargs, error, match):
    circuit = QuantumCircuit(1)
    circuit.h(0)

    with pytest.raises(error, match=match):
        check_equivalence(circuit, circuit.copy(), **kwargs)


def test_mismatched_circuits_are_rejected():
    one = QuantumCircuit(1, 1)
    two_qubits = QuantumCircuit(2, 1)
    two_clbits = QuantumCircuit(1, 2)

    with pytest.raises(TypeError, match="original"):
        check_equivalence("circuit", one, model=UNITARY)
    with pytest.raises(TypeError, match="mutant"):
        check_equivalence(one, None, model=UNITARY)
    with pytest.raises(ValueError, match="qubits"):
        check_equivalence(one, two_qubits, model=UNITARY)
    with pytest.raises(ValueError, match="classical bits"):
        check_equivalence(one, two_clbits, model=UNITARY)


def lazy_gate_class(built: list):
    class LazyGate(Gate):
        def __init__(self):
            super().__init__("lazy_gate", 1, [])

        def _define(self):
            built.append(self)
            body = QuantumCircuit(1)
            body.x(0)
            self.definition = body

    return LazyGate


def test_check_equivalence_does_not_modify_or_build_definitions_on_inputs():
    built = []
    original = QuantumCircuit(1, 1)
    original.append(lazy_gate_class(built)(), [0])
    original.h(0)
    original.measure(0, 0)
    mutant = remove_instruction(original, 1)
    snapshot = original.copy()
    inputs = [original.data[0].operation, mutant.data[0].operation]

    for model in (UNITARY, DISTRIBUTION):
        check_equivalence(original, mutant, model=model)

    assert built
    assert all(all(operation is not given for given in inputs) for operation in built)
    assert original == snapshot


def test_results_are_deterministic():
    original = QuantumCircuit(2, 2)
    original.ry(0.3, 0)
    original.cx(0, 1)
    original.measure([0, 1], [0, 1])
    mutant = remove_instruction(original, 1)

    assert check_equivalence(original, mutant, model=DISTRIBUTION) == check_equivalence(
        original, mutant, model=DISTRIBUTION
    )


def test_valid_results_are_accepted():
    results = [
        EquivalenceResult(UNITARY, EQUIVALENT, None, 0.0, None),
        EquivalenceResult(DISTRIBUTION, NOT_EQUIVALENT, None, 0.5, 0.5),
        EquivalenceResult(UNITARY, UNKNOWN, UnknownReason.MEASUREMENT, None, None),
        EquivalenceResult(DISTRIBUTION, UNKNOWN, UnknownReason.RESET, None, None),
    ]

    assert len(set(results)) == 4


@pytest.mark.parametrize(
    ("fields", "error", "match"),
    [
        (("unitary", EQUIVALENT, None, 0.0, None), TypeError, "model"),
        ((UNITARY, "equivalent", None, 0.0, None), TypeError, "verdict"),
        ((UNITARY, UNKNOWN, "measurement", None, None), TypeError, "reason"),
        ((UNITARY, EQUIVALENT, None, True, None), TypeError, "max_difference"),
        ((UNITARY, EQUIVALENT, None, "0", None), TypeError, "max_difference"),
        ((UNITARY, EQUIVALENT, None, -0.1, None), ValueError, "max_difference"),
        ((UNITARY, EQUIVALENT, None, math.nan, None), ValueError, "max_difference"),
        ((DISTRIBUTION, EQUIVALENT, None, 0.0, math.inf), ValueError, "total_variation"),
        ((UNITARY, EQUIVALENT, UnknownReason.RESET, 0.0, None), ValueError, "reason"),
        ((UNITARY, UNKNOWN, None, None, None), ValueError, "reason"),
        ((UNITARY, UNKNOWN, UnknownReason.RESET, 0.0, None), ValueError, "UNKNOWN"),
        ((DISTRIBUTION, UNKNOWN, UnknownReason.RESET, None, 0.0), ValueError, "UNKNOWN"),
        ((UNITARY, NOT_EQUIVALENT, None, None, None), ValueError, "max_difference"),
        ((UNITARY, EQUIVALENT, None, 0.0, 0.0), ValueError, "total_variation"),
        ((DISTRIBUTION, EQUIVALENT, None, 0.0, None), ValueError, "total_variation"),
        ((DISTRIBUTION, UNKNOWN, UnknownReason.MEASUREMENT, None, None), ValueError, "does not apply"),
        ((UNITARY, UNKNOWN, UnknownReason.NO_MEASUREMENTS, None, None), ValueError, "does not apply"),
    ],
    ids=[
        "str-model",
        "str-verdict",
        "str-reason",
        "bool-difference",
        "str-difference",
        "negative-difference",
        "nan-difference",
        "infinite-total-variation",
        "reason-without-unknown",
        "unknown-without-reason",
        "unknown-with-difference",
        "unknown-with-total-variation",
        "missing-difference",
        "unitary-with-total-variation",
        "distribution-without-total-variation",
        "unitary-only-reason-on-distribution",
        "distribution-only-reason-on-unitary",
    ],
)
def test_invalid_results_are_rejected(fields, error, match):
    with pytest.raises(error, match=match):
        EquivalenceResult(*fields)


def phase_circuit() -> QuantumCircuit:
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.barrier()
    circuit.rz(2 * math.pi, 0)
    circuit.x(0)
    return circuit


def unitary_oracle(reference: QuantumCircuit):
    expected = Operator(reference)

    def oracle(candidate: QuantumCircuit) -> None:
        assert Operator(candidate).equiv(expected)

    return oracle


def verdicts(classified: ClassifiedReport) -> list[str | None]:
    return [None if result is None else result.verdict.value for result in classified.results]


def test_equivalent_survivors_raise_the_adjusted_score():
    circuit = phase_circuit()
    report = run_removal_mutants(circuit, unitary_oracle(circuit), allow_barrier=True)

    classified = classify_report(circuit, report, model=UNITARY)
    metrics = classified.metrics()

    assert [result.outcome.value for result in report.results] == ["killed", "survived", "survived", "killed"]
    assert verdicts(classified) == ["not_equivalent", "equivalent", "equivalent", "not_equivalent"]
    assert metrics == AdjustedMetrics(2, 2, 0, 0, 2, 0, 0)
    assert metrics.base.score == report.score() == 0.5
    assert metrics.adjusted_score == 1.0


def test_skipped_candidates_have_no_classification():
    circuit = phase_circuit()
    report = run_removal_mutants(circuit, unitary_oracle(circuit))

    classified = classify_report(circuit, report, model=UNITARY)

    assert report.results[1].outcome is MutantOutcome.NOT_RUN
    assert verdicts(classified) == ["not_equivalent", None, "equivalent", "not_equivalent"]
    assert classified.metrics() == AdjustedMetrics(2, 1, 0, 1, 1, 0, 0)


def test_killed_equivalent_mutants_stay_counted_and_are_reported():
    circuit = phase_circuit()

    def structural_oracle(candidate: QuantumCircuit) -> None:
        assert len(candidate.data) == 4

    report = run_removal_mutants(circuit, structural_oracle, allow_barrier=True)
    metrics = classify_report(circuit, report, model=UNITARY).metrics()

    assert metrics == AdjustedMetrics(4, 0, 0, 0, 0, 2, 0)
    assert metrics.base.score == metrics.adjusted_score == 1.0


def test_equivalent_errors_are_reported_without_changing_the_score():
    circuit = phase_circuit()

    def oracle(candidate: QuantumCircuit) -> None:
        if "barrier" not in op_names(candidate):
            raise RuntimeError("needs the barrier")
        assert len(candidate.data) == 4

    report = run_removal_mutants(circuit, oracle, allow_barrier=True)
    metrics = classify_report(circuit, report, model=UNITARY).metrics()

    assert [result.outcome.value for result in report.results] == ["killed", "error", "killed", "killed"]
    assert metrics == AdjustedMetrics(3, 0, 1, 0, 0, 1, 1)
    assert metrics.adjusted_score == metrics.base.score == 1.0


def test_unknown_and_not_equivalent_verdicts_change_nothing():
    circuit = phase_circuit()
    report = run_removal_mutants(circuit, lambda candidate: None, allow_barrier=True)

    classified = classify_report(circuit, report, model=DISTRIBUTION)
    metrics = classified.metrics()

    assert all(result.reason is UnknownReason.NO_MEASUREMENTS for result in classified.results)
    assert metrics.adjusted_score == metrics.base.score == 0.0
    assert metrics.equivalent_survived == 0


def test_distribution_classification_of_a_run():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.z(0)
    circuit.measure(0, 0)
    report = run_removal_mutants(circuit, lambda candidate: None)

    classified = classify_report(circuit, report, model=DISTRIBUTION)

    assert verdicts(classified) == ["not_equivalent", "equivalent", None]
    assert classified.results[0].total_variation == pytest.approx(0.5)
    assert classified.metrics() == AdjustedMetrics(0, 2, 0, 1, 1, 0, 0)


def mismatch_report():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.rx(0.4, 1)
    circuit.cx(0, 1)
    circuit.h(1)
    return circuit, run_removal_mutants(circuit, lambda candidate: None)


def test_wrong_number_of_instructions_is_rejected():
    circuit, report = mismatch_report()
    longer = circuit.copy()
    longer.x(0)

    with pytest.raises(ValueError, match="5 instructions but the report has 4"):
        classify_report(longer, report, model=UNITARY)


def test_mismatched_instruction_name_is_rejected():
    circuit, report = mismatch_report()
    renamed = QuantumCircuit(2)
    renamed.h(0)
    renamed.ry(0.4, 1)
    renamed.cx(0, 1)
    renamed.h(1)

    with pytest.raises(ValueError, match="instruction 1 is 'ry' in circuit but 'rx'"):
        classify_report(renamed, report, model=UNITARY)


def test_mismatched_parameter_is_rejected():
    circuit, report = mismatch_report()
    other_angle = QuantumCircuit(2)
    other_angle.h(0)
    other_angle.rx(0.5, 1)
    other_angle.cx(0, 1)
    other_angle.h(1)

    with pytest.raises(ValueError, match="mutant 0 in the report"):
        classify_report(other_angle, report, model=UNITARY)


def test_swapped_qubits_are_rejected():
    circuit, report = mismatch_report()
    swapped = QuantumCircuit(2)
    swapped.h(0)
    swapped.rx(0.4, 1)
    swapped.cx(1, 0)
    swapped.h(1)

    with pytest.raises(ValueError, match="mutant 0 in the report"):
        classify_report(swapped, report, model=UNITARY)


def test_mutant_paired_with_the_wrong_index_is_rejected():
    circuit, report = mismatch_report()
    first, second = report.results[0], report.results[3]
    wrong_candidate = dataclasses.replace(first.candidate, mutant=second.candidate.mutant)
    tampered = RunReport(
        (MutantResult(wrong_candidate, first.outcome, None),) + report.results[1:],
        killed=report.killed,
        survived=report.survived,
        errors=report.errors,
        not_run=report.not_run,
    )

    with pytest.raises(ValueError, match="mutant 0 in the report is not circuit with instruction 0 removed"):
        classify_report(circuit, tampered, model=UNITARY)


def test_classify_report_does_not_modify_circuit_or_report_mutants():
    built = []
    circuit = QuantumCircuit(1)
    circuit.append(lazy_gate_class(built)(), [0])
    circuit.h(0)
    report = run_removal_mutants(circuit, lambda candidate: None)
    snapshot = circuit.copy()
    stored = [circuit.data[0].operation] + [
        operation
        for result in report.results
        for operation in (instruction.operation for instruction in result.candidate.mutant.data)
    ]
    built.clear()

    classified = classify_report(circuit, report, model=UNITARY)

    assert verdicts(classified) == ["not_equivalent", "not_equivalent"]
    assert built
    assert all(all(operation is not given for given in stored) for operation in built)
    assert circuit == snapshot


def test_classify_report_type_checks():
    circuit, report = mismatch_report()

    with pytest.raises(TypeError, match="circuit"):
        classify_report("circuit", report, model=UNITARY)
    with pytest.raises(TypeError, match="report"):
        classify_report(circuit, "report", model=UNITARY)
    with pytest.raises(TypeError, match="model"):
        classify_report(circuit, report, model="unitary")


def classified_parts():
    circuit = phase_circuit()
    report = run_removal_mutants(circuit, unitary_oracle(circuit))
    classified = classify_report(circuit, report, model=UNITARY)
    return report, classified.results


@pytest.mark.parametrize(
    ("build", "error", "match"),
    [
        (lambda r, x: ClassifiedReport("report", UNITARY, x), TypeError, "report"),
        (lambda r, x: ClassifiedReport(r, "unitary", x), TypeError, "model"),
        (lambda r, x: ClassifiedReport(r, UNITARY, list(x)), TypeError, "tuple"),
        (lambda r, x: ClassifiedReport(r, UNITARY, x[:3]), ValueError, "3 entries"),
        (lambda r, x: ClassifiedReport(r, UNITARY, (None,) + x[1:]), ValueError, "result 0 was run"),
        (lambda r, x: ClassifiedReport(r, UNITARY, (x[0], x[0]) + x[2:]), ValueError, "result 1 was not run"),
        (lambda r, x: ClassifiedReport(r, UNITARY, ("verdict",) + x[1:]), TypeError, "result 0"),
        (lambda r, x: ClassifiedReport(r, DISTRIBUTION, x), ValueError, "uses unitary"),
    ],
    ids=[
        "non-report",
        "str-model",
        "list-results",
        "wrong-length",
        "none-for-run-result",
        "result-for-not-run",
        "wrong-element-type",
        "model-mismatch",
    ],
)
def test_invalid_classified_reports_are_rejected(build, error, match):
    report, results = classified_parts()

    with pytest.raises(error, match=match):
        build(report, results)


def test_classified_report_metrics_use_its_own_report():
    report, results = classified_parts()

    metrics = ClassifiedReport(report, UNITARY, results).metrics()

    assert (metrics.killed, metrics.survived, metrics.errors, metrics.not_run) == (
        report.killed,
        report.survived,
        report.errors,
        report.not_run,
    )
    assert metrics.base == report.metrics()


def opaque_gate() -> Gate:
    return Gate("opaque_gate", 1, [])


@pytest.mark.parametrize("model", [UNITARY, DISTRIBUTION])
def test_gate_without_matrix_or_definition_is_unsupported_operation(model):
    circuit = QuantumCircuit(1, 1)
    circuit.append(opaque_gate(), [0])
    circuit.h(0)
    if model is DISTRIBUTION:
        circuit.measure(0, 0)

    result = check_equivalence(circuit, remove_instruction(circuit, 1), model=model)

    assert_unknown(result, UnknownReason.UNSUPPORTED_OPERATION)


def test_unsupported_operation_in_the_mutant_only():
    original = QuantumCircuit(1)
    original.h(0)
    mutant = QuantumCircuit(1)
    mutant.append(opaque_gate(), [0])

    assert_unknown(check_equivalence(original, mutant, model=UNITARY), UnknownReason.UNSUPPORTED_OPERATION)


def test_original_is_checked_completely_before_the_mutant():
    original = QuantumCircuit(1, 1)
    original.append(opaque_gate(), [0])
    mutant = QuantumCircuit(1, 1)
    mutant.measure(0, 0)

    assert_unknown(check_equivalence(original, mutant, model=UNITARY), UnknownReason.UNSUPPORTED_OPERATION)
    assert_unknown(check_equivalence(mutant, original, model=UNITARY), UnknownReason.MEASUREMENT)


def test_custom_gate_with_a_definition_is_supported():
    body = QuantumCircuit(1, name="custom")
    body.h(0)
    body.z(0)
    circuit = QuantumCircuit(1)
    circuit.append(body.to_gate(), [0])
    circuit.x(0)

    result = check_equivalence(circuit, circuit.copy(), model=UNITARY)

    assert result.verdict is EQUIVALENT


def test_errors_other_than_qiskit_errors_propagate():
    class BrokenGate(Gate):
        def __init__(self):
            super().__init__("broken_gate", 1, [])

        def _define(self):
            raise RuntimeError("definition failed")

    circuit = QuantumCircuit(1)
    circuit.append(BrokenGate(), [0])
    circuit.h(0)
    report = run_removal_mutants(circuit, lambda candidate: None)

    with pytest.raises(RuntimeError, match="definition failed"):
        check_equivalence(circuit, circuit.copy(), model=UNITARY)
    with pytest.raises(RuntimeError, match="definition failed"):
        classify_report(circuit, report, model=UNITARY)


def test_classify_report_marks_unsupported_operation_without_failing():
    circuit = QuantumCircuit(1)
    circuit.append(opaque_gate(), [0])
    circuit.h(0)
    report = run_removal_mutants(circuit, lambda candidate: None)

    classified = classify_report(circuit, report, model=UNITARY)

    assert [result.reason for result in classified.results] == [UnknownReason.UNSUPPORTED_OPERATION] * 2
    assert classified.metrics().adjusted_score == classified.metrics().base.score == 0.0


def test_unsupported_original_gives_its_reason_to_a_supported_mutant():
    circuit = QuantumCircuit(1)
    circuit.reset(0)
    circuit.h(0)
    report = run_removal_mutants(circuit, lambda candidate: None)
    removed_reset = report.results[0].candidate.mutant

    classified = classify_report(circuit, report, model=UNITARY)

    assert op_names(removed_reset) == ["h"]
    assert check_equivalence(removed_reset, removed_reset.copy(), model=UNITARY).verdict is EQUIVALENT
    assert [result.reason for result in classified.results] == [UnknownReason.RESET, UnknownReason.RESET]


def test_classify_report_passes_atol_through():
    circuit = QuantumCircuit(1)
    circuit.rz(1e-3, 0)
    circuit.h(0)
    report = run_removal_mutants(circuit, lambda candidate: None)

    default = classify_report(circuit, report, model=UNITARY)
    loose = classify_report(circuit, report, model=UNITARY, atol=1e-3)

    assert default.results[0].verdict is NOT_EQUIVALENT
    assert loose.results[0].verdict is EQUIVALENT
    assert loose.results[0].max_difference == default.results[0].max_difference


def test_classify_report_passes_max_qubits_through():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    report = run_removal_mutants(circuit, lambda candidate: None)

    classified = classify_report(circuit, report, model=UNITARY, max_qubits=1)

    assert [result.reason for result in classified.results] == [UnknownReason.TOO_MANY_QUBITS] * 2
    assert all(
        result.reason is None
        for result in classify_report(circuit, report, model=UNITARY, max_qubits=2).results
    )


@pytest.mark.parametrize("extra_bit", [Qubit, Clbit], ids=["extra-qubit", "extra-clbit"])
def test_mutant_with_an_extra_unused_bit_is_rejected(extra_bit):
    circuit, report = mismatch_report()
    first = report.results[0]
    padded = first.candidate.mutant.copy()
    padded.add_bits([extra_bit()])
    assert list(padded.data) == list(first.candidate.mutant.data)
    tampered = RunReport(
        (MutantResult(dataclasses.replace(first.candidate, mutant=padded), first.outcome, None),)
        + report.results[1:],
        killed=report.killed,
        survived=report.survived,
        errors=report.errors,
        not_run=report.not_run,
    )

    with pytest.raises(ValueError, match="mutant 0 in the report"):
        classify_report(circuit, tampered, model=UNITARY)


def precedence_cases():
    unbound_first = QuantumCircuit(3, 1)
    unbound_first.rx(Parameter("theta"), 0)
    unbound_first.reset(1)
    qubits_before_scan = QuantumCircuit(3, 1)
    qubits_before_scan.reset(1)
    loose_before_scan = QuantumCircuit(QuantumRegister(1, "q"), ClassicalRegister(1, "c"))
    loose_before_scan.add_bits([Clbit()])
    loose_before_scan.reset(0)
    loose_before_scan.measure(0, 0)
    unbound_before_loose = loose_before_scan.copy()
    unbound_before_loose.rx(Parameter("phi"), 0)
    mid_before_reset = QuantumCircuit(2, 1)
    mid_before_reset.measure(0, 0)
    mid_before_reset.h(0)
    mid_before_reset.reset(1)
    reset_before_mid = QuantumCircuit(2, 1)
    reset_before_mid.reset(1)
    reset_before_mid.measure(0, 0)
    reset_before_mid.h(0)
    no_measurements_before_build = QuantumCircuit(1, 1)
    no_measurements_before_build.append(opaque_gate(), [0])
    reset_before_build = QuantumCircuit(1)
    reset_before_build.append(opaque_gate(), [0])
    reset_before_build.reset(0)
    return [
        (UNITARY, unbound_first, 1, UnknownReason.UNBOUND_PARAMETERS),
        (UNITARY, qubits_before_scan, 1, UnknownReason.TOO_MANY_QUBITS),
        (DISTRIBUTION, loose_before_scan, None, UnknownReason.CLBITS_OUTSIDE_REGISTERS),
        (DISTRIBUTION, unbound_before_loose, None, UnknownReason.UNBOUND_PARAMETERS),
        (DISTRIBUTION, mid_before_reset, None, UnknownReason.MID_CIRCUIT_MEASUREMENT),
        (DISTRIBUTION, reset_before_mid, None, UnknownReason.RESET),
        (DISTRIBUTION, no_measurements_before_build, None, UnknownReason.NO_MEASUREMENTS),
        (UNITARY, reset_before_build, None, UnknownReason.RESET),
    ]


@pytest.mark.parametrize(
    ("model", "circuit", "max_qubits", "reason"),
    precedence_cases(),
    ids=[
        "unbound-before-cap-and-reset",
        "cap-before-reset",
        "loose-clbit-before-reset",
        "unbound-before-loose-clbit",
        "first-instruction-mid-circuit",
        "first-instruction-reset",
        "no-measurements-before-build",
        "scan-before-build",
    ],
)
def test_unknown_reasons_follow_the_documented_order(model, circuit, max_qubits, reason):
    assert_unknown(
        check_equivalence(circuit, circuit.copy(), model=model, max_qubits=max_qubits), reason
    )


def qubit_order_circuit(*registers: QuantumRegister) -> QuantumCircuit:
    first, second = sorted(registers, key=lambda register: register.name)
    circuit = QuantumCircuit(*registers)
    circuit.x(first[0])
    circuit.rz(2 * math.pi, first[0])
    circuit.h(second[0])
    return circuit


def test_circuit_with_reordered_qubits_is_rejected():
    a = QuantumRegister(1, "a")
    b = QuantumRegister(1, "b")
    run_circuit = qubit_order_circuit(a, b)
    reordered = qubit_order_circuit(b, a)
    report = run_removal_mutants(run_circuit, lambda candidate: None)
    assert list(reordered.data) == list(run_circuit.data)
    assert list(reordered.qubits) != list(run_circuit.qubits)

    with pytest.raises(ValueError, match="same qubits in the same order"):
        classify_report(reordered, report, model=UNITARY)

    accepted = classify_report(run_circuit, report, model=UNITARY)
    assert verdicts(accepted) == ["not_equivalent", "equivalent", "not_equivalent"]


def clbit_order_circuit(*clbit_registers: ClassicalRegister) -> QuantumCircuit:
    first, second = sorted(clbit_registers, key=lambda register: register.name)
    circuit = QuantumCircuit(QuantumRegister(2, "q"), *clbit_registers)
    circuit.x(0)
    circuit.barrier()
    circuit.measure(0, first[0])
    circuit.measure(1, second[0])
    return circuit


def test_circuit_with_reordered_classical_bits_is_rejected():
    ca = ClassicalRegister(1, "ca")
    cb = ClassicalRegister(1, "cb")
    run_circuit = clbit_order_circuit(ca, cb)
    reordered = clbit_order_circuit(cb, ca)
    report = run_removal_mutants(run_circuit, lambda candidate: None, allow_barrier=True)
    assert list(reordered.data) == list(run_circuit.data)
    assert list(reordered.clbits) != list(run_circuit.clbits)

    with pytest.raises(ValueError, match="same classical bits in the same order"):
        classify_report(reordered, report, model=DISTRIBUTION)

    accepted = classify_report(run_circuit, report, model=DISTRIBUTION)
    assert verdicts(accepted) == ["not_equivalent", "equivalent", None, None]


def test_equal_circuit_built_from_new_registers_is_accepted():
    run_circuit = clbit_order_circuit(ClassicalRegister(1, "ca"), ClassicalRegister(1, "cb"))
    rebuilt = clbit_order_circuit(ClassicalRegister(1, "ca"), ClassicalRegister(1, "cb"))
    report = run_removal_mutants(run_circuit, lambda candidate: None, allow_barrier=True)

    classified = classify_report(rebuilt, report, model=DISTRIBUTION)

    assert verdicts(classified) == ["not_equivalent", "equivalent", None, None]
