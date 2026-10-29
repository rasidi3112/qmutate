import dataclasses
import math

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import ClassicalRegister, Clbit, Gate, QuantumRegister
from qiskit.exceptions import QiskitError

from qmutate import (
    BaselineFailedError,
    DistributionComparison,
    DistributionOracle,
    EquivalenceModel,
    MutantOutcome,
    SamplingVerdict,
    check_equivalence,
    compare_counts,
    distribution_oracle,
    family_delta,
    remove_instruction,
    run_removal_mutants,
    sample_counts,
    shots_for_threshold,
)
from qmutate.equivalence import _ideal_distribution

DISTINGUISHED = SamplingVerdict.DISTINGUISHED
WITHIN = SamplingVerdict.WITHIN_TOLERANCE
INCONCLUSIVE = SamplingVerdict.INCONCLUSIVE


def hand_threshold(shots_a: int, shots_b: int, num_clbits: int, delta: float) -> float:
    def margin(shots: int) -> float:
        return 0.5 * (
            math.sqrt((2**num_clbits - 1) / shots) + math.sqrt(2 * math.log(1 / delta) / shots)
        )

    return margin(shots_a) + margin(shots_b)


def zeros(num_clbits: int, shots: int) -> dict[str, int]:
    return {"0" * num_clbits: shots}


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


@pytest.mark.parametrize(
    ("num_clbits", "shots", "expected"),
    [
        (1, 100, 0.403),
        (1, 1000, 0.128),
        (1, 10000, 0.040),
        (3, 1000, 0.180),
        (5, 10000, 0.086),
        (10, 1000, 1.107),
        (16, 1_000_000, 0.259),
    ],
)
def test_threshold_matches_the_documented_table(num_clbits, shots, expected):
    comparison = compare_counts(zeros(num_clbits, shots), zeros(num_clbits, shots), num_clbits=num_clbits)

    assert comparison.threshold == pytest.approx(hand_threshold(shots, shots, num_clbits, 0.01), rel=1e-12)
    assert round(comparison.threshold, 3) == expected


def test_unequal_shot_counts_add_both_margins():
    comparison = compare_counts(zeros(2, 400), zeros(2, 2500), num_clbits=2, delta=0.05)

    assert comparison.shots_a == 400
    assert comparison.shots_b == 2500
    assert comparison.threshold == pytest.approx(hand_threshold(400, 2500, 2, 0.05), rel=1e-12)


def test_distance_and_bounds_are_hand_computed():
    comparison = compare_counts({"0": 3, "1": 1}, {"0": 1, "1": 1}, num_clbits=1)

    assert comparison.distance == pytest.approx(0.25)
    assert comparison.lower_bound == 0.0
    assert comparison.upper_bound == 1.0
    assert comparison.verdict is INCONCLUSIVE


def test_disjoint_supports_have_distance_one():
    comparison = compare_counts({"00": 10}, {"11": 30}, num_clbits=2)

    assert comparison.distance == 1.0


def comparison_with(distance: float, tolerance: float = 0.0) -> DistributionComparison:
    return DistributionComparison(1_000_000, 1_000_000, 1, 0.01, tolerance, distance)


def test_verdict_branches():
    assert comparison_with(0.5).verdict is DISTINGUISHED
    assert comparison_with(0.0, tolerance=0.1).verdict is WITHIN
    assert comparison_with(0.002).verdict is INCONCLUSIVE
    assert comparison_with(0.5, tolerance=0.3).verdict is DISTINGUISHED
    assert comparison_with(0.3, tolerance=0.3).verdict is INCONCLUSIVE


def test_verdict_boundaries_are_inclusive_for_within_and_strict_for_distinguished():
    probe = comparison_with(0.2)
    at_upper = dataclasses.replace(probe, tolerance=probe.upper_bound)
    at_lower = dataclasses.replace(probe, tolerance=probe.lower_bound)

    assert at_upper.verdict is WITHIN
    assert at_lower.verdict is INCONCLUSIVE
    assert dataclasses.replace(probe, tolerance=probe.lower_bound * 0.999).verdict is DISTINGUISHED


def test_zero_tolerance_never_gives_within():
    assert comparison_with(0.0).verdict is INCONCLUSIVE
    assert compare_counts({"0": 10**9}, {"0": 10**9}, num_clbits=1).verdict is INCONCLUSIVE


def test_uninformative_threshold_is_always_inconclusive():
    comparison = compare_counts({"0" * 10: 100}, {"1" * 10: 100}, num_clbits=10)
    large = compare_counts({"0" * 2000: 5}, {"1" * 2000: 5}, num_clbits=2000)

    assert comparison.distance == 1.0
    assert not comparison.informative
    assert comparison.verdict is INCONCLUSIVE
    assert math.isfinite(large.threshold) and not large.informative


def delta_for_threshold_exactly_one(shots: int) -> float:
    analytic = math.exp(-((math.sqrt(shots) - 1) ** 2) / 2)
    candidate = analytic
    for _ in range(4):
        candidate = math.nextafter(candidate, 0)
    for _ in range(9):
        if 0 < candidate < 1 and DistributionComparison(shots, shots, 1, candidate, 0.0, 0.0).threshold == 1.0:
            return candidate
        candidate = math.nextafter(candidate, 1)
    pytest.skip("no delta with a threshold of exactly 1.0 on this platform")


def test_threshold_of_exactly_one_is_not_informative():
    delta = delta_for_threshold_exactly_one(2)
    comparison = DistributionComparison(2, 2, 1, delta, 0.0, 0.5)

    assert comparison.threshold == 1.0
    assert not comparison.informative
    assert comparison.verdict is INCONCLUSIVE
    with pytest.raises(ValueError, match="at least 1"):
        distribution_oracle(h_measure(), shots=2, seed=0, delta=delta, sampler=lambda c, shots, seed: {"0": 1, "1": 1})


def test_spaces_between_registers_are_removed():
    comparison = compare_counts({"1 0": 4, "0 1": 4}, {"10": 4, "01": 4}, num_clbits=2)

    assert comparison.distance == 0.0


def test_numpy_integer_counts_are_accepted():
    comparison = compare_counts({"0": np.int64(5)}, {"0": 5}, num_clbits=1)

    assert comparison.shots_a == 5


@pytest.mark.parametrize(
    ("counts", "error", "match"),
    [
        ([("0", 1)], TypeError, "mapping"),
        ({0: 1}, TypeError, "keys must be str"),
        ({"00": 1}, ValueError, "length 1"),
        ({"2": 1}, ValueError, "bit string"),
        ({"": 1}, ValueError, "bit string"),
        ({"0": True}, TypeError, "values must be int"),
        ({"0": 1.0}, TypeError, "values must be int"),
        ({"0": -1, "1": 2}, ValueError, "negative"),
        ({"0": 0, "1": 0}, ValueError, "at least one shot"),
        ({}, ValueError, "at least one shot"),
    ],
    ids=["non-mapping", "non-str-key", "wrong-length", "bad-character", "empty-key", "bool-value", "float-value", "negative", "zero-total", "empty"],
)
def test_invalid_counts_are_rejected(counts, error, match):
    with pytest.raises(error, match=match):
        compare_counts(counts, {"0": 1}, num_clbits=1)


def test_keys_repeating_after_space_removal_are_rejected():
    with pytest.raises(ValueError, match="repeats an outcome"):
        compare_counts({"1 0": 1, "10": 1}, {"10": 2}, num_clbits=2)


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"num_clbits": 0}, ValueError, "num_clbits"),
        ({"num_clbits": True}, TypeError, "num_clbits"),
        ({"num_clbits": 1.0}, TypeError, "num_clbits"),
        ({"num_clbits": 1, "delta": 0}, ValueError, "delta"),
        ({"num_clbits": 1, "delta": 1}, ValueError, "delta"),
        ({"num_clbits": 1, "delta": math.nan}, ValueError, "delta"),
        ({"num_clbits": 1, "delta": True}, TypeError, "delta"),
        ({"num_clbits": 1, "delta": "0.01"}, TypeError, "delta"),
        ({"num_clbits": 1, "tolerance": -0.1}, ValueError, "tolerance"),
        ({"num_clbits": 1, "tolerance": 1.0}, ValueError, "tolerance"),
        ({"num_clbits": 1, "tolerance": math.inf}, ValueError, "tolerance"),
        ({"num_clbits": 1, "tolerance": True}, TypeError, "tolerance"),
    ],
)
def test_invalid_comparison_options_are_rejected(kwargs, error, match):
    with pytest.raises(error, match=match):
        compare_counts({"0": 1}, {"0": 1}, **kwargs)


@pytest.mark.parametrize(
    ("fields", "error", "match"),
    [
        ((0, 1, 1, 0.01, 0.0, 0.0), ValueError, "shots_a"),
        ((1, True, 1, 0.01, 0.0, 0.0), TypeError, "shots_b"),
        ((1, 1, 0, 0.01, 0.0, 0.0), ValueError, "num_clbits"),
        ((1, 1, 1, 1.5, 0.0, 0.0), ValueError, "delta"),
        ((1, 1, 1, 0.01, 1.0, 0.0), ValueError, "tolerance"),
        ((1, 1, 1, 0.01, 0.0, 1.5), ValueError, "distance"),
        ((1, 1, 1, 0.01, 0.0, -0.1), ValueError, "distance"),
        ((1, 1, 1, 0.01, 0.0, math.nan), ValueError, "distance"),
        ((1, 1, 1, 0.01, 0.0, "0"), TypeError, "distance"),
    ],
)
def test_invalid_comparison_fields_are_rejected(fields, error, match):
    with pytest.raises(error, match=match):
        DistributionComparison(*fields)


def test_comparisons_are_immutable_and_comparable():
    comparison = compare_counts({"0": 3}, {"1": 3}, num_clbits=1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        comparison.distance = 0.0
    assert comparison == compare_counts({"0": 3}, {"1": 3}, num_clbits=1)
    assert hash(comparison) == hash(compare_counts({"0": 3}, {"1": 3}, num_clbits=1))
    assert type(comparison.verdict) is SamplingVerdict


def test_verdict_values_are_stable():
    assert [verdict.value for verdict in SamplingVerdict] == [
        "distinguished",
        "within_tolerance",
        "inconclusive",
    ]


@pytest.mark.parametrize("num_clbits", [1, 2, 3, 5, 8, 12])
@pytest.mark.parametrize("delta", [0.1, 0.01, 1e-6])
@pytest.mark.parametrize("target", [0.9, 0.5, 0.2, 0.1, 0.05, 0.0123])
def test_shots_for_threshold_is_minimal(num_clbits, delta, target):
    shots = shots_for_threshold(target, num_clbits, delta)

    def threshold(n: int) -> float:
        return compare_counts(zeros(num_clbits, n), zeros(num_clbits, n), num_clbits=num_clbits, delta=delta).threshold

    assert threshold(shots) <= target
    assert shots == 1 or threshold(shots - 1) > target


@pytest.mark.parametrize("exact_shots", [100, 3227, 10007, 123457])
def test_shots_for_threshold_at_an_exact_boundary(exact_shots):
    target = compare_counts(zeros(3, exact_shots), zeros(3, exact_shots), num_clbits=3).threshold

    assert shots_for_threshold(target, 3) == exact_shots


@pytest.mark.parametrize("num_clbits", [1, 2, 3])
def test_shots_for_threshold_at_and_just_below_every_small_boundary(num_clbits):
    for shots in range(1, 300):
        target = compare_counts(zeros(num_clbits, shots), zeros(num_clbits, shots), num_clbits=num_clbits).threshold
        if not 0 < target < 1:
            continue
        assert shots_for_threshold(target, num_clbits) == shots
        assert shots_for_threshold(math.nextafter(target, 0), num_clbits) == shots + 1


def test_shots_for_threshold_examples():
    assert [shots_for_threshold(0.1, bits) for bits in (1, 3, 5, 10)] == [1629, 3227, 7401, 122635]


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ((0.0, 1), ValueError),
        ((1.0, 1), ValueError),
        ((1.5, 1), ValueError),
        ((math.nan, 1), ValueError),
        ((True, 1), TypeError),
        ((0.1, 0), ValueError),
        ((0.1, 1, 0.0), ValueError),
    ],
)
def test_shots_for_threshold_rejects_invalid_arguments(args, error):
    with pytest.raises(error):
        shots_for_threshold(*args)


def test_family_delta():
    assert family_delta(0.05, 22) == pytest.approx(0.05 / 22)
    assert family_delta(0.5, 1) == 0.5
    for args, error in [((0.0, 2), ValueError), ((1.0, 2), ValueError), ((True, 2), TypeError), ((0.05, 0), ValueError), ((0.05, True), TypeError)]:
        with pytest.raises(error):
            family_delta(*args)


class RecordingSampler:
    def __init__(self, decide):
        self.decide = decide
        self.calls = []

    def __call__(self, circuit, shots, seed):
        self.calls.append((circuit, shots, seed))
        return self.decide(circuit, shots, seed)


def h_measure() -> QuantumCircuit:
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    return circuit


def by_content(circuit, shots, seed):
    if "h" in op_names(circuit):
        return {"0": shots // 2, "1": shots - shots // 2}
    return {"0": shots}


def test_sample_counts_passes_a_copy_and_its_arguments_to_the_sampler():
    circuit = h_measure()
    sampler = RecordingSampler(lambda c, shots, seed: {"0": shots})

    counts = sample_counts(circuit, shots=40, seed=9, sampler=sampler)

    received, shots, seed = sampler.calls[0]
    assert counts == {"0": 40}
    assert (shots, seed) == (40, 9)
    assert received is not circuit
    assert received == circuit


def test_sample_counts_normalizes_and_sorts_keys():
    circuit = QuantumCircuit(QuantumRegister(2), ClassicalRegister(1, "a"), ClassicalRegister(1, "b"))
    circuit.measure([0, 1], [0, 1])

    counts = sample_counts(circuit, shots=6, seed=0, sampler=lambda c, shots, seed: {"1 1": 2, "0 1": 4})

    assert counts == {"01": 4, "11": 2}
    assert list(counts) == ["01", "11"]


@pytest.mark.parametrize(
    ("output", "match"),
    [({"0": 3}, "returned 3 shots"), ({"00": 4}, "length 1"), ([("0", 4)], "mapping")],
)
def test_sample_counts_rejects_invalid_sampler_output(output, match):
    with pytest.raises((ValueError, TypeError), match=match):
        sample_counts(h_measure(), shots=4, seed=0, sampler=lambda c, shots, seed: output)


def test_sampler_errors_propagate_from_sample_counts():
    def broken(circuit, shots, seed):
        raise RuntimeError("sampler failed")

    with pytest.raises(RuntimeError, match="sampler failed"):
        sample_counts(h_measure(), shots=4, seed=0, sampler=broken)


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"shots": 0, "seed": 0}, ValueError, "shots"),
        ({"shots": True, "seed": 0}, TypeError, "shots"),
        ({"shots": 4, "seed": -1}, ValueError, "seed"),
        ({"shots": 4, "seed": True}, TypeError, "seed"),
        ({"shots": 4, "seed": 0, "sampler": "BasicSimulator"}, TypeError, "sampler"),
    ],
)
def test_sample_counts_rejects_invalid_arguments(kwargs, error, match):
    with pytest.raises(error, match=match):
        sample_counts(h_measure(), **kwargs)
    with pytest.raises(TypeError, match="circuit"):
        sample_counts("circuit", shots=4, seed=0)


def layout_cases():
    no_clbits = QuantumCircuit(1)
    no_clbits.h(0)
    loose = QuantumCircuit(QuantumRegister(1), ClassicalRegister(1, "c"))
    loose.add_bits([Clbit()])
    loose.measure(0, 1)
    shared = ClassicalRegister(2, "s")
    overlapping = QuantumCircuit(QuantumRegister(1), shared)
    overlapping.add_register(ClassicalRegister(bits=[shared[0]], name="o"))
    overlapping.measure(0, 0)
    return [(no_clbits, "no classical bits"), (loose, "exactly one register"), (overlapping, "exactly one register")]


@pytest.mark.parametrize(("circuit", "match"), layout_cases(), ids=["no-clbits", "loose-clbit", "overlapping-registers"])
def test_unsupported_classical_layouts_are_rejected(circuit, match):
    with pytest.raises(ValueError, match=match):
        sample_counts(circuit, shots=4, seed=0, sampler=lambda c, shots, seed: {"0": shots})
    with pytest.raises(ValueError, match=match):
        distribution_oracle(circuit, shots=1000, seed=0, sampler=lambda c, shots, seed: {"0": shots})


def test_sampling_does_not_build_definitions_on_the_original():
    built = []

    class LazyGate(Gate):
        def __init__(self):
            super().__init__("lazy_gate", 1, [])

        def _define(self):
            built.append(self)
            body = QuantumCircuit(1)
            body.x(0)
            self.definition = body

    circuit = QuantumCircuit(1, 1)
    circuit.append(LazyGate(), [0])
    circuit.measure(0, 0)
    original_operation = circuit.data[0].operation
    snapshot = circuit.copy()

    def expanding_sampler(copy, shots, seed):
        for instruction in copy.data:
            getattr(instruction.operation, "definition", None)
        return {"0": shots}

    sample_counts(circuit, shots=4, seed=0, sampler=expanding_sampler)

    assert built
    assert all(operation is not original_operation for operation in built)
    assert circuit == snapshot


def test_oracle_uses_seed_for_reference_and_seed_plus_one_for_every_call():
    sampler = RecordingSampler(by_content)
    circuit = h_measure()

    oracle = distribution_oracle(circuit, shots=1000, seed=40, sampler=sampler)
    oracle(circuit)
    with pytest.raises(AssertionError):
        oracle(remove_instruction(circuit, 0))
    oracle(circuit)

    assert [seed for _, _, seed in sampler.calls] == [40, 41, 41, 41]
    assert all(shots == 1000 for _, shots, _ in sampler.calls)


def test_oracle_exposes_its_settings_read_only():
    oracle = distribution_oracle(h_measure(), shots=1000, seed=3, delta=0.02, tolerance=0.1, sampler=by_content)

    assert (oracle.shots, oracle.seed, oracle.delta, oracle.tolerance, oracle.num_clbits) == (1000, 3, 0.02, 0.1, 1)
    assert oracle.threshold == pytest.approx(hand_threshold(1000, 1000, 1, 0.02))
    assert oracle.informative
    assert dict(oracle.reference_counts) == {"0": 500, "1": 500}
    with pytest.raises(TypeError):
        oracle.reference_counts["0"] = 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        oracle.seed = 4


def test_oracle_kills_only_distinguished_circuits():
    circuit = h_measure()
    oracle = distribution_oracle(circuit, shots=1000, seed=0, sampler=by_content)
    close = distribution_oracle(circuit, shots=1000, seed=0, tolerance=0.9, sampler=by_content)

    assert oracle(circuit) is None
    with pytest.raises(AssertionError, match=r"distance 0\.500000, threshold 0\.127593"):
        oracle(remove_instruction(circuit, 0))
    assert close(remove_instruction(circuit, 0)) is None


def test_oracle_lets_within_tolerance_and_inconclusive_survive():
    circuit = h_measure()

    def nearly(copy, shots, seed):
        return {"0": 500, "1": 500} if seed == 0 else {"0": 520, "1": 480}

    inconclusive = distribution_oracle(circuit, shots=1000, seed=0, sampler=nearly)
    within = distribution_oracle(circuit, shots=1000, seed=0, tolerance=0.5, sampler=nearly)
    report = run_removal_mutants(circuit, inconclusive)

    assert compare_counts({"0": 500, "1": 500}, {"0": 520, "1": 480}, num_clbits=1).verdict is INCONCLUSIVE
    assert inconclusive(circuit) is None
    assert within(circuit) is None
    assert report.results[0].outcome is MutantOutcome.SURVIVED


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"shots": 0, "seed": 0}, ValueError, "shots"),
        ({"shots": 1000, "seed": -1}, ValueError, "seed"),
        ({"shots": 1000, "seed": 0, "delta": 0}, ValueError, "delta"),
        ({"shots": 1000, "seed": 0, "tolerance": 1}, ValueError, "tolerance"),
        ({"shots": 1000, "seed": 0, "sampler": 5}, TypeError, "sampler"),
        ({"shots": 10, "seed": 0}, ValueError, "shots_for_threshold suggests"),
    ],
)
def test_distribution_oracle_rejects_invalid_arguments(kwargs, error, match):
    with pytest.raises(error, match=match):
        distribution_oracle(h_measure(), **{"sampler": by_content, **kwargs})


def test_distribution_oracle_rejects_references_without_measurements():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)

    with pytest.raises(ValueError, match="measures nothing"):
        distribution_oracle(circuit, shots=1000, seed=0, sampler=by_content)
    with pytest.raises(TypeError, match="reference"):
        distribution_oracle("circuit", shots=1000, seed=0)


def test_oracle_call_requires_the_reference_classical_layout():
    reference = QuantumCircuit(QuantumRegister(2, "q"), ClassicalRegister(1, "a"), ClassicalRegister(1, "b"))
    reference.measure([0, 1], [0, 1])
    other = QuantumCircuit(QuantumRegister(2, "q"), ClassicalRegister(1, "b"), ClassicalRegister(1, "a"))
    other.measure([0, 1], [0, 1])
    oracle = distribution_oracle(reference, shots=1000, seed=0, sampler=lambda c, shots, seed: {"00": shots})

    with pytest.raises(ValueError, match="classical bits and registers"):
        oracle(other)
    with pytest.raises(TypeError, match="circuit"):
        oracle("circuit")


@pytest.mark.parametrize(
    ("overrides", "error", "match"),
    [
        ({"reference_counts": {"0": 999}}, ValueError, "exactly 1000 shots"),
        ({"clbits": ()}, ValueError, "clbits"),
        ({"clbits": [Clbit()]}, TypeError, "clbits"),
        ({"cregs": ["c"]}, TypeError, "cregs"),
        ({"shots": 10, "reference_counts": {"0": 10}}, ValueError, "at least 1"),
    ],
)
def test_direct_oracle_construction_is_validated(overrides, error, match):
    fields = {
        "shots": 1000,
        "seed": 0,
        "delta": 0.01,
        "tolerance": 0.0,
        "reference_counts": {"0": 1000},
        "clbits": (Clbit(),),
        "cregs": (),
    }
    fields.update(overrides)

    with pytest.raises(error, match=match):
        DistributionOracle(**fields)


def test_oracle_works_with_the_runner_and_is_reproducible():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.barrier()
    circuit.measure(0, 0)

    first = run_removal_mutants(circuit, distribution_oracle(circuit, shots=1000, seed=1, sampler=by_content), allow_barrier=True)
    second = run_removal_mutants(circuit, distribution_oracle(circuit, shots=1000, seed=1, sampler=by_content), allow_barrier=True)

    assert [result.outcome.value for result in first.results] == ["killed", "survived", "not_run"]
    assert first == second


def test_distinguished_baseline_stops_the_run_without_a_report():
    def unstable(copy, shots, seed):
        return {"0": shots} if seed % 2 == 0 else {"1": shots}

    oracle = distribution_oracle(h_measure(), shots=1000, seed=4, sampler=unstable)

    with pytest.raises(BaselineFailedError) as raised:
        run_removal_mutants(h_measure(), oracle)

    assert isinstance(raised.value.__cause__, AssertionError)
    assert "distinguished from the reference" in str(raised.value)


def test_sampler_error_during_baseline_stops_the_run():
    def fails_on_calls(copy, shots, seed):
        if seed == 1:
            raise RuntimeError("sampler failed")
        return {"0": shots}

    oracle = distribution_oracle(h_measure(), shots=1000, seed=0, sampler=fails_on_calls)

    with pytest.raises(BaselineFailedError) as raised:
        run_removal_mutants(h_measure(), oracle)

    assert isinstance(raised.value.__cause__, RuntimeError)


def test_sampler_error_for_a_mutant_is_recorded_as_error():
    def fails_without_h(copy, shots, seed):
        if seed == 1 and "h" not in op_names(copy):
            raise RuntimeError("cannot sample")
        return by_content(copy, shots, seed)

    circuit = h_measure()
    report = run_removal_mutants(circuit, distribution_oracle(circuit, shots=1000, seed=0, sampler=fails_without_h))

    assert report.results[0].outcome is MutantOutcome.ERROR
    assert report.results[0].error_type == "RuntimeError"


def test_reference_the_default_sampler_cannot_run_raises_at_creation():
    circuit = QuantumCircuit(1, 1)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(0)

    with pytest.raises(QiskitError):
        distribution_oracle(circuit, shots=1000, seed=0)


def deterministic_layouts():
    q = QuantumRegister(3, "q")
    a = ClassicalRegister(1, "a")
    b = ClassicalRegister(2, "b")
    forward = QuantumCircuit(q, a, b)
    forward.x(0)
    forward.measure(0, a[0])
    forward.measure(0, b[1])
    backward = QuantumCircuit(QuantumRegister(3, "q"), ClassicalRegister(2, "b"), ClassicalRegister(1, "a"))
    backward.x(0)
    backward.measure(0, backward.cregs[1][0])
    backward.measure(0, backward.cregs[0][1])
    bits = [Clbit(), Clbit()]
    reversed_register = QuantumCircuit(QuantumRegister(1, "q"))
    reversed_register.add_bits(bits)
    reversed_register.add_register(ClassicalRegister(bits=[bits[1], bits[0]], name="r"))
    reversed_register.x(0)
    reversed_register.measure(0, bits[0])
    return {"registers-a-b": forward, "registers-b-a": backward, "register-from-reversed-bits": reversed_register}


@pytest.mark.parametrize("name", list(deterministic_layouts()))
def test_sampled_keys_match_the_exact_distribution_keys(name):
    """Fixed-seed check with the real simulator: for deterministic circuits the
    space-free keys follow ``circuit.clbits`` order, as the exact model does."""
    circuit = deterministic_layouts()[name]

    counts = sample_counts(circuit, shots=16, seed=1)

    assert counts == {next(iter(_ideal_distribution(circuit))): 16}


def bell_uniform() -> QuantumCircuit:
    circuit = QuantumCircuit(2, 2)
    circuit.h([0, 1])
    circuit.measure([0, 1], [0, 1])
    return circuit


def verdict_counts(first: QuantumCircuit, second: QuantumCircuit, shots: int, tolerance: float) -> dict:
    tally = {verdict: 0 for verdict in SamplingVerdict}
    for trial in range(200):
        comparison = compare_counts(
            sample_counts(first, shots=shots, seed=2 * trial),
            sample_counts(second, shots=shots, seed=2 * trial + 1),
            num_clbits=first.num_clbits,
            delta=0.01,
            tolerance=tolerance,
        )
        tally[comparison.verdict] += 1
    return tally


def test_regression_fixed_seeds_identical_circuits_rarely_distinguished():
    """Deterministic regression test with 200 fixed seed pairs, not statistical
    validation. The limit of 14 is chosen so that, if the seeds were random and
    the per-trial rate were at the bound's worst case 2 * delta = 0.02, the
    test would fail with probability below 2e-5."""
    tally = verdict_counts(bell_uniform(), bell_uniform(), shots=1000, tolerance=0.0)

    assert tally[DISTINGUISHED] <= 14


def h_removed_pair() -> tuple[QuantumCircuit, QuantumCircuit]:
    original = h_measure()
    mutant = remove_instruction(original, 0)
    exact = check_equivalence(original, mutant, model=EquivalenceModel.IDEAL_DISTRIBUTION)
    assert exact.total_variation == pytest.approx(0.5)
    return original, mutant


def test_regression_fixed_seeds_large_difference_detected():
    """Deterministic regression test, not statistical validation: true distance
    0.5 exceeds 2 * threshold (about 0.255) at 1000 shots, where the bound
    guarantees DISTINGUISHED with probability at least 0.98 per trial."""
    original, mutant = h_removed_pair()

    tally = verdict_counts(original, mutant, shots=1000, tolerance=0.0)

    assert tally[DISTINGUISHED] >= 186


def test_regression_fixed_seeds_large_difference_never_within_tolerance():
    """Deterministic regression test, not statistical validation: true distance
    0.5 exceeds the tolerance 0.2, so WITHIN_TOLERANCE is a false verdict that
    the bound limits to probability 0.02 per trial."""
    original, mutant = h_removed_pair()

    tally = verdict_counts(original, mutant, shots=2000, tolerance=0.2)

    assert tally[WITHIN] <= 14


def test_regression_fixed_seeds_identical_circuits_within_tolerance():
    """Deterministic regression test, not statistical validation: true distance
    0 is below tolerance 0.2 minus 2 * threshold (about 0.095) at 10000 shots,
    where the bound guarantees WITHIN_TOLERANCE with probability at least 0.98
    per trial."""
    tally = verdict_counts(bell_uniform(), bell_uniform(), shots=10000, tolerance=0.2)

    assert tally[WITHIN] >= 186


def test_regression_fixed_seed_oracle_run_with_the_default_sampler():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.barrier()
    circuit.measure(0, 0)

    def run():
        return run_removal_mutants(circuit, distribution_oracle(circuit, shots=1000, seed=7), allow_barrier=True)

    first = run()

    assert [result.outcome.value for result in first.results] == ["killed", "survived", "not_run"]
    assert first == run()


def test_regression_fixed_seed_default_sampler_uses_the_seed():
    """Fixed-seed regression check that the default sampler forwards the seed."""
    circuit = h_measure()

    same = sample_counts(circuit, shots=1000, seed=1) == sample_counts(circuit, shots=1000, seed=1)
    different = sample_counts(circuit, shots=1000, seed=1) != sample_counts(circuit, shots=1000, seed=2)

    assert same
    assert different
