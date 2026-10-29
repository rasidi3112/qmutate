import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import PauliEvolutionGate
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Operator, SparsePauliOp

from qmutate import (
    BaselineFailedError,
    CandidateStatus,
    MutantOutcome,
    MutantResult,
    RunReport,
    generate_removal_mutants,
    mutation_score,
    run_removal_mutants,
)


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


def outcomes(report: RunReport) -> list[tuple[int, str, str | None]]:
    for result in report.results:
        assert type(result.outcome) is MutantOutcome
    return [
        (result.candidate.index, result.outcome.value, result.error_type)
        for result in report.results
    ]


def unitary_oracle(reference: QuantumCircuit):
    expected = Operator(reference)

    def oracle(circuit: QuantumCircuit) -> None:
        assert Operator(circuit).equiv(expected)

    return oracle


class Recorder:
    def __init__(self, inner=None):
        self.calls = []
        self.inner = inner

    def __call__(self, circuit: QuantumCircuit):
        self.calls.append(op_names(circuit))
        if self.inner is not None:
            return self.inner(circuit)
        return None


def three_gates() -> QuantumCircuit:
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.x(1)
    circuit.cx(0, 1)
    return circuit


def with_barrier() -> QuantumCircuit:
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)
    return circuit


def test_every_mutant_killed_by_unitary_oracle():
    circuit = three_gates()

    report = run_removal_mutants(circuit, unitary_oracle(circuit))

    assert outcomes(report) == [(0, "killed", None), (1, "killed", None), (2, "killed", None)]
    assert (report.killed, report.survived, report.errors, report.not_run) == (3, 0, 0, 0)
    assert report.score() == 1.0


def test_barrier_removal_survives_unitary_oracle():
    circuit = with_barrier()

    report = run_removal_mutants(circuit, unitary_oracle(circuit), allow_barrier=True)

    assert outcomes(report) == [(0, "killed", None), (1, "survived", None), (2, "killed", None)]
    assert report.score() == pytest.approx(2 / 3)


def test_skipped_candidates_are_not_run_and_oracle_is_not_called():
    circuit = with_barrier()
    oracle = Recorder(unitary_oracle(circuit))

    report = run_removal_mutants(circuit, oracle)

    assert outcomes(report) == [(0, "killed", None), (1, "not_run", None), (2, "killed", None)]
    assert report.results[1].candidate.status is CandidateStatus.SKIPPED
    assert oracle.calls == [["h", "barrier", "cx"], ["barrier", "cx"], ["h", "barrier"]]
    assert (report.killed, report.not_run) == (2, 1)
    assert report.score() == 1.0


def test_oracle_errors_are_recorded_and_excluded_from_score():
    circuit = three_gates()
    check = unitary_oracle(circuit)

    def oracle(candidate: QuantumCircuit) -> None:
        if "cx" not in op_names(candidate):
            raise ValueError("cannot evaluate a circuit without cx")
        check(candidate)

    report = run_removal_mutants(circuit, oracle)

    assert outcomes(report) == [(0, "killed", None), (1, "killed", None), (2, "error", "ValueError")]
    assert (report.killed, report.survived, report.errors) == (2, 0, 1)
    assert report.score() == mutation_score(2, 2)


def test_assertion_error_subclass_counts_as_killed():
    class CircuitMismatch(AssertionError):
        pass

    circuit = three_gates()

    def oracle(candidate: QuantumCircuit) -> None:
        if len(candidate.data) < len(circuit.data):
            raise CircuitMismatch("shorter circuit")

    report = run_removal_mutants(circuit, oracle)

    assert outcomes(report) == [(0, "killed", None), (1, "killed", None), (2, "killed", None)]


def test_oracle_return_value_is_ignored():
    report = run_removal_mutants(three_gates(), lambda candidate: False)

    assert [result.outcome for result in report.results] == [MutantOutcome.SURVIVED] * 3


def raise_keyboard_interrupt():
    raise KeyboardInterrupt


def raise_system_exit():
    raise SystemExit(3)


def call_pytest_fail():
    pytest.fail("oracle used pytest.fail")


@pytest.mark.parametrize(
    ("raise_it", "expected"),
    [
        (raise_keyboard_interrupt, KeyboardInterrupt),
        (raise_system_exit, SystemExit),
        (call_pytest_fail, pytest.fail.Exception),
    ],
    ids=["keyboard-interrupt", "system-exit", "pytest-fail"],
)
def test_base_exceptions_from_a_mutant_call_propagate(raise_it, expected):
    calls = []

    def oracle(candidate: QuantumCircuit) -> None:
        calls.append(op_names(candidate))
        if len(calls) == 2:
            raise_it()

    with pytest.raises(expected):
        run_removal_mutants(three_gates(), oracle)

    assert len(calls) == 2


@pytest.mark.parametrize(
    ("raise_it", "expected"),
    [(raise_keyboard_interrupt, KeyboardInterrupt), (raise_system_exit, SystemExit)],
    ids=["keyboard-interrupt", "system-exit"],
)
def test_base_exceptions_from_the_baseline_propagate_unwrapped(raise_it, expected):
    calls = []

    def oracle(candidate: QuantumCircuit) -> None:
        calls.append(op_names(candidate))
        raise_it()

    with pytest.raises(expected):
        run_removal_mutants(three_gates(), oracle)

    assert len(calls) == 1


@pytest.mark.parametrize(
    "error",
    [AssertionError("baseline assertion"), RuntimeError("baseline crash")],
    ids=["assertion", "other-exception"],
)
def test_baseline_failure_stops_before_any_mutant(error):
    calls = []

    def oracle(candidate: QuantumCircuit) -> None:
        calls.append(op_names(candidate))
        raise error

    with pytest.raises(BaselineFailedError, match=type(error).__name__) as raised:
        run_removal_mutants(three_gates(), oracle)

    assert raised.value.__cause__ is error
    assert not isinstance(raised.value, AssertionError)
    assert calls == [["h", "x", "cx"]]


def test_oracle_is_called_once_per_generated_candidate_in_index_order():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)
    circuit.measure(0, 0)
    circuit.x(1)
    oracle = Recorder()

    report = run_removal_mutants(circuit, oracle)

    original = op_names(circuit)
    generated = [0, 2, 4]
    assert oracle.calls == [original] + [original[:i] + original[i + 1 :] for i in generated]
    assert [result.candidate.index for result in report.results] == [0, 1, 2, 3, 4]
    assert [result.outcome.value for result in report.results] == [
        "survived",
        "not_run",
        "survived",
        "not_run",
        "survived",
    ]


def test_empty_circuit_runs_only_the_baseline():
    oracle = Recorder()

    report = run_removal_mutants(QuantumCircuit(2), oracle)

    assert oracle.calls == [[]]
    assert report.results == ()
    with pytest.raises(ZeroDivisionError):
        report.score()


def test_score_matches_mutation_score_and_excludes_error_and_not_run():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.x(1)
    circuit.cx(0, 1)
    check = unitary_oracle(circuit)

    def oracle(candidate: QuantumCircuit) -> None:
        if "x" not in op_names(candidate):
            raise RuntimeError("unsupported")
        check(candidate)

    report = run_removal_mutants(circuit, oracle)

    assert outcomes(report) == [
        (0, "killed", None),
        (1, "not_run", None),
        (2, "error", "RuntimeError"),
        (3, "killed", None),
    ]
    assert report.score() == mutation_score(report.killed, report.killed + report.survived)
    assert report.score() == 1.0


def test_score_raises_when_nothing_was_killed_or_survived():
    only_measurements = QuantumCircuit(1, 1)
    only_measurements.measure(0, 0)

    def always_errors(candidate: QuantumCircuit) -> None:
        if len(candidate.data) < 3:
            raise RuntimeError("cannot evaluate")

    not_run = run_removal_mutants(only_measurements, lambda candidate: None)
    errors = run_removal_mutants(three_gates(), always_errors)

    assert (not_run.not_run, errors.errors) == (1, 3)
    for report in (not_run, errors):
        with pytest.raises(ZeroDivisionError):
            report.score()


def test_original_circuit_is_unchanged_even_if_the_oracle_edits_its_input():
    body = QuantumCircuit(1, name="custom")
    body.rx(0.5, 0)
    circuit = QuantumCircuit(2, 1, name="original", metadata={"tags": ["original"]})
    circuit.append(body.to_gate(), [0])
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(1)
    circuit.h(1)
    snapshot = circuit.copy()

    def editing_oracle(candidate: QuantumCircuit) -> None:
        candidate.metadata["tags"].append("oracle")
        candidate.name = "edited"
        for instruction in candidate.data:
            operation = instruction.operation
            if operation.name == "if_else":
                operation.blocks[0].z(0)
            if operation.name == "custom":
                operation.label = "edited"
                operation.definition.h(0)
        candidate.z(0)

    report = run_removal_mutants(circuit, editing_oracle)
    fresh = generate_removal_mutants(circuit)

    assert circuit == snapshot
    assert circuit.name == "original"
    assert circuit.metadata == {"tags": ["original"]}
    assert op_names(circuit.data[2].operation.blocks[0]) == ["x"]
    assert circuit.data[0].operation.label is None
    assert op_names(circuit.data[0].operation.definition) == ["rx"]
    for result, candidate in zip(report.results, fresh):
        assert result.candidate == candidate
        if candidate.mutant is not None:
            assert result.candidate.mutant.name == "original"
            assert result.candidate.mutant.metadata == {"tags": ["original"]}


def test_known_limitation_oracle_edits_to_shared_attributes_reach_original():
    """Documents a limitation: the oracle's copy follows remove_instruction's
    isolation rules, so state that is not guaranteed independent there, such
    as ``PauliEvolutionGate.operator``, is shared with the original circuit
    (observed with Qiskit 2.0.3 and 2.6.1).
    """
    circuit = QuantumCircuit(1)
    circuit.append(PauliEvolutionGate(SparsePauliOp(["Z"], coeffs=[1.0]), time=0.5), [0])
    circuit.h(0)
    seen = []

    def editing_oracle(candidate: QuantumCircuit) -> None:
        seen.append(op_names(candidate))
        if seen == [["PauliEvolution", "h"]]:
            candidate.data[0].operation.operator.coeffs[0] = 7.0

    run_removal_mutants(circuit, editing_oracle)

    assert circuit.data[0].operation.operator.coeffs.tolist() == [7.0]


def sampled_bell_oracle(record: list[dict[str, int]]):
    backend = BasicSimulator()

    def oracle(candidate: QuantumCircuit) -> None:
        counts = backend.run(candidate, shots=200, seed_simulator=11).result().get_counts()
        record.append(dict(sorted(counts.items())))
        assert set(counts) == {"00", "11"}
        assert min(counts.values()) > 50

    return oracle


def bell_with_measurements() -> QuantumCircuit:
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    return circuit


def test_seeded_simulator_oracle_gives_reproducible_reports():
    first_counts: list[dict[str, int]] = []
    second_counts: list[dict[str, int]] = []

    first = run_removal_mutants(bell_with_measurements(), sampled_bell_oracle(first_counts))
    second = run_removal_mutants(bell_with_measurements(), sampled_bell_oracle(second_counts))

    assert outcomes(first) == [
        (0, "killed", None),
        (1, "killed", None),
        (2, "not_run", None),
        (3, "not_run", None),
    ]
    assert first == second
    assert first_counts == second_counts
    assert len(first_counts) == 3


def test_non_callable_oracle_raises_type_error():
    with pytest.raises(TypeError, match="oracle must be callable"):
        run_removal_mutants(three_gates(), "not callable")


def test_non_circuit_raises_type_error_without_calling_oracle():
    oracle = Recorder()

    with pytest.raises(TypeError, match="circuit must be a QuantumCircuit"):
        run_removal_mutants([("h", 0)], oracle)

    assert oracle.calls == []


def test_routed_circuit_is_rejected_before_calling_oracle():
    source = QuantumCircuit(3)
    source.h(0)
    source.cx(0, 2)
    routed = transpile(
        source,
        basis_gates=["u", "cx", "swap"],
        coupling_map=[[0, 1], [1, 2]],
        initial_layout=[0, 1, 2],
        optimization_level=0,
        seed_transpiler=3,
    )
    oracle = Recorder()

    with pytest.raises(ValueError, match="final_layout"):
        run_removal_mutants(routed, oracle)

    assert oracle.calls == []


def candidates_pair():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    generated, skipped = generate_removal_mutants(circuit)
    assert generated.status is CandidateStatus.GENERATED
    assert skipped.status is CandidateStatus.SKIPPED
    return generated, skipped


def test_valid_mutant_results_are_accepted():
    generated, skipped = candidates_pair()

    results = [
        MutantResult(generated, MutantOutcome.KILLED, None),
        MutantResult(generated, MutantOutcome.SURVIVED, None),
        MutantResult(generated, MutantOutcome.ERROR, "ValueError"),
        MutantResult(skipped, MutantOutcome.NOT_RUN, None),
    ]

    assert [result.outcome.value for result in results] == ["killed", "survived", "error", "not_run"]
    assert len(set(results)) == 4


@pytest.mark.parametrize(
    ("build", "error", "match"),
    [
        (lambda g, s: MutantResult("candidate", MutantOutcome.KILLED, None), TypeError, "candidate"),
        (lambda g, s: MutantResult(g, "killed", None), TypeError, "outcome"),
        (lambda g, s: MutantResult(g, MutantOutcome.ERROR, 3), TypeError, "error_type"),
        (lambda g, s: MutantResult(g, MutantOutcome.NOT_RUN, None), ValueError, "NOT_RUN"),
        (lambda g, s: MutantResult(s, MutantOutcome.KILLED, None), ValueError, "NOT_RUN"),
        (lambda g, s: MutantResult(g, MutantOutcome.ERROR, None), ValueError, "non-empty"),
        (lambda g, s: MutantResult(g, MutantOutcome.ERROR, ""), ValueError, "non-empty"),
        (lambda g, s: MutantResult(g, MutantOutcome.KILLED, "AssertionError"), ValueError, "only allowed"),
        (lambda g, s: MutantResult(s, MutantOutcome.NOT_RUN, "ValueError"), ValueError, "only allowed"),
    ],
    ids=[
        "non-candidate",
        "str-outcome",
        "non-str-error-type",
        "not-run-for-generated",
        "killed-for-skipped",
        "error-without-type",
        "error-with-empty-type",
        "killed-with-type",
        "not-run-with-type",
    ],
)
def test_invalid_mutant_results_are_rejected(build, error, match):
    generated, skipped = candidates_pair()

    with pytest.raises(error, match=match):
        build(generated, skipped)


def valid_results() -> tuple[MutantResult, MutantResult]:
    generated, skipped = candidates_pair()
    return (
        MutantResult(generated, MutantOutcome.KILLED, None),
        MutantResult(skipped, MutantOutcome.NOT_RUN, None),
    )


def test_valid_run_report_is_accepted():
    report = RunReport(valid_results(), killed=1, survived=0, errors=0, not_run=1)

    assert report.score() == 1.0
    assert report == RunReport(valid_results(), killed=1, survived=0, errors=0, not_run=1)
    assert hash(report) == hash(RunReport(valid_results(), killed=1, survived=0, errors=0, not_run=1))


@pytest.mark.parametrize(
    ("build", "error", "match"),
    [
        (lambda r: RunReport(list(r), 1, 0, 0, 1), TypeError, "tuple"),
        (lambda r: RunReport((r[0], "result"), 1, 0, 0, 1), TypeError, "MutantResult"),
        (lambda r: RunReport((r[1], r[0]), 1, 0, 0, 1), ValueError, "index order"),
        (lambda r: RunReport((r[1],), 0, 0, 0, 1), ValueError, "index order"),
        (lambda r: RunReport(r, 2, 0, 0, 1), ValueError, "killed"),
        (lambda r: RunReport(r, 1, 1, 0, 1), ValueError, "survived"),
        (lambda r: RunReport(r, 1, 0, 1, 1), ValueError, "errors"),
        (lambda r: RunReport(r, 1, 0, 0, 0), ValueError, "not_run"),
        (lambda r: RunReport(r, True, 0, 0, 1), TypeError, "killed"),
        (lambda r: RunReport(r, 1, 0, 0, 1.0), TypeError, "not_run"),
        (lambda r: RunReport(r, 1, -1, 0, 1), ValueError, "survived"),
    ],
    ids=[
        "list-results",
        "non-result-element",
        "out-of-order",
        "missing-leading-index",
        "wrong-killed",
        "wrong-survived",
        "wrong-errors",
        "wrong-not-run",
        "bool-count",
        "float-count",
        "negative-count",
    ],
)
def test_invalid_run_reports_are_rejected(build, error, match):
    with pytest.raises(error, match=match):
        build(valid_results())
