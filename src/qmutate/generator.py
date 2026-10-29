"""Index-ordered enumeration of mutants for Qiskit quantum circuits."""

from dataclasses import dataclass, field
from enum import StrEnum

from qiskit.circuit import QuantumCircuit

from qmutate.mutation import _reject_unsupported_circuit, _removal


class CandidateStatus(StrEnum):
    """Outcome of considering one top-level instruction for removal."""

    GENERATED = "generated"
    SKIPPED = "skipped"


class SkipReason(StrEnum):
    """Stable reason why a removal candidate was skipped."""

    MEASUREMENT_NOT_ALLOWED = "measurement_not_allowed"
    BARRIER_NOT_ALLOWED = "barrier_not_allowed"


_SKIP_REASONS = {
    "measurement": SkipReason.MEASUREMENT_NOT_ALLOWED,
    "barrier": SkipReason.BARRIER_NOT_ALLOWED,
}


@dataclass(frozen=True)
class RemovalCandidate:
    """One top-level instruction considered for removal.

    Attributes:
        index: Position of the instruction in the original ``circuit.data``.
        name: Name of the instruction's operation in the original circuit.
        status: Whether a mutant was generated or the candidate was skipped.
        mutant: The mutant circuit, or ``None`` when skipped.
        skip_reason: Why the candidate was skipped, or ``None`` when a
            mutant was generated.

    Contract, checked on construction:
        * ``index`` is a non-negative ``int`` (not ``bool``) and ``name`` is
          a ``str``.
        * ``status`` is a ``CandidateStatus`` and ``skip_reason`` is a
          ``SkipReason`` or ``None``; plain strings are rejected.
        * ``mutant`` is a ``QuantumCircuit`` or ``None``.
        * A ``GENERATED`` candidate has a mutant and no skip reason; a
          ``SKIPPED`` candidate has a skip reason and no mutant.

        Wrong types raise ``TypeError`` and inconsistent combinations raise
        ``ValueError``.

    Equality and hashing:
        Two candidates are equal when all five fields are equal. ``mutant``
        is compared with ``QuantumCircuit.__eq__``, a structural comparison
        that ignores the circuit name and metadata. It is not quantum
        semantic equivalence: mutants that implement the same unitary with
        different instructions are unequal.

        The hash covers every field except ``mutant``. Those fields are
        immutable, so a candidate's hash never changes and equal candidates
        always have equal hashes. Equality, however, follows the mutant's
        current contents. After a candidate's mutant is edited in place, that
        candidate is still found in a ``set`` or as a ``dict`` key, but a
        different candidate that used to be equal to it no longer matches.
        Deduplicating candidates with a ``set`` is therefore structural and
        reflects the mutants' contents at the time each comparison is made.
    """

    index: int
    name: str
    status: CandidateStatus
    mutant: QuantumCircuit | None = field(hash=False)
    skip_reason: SkipReason | None

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise TypeError(f"index must be an int, got {type(self.index).__name__}")
        if self.index < 0:
            raise ValueError(f"index must be non-negative, got {self.index}")
        if not isinstance(self.name, str):
            raise TypeError(f"name must be a str, got {type(self.name).__name__}")
        if type(self.status) is not CandidateStatus:
            raise TypeError(f"status must be a CandidateStatus, got {type(self.status).__name__}")
        if self.skip_reason is not None and type(self.skip_reason) is not SkipReason:
            raise TypeError(
                f"skip_reason must be a SkipReason or None, got {type(self.skip_reason).__name__}"
            )
        if self.mutant is not None and not isinstance(self.mutant, QuantumCircuit):
            raise TypeError(
                f"mutant must be a QuantumCircuit or None, got {type(self.mutant).__name__}"
            )
        if self.status is CandidateStatus.GENERATED:
            if self.mutant is None or self.skip_reason is not None:
                raise ValueError("a generated candidate needs a mutant and no skip_reason")
        elif self.mutant is not None or self.skip_reason is None:
            raise ValueError("a skipped candidate needs a skip_reason and no mutant")


def generate_removal_mutants(
    circuit: QuantumCircuit,
    *,
    allow_measure: bool = False,
    allow_barrier: bool = False,
) -> list[RemovalCandidate]:
    """Return one removal candidate per top-level instruction of ``circuit``.

    Candidates are always listed in the order of ``circuit.data``, so
    ``result[i].index == i``. Each candidate is produced by the same internal
    removal path as ``remove_instruction(circuit, index,
    allow_measure=allow_measure, allow_barrier=allow_barrier)``: one isolated
    copy of the circuit is made, the measurement and barrier policy is
    checked on that copy, and the mutant is built from that same copy. Each
    generated mutant removes exactly one top-level instruction and follows
    the isolation and copying rules documented there. The input circuit is
    never modified.

    Determinism:
        The order and the indices of the candidates are always
        deterministic. Statuses, skip reasons and mutants are deterministic,
        and a generated mutant equals what a separate ``remove_instruction``
        call returns for the same index, only when every operation's
        definition is deterministic. Definitions are built lazily on copies,
        so an operation whose definition changes between builds or depends
        on outside state can be classified differently by different calls,
        and a separate ``remove_instruction`` call may reject a removal that
        this function generated, or the reverse. Within one call, every
        candidate's status and mutant come from the same check, and policy
        rejections are never raised as errors.

    A candidate is skipped exactly when that check rejects it:

    * ``SkipReason.MEASUREMENT_NOT_ALLOWED`` when the operation is, or may
      contain, a measurement and ``allow_measure`` is false;
    * otherwise ``SkipReason.BARRIER_NOT_ALLOWED`` when the operation is or
      contains a barrier and ``allow_barrier`` is false.

    Only one reason is reported. An operation that contains both a
    measurement and a barrier reports ``MEASUREMENT_NOT_ALLOWED`` unless
    ``allow_measure`` is true, in which case it reports
    ``BARRIER_NOT_ALLOWED`` unless ``allow_barrier`` is true.

    Any other error raised while copying, checking or building a candidate
    propagates unchanged; it is never reported as a skip.

    The candidates say nothing about whether a mutant is equivalent to the
    original or would be killed by a test suite.

    Args:
        circuit: Circuit to enumerate.
        allow_measure: When false, operations that are or may contain a
            measurement are skipped.
        allow_barrier: When false, operations that are or contain a barrier
            are skipped.

    Returns:
        A list with one ``RemovalCandidate`` per top-level instruction. It is
        empty for a circuit without instructions. All mutants are built
        before the function returns.

    Raises:
        TypeError: If ``circuit`` is not a ``QuantumCircuit``.
        ValueError: If the whole circuit cannot be mutated because it is
            routed (its ``layout`` has a ``final_layout``) or scheduled
            (``op_start_times`` is set). This is raised before any candidate
            is considered, even for an empty circuit.
    """
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError(f"circuit must be a QuantumCircuit, got {type(circuit).__name__}")
    _reject_unsupported_circuit(circuit)

    candidates = []
    for index, instruction in enumerate(circuit.data):
        name = instruction.operation.name
        mutant, rejection = _removal(circuit, index, allow_measure, allow_barrier)
        if rejection is None:
            candidates.append(
                RemovalCandidate(index, name, CandidateStatus.GENERATED, mutant, None)
            )
        else:
            candidates.append(
                RemovalCandidate(
                    index, name, CandidateStatus.SKIPPED, None, _SKIP_REASONS[rejection]
                )
            )
    return candidates
