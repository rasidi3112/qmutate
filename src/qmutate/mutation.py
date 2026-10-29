"""Mutation operators for Qiskit quantum circuits."""

import copy
from numbers import Number

from qiskit.circuit import (
    Barrier,
    ControlFlowOp,
    Gate,
    Instruction,
    Measure,
    Operation,
    ParameterExpression,
    QuantumCircuit,
)


def remove_instruction(
    circuit: QuantumCircuit,
    index: int,
    *,
    allow_measure: bool = False,
    allow_barrier: bool = False,
) -> QuantumCircuit:
    """Return a copy of ``circuit`` with the instruction at ``index`` removed.

    ``index`` addresses the top-level instruction sequence ``circuit.data``.
    Instructions nested inside control-flow blocks are not addressable; a
    control-flow operation such as ``if_else`` counts as one instruction and
    is removed as a whole.

    The original circuit is never modified by this function, including when
    an exception is raised; the measurement and barrier checks run on a copy.
    Isolation is not universal, and editing some objects on the mutant can
    still change the original, as listed below. Statements about Qiskit
    behaviour were verified with Qiskit 2.0.3 and 2.6.1 only.

    Isolated (editing these on the mutant leaves ``circuit`` unchanged):
        * Every instruction object, at top level, inside control-flow blocks
          (recursively), and inside the ``definition`` of non-gate
          instructions (recursively), including its ``label``.
        * Control-flow blocks at those levels; they are rebuilt recursively.
        * Instruction ``params`` that are not numbers, strings or parameter
          expressions (for example NumPy arrays) at those levels; they are
          deep-copied.
        * Definitions of non-gate instructions; they are rebuilt
          recursively. A definition that is built lazily is built on the
          copy, never on the original instruction.
        * The definition circuit of a ``Gate``, as copied by Qiskit.
        * ``metadata`` and ``layout``, deep-copied with the circuit.

    Copied by a specific policy:
        * Name, global phase, quantum, ancilla and classical registers,
          loose bits, typed classical variables and stretches are kept.
          Registers, bits and variables are the same immutable objects as
          in ``circuit``. They are kept even when the removed instruction
          was their only user. Removing the ``store`` that initialises a
          declared variable leaves the variable declared but uninitialised.
        * Parameters compare equal to the original ``Parameter`` objects and
          can be bound with them, but they are not guaranteed to be the same
          Python objects. Parameters used only by the removed instruction
          disappear from ``mutant.parameters``.
        * ``layout`` is kept only for circuits without a ``final_layout``;
          routed and scheduled circuits are rejected (see below).

    Not guaranteed independent:
        * Contents of ``Gate`` definitions, which are not traversed. Mutable
          params of gates nested there are shared when Qiskit copies
          ``params`` shallowly (observed in 2.0.3, not in 2.6.1), and
          control-flow blocks placed in a gate definition by assigning
          ``definition`` directly share their instruction objects (observed
          in both versions).
        * Attributes other than ``params``, ``label``, ``definition`` and
          control-flow blocks, such as ``PauliEvolutionGate.operator`` or
          attributes of user-defined ``Instruction`` subclasses. Qiskit copies
          these shallowly (observed in both versions).
        * Operations that are not ``Instruction`` objects, such as
          ``Clifford`` or ``AnnotatedOperation``, rely on Qiskit's own deep
          copy.

    Parameters:
        Parameters of the mutant compare equal to the original ``Parameter``
        objects and can be bound with them, but they are not guaranteed to be
        the same Python objects. Parameters used only by the removed
        instruction disappear from ``mutant.parameters``.

    Measurements:
        Removing a measurement deletes both the readout and the collapse of
        the qubit. Later operations on that qubit can see a different
        quantum state, and the target classical bit keeps whatever value it
        held before: a value written by an earlier measurement, or the
        backend's initial value (``0`` on Qiskit's reference simulators,
        which other backends need not guarantee). Classical conditions that
        read the bit can therefore change. If a later measurement overwrites
        the same bit, the mutant may be equivalent to the original. Removal
        requires ``allow_measure=True``.

    Barriers:
        A barrier does not affect the ideal unitary or the ideal output
        distribution. It does constrain transpilation and scheduling, so
        removing it can change the compiled circuit (for example, letting
        neighbouring gates cancel), the circuit structure seen by tests, and
        results on noisy or timing-sensitive hardware. Removal requires
        ``allow_barrier=True``.

    Composite instructions:
        The ``allow_*`` flags also apply to measurements and barriers nested
        anywhere inside the removed operation. Control-flow blocks and the
        ``definition`` of non-gate instructions are inspected recursively.
        An opaque non-gate operation (no definition) that acts on classical
        bits is treated as a possible measurement. ``Gate`` definitions are
        not inspected: a gate has no classical bits and Qiskit's
        ``to_gate`` rejects barriers, but a barrier placed in a gate
        definition by assigning ``definition`` directly is not detected.

    Rejected circuits:
        Circuits whose ``layout`` has a ``final_layout`` are rejected,
        because removing an instruction (for example a routing swap, or part
        of a decomposed one) can make the recorded output permutation false.
        Scheduled circuits (``op_start_times`` is set) are rejected, because
        their start times and duration would describe instructions that no
        longer exist.

    Args:
        circuit: Circuit to mutate.
        index: Non-negative position in ``circuit.data``. Negative indices are
            rejected so every mutant is addressed explicitly.
        allow_measure: Permit removing an operation that is or may contain a
            measurement.
        allow_barrier: Permit removing an operation that is or contains a
            barrier.

    Returns:
        A new ``QuantumCircuit`` with one fewer top-level instruction.

    Raises:
        TypeError: If ``circuit`` is not a ``QuantumCircuit`` or ``index`` is
            not an ``int`` (``bool`` is rejected).
        IndexError: If ``index`` is negative or not smaller than
            ``len(circuit.data)``. Every index is invalid for an empty circuit.
        ValueError: If the circuit is routed or scheduled, or if the selected
            operation is or contains a measurement or barrier and the matching
            ``allow_*`` flag is not set.
    """
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError(f"circuit must be a QuantumCircuit, got {type(circuit).__name__}")
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError(f"index must be an int, got {type(index).__name__}")

    size = len(circuit.data)
    if not 0 <= index < size:
        raise IndexError(
            f"instruction index {index} is out of range for a circuit with {size} instructions"
        )

    _reject_unsupported_circuit(circuit)

    mutant, rejection = _removal(circuit, index, allow_measure, allow_barrier)
    name = circuit.data[index].operation.name
    if rejection == "measurement":
        raise ValueError(
            f"instruction {index} ({name}) is or may contain a measurement; "
            "pass allow_measure=True to remove it"
        )
    if rejection == "barrier":
        raise ValueError(
            f"instruction {index} ({name}) is or contains a barrier; "
            "pass allow_barrier=True to remove it"
        )
    return mutant


def _removal(
    circuit: QuantumCircuit, index: int, allow_measure: bool, allow_barrier: bool
) -> tuple[QuantumCircuit | None, str | None]:
    """Check and perform one removal on a single isolated copy of ``circuit``.

    This is the only place where the measurement and barrier policy is
    applied. The check and the construction of the mutant use the same copy,
    so they cannot disagree, even for instructions whose lazily built
    definition differs between builds.

    ``index`` must already be valid and the circuit must already have passed
    ``_reject_unsupported_circuit``.

    Returns:
        ``(mutant, None)`` when the removal is allowed, otherwise
        ``(None, "measurement")`` or ``(None, "barrier")``. The measurement
        rejection takes precedence when both apply.
    """
    isolated = _isolated_copy(circuit)
    contained = _contained_kinds(isolated.data[index].operation)
    if "measurement" in contained and not allow_measure:
        return None, "measurement"
    if "barrier" in contained and not allow_barrier:
        return None, "barrier"

    mutant = isolated.copy_empty_like(vars_mode="alike")
    for position, instruction in enumerate(isolated.data):
        if position != index:
            mutant.append(instruction)
    return mutant, None


def _reject_unsupported_circuit(circuit: QuantumCircuit) -> None:
    """Raise ``ValueError`` if ``circuit`` is routed or scheduled."""
    if circuit.layout is not None and circuit.layout.final_layout is not None:
        raise ValueError(
            "circuit has a final_layout from routing, which removing an instruction can invalidate"
        )
    if getattr(circuit, "op_start_times", None) is not None:
        raise ValueError(
            "circuit is scheduled; its op_start_times and duration would become stale"
        )


def _isolated_copy(circuit: QuantumCircuit) -> QuantumCircuit:
    """Return a deep copy of ``circuit`` that shares no mutable params or blocks.

    Some Qiskit versions copy instruction ``params`` only shallowly, so
    control-flow blocks are rebuilt recursively and other parameters that
    are not numbers, strings or parameter expressions are deep-copied.
    """
    source = copy.deepcopy(circuit)
    rebuilt = source.copy_empty_like(vars_mode="alike")
    for instruction in source.data:
        operation = instruction.operation
        if isinstance(operation, ControlFlowOp):
            operation = operation.replace_blocks(
                [_isolated_copy(block) for block in operation.blocks]
            )
        elif isinstance(operation, Instruction):
            operation = _isolated_instruction(operation)
        rebuilt.append(instruction.replace(operation=operation))
    return rebuilt


def _isolated_instruction(operation: Instruction) -> Instruction:
    """Return a copy of ``operation`` with mutable params and non-gate definitions isolated."""
    isolated = copy.copy(operation)
    if _has_mutable_params(operation):
        isolated.params = copy.deepcopy(operation.params)
    if not isinstance(operation, Gate):
        definition = isolated.definition
        if definition is not None:
            isolated.definition = _isolated_copy(definition)
    return isolated


def _has_mutable_params(operation: Instruction) -> bool:
    """Return whether ``operation`` has a parameter that may be mutable."""
    return any(
        not isinstance(param, (Number, str, ParameterExpression)) for param in operation.params
    )


def _contained_kinds(operation: Operation) -> set[str]:
    """Return which of ``"measurement"`` and ``"barrier"`` ``operation`` is or contains."""
    if isinstance(operation, Measure):
        return {"measurement"}
    if isinstance(operation, Barrier):
        return {"barrier"}
    if isinstance(operation, Gate):
        return set()
    if isinstance(operation, ControlFlowOp):
        bodies = list(operation.blocks)
    else:
        definition = getattr(operation, "definition", None)
        if definition is None:
            return {"measurement"} if operation.num_clbits else set()
        bodies = [definition]
    return {
        kind
        for body in bodies
        for instruction in body.data
        for kind in _contained_kinds(instruction.operation)
    }
