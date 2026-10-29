"""Metrics for mutation testing results."""

from dataclasses import dataclass


def mutation_score(killed: int, eligible: int) -> float:
    """Return the mutation score as a ratio in ``[0.0, 1.0]``.

    The score is ``killed / eligible`` where:

    * ``eligible`` is the number of valid, non-equivalent mutants whose test
      outcome was conclusive (killed or survived). Invalid mutants (those
      that cannot be built or executed), mutants known or judged to be
      equivalent to the original, and mutants with inconclusive outcomes
      must be excluded from this count by the caller.
    * ``killed`` is the number of eligible mutants detected by at least one
      failing test. Excluded mutants must never be counted as killed.

    The function receives only these two integers, so it cannot verify how
    mutants were classified. It rejects only counts that are impossible on
    their own, such as ``killed > eligible``.

    Limitations:
        The score is only as accurate as the classification of mutants.
        Equivalence is undecidable in general and, for quantum circuits,
        often judged statistically, so undetected equivalent mutants deflate
        the score. Results from sampled executions depend on shot counts,
        seeds and noise. The score says nothing about which kinds of faults
        survive, and it is not comparable across different mutant sets.

    Args:
        killed: Number of eligible mutants killed by the test suite.
        eligible: Number of eligible non-equivalent mutants.

    Returns:
        ``killed / eligible`` as a float ratio, not a percentage.

    Raises:
        TypeError: If either count is not an ``int`` (``bool`` is rejected).
        ValueError: If a count is negative or ``killed > eligible``.
        ZeroDivisionError: If ``eligible`` is ``0``; the score is undefined
            when there are no eligible mutants.
    """
    for name, value in (("killed", killed), ("eligible", eligible)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value}")

    if killed > eligible:
        raise ValueError(f"killed ({killed}) cannot exceed eligible ({eligible})")
    if eligible == 0:
        raise ZeroDivisionError("mutation score is undefined when there are no eligible mutants")

    return killed / eligible


@dataclass(frozen=True)
class MutationMetrics:
    """Summary metrics derived from the four mutant outcome counts.

    Only the four counts are stored; every other value is derived from them,
    so the summary cannot be internally inconsistent.

    Attributes:
        killed: Mutants whose oracle raised ``AssertionError``.
        survived: Mutants whose oracle returned normally.
        errors: Mutants whose oracle raised another exception.
        not_run: Candidates that were skipped, so the oracle was not called.

    Derived values:
        * ``total`` counts every candidate: all four counts.
        * ``executed`` counts mutants the oracle ran on: ``killed``,
          ``survived`` and ``errors``.
        * ``eligible`` is the mutation-score denominator: ``killed`` and
          ``survived`` only. Errors and not-run candidates are excluded.
        * ``score`` is ``mutation_score(killed, eligible)``, or ``None`` when
          ``eligible`` is zero. Unlike ``mutation_score`` it never raises.
        * ``error_rate`` is ``errors / executed``, or ``None`` when
          ``executed`` is zero.

        Both rates are ratios in ``[0.0, 1.0]``, not percentages, and keep
        full float precision.

    Raises:
        TypeError: If a count is not an ``int`` (``bool`` is rejected).
        ValueError: If a count is negative.
    """

    killed: int
    survived: int
    errors: int
    not_run: int

    def __post_init__(self) -> None:
        for name in ("killed", "survived", "errors", "not_run"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")

    @property
    def total(self) -> int:
        """Number of candidates, whatever their outcome."""
        return self.killed + self.survived + self.errors + self.not_run

    @property
    def executed(self) -> int:
        """Number of mutants the oracle was called on."""
        return self.killed + self.survived + self.errors

    @property
    def eligible(self) -> int:
        """Number of mutants in the mutation-score denominator."""
        return self.killed + self.survived

    @property
    def score(self) -> float | None:
        """``mutation_score(killed, eligible)``, or ``None`` when undefined."""
        if self.eligible == 0:
            return None
        return mutation_score(self.killed, self.eligible)

    @property
    def error_rate(self) -> float | None:
        """``errors / executed``, or ``None`` when no mutant was executed."""
        if self.executed == 0:
            return None
        return self.errors / self.executed


@dataclass(frozen=True)
class AdjustedMetrics:
    """Outcome counts combined with exact equivalence verdicts.

    Attributes:
        killed: Mutants whose oracle raised ``AssertionError``.
        survived: Mutants whose oracle returned normally.
        errors: Mutants whose oracle raised another exception.
        not_run: Candidates that were skipped.
        equivalent_survived: Survived mutants classified as equivalent.
        equivalent_killed: Killed mutants classified as equivalent.
        equivalent_errors: Error mutants classified as equivalent.

    Derived values:
        * ``base`` is the ``MutationMetrics`` of the four outcome counts, so
          ``base.score`` is the unadjusted mutation score.
        * ``adjusted_eligible`` is ``killed + survived - equivalent_survived``.
          Only equivalent survivors leave the denominator.
        * ``adjusted_score`` is ``mutation_score(killed, adjusted_eligible)``,
          or ``None`` when ``adjusted_eligible`` is zero.

        Equivalent mutants that were killed stay in both the numerator and
        the denominator of the base and adjusted scores; they are reported in
        ``equivalent_killed`` because killing an equivalent mutant means the
        oracle observed something outside the equivalence model. Equivalent
        errors are informational, since errors are never part of a score.
        The adjusted score is therefore never lower than the base score when
        both are defined.

    Raises:
        TypeError: If a count is not an ``int`` (``bool`` is rejected).
        ValueError: If a count is negative or an equivalent count exceeds the
            matching outcome count.
    """

    killed: int
    survived: int
    errors: int
    not_run: int
    equivalent_survived: int
    equivalent_killed: int
    equivalent_errors: int

    def __post_init__(self) -> None:
        names = (
            "killed",
            "survived",
            "errors",
            "not_run",
            "equivalent_survived",
            "equivalent_killed",
            "equivalent_errors",
        )
        for name in names:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"{name} must be non-negative, got {value}")
        for part, whole in (
            ("equivalent_survived", "survived"),
            ("equivalent_killed", "killed"),
            ("equivalent_errors", "errors"),
        ):
            if getattr(self, part) > getattr(self, whole):
                raise ValueError(f"{part} cannot exceed {whole}")

    @property
    def base(self) -> MutationMetrics:
        """Unadjusted metrics of the four outcome counts."""
        return MutationMetrics(self.killed, self.survived, self.errors, self.not_run)

    @property
    def adjusted_eligible(self) -> int:
        """``killed + survived - equivalent_survived``."""
        return self.killed + self.survived - self.equivalent_survived

    @property
    def adjusted_score(self) -> float | None:
        """``mutation_score(killed, adjusted_eligible)``, or ``None`` when undefined."""
        if self.adjusted_eligible == 0:
            return None
        return mutation_score(self.killed, self.adjusted_eligible)
