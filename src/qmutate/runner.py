"""Running a test oracle against removal mutants of a Qiskit circuit."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from qiskit.circuit import QuantumCircuit

from qmutate.generator import CandidateStatus, RemovalCandidate, generate_removal_mutants
from qmutate.metrics import MutationMetrics, mutation_score
from qmutate.mutation import _isolated_copy

Oracle = Callable[[QuantumCircuit], object]


class MutantOutcome(StrEnum):
    """Result of running the oracle against one removal candidate."""

    KILLED = "killed"
    SURVIVED = "survived"
    ERROR = "error"
    NOT_RUN = "not_run"


class BaselineFailedError(RuntimeError):
    """Raised when the oracle does not pass on the original circuit.

    The exception raised by the oracle is kept as ``__cause__``. No mutant
    is run once the baseline has failed.
    """


@dataclass(frozen=True)
class MutantResult:
    """Outcome of one removal candidate.

    Attributes:
        candidate: The candidate produced by ``generate_removal_mutants``.
        outcome: ``KILLED`` if the oracle raised ``AssertionError``,
            ``SURVIVED`` if it returned normally, ``ERROR`` if it raised any
            other ``Exception``, and ``NOT_RUN`` if the candidate was
            skipped and the oracle was not called.
        error_type: The class name of the exception for ``ERROR``, and
            ``None`` for every other outcome.

    Contract, checked on construction:
        * ``candidate`` is a ``RemovalCandidate``, ``outcome`` is a
          ``MutantOutcome`` and ``error_type`` is a ``str`` or ``None``.
        * ``outcome`` is ``NOT_RUN`` exactly when the candidate is skipped.
        * ``error_type`` is a non-empty string exactly when ``outcome`` is
          ``ERROR``.

        Wrong types raise ``TypeError`` and inconsistent combinations raise
        ``ValueError``.
    """

    candidate: RemovalCandidate
    outcome: MutantOutcome
    error_type: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, RemovalCandidate):
            raise TypeError(
                f"candidate must be a RemovalCandidate, got {type(self.candidate).__name__}"
            )
        if type(self.outcome) is not MutantOutcome:
            raise TypeError(f"outcome must be a MutantOutcome, got {type(self.outcome).__name__}")
        if self.error_type is not None and not isinstance(self.error_type, str):
            raise TypeError(
                f"error_type must be a str or None, got {type(self.error_type).__name__}"
            )
        skipped = self.candidate.status is CandidateStatus.SKIPPED
        if skipped != (self.outcome is MutantOutcome.NOT_RUN):
            raise ValueError("outcome must be NOT_RUN exactly when the candidate was skipped")
        if self.outcome is MutantOutcome.ERROR:
            if not self.error_type:
                raise ValueError("an ERROR result needs a non-empty error_type")
        elif self.error_type is not None:
            raise ValueError("error_type is only allowed for ERROR results")


@dataclass(frozen=True)
class RunReport:
    """Results of running an oracle against every removal candidate.

    Attributes:
        results: One ``MutantResult`` per top-level instruction of the
            original circuit, in index order.
        killed: Number of ``KILLED`` results.
        survived: Number of ``SURVIVED`` results.
        errors: Number of ``ERROR`` results. A failing baseline is never
            counted here; it raises ``BaselineFailedError`` instead.
        not_run: Number of ``NOT_RUN`` results.

    Contract, checked on construction:
        * ``results`` is a ``tuple`` of ``MutantResult`` whose candidate
          indices are ``0, 1, ..., len(results) - 1`` in order.
        * Each count is a non-negative ``int`` (not ``bool``) equal to the
          number of results with the matching outcome.

        Wrong types raise ``TypeError`` and inconsistent values raise
        ``ValueError``.
    """

    results: tuple[MutantResult, ...]
    killed: int
    survived: int
    errors: int
    not_run: int

    def __post_init__(self) -> None:
        if not isinstance(self.results, tuple):
            raise TypeError(f"results must be a tuple, got {type(self.results).__name__}")
        for position, result in enumerate(self.results):
            if not isinstance(result, MutantResult):
                raise TypeError(
                    f"results must contain MutantResult objects, got {type(result).__name__}"
                )
            if result.candidate.index != position:
                raise ValueError(
                    f"results must be in index order; position {position} has index "
                    f"{result.candidate.index}"
                )
        expected = {
            "killed": MutantOutcome.KILLED,
            "survived": MutantOutcome.SURVIVED,
            "errors": MutantOutcome.ERROR,
            "not_run": MutantOutcome.NOT_RUN,
        }
        for name, outcome in expected.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, got {type(value).__name__}")
            actual = sum(1 for result in self.results if result.outcome is outcome)
            if value != actual:
                raise ValueError(f"{name} is {value} but results contain {actual}")

    def score(self) -> float:
        """Return ``mutation_score(killed, killed + survived)``.

        ``ERROR`` and ``NOT_RUN`` results are excluded from the denominator.
        Like ``mutation_score``, this raises ``ZeroDivisionError`` when no
        mutant was killed or survived.
        """
        return mutation_score(self.killed, self.killed + self.survived)

    def metrics(self) -> MutationMetrics:
        """Return the summary metrics for this report's four outcome counts.

        ``metrics().score`` equals ``score()`` whenever the score is defined,
        and is ``None`` where ``score()`` would raise ``ZeroDivisionError``.
        """
        return MutationMetrics(self.killed, self.survived, self.errors, self.not_run)


def run_removal_mutants(
    circuit: QuantumCircuit,
    oracle: Oracle,
    *,
    allow_measure: bool = False,
    allow_barrier: bool = False,
) -> RunReport:
    """Run ``oracle`` against ``circuit`` and each of its removal mutants.

    The run has three steps:

    1. ``generate_removal_mutants(circuit, allow_measure=allow_measure,
       allow_barrier=allow_barrier)`` builds the candidates. Its errors,
       including the rejection of routed and scheduled circuits, are raised
       before the oracle is called.
    2. The oracle is called once on a copy of the original circuit. If it
       raises ``AssertionError`` or any other ``Exception``, the run stops
       with ``BaselineFailedError`` before any mutant is run, and the
       oracle's exception is kept as ``__cause__``.
    3. The oracle is called exactly once for each generated candidate, in
       index order. Skipped candidates become ``NOT_RUN`` without calling
       the oracle.

    Oracle contract:
        The oracle receives a ``QuantumCircuit`` and signals failure by
        raising ``AssertionError``, which includes plain ``assert``
        statements and ``numpy.testing`` assertions; that outcome is
        ``KILLED``. Returning normally is ``SURVIVED``, whatever the return
        value. Any other ``Exception`` is ``ERROR``. ``BaseException``
        subclasses that are not ``Exception``, such as ``KeyboardInterrupt``,
        ``SystemExit`` and the exceptions raised by ``pytest.fail`` and
        ``pytest.skip``, are not caught and propagate immediately.

        The runner adds no randomness. Results are only as reproducible as
        the oracle: an oracle that samples should fix its seeds.

    Oracle input:
        The oracle never receives ``circuit`` itself or a candidate's
        ``mutant``. Each call gets a fresh copy made with the same isolation
        rules as ``remove_instruction``, so most in-place edits by the
        oracle reach neither the original circuit nor the mutants stored in
        the report. Those rules are not universal: state that
        ``remove_instruction`` documents as not guaranteed independent, such
        as ``PauliEvolutionGate.operator``, attributes of user-defined
        instruction subclasses and the contents of ``Gate`` definitions, can
        still be shared, so oracles should not modify their input.

        Only exceptions raised by the oracle call are classified. An error
        while copying a circuit for the oracle propagates unchanged.

    Args:
        circuit: Circuit under test.
        oracle: Callable that tests one circuit.
        allow_measure: Passed to ``generate_removal_mutants``.
        allow_barrier: Passed to ``generate_removal_mutants``.

    Returns:
        A ``RunReport`` with one result per top-level instruction.

    Raises:
        TypeError: If ``oracle`` is not callable or ``circuit`` is not a
            ``QuantumCircuit``.
        ValueError: If ``circuit`` is routed or scheduled.
        BaselineFailedError: If the oracle does not pass on the original
            circuit.
    """
    if not callable(oracle):
        raise TypeError(f"oracle must be callable, got {type(oracle).__name__}")
    candidates = generate_removal_mutants(
        circuit, allow_measure=allow_measure, allow_barrier=allow_barrier
    )

    try:
        oracle(_isolated_copy(circuit))
    except Exception as error:
        raise BaselineFailedError(
            f"oracle did not pass on the original circuit: {type(error).__name__}: {error}"
        ) from error

    results = tuple(_run_candidate(candidate, oracle) for candidate in candidates)
    return RunReport(
        results=results,
        killed=sum(1 for result in results if result.outcome is MutantOutcome.KILLED),
        survived=sum(1 for result in results if result.outcome is MutantOutcome.SURVIVED),
        errors=sum(1 for result in results if result.outcome is MutantOutcome.ERROR),
        not_run=sum(1 for result in results if result.outcome is MutantOutcome.NOT_RUN),
    )


def _run_candidate(candidate: RemovalCandidate, oracle: Oracle) -> MutantResult:
    """Run ``oracle`` once on a copy of ``candidate``'s mutant, if it has one."""
    if candidate.status is CandidateStatus.SKIPPED:
        return MutantResult(candidate, MutantOutcome.NOT_RUN, None)
    oracle_input = _isolated_copy(candidate.mutant)
    try:
        oracle(oracle_input)
    except AssertionError:
        return MutantResult(candidate, MutantOutcome.KILLED, None)
    except Exception as error:
        return MutantResult(candidate, MutantOutcome.ERROR, type(error).__name__)
    return MutantResult(candidate, MutantOutcome.SURVIVED, None)
