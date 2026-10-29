import itertools

import pytest

from qmutate import AdjustedMetrics, MutationMetrics, mutation_score

FIELDS = (
    "killed",
    "survived",
    "errors",
    "not_run",
    "equivalent_survived",
    "equivalent_killed",
    "equivalent_errors",
)


def counts(**overrides) -> dict[str, int]:
    values = dict.fromkeys(FIELDS, 0)
    values.update(overrides)
    return values


def test_worked_example():
    metrics = AdjustedMetrics(
        killed=6,
        survived=4,
        errors=1,
        not_run=2,
        equivalent_survived=2,
        equivalent_killed=0,
        equivalent_errors=0,
    )

    assert metrics.base == MutationMetrics(6, 4, 1, 2)
    assert metrics.base.score == 0.6
    assert metrics.adjusted_eligible == 8
    assert metrics.adjusted_score == 0.75


def test_only_equivalent_survivors_leave_the_denominator():
    metrics = AdjustedMetrics(**counts(killed=3, survived=2, errors=2, equivalent_survived=1, equivalent_killed=2, equivalent_errors=2))

    assert metrics.adjusted_eligible == 3 + 2 - 1
    assert metrics.adjusted_score == mutation_score(3, 4)
    assert metrics.base.score == mutation_score(3, 5)


def test_equivalent_killed_mutants_stay_in_both_scores():
    with_equivalent_kills = AdjustedMetrics(**counts(killed=4, survived=1, equivalent_killed=3))
    without = AdjustedMetrics(**counts(killed=4, survived=1))

    assert with_equivalent_kills.adjusted_score == without.adjusted_score == 0.8
    assert with_equivalent_kills.base.score == 0.8


def test_adjusted_score_is_none_when_nothing_eligible_remains():
    only_equivalent_survivors = AdjustedMetrics(**counts(survived=2, equivalent_survived=2))
    empty = AdjustedMetrics(**counts())

    assert only_equivalent_survivors.adjusted_eligible == 0
    assert only_equivalent_survivors.adjusted_score is None
    assert only_equivalent_survivors.base.score == 0.0
    assert empty.adjusted_score is None


def test_adjusted_score_is_never_below_base_score():
    for killed, survived, equivalent_survived in itertools.product(range(4), range(4), range(4)):
        if equivalent_survived > survived:
            continue
        metrics = AdjustedMetrics(
            **counts(killed=killed, survived=survived, equivalent_survived=equivalent_survived)
        )
        if metrics.base.score is not None and metrics.adjusted_score is not None:
            assert metrics.adjusted_score >= metrics.base.score


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [True, 1.0, "1", None])
def test_counts_reject_non_int_values(field, value):
    with pytest.raises(TypeError, match=field):
        AdjustedMetrics(**counts(**{field: value}))


@pytest.mark.parametrize("field", FIELDS)
def test_counts_reject_negative_values(field):
    with pytest.raises(ValueError, match=f"{field} must be non-negative"):
        AdjustedMetrics(**counts(**{field: -1}))


@pytest.mark.parametrize(
    ("part", "whole"),
    [
        ("equivalent_survived", "survived"),
        ("equivalent_killed", "killed"),
        ("equivalent_errors", "errors"),
    ],
)
def test_equivalent_count_cannot_exceed_its_outcome_count(part, whole):
    with pytest.raises(ValueError, match=f"{part} cannot exceed {whole}"):
        AdjustedMetrics(**counts(**{part: 2, whole: 1}))


def test_adjusted_metrics_are_immutable_and_hashable():
    metrics = AdjustedMetrics(**counts(killed=1, survived=1, equivalent_survived=1))

    with pytest.raises(AttributeError):
        metrics.killed = 2
    assert hash(metrics) == hash(AdjustedMetrics(**counts(killed=1, survived=1, equivalent_survived=1)))
