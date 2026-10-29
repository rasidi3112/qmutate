import pytest

from qmutate import mutation_score


def test_known_example():
    assert mutation_score(killed=3, eligible=4) == pytest.approx(0.75)


def test_all_eligible_mutants_killed():
    assert mutation_score(killed=12, eligible=12) == 1.0


def test_no_mutants_killed():
    assert mutation_score(killed=0, eligible=5) == 0.0


def test_returns_ratio_not_percentage():
    score = mutation_score(killed=1, eligible=2)

    assert isinstance(score, float)
    assert score == 0.5


def test_zero_eligible_mutants_is_undefined():
    with pytest.raises(ZeroDivisionError, match="no eligible mutants"):
        mutation_score(killed=0, eligible=0)


@pytest.mark.parametrize(("killed", "eligible"), [(-1, 5), (0, -1), (-2, -1)])
def test_negative_counts_rejected(killed, eligible):
    with pytest.raises(ValueError, match="non-negative"):
        mutation_score(killed=killed, eligible=eligible)


@pytest.mark.parametrize(("killed", "eligible"), [(6, 5), (1, 0)])
def test_killed_cannot_exceed_eligible(killed, eligible):
    with pytest.raises(ValueError, match="cannot exceed eligible"):
        mutation_score(killed=killed, eligible=eligible)


@pytest.mark.parametrize(
    ("killed", "eligible"),
    [(1.0, 2), (1, 2.0), ("1", 2), (True, 2), (1, None)],
)
def test_non_integer_counts_rejected(killed, eligible):
    with pytest.raises(TypeError, match="must be an int"):
        mutation_score(killed=killed, eligible=eligible)

