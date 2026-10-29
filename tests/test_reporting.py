import json

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Instruction
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Operator

from qmutate import format_text_report, report_to_dict, run_removal_mutants
from qmutate.reporting import REPORT_SCHEMA_VERSION


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


def mixed_report():
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


def empty_report():
    return run_removal_mutants(QuantumCircuit(1), lambda candidate: None)


def all_error_report():
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.x(0)

    def oracle(candidate: QuantumCircuit) -> None:
        if len(candidate.data) < 2:
            raise RuntimeError("cannot evaluate")

    return run_removal_mutants(circuit, oracle)


def all_skipped_report():
    circuit = QuantumCircuit(2, 2)
    circuit.barrier()
    circuit.measure([0, 1], [0, 1])
    return run_removal_mutants(circuit, lambda candidate: None)


def all_killed_report():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    expected = Operator(circuit)

    def oracle(candidate: QuantumCircuit) -> None:
        assert Operator(candidate).equiv(expected)

    return run_removal_mutants(circuit, oracle)


def all_survived_report():
    circuit = QuantumCircuit(1)
    circuit.h(0)
    circuit.x(0)
    return run_removal_mutants(circuit, lambda candidate: None)


def plain_types(value) -> bool:
    if value is None or type(value) in (str, int, float):
        return True
    if type(value) is list:
        return all(plain_types(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and plain_types(item) for key, item in value.items())
    return False


def test_mixed_report_dict_is_exact():
    assert report_to_dict(mixed_report()) == {
        "schema_version": 1,
        "summary": {
            "total": 4,
            "killed": 1,
            "survived": 1,
            "errors": 1,
            "not_run": 1,
            "executed": 3,
            "eligible": 2,
            "score": 0.5,
            "error_rate": 1 / 3,
        },
        "mutants": [
            {"index": 0, "name": "h", "outcome": "killed", "skip_reason": None, "error_type": None},
            {
                "index": 1,
                "name": "barrier",
                "outcome": "not_run",
                "skip_reason": "barrier_not_allowed",
                "error_type": None,
            },
            {"index": 2, "name": "cx", "outcome": "error", "skip_reason": None, "error_type": "ValueError"},
            {"index": 3, "name": "x", "outcome": "survived", "skip_reason": None, "error_type": None},
        ],
    }


def test_dict_key_order_is_stable():
    data = report_to_dict(mixed_report())

    assert list(data) == ["schema_version", "summary", "mutants"]
    assert list(data["summary"]) == [
        "total",
        "killed",
        "survived",
        "errors",
        "not_run",
        "executed",
        "eligible",
        "score",
        "error_rate",
    ]
    assert all(
        list(mutant) == ["index", "name", "outcome", "skip_reason", "error_type"]
        for mutant in data["mutants"]
    )


def test_schema_version_is_one():
    assert REPORT_SCHEMA_VERSION == 1
    assert report_to_dict(empty_report())["schema_version"] == 1


@pytest.mark.parametrize(
    "build",
    [mixed_report, empty_report, all_error_report, all_skipped_report, all_killed_report, all_survived_report],
)
def test_dict_contains_only_plain_json_types_and_round_trips(build):
    data = report_to_dict(build())

    assert plain_types(data)
    encoded = json.dumps(data)
    assert json.loads(encoded) == data
    assert list(json.loads(encoded)["summary"]) == list(data["summary"])


def test_full_float_precision_is_kept_in_the_dict():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)
    expected = Operator(circuit)

    def oracle(candidate: QuantumCircuit) -> None:
        assert Operator(candidate).equiv(expected)

    two_thirds = report_to_dict(run_removal_mutants(circuit, oracle, allow_barrier=True))["summary"]
    one_third = report_to_dict(mixed_report())["summary"]

    assert two_thirds["score"] == 2 / 3
    assert one_third["error_rate"] == 1 / 3
    assert json.loads(json.dumps(two_thirds))["score"] == 2 / 3
    assert json.loads(json.dumps(one_third))["error_rate"] == 1 / 3


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (empty_report, (0, 0, 0, 0, 0, 0, 0, None, None)),
        (all_error_report, (2, 0, 0, 2, 0, 2, 0, None, 1.0)),
        (all_skipped_report, (3, 0, 0, 0, 3, 0, 0, None, None)),
        (all_killed_report, (2, 2, 0, 0, 0, 2, 2, 1.0, 0.0)),
        (all_survived_report, (2, 0, 2, 0, 0, 2, 2, 0.0, 0.0)),
    ],
    ids=["empty", "all-error", "all-skipped", "all-killed", "all-survived"],
)
def test_edge_case_summaries(build, expected):
    assert tuple(report_to_dict(build())["summary"].values()) == expected


def test_mixed_text_report_is_exact():
    assert format_text_report(mixed_report()) == "\n".join(
        [
            "qmutate removal mutants: 4 candidates",
            "killed 1 | survived 1 | error 1 | not run 1",
            "mutation score: 50.00% (1 of 2 killed; error and not_run excluded)",
            "error rate: 33.33% (1 of 3 executed)",
            "",
            "index  instruction  outcome   detail",
            "0      h            killed",
            "1      barrier      not_run   barrier_not_allowed",
            "2      cx           error     ValueError",
            "3      x            survived",
            "",
            "Surviving mutants may be equivalent to the original; qmutate does not detect equivalence.",
        ]
    )


def test_empty_text_report_shows_undefined_rates():
    assert format_text_report(empty_report()) == "\n".join(
        [
            "qmutate removal mutants: 0 candidates",
            "killed 0 | survived 0 | error 0 | not run 0",
            "mutation score: undefined (no killed or survived mutants; error and not_run excluded)",
            "error rate: undefined (no mutants executed)",
            "",
            "No top-level instructions.",
        ]
    )


def test_all_error_text_report():
    assert format_text_report(all_error_report()) == "\n".join(
        [
            "qmutate removal mutants: 2 candidates",
            "killed 0 | survived 0 | error 2 | not run 0",
            "mutation score: undefined (no killed or survived mutants; error and not_run excluded)",
            "error rate: 100.00% (2 of 2 executed)",
            "",
            "index  instruction  outcome  detail",
            "0      h            error    RuntimeError",
            "1      x            error    RuntimeError",
        ]
    )


def test_all_skipped_text_report():
    assert format_text_report(all_skipped_report()) == "\n".join(
        [
            "qmutate removal mutants: 3 candidates",
            "killed 0 | survived 0 | error 0 | not run 3",
            "mutation score: undefined (no killed or survived mutants; error and not_run excluded)",
            "error rate: undefined (no mutants executed)",
            "",
            "index  instruction  outcome  detail",
            "0      barrier      not_run  barrier_not_allowed",
            "1      measure      not_run  measurement_not_allowed",
            "2      measure      not_run  measurement_not_allowed",
        ]
    )


def test_all_killed_and_all_survived_text_scores():
    killed = format_text_report(all_killed_report()).splitlines()
    survived = format_text_report(all_survived_report()).splitlines()

    assert killed[2] == "mutation score: 100.00% (2 of 2 killed; error and not_run excluded)"
    assert killed[-1] == "1      cx           killed"
    assert survived[2] == "mutation score: 0.00% (0 of 2 killed; error and not_run excluded)"
    assert survived[-1].startswith("Surviving mutants may be equivalent")


def test_single_candidate_uses_singular_wording():
    circuit = QuantumCircuit(1)
    circuit.x(0)

    text = format_text_report(run_removal_mutants(circuit, lambda candidate: None))

    assert text.splitlines()[0] == "qmutate removal mutants: 1 candidate"


def test_text_rounds_only_for_display():
    report = mixed_report()

    text = format_text_report(report)

    assert "33.33%" in text
    assert report_to_dict(report)["summary"]["error_rate"] == 1 / 3


def test_unicode_and_long_names_and_two_digit_indices_are_aligned():
    circuit = QuantumCircuit(1)
    for _ in range(10):
        circuit.x(0)
    circuit.append(Instruction("θ-rotation-量子", 1, 0, []), [0])
    circuit.append(Instruction("a_very_long_custom_instruction_name", 1, 0, []), [0])

    lines = format_text_report(run_removal_mutants(circuit, lambda candidate: None)).splitlines()
    table = lines[5:17]

    assert table[0] == "index  instruction                          outcome   detail"
    assert table[1] == "0      x                                    survived"
    assert table[11] == "10     θ-rotation-量子                        survived"
    assert len("θ-rotation-量子") == 13
    assert lines[17] == "11     a_very_long_custom_instruction_name  survived"
    assert all(line == line.rstrip() for line in lines)
    assert report_to_dict(run_removal_mutants(circuit, lambda candidate: None))["mutants"][10]["name"] == (
        "θ-rotation-量子"
    )


def test_text_is_built_from_the_dict():
    report = mixed_report()
    data = report_to_dict(report)
    text = format_text_report(report)

    for mutant in data["mutants"]:
        detail = mutant["skip_reason"] or mutant["error_type"] or ""
        assert any(
            line.split()[:3] == [str(mutant["index"]), mutant["name"], mutant["outcome"]]
            and line.endswith(detail)
            for line in text.splitlines()
        )


def seeded_report():
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    backend = BasicSimulator()

    def oracle(candidate: QuantumCircuit) -> None:
        counts = backend.run(candidate, shots=200, seed_simulator=11).result().get_counts()
        assert set(counts) == {"00", "11"}

    return run_removal_mutants(circuit, oracle)


def test_reports_are_deterministic_for_identical_runs():
    first = seeded_report()
    second = seeded_report()

    assert report_to_dict(first) == report_to_dict(second)
    assert format_text_report(first) == format_text_report(second)
    assert report_to_dict(first) == report_to_dict(first)


@pytest.mark.parametrize("function", [report_to_dict, format_text_report])
@pytest.mark.parametrize("value", [None, {"schema_version": 1}, "report"])
def test_non_report_input_raises_type_error(function, value):
    with pytest.raises(TypeError, match="report must be a RunReport"):
        function(value)
