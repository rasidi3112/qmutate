"""Exact equivalence checks between a circuit and its removal mutants."""

import math
from dataclasses import dataclass
from enum import StrEnum

from qiskit.circuit import Barrier, ControlFlowOp, Delay, Gate, Measure, QuantumCircuit, Reset
from qiskit.exceptions import QiskitError
from qiskit.quantum_info import Operator, Statevector

from qmutate.metrics import AdjustedMetrics
from qmutate.mutation import _isolated_copy
from qmutate.runner import MutantOutcome, RunReport


class EquivalenceModel(StrEnum):
    """What two circuits must agree on to be called equivalent."""

    UNITARY = "unitary"
    IDEAL_DISTRIBUTION = "ideal_distribution"


class EquivalenceVerdict(StrEnum):
    """Outcome of an exact equivalence check."""

    EQUIVALENT = "equivalent"
    NOT_EQUIVALENT = "not_equivalent"
    UNKNOWN = "unknown"


class UnknownReason(StrEnum):
    """Stable reason why an equivalence check could not be decided."""

    UNBOUND_PARAMETERS = "unbound_parameters"
    TOO_MANY_QUBITS = "too_many_qubits"
    CLBITS_OUTSIDE_REGISTERS = "clbits_outside_registers"
    MEASUREMENT = "measurement"
    RESET = "reset"
    CONTROL_FLOW = "control_flow"
    NON_GATE_INSTRUCTION = "non_gate_instruction"
    MID_CIRCUIT_MEASUREMENT = "mid_circuit_measurement"
    NO_MEASUREMENTS = "no_measurements"
    UNSUPPORTED_OPERATION = "unsupported_operation"


_DEFAULT_MAX_QUBITS = {EquivalenceModel.UNITARY: 10, EquivalenceModel.IDEAL_DISTRIBUTION: 16}

_MODEL_SPECIFIC_REASONS = {
    UnknownReason.MEASUREMENT: EquivalenceModel.UNITARY,
    UnknownReason.CLBITS_OUTSIDE_REGISTERS: EquivalenceModel.IDEAL_DISTRIBUTION,
    UnknownReason.MID_CIRCUIT_MEASUREMENT: EquivalenceModel.IDEAL_DISTRIBUTION,
    UnknownReason.NO_MEASUREMENTS: EquivalenceModel.IDEAL_DISTRIBUTION,
}


@dataclass(frozen=True)
class EquivalenceResult:
    """Result of comparing an original circuit with a mutant under one model.

    Attributes:
        model: The model the circuits were compared under.
        verdict: ``EQUIVALENT``, ``NOT_EQUIVALENT`` or ``UNKNOWN``.
        reason: Why the check could not be decided; set exactly for
            ``UNKNOWN``.
        max_difference: For ``UNITARY``, the largest entry-wise difference
            after trace-aligned global phase; for ``IDEAL_DISTRIBUTION``, the
            largest difference in any single outcome probability. ``None``
            exactly for ``UNKNOWN``.
        total_variation: Total variation distance between the two outcome
            distributions; set exactly for ``IDEAL_DISTRIBUTION`` results
            that are not ``UNKNOWN``.

    Contract, checked on construction:
        * ``model``, ``verdict`` and ``reason`` are enum members, not plain
          strings, and model-specific reasons match ``model``.
        * Differences are non-negative finite numbers (``bool`` is rejected).
        * The presence of each field follows the rules above.

        Wrong types raise ``TypeError`` and inconsistent values raise
        ``ValueError``.
    """

    model: EquivalenceModel
    verdict: EquivalenceVerdict
    reason: UnknownReason | None
    max_difference: float | None
    total_variation: float | None

    def __post_init__(self) -> None:
        if type(self.model) is not EquivalenceModel:
            raise TypeError(f"model must be an EquivalenceModel, got {type(self.model).__name__}")
        if type(self.verdict) is not EquivalenceVerdict:
            raise TypeError(
                f"verdict must be an EquivalenceVerdict, got {type(self.verdict).__name__}"
            )
        if self.reason is not None and type(self.reason) is not UnknownReason:
            raise TypeError(
                f"reason must be an UnknownReason or None, got {type(self.reason).__name__}"
            )
        for name in ("max_difference", "total_variation"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a float or None, got {type(value).__name__}")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a non-negative finite number, got {value}")

        unknown = self.verdict is EquivalenceVerdict.UNKNOWN
        if unknown != (self.reason is not None):
            raise ValueError("reason must be set exactly for UNKNOWN results")
        if unknown:
            if self.max_difference is not None or self.total_variation is not None:
                raise ValueError("an UNKNOWN result has no max_difference or total_variation")
            required_model = _MODEL_SPECIFIC_REASONS.get(self.reason)
            if required_model is not None and required_model is not self.model:
                raise ValueError(f"reason {self.reason.value} does not apply to {self.model.value}")
            return
        if self.max_difference is None:
            raise ValueError("max_difference is required unless the verdict is UNKNOWN")
        distribution = self.model is EquivalenceModel.IDEAL_DISTRIBUTION
        if distribution != (self.total_variation is not None):
            raise ValueError("total_variation is set exactly for ideal_distribution results")


def check_equivalence(
    original: QuantumCircuit,
    mutant: QuantumCircuit,
    *,
    model: EquivalenceModel,
    atol: float = 1e-8,
    max_qubits: int | None = None,
) -> EquivalenceResult:
    """Compare ``original`` and ``mutant`` exactly under ``model``.

    Both circuits are copied with the isolation rules of
    ``remove_instruction`` before anything is computed, so neither circuit
    is modified and no lazily built definition is built on them.

    ``UNITARY`` model:
        Supports circuits made of ``Gate`` operations, barriers and delays.
        With ``U`` the original's matrix, ``V`` the mutant's, ``t =
        trace(V^dagger U)`` and the global phase ``e^{i phi} = t / |t|``
        (``1`` when ``t == 0``), ``max_difference`` is the largest
        ``|U_ij - e^{i phi} V_ij|``. The verdict is ``EQUIVALENT`` exactly
        when ``max_difference <= atol``. ``Operator.equiv`` is not used.

        This phase minimises the Frobenius norm of ``U - e^{i phi} V``, not
        the largest entry-wise difference. With ``m_star`` the smallest
        largest entry-wise difference over all global phases and ``n``
        qubits, the following bound is proven:
        ``m_star <= max_difference <= min(2, 2**n * m_star,
        (1 + 2 * 2**(n / 2)) * m_star)``. The factor ``2**n`` follows from
        the Frobenius norm over ``4**n`` entries; the factor
        ``1 + 2 * 2**(n / 2)`` follows from bounding how far the trace phase
        can move from the best phase. No tighter factor, such as
        ``2**(n / 2)``, is claimed. The test suite checks the proven bound on
        seeded random cases with up to 3 qubits; that is a check of the
        implementation, not a proof.

    ``IDEAL_DISTRIBUTION`` model:
        Compares the probability distribution of all classical bits after
        running the circuit from ``|0...0>``. Measurements must be terminal:
        after a qubit is measured, only further measurements, barriers and
        delays may act on it. A qubit measured into several classical bits
        writes the same value to each, a classical bit written more than
        once keeps the value of the last measurement, and a classical bit
        that is never written is ``0``. Every classical bit must belong to a
        register. ``max_difference`` is the largest difference in a single
        outcome probability and ``total_variation`` is half the sum of the
        absolute differences. The verdict is ``EQUIVALENT`` exactly when
        ``total_variation <= atol``.

    ``UNKNOWN`` results:
        The verdict is ``UNKNOWN`` with a stable ``UnknownReason`` when the
        original or the mutant is not supported. The original is checked
        completely before the mutant, so the original's reason is reported
        first. For each circuit, reasons are checked in this order: unbound
        parameters, more qubits than ``max_qubits``, classical bits outside
        registers (distribution model only), then the first unsupported
        instruction (measurement in the unitary model, reset, control flow,
        non-gate instruction, mid-circuit measurement), then no measurement
        at all (distribution model only). Only when none of these applies is
        the circuit prepared for comparison: in the unitary model its matrix
        is built; in the distribution model a gates-only copy is assembled
        (``copy_empty_like``, ``append`` and bit lookups) and its
        statevector is built. Any ``QiskitError``, including subclasses such
        as ``CircuitError``, raised during this preparation gives
        ``UNSUPPORTED_OPERATION``. That covers operations Qiskit cannot
        simulate, such as a gate with neither a matrix nor a definition, but
        also a ``QiskitError`` raised by the implementation of a custom gate,
        for example in its ``_define``. ``UNSUPPORTED_OPERATION`` therefore
        means that preparation failed with a ``QiskitError``, not that the
        operation is certainly unsupported. Exceptions of any other type,
        such as ``RuntimeError``, propagate unchanged.

    Numerical tolerance:
        ``atol`` is an absolute tolerance on ``max_difference`` (unitary) or
        ``total_variation`` (distribution). Floating-point rounding in
        equal circuits is typically around ``1e-16``. Verdicts are
        numerical, not symbolic proofs of equivalence.

    Args:
        original: The original circuit.
        mutant: The circuit to compare against it.
        model: ``EquivalenceModel.UNITARY`` or
            ``EquivalenceModel.IDEAL_DISTRIBUTION``.
        atol: Absolute tolerance for the verdict.
        max_qubits: Largest supported number of qubits; defaults to 10 for
            ``UNITARY`` and 16 for ``IDEAL_DISTRIBUTION``.

    Returns:
        An ``EquivalenceResult``.

    Raises:
        TypeError: If a circuit is not a ``QuantumCircuit``, ``model`` is not
            an ``EquivalenceModel``, or ``atol`` or ``max_qubits`` has the
            wrong type (``bool`` is rejected).
        ValueError: If ``atol`` is negative or not finite, ``max_qubits`` is
            less than 1, or the circuits have different numbers of qubits or
            classical bits.

        Exceptions that are not ``QiskitError``, raised while copying or
        preparing a circuit, propagate unchanged, for example a
        ``RuntimeError`` from a custom gate's ``_define``. A ``QiskitError``
        during preparation gives ``UNSUPPORTED_OPERATION`` instead, as
        described above.
    """
    for name, circuit in (("original", original), ("mutant", mutant)):
        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(f"{name} must be a QuantumCircuit, got {type(circuit).__name__}")
    cap = _validated_cap(model, atol, max_qubits)
    _require_same_shape(original, mutant)

    observables = []
    for circuit in (original, mutant):
        reason, observable = _prepared(_isolated_copy(circuit), model, cap)
        if reason is not None:
            return _unknown(model, reason)
        observables.append(observable)
    return _compare(model, observables[0], observables[1], atol)


@dataclass(frozen=True)
class ClassifiedReport:
    """Equivalence verdicts for every result of one run.

    Attributes:
        report: The run whose mutants were classified.
        model: The model every verdict uses.
        results: One entry per ``report.results`` entry, in the same order:
            ``None`` for ``NOT_RUN`` results and an ``EquivalenceResult``
            for every other result.

    Contract, checked on construction:
        ``report`` is a ``RunReport``, ``model`` an ``EquivalenceModel`` and
        ``results`` a tuple of the same length as ``report.results`` that
        follows the rules above, with every verdict using ``model``. Wrong
        types raise ``TypeError`` and inconsistent values raise
        ``ValueError``.

        Only ``classify_report`` checks that the verdicts belong to the
        report's mutants. A ``ClassifiedReport`` built directly is only
        checked for the structure above.
    """

    report: RunReport
    model: EquivalenceModel
    results: tuple[EquivalenceResult | None, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.report, RunReport):
            raise TypeError(f"report must be a RunReport, got {type(self.report).__name__}")
        if type(self.model) is not EquivalenceModel:
            raise TypeError(f"model must be an EquivalenceModel, got {type(self.model).__name__}")
        if not isinstance(self.results, tuple):
            raise TypeError(f"results must be a tuple, got {type(self.results).__name__}")
        if len(self.results) != len(self.report.results):
            raise ValueError(
                f"results has {len(self.results)} entries but the report has "
                f"{len(self.report.results)}"
            )
        for position, (run_result, classification) in enumerate(
            zip(self.report.results, self.results)
        ):
            if run_result.outcome is MutantOutcome.NOT_RUN:
                if classification is not None:
                    raise ValueError(f"result {position} was not run, so its entry must be None")
            elif classification is None:
                raise ValueError(f"result {position} was run, so it needs an EquivalenceResult")
            elif not isinstance(classification, EquivalenceResult):
                raise TypeError(
                    f"result {position} must be an EquivalenceResult, "
                    f"got {type(classification).__name__}"
                )
            elif classification.model is not self.model:
                raise ValueError(
                    f"result {position} uses {classification.model.value}, "
                    f"not {self.model.value}"
                )

    def metrics(self) -> AdjustedMetrics:
        """Return ``AdjustedMetrics`` for this report and these verdicts.

        A mutant counts as equivalent only when its verdict is
        ``EQUIVALENT``; ``NOT_EQUIVALENT`` and ``UNKNOWN`` change nothing.
        """
        equivalent = {MutantOutcome.KILLED: 0, MutantOutcome.SURVIVED: 0, MutantOutcome.ERROR: 0}
        for run_result, classification in zip(self.report.results, self.results):
            if (
                classification is not None
                and classification.verdict is EquivalenceVerdict.EQUIVALENT
            ):
                equivalent[run_result.outcome] += 1
        return AdjustedMetrics(
            killed=self.report.killed,
            survived=self.report.survived,
            errors=self.report.errors,
            not_run=self.report.not_run,
            equivalent_survived=equivalent[MutantOutcome.SURVIVED],
            equivalent_killed=equivalent[MutantOutcome.KILLED],
            equivalent_errors=equivalent[MutantOutcome.ERROR],
        )


def classify_report(
    circuit: QuantumCircuit,
    report: RunReport,
    *,
    model: EquivalenceModel,
    atol: float = 1e-8,
    max_qubits: int | None = None,
) -> ClassifiedReport:
    """Classify every mutant of ``report`` against the original ``circuit``.

    Before anything is computed, ``circuit`` is checked against the run on
    isolated copies: it must have one top-level instruction per report
    result, every instruction name must match its candidate, and then every
    generated mutant must equal ``circuit`` with exactly the candidate's
    instruction removed, compared instruction by instruction with Qiskit's
    instruction equality (operations, parameters, and the qubits and
    classical bits they act on). Every mutant must also have the same
    qubits and the same classical bits as ``circuit``, in the same order,
    compared with Qiskit's bit equality, because both the unitary matrix
    and the outcome keys depend on bit positions. Names are checked for all
    indices before any mutant is compared. A mismatch raises ``ValueError``
    naming the first mismatched index of the failing check. Operations whose
    lazily built definitions change between builds can fail this check.

    Other circuit attributes are not compared: global phase, name, metadata
    and layout may differ from the run's original circuit. None of them
    changes a verdict, because the unitary model aligns global phase, the
    distribution model is independent of it, and neither model uses the
    layout.

    The mutants classified are the ones stored in the report, so the
    verdicts describe exactly the mutants the oracle ran on. Each verdict
    follows ``check_equivalence``; when the original circuit itself is not
    supported, every generated mutant gets ``UNKNOWN`` with the original's
    reason. Neither ``circuit`` nor the report's mutants are modified.

    Raises:
        TypeError: If ``circuit`` is not a ``QuantumCircuit``, ``report`` is
            not a ``RunReport``, or ``model``, ``atol`` or ``max_qubits``
            has the wrong type.
        ValueError: If the options are invalid or ``circuit`` does not match
            the run.

        As in ``check_equivalence``, any ``QiskitError`` while preparing a
        circuit for comparison, including one raised by a custom gate's
        implementation, gives ``UNSUPPORTED_OPERATION``; exceptions of other
        types propagate unchanged.
    """
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError(f"circuit must be a QuantumCircuit, got {type(circuit).__name__}")
    if not isinstance(report, RunReport):
        raise TypeError(f"report must be a RunReport, got {type(report).__name__}")
    cap = _validated_cap(model, atol, max_qubits)

    source = _isolated_copy(circuit)
    if len(source.data) != len(report.results):
        raise ValueError(
            f"circuit has {len(source.data)} instructions but the report has "
            f"{len(report.results)} results"
        )
    for run_result in report.results:
        candidate = run_result.candidate
        name = source.data[candidate.index].operation.name
        if name != candidate.name:
            raise ValueError(
                f"instruction {candidate.index} is {name!r} in circuit but "
                f"{candidate.name!r} in the report"
            )
    mutant_copies = []
    for run_result in report.results:
        candidate = run_result.candidate
        index = candidate.index
        if candidate.mutant is None:
            mutant_copies.append(None)
            continue
        mutant_copy = _isolated_copy(candidate.mutant)
        expected = [
            instruction for position, instruction in enumerate(source.data) if position != index
        ]
        if list(mutant_copy.qubits) != list(source.qubits):
            raise ValueError(
                f"mutant {index} in the report does not have the same qubits in the same order "
                "as circuit"
            )
        if list(mutant_copy.clbits) != list(source.clbits):
            raise ValueError(
                f"mutant {index} in the report does not have the same classical bits in the same "
                "order as circuit"
            )
        if list(mutant_copy.data) != expected:
            raise ValueError(
                f"mutant {index} in the report is not circuit with instruction {index} removed"
            )
        mutant_copies.append(mutant_copy)

    original_reason, original_observable = _prepared(source, model, cap)
    results = []
    for mutant_copy in mutant_copies:
        if mutant_copy is None:
            results.append(None)
        elif original_reason is not None:
            results.append(_unknown(model, original_reason))
        else:
            reason, mutant_observable = _prepared(mutant_copy, model, cap)
            if reason is not None:
                results.append(_unknown(model, reason))
            else:
                results.append(_compare(model, original_observable, mutant_observable, atol))
    return ClassifiedReport(report, model, tuple(results))


def _validated_cap(model: EquivalenceModel, atol: float, max_qubits: int | None) -> int:
    """Validate the shared options and return the qubit cap."""
    if type(model) is not EquivalenceModel:
        raise TypeError(f"model must be an EquivalenceModel, got {type(model).__name__}")
    if isinstance(atol, bool) or not isinstance(atol, (int, float)):
        raise TypeError(f"atol must be a float, got {type(atol).__name__}")
    if not math.isfinite(atol) or atol < 0:
        raise ValueError(f"atol must be a non-negative finite number, got {atol}")
    if max_qubits is None:
        return _DEFAULT_MAX_QUBITS[model]
    if isinstance(max_qubits, bool) or not isinstance(max_qubits, int):
        raise TypeError(f"max_qubits must be an int or None, got {type(max_qubits).__name__}")
    if max_qubits < 1:
        raise ValueError(f"max_qubits must be at least 1, got {max_qubits}")
    return max_qubits


def _require_same_shape(original: QuantumCircuit, mutant: QuantumCircuit) -> None:
    """Raise ``ValueError`` unless both circuits have the same bit counts."""
    if original.num_qubits != mutant.num_qubits:
        raise ValueError(
            f"circuits have {original.num_qubits} and {mutant.num_qubits} qubits"
        )
    if original.num_clbits != mutant.num_clbits:
        raise ValueError(
            f"circuits have {original.num_clbits} and {mutant.num_clbits} classical bits"
        )


def _unknown(model: EquivalenceModel, reason: UnknownReason) -> EquivalenceResult:
    return EquivalenceResult(model, EquivalenceVerdict.UNKNOWN, reason, None, None)


def _unsupported(
    circuit: QuantumCircuit, model: EquivalenceModel, cap: int
) -> UnknownReason | None:
    """Return why ``circuit`` cannot be checked under ``model``, or ``None``."""
    if circuit.parameters:
        return UnknownReason.UNBOUND_PARAMETERS
    if circuit.num_qubits > cap:
        return UnknownReason.TOO_MANY_QUBITS
    distribution = model is EquivalenceModel.IDEAL_DISTRIBUTION
    if distribution:
        in_registers = {bit for register in circuit.cregs for bit in register}
        if any(bit not in in_registers for bit in circuit.clbits):
            return UnknownReason.CLBITS_OUTSIDE_REGISTERS
    measured = set()
    for instruction in circuit.data:
        operation = instruction.operation
        if isinstance(operation, (Barrier, Delay)):
            continue
        if isinstance(operation, Measure):
            if not distribution:
                return UnknownReason.MEASUREMENT
            measured.update(instruction.qubits)
            continue
        if isinstance(operation, Reset):
            return UnknownReason.RESET
        if isinstance(operation, ControlFlowOp):
            return UnknownReason.CONTROL_FLOW
        if not isinstance(operation, Gate):
            return UnknownReason.NON_GATE_INSTRUCTION
        if measured.intersection(instruction.qubits):
            return UnknownReason.MID_CIRCUIT_MEASUREMENT
    if distribution and not measured:
        return UnknownReason.NO_MEASUREMENTS
    return None


def _prepared(circuit: QuantumCircuit, model: EquivalenceModel, cap: int):
    """Return ``(reason, None)`` if ``circuit`` is unsupported, else ``(None, observable)``.

    The checks of ``_unsupported`` run first. Only then is the circuit
    prepared by ``_observable``, which in the distribution model also covers
    assembling the gates-only copy. Any ``QiskitError`` raised during
    preparation, whether from an operation Qiskit cannot simulate or from a
    custom gate's own code, gives ``UNSUPPORTED_OPERATION``. Any other
    exception propagates.
    """
    reason = _unsupported(circuit, model, cap)
    if reason is not None:
        return reason, None
    try:
        return None, _observable(circuit, model)
    except QiskitError:
        return UnknownReason.UNSUPPORTED_OPERATION, None


def _observable(circuit: QuantumCircuit, model: EquivalenceModel):
    """Return the matrix or the outcome distribution compared under ``model``."""
    if model is EquivalenceModel.UNITARY:
        return Operator(circuit).data
    return _ideal_distribution(circuit)


def _ideal_distribution(circuit: QuantumCircuit) -> dict[str, float]:
    """Return the exact distribution of all classical bits of a supported circuit.

    Keys are bit strings with classical bit 0 rightmost, using each bit's
    index in ``circuit.clbits`` and no register separators.
    """
    writer = {}
    gates = circuit.copy_empty_like(vars_mode="alike")
    for instruction in circuit.data:
        operation = instruction.operation
        if isinstance(operation, Measure):
            clbit = circuit.find_bit(instruction.clbits[0]).index
            writer[clbit] = circuit.find_bit(instruction.qubits[0]).index
        elif isinstance(operation, Gate):
            gates.append(instruction)
    width = circuit.num_clbits
    distribution: dict[str, float] = {}
    for state, probability in enumerate(Statevector(gates).probabilities()):
        if probability == 0:
            continue
        bits = ["0"] * width
        for clbit, qubit in writer.items():
            bits[width - 1 - clbit] = "1" if (state >> qubit) & 1 else "0"
        key = "".join(bits)
        distribution[key] = distribution.get(key, 0.0) + float(probability)
    return distribution


def _compare(
    model: EquivalenceModel, original_observable, mutant_observable, atol: float
) -> EquivalenceResult:
    """Build the result of comparing two supported observables."""
    if model is EquivalenceModel.UNITARY:
        difference = _unitary_difference(original_observable, mutant_observable)
        verdict = (
            EquivalenceVerdict.EQUIVALENT if difference <= atol else EquivalenceVerdict.NOT_EQUIVALENT
        )
        return EquivalenceResult(model, verdict, None, difference, None)
    keys = sorted(set(original_observable) | set(mutant_observable))
    differences = [
        abs(original_observable.get(key, 0.0) - mutant_observable.get(key, 0.0)) for key in keys
    ]
    max_difference = max(differences, default=0.0)
    total_variation = 0.5 * sum(differences)
    verdict = (
        EquivalenceVerdict.EQUIVALENT
        if total_variation <= atol
        else EquivalenceVerdict.NOT_EQUIVALENT
    )
    return EquivalenceResult(model, verdict, None, max_difference, total_variation)


def _unitary_difference(u, v) -> float:
    """Largest entry-wise ``|u - e^{i phi} v|`` with ``e^{i phi}`` from ``trace(v^dagger u)``."""
    overlap = complex((v.conj().T @ u).trace())
    phase = overlap / abs(overlap) if abs(overlap) > 0 else 1.0
    return float(abs(u - phase * v).max())
