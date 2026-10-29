import dataclasses

import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Instruction, Parameter
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.quantum_info import Operator

from qmutate import (
    CandidateStatus,
    RemovalCandidate,
    SkipReason,
    generate_removal_mutants,
    remove_instruction,
)


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


def operands(circuit: QuantumCircuit) -> list[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    return [
        (
            instruction.operation.name,
            tuple(circuit.find_bit(qubit).index for qubit in instruction.qubits),
            tuple(circuit.find_bit(clbit).index for clbit in instruction.clbits),
        )
        for instruction in circuit.data
    ]


def statuses(candidates: list[RemovalCandidate]) -> list[tuple[int, str, str, str | None]]:
    for candidate in candidates:
        assert type(candidate.status) is CandidateStatus
        assert candidate.skip_reason is None or type(candidate.skip_reason) is SkipReason
    return [
        (
            candidate.index,
            candidate.name,
            candidate.status.value,
            None if candidate.skip_reason is None else candidate.skip_reason.value,
        )
        for candidate in candidates
    ]


@pytest.fixture
def mixed() -> QuantumCircuit:
    circuit = QuantumCircuit(2, 2, name="mixed")
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)
    circuit.measure(0, 0)
    circuit.x(1)
    return circuit


def custom_instruction(*, measure: bool = False, barrier: bool = False) -> Instruction:
    body = QuantumCircuit(1, 1 if measure else 0, name="composite")
    body.h(0)
    if barrier:
        body.barrier()
    if measure:
        body.measure(0, 0)
    return body.to_instruction()


def test_status_and_reason_values_are_stable():
    assert [status.value for status in CandidateStatus] == ["generated", "skipped"]
    assert [reason.value for reason in SkipReason] == [
        "measurement_not_allowed",
        "barrier_not_allowed",
    ]


def test_every_removable_instruction_yields_a_mutant():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.x(1)
    circuit.cx(0, 1)

    candidates = generate_removal_mutants(circuit)

    assert statuses(candidates) == [
        (0, "h", "generated", None),
        (1, "x", "generated", None),
        (2, "cx", "generated", None),
    ]
    assert [op_names(candidate.mutant) for candidate in candidates] == [
        ["x", "cx"],
        ["h", "cx"],
        ["h", "x"],
    ]


@pytest.mark.parametrize(
    "circuit",
    [QuantumCircuit(), QuantumCircuit(2, 2)],
    ids=["no-bits", "with-bits"],
)
def test_empty_circuit_yields_no_candidates(circuit):
    assert generate_removal_mutants(circuit) == []


def test_circuit_with_only_measurements_and_barriers_is_all_skipped():
    circuit = QuantumCircuit(2, 2)
    circuit.barrier()
    circuit.measure([0, 1], [0, 1])

    candidates = generate_removal_mutants(circuit)

    assert statuses(candidates) == [
        (0, "barrier", "skipped", "barrier_not_allowed"),
        (1, "measure", "skipped", "measurement_not_allowed"),
        (2, "measure", "skipped", "measurement_not_allowed"),
    ]
    assert all(candidate.mutant is None for candidate in candidates)


def test_allow_flags_turn_measurements_and_barriers_into_mutants():
    circuit = QuantumCircuit(1, 1)
    circuit.barrier()
    circuit.measure(0, 0)

    only_measure = generate_removal_mutants(circuit, allow_measure=True)
    only_barrier = generate_removal_mutants(circuit, allow_barrier=True)
    both = generate_removal_mutants(circuit, allow_measure=True, allow_barrier=True)

    assert [candidate.status for candidate in only_measure] == ["skipped", "generated"]
    assert [candidate.status for candidate in only_barrier] == ["generated", "skipped"]
    assert [op_names(candidate.mutant) for candidate in both] == [["measure"], ["barrier"]]


def test_mixed_circuit_reports_generated_and_skipped_in_index_order(mixed):
    candidates = generate_removal_mutants(mixed)

    assert statuses(candidates) == [
        (0, "h", "generated", None),
        (1, "barrier", "skipped", "barrier_not_allowed"),
        (2, "cx", "generated", None),
        (3, "measure", "skipped", "measurement_not_allowed"),
        (4, "x", "generated", None),
    ]


def test_reported_index_and_name_match_original(mixed):
    candidates = generate_removal_mutants(mixed)

    assert [candidate.index for candidate in candidates] == list(range(len(mixed.data)))
    assert [candidate.name for candidate in candidates] == op_names(mixed)


def test_each_mutant_removes_exactly_the_reported_instruction(mixed):
    original = operands(mixed)

    for candidate in generate_removal_mutants(mixed, allow_measure=True, allow_barrier=True):
        expected = original[: candidate.index] + original[candidate.index + 1 :]
        assert operands(candidate.mutant) == expected
        assert candidate.mutant.num_qubits == mixed.num_qubits
        assert candidate.mutant.num_clbits == mixed.num_clbits
        assert candidate.mutant.name == mixed.name


def test_mutants_match_remove_instruction(mixed):
    generated = [
        candidate
        for candidate in generate_removal_mutants(mixed)
        if candidate.status is CandidateStatus.GENERATED
    ]

    assert [candidate.index for candidate in generated] == [0, 2, 4]
    for candidate in generated:
        assert candidate.mutant == remove_instruction(mixed, candidate.index)


def test_skipped_candidates_are_rejected_by_remove_instruction(mixed):
    skipped = [
        candidate
        for candidate in generate_removal_mutants(mixed)
        if candidate.status is CandidateStatus.SKIPPED
    ]

    assert [candidate.index for candidate in skipped] == [1, 3]
    for candidate in skipped:
        with pytest.raises(ValueError, match="allow_"):
            remove_instruction(mixed, candidate.index)


def test_mutants_keep_name_metadata_and_global_phase_explicitly():
    circuit = QuantumCircuit(2, name="annotated", global_phase=0.25, metadata={"run": {"seed": 7}})
    circuit.h(0)
    circuit.cx(0, 1)

    generated = generate_removal_mutants(circuit)

    assert len(generated) == 2
    for candidate in generated:
        mutant = candidate.mutant
        assert mutant.name == "annotated"
        assert mutant.global_phase == pytest.approx(0.25)
        assert mutant.metadata == {"run": {"seed": 7}}
        assert mutant.metadata is not circuit.metadata
        mutant.metadata["run"]["seed"] = 8
    assert circuit.metadata == {"run": {"seed": 7}}


def test_parameterized_circuit_mutants_track_parameters():
    theta = Parameter("theta")
    phi = Parameter("phi")
    circuit = QuantumCircuit(1, global_phase=phi)
    circuit.rx(theta, 0)
    circuit.rz(phi, 0)

    candidates = generate_removal_mutants(circuit)

    assert statuses(candidates) == [(0, "rx", "generated", None), (1, "rz", "generated", None)]
    assert set(candidates[0].mutant.parameters) == {phi}
    assert set(candidates[1].mutant.parameters) == {theta, phi}
    bound = candidates[0].mutant.assign_parameters({phi: 0.5})
    assert float(bound.global_phase) == pytest.approx(0.5)
    assert set(circuit.parameters) == {theta, phi}


def test_if_else_without_measurement_or_barrier_is_generated():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(1)
    circuit.z(1)

    candidates = generate_removal_mutants(circuit)

    assert statuses(candidates) == [
        (0, "h", "generated", None),
        (1, "measure", "skipped", "measurement_not_allowed"),
        (2, "if_else", "generated", None),
        (3, "z", "generated", None),
    ]
    assert op_names(candidates[2].mutant) == ["h", "measure", "z"]


def test_nondeterministic_lazy_definition_never_escapes_as_error():
    """Regression test: the policy check and the mutant are built from one copy.

    The instruction's lazily built definition contains a barrier only on
    every second build. Checking and building on separate copies used to
    classify it as generated and then fail inside ``remove_instruction``.
    """
    builds = []

    class AlternatingDefinition(Instruction):
        def __init__(self):
            super().__init__("alternating", 1, 0, [])

        def _define(self):
            builds.append(self)
            body = QuantumCircuit(1)
            if len(builds) % 2 == 0:
                body.barrier()
            else:
                body.x(0)
            self.definition = body

    circuit = QuantumCircuit(1)
    circuit.append(AlternatingDefinition(), [0])
    circuit.h(0)

    candidates = generate_removal_mutants(circuit)

    assert builds
    assert [candidate.index for candidate in candidates] == [0, 1]
    first = candidates[0]
    if first.status is CandidateStatus.GENERATED:
        assert op_names(first.mutant) == ["h"]
    else:
        assert first.skip_reason is SkipReason.BARRIER_NOT_ALLOWED
    assert candidates[1].status is CandidateStatus.GENERATED


def test_results_are_deterministic(mixed):
    first = generate_removal_mutants(mixed)
    second = generate_removal_mutants(mixed)

    assert statuses(first) == statuses(second)
    assert first == second


def test_original_circuit_is_unchanged_after_generation(mixed):
    mixed.metadata = {"tags": ["original"]}
    snapshot = mixed.copy()

    candidates = generate_removal_mutants(mixed, allow_measure=True, allow_barrier=True)
    for candidate in candidates:
        candidate.mutant.metadata["tags"].append("mutant")
        candidate.mutant.z(0)

    assert mixed == snapshot
    assert op_names(mixed) == ["h", "barrier", "cx", "measure", "x"]
    assert mixed.metadata == {"tags": ["original"]}


def test_generation_does_not_build_lazy_definition_on_original():
    defined_on = []

    class LazyBarrierBlock(Instruction):
        def __init__(self):
            super().__init__("lazy_barrier_block", 1, 0, [])

        def _define(self):
            defined_on.append(self)
            body = QuantumCircuit(1)
            body.barrier()
            self.definition = body

    circuit = QuantumCircuit(1)
    circuit.append(LazyBarrierBlock(), [0])
    circuit.h(0)
    original_operation = circuit.data[0].operation

    candidates = generate_removal_mutants(circuit)

    assert statuses(candidates)[0] == (0, "lazy_barrier_block", "skipped", "barrier_not_allowed")
    assert defined_on
    assert all(operation is not original_operation for operation in defined_on)


def test_candidates_are_immutable_records(mixed):
    candidate = generate_removal_mutants(mixed)[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.index = 7


def test_composite_instructions_follow_remove_instruction_policy():
    circuit = QuantumCircuit(1, 1)
    circuit.append(custom_instruction(measure=True), [0], [0])
    circuit.append(custom_instruction(barrier=True), [0])
    circuit.append(Instruction("opaque_readout", 1, 1, []), [0], [0])
    circuit.append(custom_instruction(), [0])
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.barrier()

    candidates = generate_removal_mutants(circuit)

    assert statuses(candidates) == [
        (0, "composite", "skipped", "measurement_not_allowed"),
        (1, "composite", "skipped", "barrier_not_allowed"),
        (2, "opaque_readout", "skipped", "measurement_not_allowed"),
        (3, "composite", "generated", None),
        (4, "if_else", "skipped", "barrier_not_allowed"),
    ]


def test_operation_with_measurement_and_barrier_reports_reason_in_check_order():
    circuit = QuantumCircuit(1, 1)
    circuit.append(custom_instruction(measure=True, barrier=True), [0], [0])

    reasons = [
        generate_removal_mutants(circuit)[0].skip_reason,
        generate_removal_mutants(circuit, allow_measure=True)[0].skip_reason,
        generate_removal_mutants(circuit, allow_barrier=True)[0].skip_reason,
        generate_removal_mutants(circuit, allow_measure=True, allow_barrier=True)[0].skip_reason,
    ]

    assert reasons == [
        SkipReason.MEASUREMENT_NOT_ALLOWED,
        SkipReason.BARRIER_NOT_ALLOWED,
        SkipReason.MEASUREMENT_NOT_ALLOWED,
        None,
    ]


def test_non_circuit_raises_type_error():
    with pytest.raises(TypeError, match="circuit must be a QuantumCircuit"):
        generate_removal_mutants([("h", 0)])


def routed_circuit() -> QuantumCircuit:
    source = QuantumCircuit(3)
    source.h(0)
    source.cx(0, 2)
    return transpile(
        source,
        basis_gates=["u", "cx", "swap"],
        coupling_map=[[0, 1], [1, 2]],
        initial_layout=[0, 1, 2],
        optimization_level=0,
        seed_transpiler=3,
    )


def scheduled_circuit() -> QuantumCircuit:
    backend = GenericBackendV2(num_qubits=1, basis_gates=["x", "sx", "rz", "measure", "delay"], seed=1)
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.x(0)
    return transpile(
        circuit, backend=backend, scheduling_method="asap", optimization_level=0, seed_transpiler=1
    )


@pytest.mark.parametrize(
    ("build", "match"),
    [(routed_circuit, "final_layout"), (scheduled_circuit, "scheduled")],
    ids=["routed", "scheduled"],
)
def test_routed_or_scheduled_circuit_is_rejected_as_a_whole(build, match):
    circuit = build()
    snapshot = circuit.copy()

    with pytest.raises(ValueError, match=match):
        generate_removal_mutants(circuit)

    assert circuit == snapshot


@pytest.mark.parametrize(
    ("build", "match"),
    [(routed_circuit, "final_layout"), (scheduled_circuit, "scheduled")],
    ids=["routed", "scheduled"],
)
def test_empty_routed_or_scheduled_circuit_is_still_rejected(build, match):
    empty = build().copy_empty_like()
    assert len(empty.data) == 0

    with pytest.raises(ValueError, match=match):
        generate_removal_mutants(empty)


@pytest.mark.parametrize("error", [RuntimeError("boom"), ValueError("unexpected")])
def test_unexpected_errors_propagate_instead_of_becoming_skips(error):
    class BrokenDefinition(Instruction):
        def __init__(self):
            super().__init__("broken", 1, 0, [])

        def _define(self):
            raise error

    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.append(BrokenDefinition(), [0])

    with pytest.raises(type(error), match=str(error)):
        generate_removal_mutants(circuit)


def generated_and_skipped() -> tuple[RemovalCandidate, RemovalCandidate]:
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    generated, skipped = generate_removal_mutants(circuit)
    assert generated.status is CandidateStatus.GENERATED
    assert skipped.status is CandidateStatus.SKIPPED
    return generated, skipped


def test_generated_and_skipped_candidates_are_hashable():
    generated, skipped = generated_and_skipped()

    assert isinstance(hash(generated), int)
    assert isinstance(hash(skipped), int)
    assert len({generated, skipped}) == 2


def test_equal_candidates_have_equal_hashes():
    first = generated_and_skipped()
    second = generated_and_skipped()

    for left, right in zip(first, second):
        assert left is not right
        assert left.mutant is not right.mutant or left.mutant is None
        assert left == right
        assert hash(left) == hash(right)
    assert len(set(first) | set(second)) == 2


def test_candidates_differing_in_any_field_are_not_equal():
    generated, skipped = generated_and_skipped()
    other_mutant = QuantumCircuit(1, 1)
    other_mutant.x(0)

    variants = [
        dataclasses.replace(generated, index=5),
        dataclasses.replace(generated, name="renamed"),
        dataclasses.replace(generated, mutant=other_mutant),
        dataclasses.replace(skipped, skip_reason=SkipReason.BARRIER_NOT_ALLOWED),
        skipped,
    ]

    for variant in variants:
        assert variant != generated
    assert hash(dataclasses.replace(generated, mutant=other_mutant)) == hash(generated)


def test_hash_is_stable_when_mutant_is_edited_in_place():
    generated, _ = generated_and_skipped()
    before = hash(generated)

    generated.mutant.x(0)

    assert hash(generated) == before


def test_valid_candidate_combinations_are_accepted():
    mutant = QuantumCircuit(1)

    generated = RemovalCandidate(0, "h", CandidateStatus.GENERATED, mutant, None)
    skipped = RemovalCandidate(3, "measure", CandidateStatus.SKIPPED, None, SkipReason.MEASUREMENT_NOT_ALLOWED)

    assert generated.mutant is mutant
    assert skipped.skip_reason is SkipReason.MEASUREMENT_NOT_ALLOWED


@pytest.mark.parametrize(
    ("fields", "error", "match"),
    [
        ((True, "h", CandidateStatus.GENERATED, QuantumCircuit(1), None), TypeError, "index"),
        (("0", "h", CandidateStatus.GENERATED, QuantumCircuit(1), None), TypeError, "index"),
        ((-1, "h", CandidateStatus.GENERATED, QuantumCircuit(1), None), ValueError, "non-negative"),
        ((0, 7, CandidateStatus.GENERATED, QuantumCircuit(1), None), TypeError, "name"),
        ((0, "h", "generated", QuantumCircuit(1), None), TypeError, "status"),
        ((0, "h", CandidateStatus.SKIPPED, None, "barrier_not_allowed"), TypeError, "skip_reason"),
        ((0, "h", CandidateStatus.GENERATED, "circuit", None), TypeError, "mutant"),
        ((0, "h", CandidateStatus.GENERATED, None, None), ValueError, "generated candidate"),
        (
            (0, "h", CandidateStatus.GENERATED, QuantumCircuit(1), SkipReason.BARRIER_NOT_ALLOWED),
            ValueError,
            "generated candidate",
        ),
        (
            (0, "h", CandidateStatus.SKIPPED, QuantumCircuit(1), SkipReason.BARRIER_NOT_ALLOWED),
            ValueError,
            "skipped candidate",
        ),
        ((0, "h", CandidateStatus.SKIPPED, None, None), ValueError, "skipped candidate"),
    ],
    ids=[
        "bool-index",
        "str-index",
        "negative-index",
        "non-str-name",
        "str-status",
        "str-skip-reason",
        "non-circuit-mutant",
        "generated-without-mutant",
        "generated-with-reason",
        "skipped-with-mutant",
        "skipped-without-reason",
    ],
)
def test_invalid_candidate_combinations_are_rejected(fields, error, match):
    with pytest.raises(error, match=match):
        RemovalCandidate(*fields)


def test_hash_contract_holds_after_mutant_edit():
    first = generated_and_skipped()
    second = generated_and_skipped()
    edited = first[0]
    hash_before = hash(edited)

    edited.mutant.z(0)
    pool = [*first, *second]

    assert hash(edited) == hash_before
    assert edited != second[0]
    for left in pool:
        for right in pool:
            if left == right:
                assert hash(left) == hash(right)


def test_set_membership_follows_current_mutant_equality():
    """Documents that hashing is stable but equality follows the mutant.

    After a stored candidate's mutant is edited in place, the stored object
    is still found, while a different candidate that used to be equal to it
    no longer matches.
    """
    stored, _ = generated_and_skipped()
    twin, _ = generated_and_skipped()
    members = {stored}
    keyed = {stored: "value"}
    assert twin == stored
    assert twin in members
    assert keyed[twin] == "value"

    stored.mutant.z(0)

    assert stored in members
    assert keyed[stored] == "value"
    assert twin != stored
    assert twin not in members
    assert twin not in keyed
    assert len({stored, twin}) == 2


def test_set_deduplication_is_structural_not_semantic():
    """Documents that candidate equality is structural, not quantum equivalence."""
    named = QuantumCircuit(1, name="first", metadata={"origin": "a"})
    named.x(0)
    named.z(0)
    renamed = QuantumCircuit(1, name="second", metadata={"origin": "b"})
    renamed.x(0)
    renamed.z(0)
    same_structure = {generate_removal_mutants(named)[1], generate_removal_mutants(renamed)[1]}

    hzh = QuantumCircuit(1)
    hzh.y(0)
    hzh.h(0)
    hzh.z(0)
    hzh.h(0)
    plain_x = QuantumCircuit(1)
    plain_x.y(0)
    plain_x.x(0)
    via_hzh = generate_removal_mutants(hzh)[0]
    via_x = generate_removal_mutants(plain_x)[0]

    assert len(same_structure) == 1
    assert (via_hzh.index, via_hzh.name, via_hzh.status) == (via_x.index, via_x.name, via_x.status)
    assert Operator(via_hzh.mutant).equiv(Operator(via_x.mutant))
    assert via_hzh != via_x
    assert len({via_hzh, via_x}) == 2


def test_known_limitation_results_follow_current_definitions():
    """Documents a limitation: results follow how definitions build now.

    Definitions are built lazily on copies, so an operation whose definition
    depends on outside state can be classified differently by two calls on
    the same input circuit. Only the index order is guaranteed to stay the
    same.
    """
    state = {"barrier": False}

    class StateDependent(Instruction):
        def __init__(self):
            super().__init__("state_dependent", 1, 0, [])

        def _define(self):
            body = QuantumCircuit(1)
            if state["barrier"]:
                body.barrier()
            else:
                body.x(0)
            self.definition = body

    circuit = QuantumCircuit(1)
    circuit.append(StateDependent(), [0])
    circuit.h(0)
    snapshot = circuit.copy()

    without_barrier = generate_removal_mutants(circuit)
    state["barrier"] = True
    with_barrier = generate_removal_mutants(circuit)

    assert statuses(without_barrier) == [
        (0, "state_dependent", "generated", None),
        (1, "h", "generated", None),
    ]
    assert statuses(with_barrier) == [
        (0, "state_dependent", "skipped", "barrier_not_allowed"),
        (1, "h", "generated", None),
    ]
    with pytest.raises(ValueError, match="allow_barrier=True"):
        remove_instruction(circuit, 0)
    assert circuit == snapshot
