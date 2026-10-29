import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from qmutate import MutationMetrics, RunReport, mutation_score, run_removal_mutants


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


def derived(metrics: MutationMetrics) -> tuple:
    return (
        metrics.total,
        metrics.executed,
        metrics.eligible,
        metrics.score,
        metrics.error_rate,
    )


def test_derived_values_come_from_the_four_counts():
    metrics = MutationMetrics(killed=3, survived=2, errors=1, not_run=4)

    assert derived(metrics) == (10, 6, 5, 0.6, 1 / 6)


def test_total_executed_and_eligible_are_distinct():
    metrics = MutationMetrics(killed=1, survived=0, errors=0, not_run=0)
    with_error = MutationMetrics(killed=1, survived=0, errors=1, not_run=0)
    with_not_run = MutationMetrics(killed=1, survived=0, errors=0, not_run=1)

    assert (metrics.total, metrics.executed, metrics.eligible) == (1, 1, 1)
    assert (with_error.total, with_error.executed, with_error.eligible) == (2, 2, 1)
    assert (with_not_run.total, with_not_run.executed, with_not_run.eligible) == (2, 1, 1)


def test_errors_and_not_run_are_excluded_from_the_score_denominator():
    base = MutationMetrics(killed=1, survived=1, errors=0, not_run=0)
    noisy = MutationMetrics(killed=1, survived=1, errors=5, not_run=7)

    assert base.score == noisy.score == 0.5


def test_score_matches_mutation_score_with_full_precision():
    metrics = MutationMetrics(killed=2, survived=1, errors=0, not_run=0)

    assert metrics.score == mutation_score(2, 3)
    assert metrics.score == 2 / 3
    assert metrics.score != round(2 / 3, 4)


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((0, 0, 0, 0), (0, 0, 0, None, None)),
        ((0, 0, 3, 0), (3, 3, 0, None, 1.0)),
        ((0, 0, 0, 3), (3, 0, 0, None, None)),
        ((3, 0, 0, 0), (3, 3, 3, 1.0, 0.0)),
        ((0, 3, 0, 0), (3, 3, 3, 0.0, 0.0)),
    ],
    ids=["empty", "all-error", "all-not-run", "all-killed", "all-survived"],
)
def test_edge_cases(counts, expected):
    metrics = MutationMetrics(*counts)

    assert derived(metrics) == expected
    if expected[3] is not None:
        assert type(metrics.score) is float


def test_undefined_score_does_not_change_mutation_score_behaviour():
    metrics = MutationMetrics(killed=0, survived=0, errors=2, not_run=1)

    assert metrics.score is None
    with pytest.raises(ZeroDivisionError):
        mutation_score(0, 0)


@pytest.mark.parametrize("field", ["killed", "survived", "errors", "not_run"])
@pytest.mark.parametrize("value", [True, False, 1.0, "1", None])
def test_counts_reject_non_int_values(field, value):
    counts = {"killed": 0, "survived": 0, "errors": 0, "not_run": 0, field: value}

    with pytest.raises(TypeError, match=field):
        MutationMetrics(**counts)


@pytest.mark.parametrize("field", ["killed", "survived", "errors", "not_run"])
def test_counts_reject_negative_values(field):
    counts = {"killed": 0, "survived": 0, "errors": 0, "not_run": 0, field: -1}

    with pytest.raises(ValueError, match=f"{field} must be non-negative"):
        MutationMetrics(**counts)


def test_metrics_are_immutable_hashable_and_comparable():
    first = MutationMetrics(1, 2, 3, 4)

    with pytest.raises(AttributeError):
        first.killed = 5
    assert first == MutationMetrics(1, 2, 3, 4)
    assert hash(first) == hash(MutationMetrics(1, 2, 3, 4))
    assert first != MutationMetrics(1, 2, 3, 5)


def mixed_report() -> RunReport:
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)
    circuit.x(1)

    def oracle(candidate: QuantumCircuit) -> None:
        names = op_names(candidate)
        if "cx" not in names:
            raise ValueError("cannot evaluate without cx")
        assert "h" in names

    return run_removal_mutants(circuit, oracle)


def test_run_report_metrics_match_report_counts_and_score():
    report = mixed_report()

    metrics = report.metrics()

    assert [result.outcome.value for result in report.results] == [
        "killed",
        "not_run",
        "error",
        "survived",
    ]
    assert metrics == MutationMetrics(killed=1, survived=1, errors=1, not_run=1)
    assert metrics.score == report.score() == 0.5
    assert metrics.error_rate == 1 / 3


def test_run_report_metrics_score_is_none_where_score_raises():
    only_measurements = QuantumCircuit(1, 1)
    only_measurements.measure(0, 0)

    report = run_removal_mutants(only_measurements, lambda candidate: None)

    assert report.metrics().score is None
    with pytest.raises(ZeroDivisionError):
        report.score()


def test_run_report_metrics_for_all_killed_run():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    expected = Operator(circuit)

    def oracle(candidate: QuantumCircuit) -> None:
        assert Operator(candidate).equiv(expected)

    metrics = run_removal_mutants(circuit, oracle).metrics()

    assert metrics == MutationMetrics(killed=2, survived=0, errors=0, not_run=0)
    assert metrics.score == 1.0
