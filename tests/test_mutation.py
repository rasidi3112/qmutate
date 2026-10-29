import copy
import re

import numpy as np
import pytest
import qiskit
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import (
    AncillaRegister,
    Clbit,
    ClassicalRegister,
    Gate,
    Instruction,
    Parameter,
    QuantumRegister,
    Qubit,
)
from qiskit.circuit.classical import types
from qiskit.circuit.library import (
    HamiltonianGate,
    Initialize,
    Isometry,
    LinearFunction,
    PauliEvolutionGate,
    PermutationGate,
    UnitaryGate,
)
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.providers.fake_provider import GenericBackendV2
from qiskit.quantum_info import Operator, SparsePauliOp, random_unitary

from qmutate import remove_instruction


def op_names(circuit: QuantumCircuit) -> list[str]:
    return [instruction.operation.name for instruction in circuit.data]


def counts(circuit: QuantumCircuit, shots: int = 256) -> dict[str, int]:
    result = BasicSimulator().run(circuit, shots=shots, seed_simulator=7).result()
    return result.get_counts()


@pytest.fixture
def bell() -> QuantumCircuit:
    circuit = QuantumCircuit(2, name="bell")
    circuit.h(0)
    circuit.x(1)
    circuit.cx(0, 1)
    return circuit


def test_removes_selected_gate(bell):
    mutant = remove_instruction(bell, 1)

    expected = QuantumCircuit(2, name="bell")
    expected.h(0)
    expected.cx(0, 1)
    assert mutant == expected
    assert op_names(mutant) == ["h", "cx"]


def test_removal_changes_circuit_semantics(bell):
    mutant = remove_instruction(bell, 0)

    assert op_names(mutant) == ["x", "cx"]
    assert not Operator(mutant).equiv(Operator(bell))


def test_removed_gate_keeps_remaining_operands():
    circuit = QuantumCircuit(3)
    circuit.cx(2, 0)
    circuit.h(1)
    circuit.ccx(0, 1, 2)

    mutant = remove_instruction(circuit, 1)

    operands = [
        tuple(mutant.find_bit(qubit).index for qubit in instruction.qubits)
        for instruction in mutant.data
    ]
    assert operands == [(2, 0), (0, 1, 2)]


def test_original_circuit_is_unchanged(bell):
    bell.metadata = {"tags": ["original"]}
    snapshot = bell.copy()

    mutant = remove_instruction(bell, 2)
    mutant.metadata["tags"].append("mutant")
    mutant.z(0)

    assert bell == snapshot
    assert op_names(bell) == ["h", "x", "cx"]
    assert bell.metadata == {"tags": ["original"]}


def test_returns_new_circuit(bell):
    mutant = remove_instruction(bell, 0)

    assert mutant is not bell
    assert len(mutant.data) == len(bell.data) - 1


def test_is_deterministic(bell):
    assert remove_instruction(bell, 1) == remove_instruction(bell, 1)


@pytest.mark.parametrize("index", [-1, -3, 3, 100])
def test_out_of_range_index_raises_index_error(bell, index):
    snapshot = bell.copy()
    message = f"instruction index {index} is out of range for a circuit with 3 instructions"

    with pytest.raises(IndexError, match=re.escape(message)):
        remove_instruction(bell, index)

    assert bell == snapshot


@pytest.mark.parametrize("index", [1.0, "0", None, True, False])
def test_non_integer_index_raises_type_error(bell, index):
    snapshot = bell.copy()

    with pytest.raises(TypeError, match="index must be an int"):
        remove_instruction(bell, index)

    assert bell == snapshot


def test_non_circuit_raises_type_error():
    with pytest.raises(TypeError, match="circuit must be a QuantumCircuit"):
        remove_instruction([("h", 0)], 0)


@pytest.mark.parametrize(
    "circuit",
    [QuantumCircuit(), QuantumCircuit(2, 2)],
    ids=["no-bits", "with-bits"],
)
def test_empty_circuit_has_no_valid_index(circuit):
    with pytest.raises(IndexError, match="0 instructions"):
        remove_instruction(circuit, 0)

    assert len(circuit.data) == 0


def test_measurement_rejected_by_default():
    circuit = QuantumCircuit(1, 1)
    circuit.x(0)
    circuit.measure(0, 0)
    snapshot = circuit.copy()

    with pytest.raises(ValueError, match="allow_measure=True"):
        remove_instruction(circuit, 1)

    assert circuit == snapshot


def test_removed_only_measurement_leaves_simulator_initial_value():
    creg = ClassicalRegister(1, "out")
    circuit = QuantumCircuit(QuantumRegister(1, "q"), creg)
    circuit.x(0)
    circuit.measure(0, 0)

    mutant = remove_instruction(circuit, 1, allow_measure=True)

    assert op_names(mutant) == ["x"]
    assert mutant.cregs == [creg]
    assert counts(circuit) == {"1": 256}
    assert counts(mutant) == {"0": 256}


def test_removed_measurement_keeps_earlier_written_bit_value():
    circuit = QuantumCircuit(1, 1)
    circuit.x(0)
    circuit.measure(0, 0)
    circuit.x(0)
    circuit.measure(0, 0)

    mutant = remove_instruction(circuit, 3, allow_measure=True)

    assert counts(circuit) == {"0": 256}
    assert counts(mutant) == {"1": 256}


def test_removed_measurement_overwritten_later_gives_equivalent_counts():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    circuit.measure(0, 0)

    mutant = remove_instruction(circuit, 1, allow_measure=True)

    assert counts(mutant) == counts(circuit)
    assert set(counts(circuit)) == {"0", "1"}


def test_removed_mid_circuit_measurement_changes_later_quantum_state():
    circuit = QuantumCircuit(1, 2)
    circuit.h(0)
    circuit.measure(0, 0)
    circuit.h(0)
    circuit.measure(0, 1)

    mutant = remove_instruction(circuit, 1, allow_measure=True)

    assert set(counts(circuit)) == {"00", "01", "10", "11"}
    assert counts(mutant) == {"00": 256}


def test_barrier_rejected_by_default():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)
    snapshot = circuit.copy()

    with pytest.raises(ValueError, match="allow_barrier=True"):
        remove_instruction(circuit, 1)

    assert circuit == snapshot


def test_barrier_removal_is_ideally_equivalent():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.barrier()
    circuit.cx(0, 1)

    mutant = remove_instruction(circuit, 1, allow_barrier=True)

    assert op_names(mutant) == ["h", "cx"]
    assert Operator(mutant).equiv(Operator(circuit))


def test_barrier_removal_changes_compiled_circuit():
    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.barrier()
    circuit.h(0)
    circuit.measure(0, 0)

    mutant = remove_instruction(circuit, 1, allow_barrier=True)
    options = {"basis_gates": ["h", "measure"], "optimization_level": 3, "seed_transpiler": 1}
    compiled_original = transpile(circuit, **options)
    compiled_mutant = transpile(mutant, **options)

    assert compiled_original.count_ops().get("h") == 2
    assert "h" not in compiled_mutant.count_ops()
    assert counts(compiled_original) == counts(compiled_mutant) == {"0": 256}


def test_allow_flags_are_independent():
    circuit = QuantumCircuit(1, 1)
    circuit.barrier()
    circuit.measure(0, 0)

    with pytest.raises(ValueError, match="barrier"):
        remove_instruction(circuit, 0, allow_measure=True)
    with pytest.raises(ValueError, match="measurement"):
        remove_instruction(circuit, 1, allow_barrier=True)


def custom_instruction(*, measure: bool = False, barrier: bool = False) -> Instruction:
    body = QuantumCircuit(1, 1 if measure else 0, name="composite")
    body.h(0)
    if barrier:
        body.barrier()
    if measure:
        body.measure(0, 0)
    return body.to_instruction()


def test_custom_instruction_containing_measurement_requires_allow_measure():
    circuit = QuantumCircuit(1, 1)
    circuit.x(0)
    circuit.append(custom_instruction(measure=True), [0], [0])

    with pytest.raises(ValueError, match="allow_measure=True"):
        remove_instruction(circuit, 1)
    assert op_names(remove_instruction(circuit, 1, allow_measure=True)) == ["x"]


def test_custom_instruction_containing_barrier_requires_allow_barrier():
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.append(custom_instruction(barrier=True), [0])

    with pytest.raises(ValueError, match="allow_barrier=True"):
        remove_instruction(circuit, 1)
    assert op_names(remove_instruction(circuit, 1, allow_barrier=True)) == ["x"]


def test_control_flow_block_containing_measurement_requires_allow_measure():
    circuit = QuantumCircuit(1, 1)
    circuit.x(0)
    with circuit.if_test((circuit.clbits[0], 0)):
        circuit.measure(0, 0)

    with pytest.raises(ValueError, match="allow_measure=True"):
        remove_instruction(circuit, 1)
    assert op_names(remove_instruction(circuit, 1, allow_measure=True)) == ["x"]


def test_nested_barrier_inside_control_flow_requires_allow_barrier():
    circuit = QuantumCircuit(1, 1)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.append(custom_instruction(barrier=True), [0])

    with pytest.raises(ValueError, match="allow_barrier=True"):
        remove_instruction(circuit, 1)
    assert op_names(remove_instruction(circuit, 1, allow_barrier=True)) == ["measure"]


def test_opaque_instruction_on_classical_bits_treated_as_measurement():
    circuit = QuantumCircuit(1, 1)
    circuit.append(Instruction("opaque_readout", 1, 1, []), [0], [0])

    with pytest.raises(ValueError, match="may contain a measurement"):
        remove_instruction(circuit, 0)
    assert len(remove_instruction(circuit, 0, allow_measure=True).data) == 0


def test_composites_without_measurement_or_barrier_need_no_flags():
    body = QuantumCircuit(1, name="unitary_block")
    body.h(0)
    circuit = QuantumCircuit(1, 1)
    circuit.append(body.to_gate(), [0])
    circuit.append(custom_instruction(), [0])
    circuit.append(Initialize([0, 1]), [0])
    circuit.append(Instruction("opaque_quantum", 1, 0, []), [0])
    circuit.reset(0)

    for index in range(len(circuit.data)):
        assert len(remove_instruction(circuit, index).data) == 4


def test_guard_does_not_build_lazy_definition_on_original():
    defined_on = []

    class LazyBarrierBlock(Instruction):
        def __init__(self):
            super().__init__("lazy_barrier_block", 1, 0, [])

        def _define(self):
            defined_on.append(self)
            body = QuantumCircuit(1)
            body.barrier()
            self.definition = body

    circuit = QuantumCircuit(1)
    circuit.append(LazyBarrierBlock(), [0])
    circuit.h(0)
    original_operation = circuit.data[0].operation

    with pytest.raises(ValueError, match="allow_barrier=True"):
        remove_instruction(circuit, 0)
    remove_instruction(circuit, 0, allow_barrier=True)

    assert defined_on
    assert all(operation is not original_operation for operation in defined_on)


def test_guard_does_not_build_lazy_definition_nested_in_definition_control_flow():
    defined_on = []

    class LazyGate(Instruction):
        def __init__(self):
            super().__init__("lazy_inner", 1, 0, [])

        def _define(self):
            defined_on.append(self)
            body = QuantumCircuit(1)
            body.x(0)
            self.definition = body

    body = QuantumCircuit(1, 1)
    with body.if_test((body.clbits[0], 1)):
        body.append(LazyGate(), [0])
    wrapper = Instruction("wrapper", 1, 1, [])
    wrapper.definition = body
    circuit = QuantumCircuit(1, 1)
    circuit.append(wrapper, [0], [0])
    circuit.h(0)
    original_inner = circuit.data[0].operation.definition.data[0].operation.blocks[0].data[0].operation

    remove_instruction(circuit, 0, allow_measure=True)

    assert defined_on
    assert all(operation is not original_inner for operation in defined_on)


def test_preserves_circuit_attributes_and_registers():
    qreg = QuantumRegister(2, "q")
    anc = AncillaRegister(1, "anc")
    creg = ClassicalRegister(2, "c")
    loose_qubit = Qubit()
    loose_clbit = Clbit()
    circuit = QuantumCircuit(
        qreg,
        anc,
        creg,
        [loose_qubit, loose_clbit],
        name="annotated",
        global_phase=0.25,
        metadata={"source": "unit-test", "nested": {"run": 1}},
    )
    circuit.h(qreg[0])
    circuit.cx(qreg[0], anc[0])
    circuit.measure(qreg, creg)

    mutant = remove_instruction(circuit, 1)
    mutant.metadata["nested"]["run"] = 2

    assert mutant.name == "annotated"
    assert mutant.global_phase == pytest.approx(0.25)
    assert circuit.metadata == {"source": "unit-test", "nested": {"run": 1}}
    assert mutant.qregs == [qreg, anc]
    assert mutant.ancillas == list(anc)
    assert mutant.cregs == [creg]
    assert mutant.qubits == circuit.qubits
    assert mutant.clbits == circuit.clbits
    assert loose_qubit in mutant.qubits and loose_clbit in mutant.clbits
    assert op_names(mutant) == ["h", "measure", "measure"]


def test_preserves_bits_no_longer_used():
    circuit = QuantumCircuit(3, 1)
    circuit.x(2)

    mutant = remove_instruction(circuit, 0)

    assert mutant.num_qubits == 3
    assert mutant.num_clbits == 1
    assert len(mutant.data) == 0


def compiled_with_initial_layout() -> QuantumCircuit:
    source = QuantumCircuit(2)
    source.h(0)
    source.cx(0, 1)
    return transpile(
        source,
        basis_gates=["u", "cx"],
        coupling_map=[[0, 1], [1, 0]],
        initial_layout=[1, 0],
        seed_transpiler=11,
    )


def test_preserves_initial_layout():
    compiled = compiled_with_initial_layout()

    mutant = remove_instruction(compiled, 0)

    assert compiled.layout.final_layout is None
    assert mutant.layout == compiled.layout
    assert mutant.layout.initial_index_layout() == [1, 0]


def test_layout_edit_on_mutant_does_not_change_original():
    compiled = compiled_with_initial_layout()
    original_mapping = compiled.layout.initial_layout.get_physical_bits().copy()

    mutant = remove_instruction(compiled, 0)
    mutant.layout.initial_layout.swap(0, 1)

    assert mutant.layout.initial_layout.get_physical_bits() != original_mapping
    assert compiled.layout.initial_layout.get_physical_bits() == original_mapping


def test_routed_circuit_with_final_layout_is_rejected():
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
    assert "swap" in op_names(routed)
    snapshot = routed.copy()

    for index in (op_names(routed).index("swap"), op_names(routed).index("cx")):
        with pytest.raises(ValueError, match="final_layout"):
            remove_instruction(routed, index)

    assert routed == snapshot


def test_scheduled_circuit_is_rejected():
    backend = GenericBackendV2(num_qubits=1, basis_gates=["x", "sx", "rz", "measure", "delay"], seed=1)
    circuit = QuantumCircuit(1)
    circuit.x(0)
    circuit.x(0)
    circuit.x(0)
    scheduled = transpile(
        circuit, backend=backend, scheduling_method="asap", optimization_level=0, seed_transpiler=1
    )
    assert scheduled.op_start_times is not None
    snapshot = scheduled.copy()

    with pytest.raises(ValueError, match="scheduled"):
        remove_instruction(scheduled, 1)

    assert scheduled == snapshot


def test_preserves_typed_classical_variables():
    circuit = QuantumCircuit(1)
    flag = circuit.add_input("flag", types.Bool())
    circuit.h(0)

    mutant = remove_instruction(circuit, 0)

    assert list(mutant.iter_input_vars()) == [flag]


def test_parameter_table_tracks_removed_instruction():
    theta = Parameter("theta")
    phi = Parameter("phi")
    circuit = QuantumCircuit(1)
    circuit.rx(theta, 0)
    circuit.rz(phi, 0)
    circuit.ry(phi, 0)

    without_theta = remove_instruction(circuit, 0)
    without_one_phi = remove_instruction(circuit, 1)

    assert set(without_theta.parameters) == {phi}
    assert set(without_one_phi.parameters) == {theta, phi}
    assert set(circuit.parameters) == {theta, phi}


def test_mutant_binds_with_original_parameter_objects():
    theta = Parameter("theta")
    circuit = QuantumCircuit(1)
    circuit.rx(theta, 0)
    circuit.h(0)

    bound = remove_instruction(circuit, 1).assign_parameters({theta: 0.5})

    assert bound.parameters == set()
    assert float(bound.data[0].operation.params[0]) == pytest.approx(0.5)
    assert set(circuit.parameters) == {theta}


def test_control_flow_block_removed_as_single_instruction():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(1)
        circuit.z(1)
    circuit.y(0)

    mutant = remove_instruction(circuit, 2)

    assert op_names(circuit) == ["h", "measure", "if_else", "y"]
    assert op_names(mutant) == ["h", "measure", "y"]


def test_control_flow_block_preserved_when_other_instruction_removed():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(1)

    mutant = remove_instruction(circuit, 0)

    assert op_names(mutant) == ["measure", "if_else"]
    assert mutant.data[1].operation == circuit.data[2].operation


def test_control_flow_block_edit_on_mutant_does_not_change_original():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.x(1)

    mutant = remove_instruction(circuit, 0)
    mutant_block = mutant.data[1].operation.blocks[0]
    mutant_block.z(0)

    assert op_names(mutant.data[1].operation.blocks[0]) == ["x", "z"]
    assert op_names(circuit.data[2].operation.blocks[0]) == ["x"]


def test_nested_control_flow_edit_on_mutant_does_not_change_original():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    with circuit.for_loop(range(2)):
        with circuit.if_test((circuit.clbits[0], 1)):
            circuit.x(1)
            circuit.break_loop()
        circuit.h(1)

    def inner_true_body(outer: QuantumCircuit, loop_index: int) -> QuantumCircuit:
        loop_body = outer.data[loop_index].operation.blocks[0]
        inner_if = next(inst.operation for inst in loop_body.data if inst.operation.name == "if_else")
        return inner_if.blocks[0]

    mutant = remove_instruction(circuit, 0)
    inner_true_body(mutant, 1).z(0)

    assert op_names(inner_true_body(mutant, 1)) == ["x", "break_loop", "z"]
    assert op_names(inner_true_body(circuit, 2)) == ["x", "break_loop"]


def test_array_param_edit_on_mutant_does_not_change_original():
    circuit = QuantumCircuit(1)
    circuit.append(Instruction("tagged", 1, 0, [np.array([1.0, 2.0])]), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.params[0][0] = 99.0

    assert mutant.data[0].operation.params[0].tolist() == [99.0, 2.0]
    assert circuit.data[0].operation.params[0].tolist() == [1.0, 2.0]


def test_array_param_inside_control_flow_block_is_isolated():
    circuit = QuantumCircuit(1, 1)
    circuit.measure(0, 0)
    with circuit.if_test((circuit.clbits[0], 1)):
        circuit.append(Instruction("tagged", 1, 0, [np.array([1.0, 2.0])]), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 2)
    mutant.data[1].operation.blocks[0].data[0].operation.params[0][0] = 99.0

    assert mutant.data[1].operation.blocks[0].data[0].operation.params[0].tolist() == [99.0, 2.0]
    assert circuit.data[1].operation.blocks[0].data[0].operation.params[0].tolist() == [1.0, 2.0]


def test_mixed_parameter_and_array_params_stay_bindable():
    theta = Parameter("theta")
    circuit = QuantumCircuit(1)
    circuit.append(Instruction("mixed", 1, 0, [theta, np.array([1.0])]), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.params[1][0] = 5.0
    bound = mutant.assign_parameters({theta: 0.25})

    assert set(mutant.parameters) == {theta}
    assert float(bound.data[0].operation.params[0]) == pytest.approx(0.25)
    assert circuit.data[0].operation.params[1].tolist() == [1.0]
    assert set(circuit.parameters) == {theta}


@pytest.mark.parametrize(
    "operation",
    [
        UnitaryGate(random_unitary(4, seed=3).data),
        Isometry(random_unitary(4, seed=3).data, 0, 0),
        HamiltonianGate(np.diag([1.0, -1.0, 0.5, 0.2]), 0.3),
        PermutationGate([1, 0]),
        LinearFunction([[1, 1], [0, 1]]),
    ],
    ids=lambda operation: operation.name,
)
def test_library_operations_with_array_params_keep_semantics(operation):
    circuit = QuantumCircuit(2)
    circuit.append(operation, [0, 1])
    circuit.h(0)
    reference = QuantumCircuit(2)
    reference.append(operation, [0, 1])

    mutant = remove_instruction(circuit, 1)

    assert type(mutant.data[0].operation) is type(circuit.data[0].operation)
    assert Operator(mutant).equiv(Operator(reference))


def control_flow_circuit(kind: str) -> QuantumCircuit:
    circuit = QuantumCircuit(1, 1)
    circuit.measure(0, 0)
    if kind == "while":
        with circuit.while_loop((circuit.clbits[0], 1)):
            circuit.x(0)
    elif kind == "switch":
        with circuit.switch(circuit.clbits[0]) as case:
            with case(1):
                circuit.x(0)
            with case(case.DEFAULT):
                circuit.x(0)
    else:
        with circuit.box():
            circuit.x(0)
    circuit.h(0)
    return circuit


@pytest.mark.parametrize("kind", ["while", "switch", "box"])
def test_other_control_flow_block_edits_on_mutant_do_not_change_original(kind):
    circuit = control_flow_circuit(kind)

    mutant = remove_instruction(circuit, 2)
    mutant.data[1].operation.blocks[0].z(0)

    assert op_names(mutant.data[1].operation.blocks[0]) == ["x", "z"]
    assert op_names(circuit.data[1].operation.blocks[0]) == ["x"]


def test_array_param_inside_instruction_definition_is_isolated():
    body = QuantumCircuit(1, name="wrapper")
    body.append(Instruction("tagged", 1, 0, [np.array([1.0, 2.0])]), [0])
    circuit = QuantumCircuit(1)
    circuit.append(body.to_instruction(), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.definition.data[0].operation.params[0][0] = 99.0

    assert mutant.data[0].operation.definition.data[0].operation.params[0].tolist() == [99.0, 2.0]
    assert circuit.data[0].operation.definition.data[0].operation.params[0].tolist() == [1.0, 2.0]


def test_operation_in_control_flow_inside_instruction_definition_is_isolated():
    body = QuantumCircuit(1, 1)
    with body.if_test((body.clbits[0], 1)):
        body.append(Instruction("custom", 1, 0, []), [0])
    wrapper = Instruction("wrapper", 1, 1, [])
    wrapper.definition = body
    circuit = QuantumCircuit(1, 1)
    circuit.append(wrapper, [0], [0])
    circuit.h(0)

    def nested(outer: QuantumCircuit) -> Instruction:
        return outer.data[0].operation.definition.data[0].operation.blocks[0].data[0].operation

    mutant = remove_instruction(circuit, 1)
    nested(mutant).label = "edited"

    assert nested(mutant).label == "edited"
    assert nested(circuit).label is None


class ArrayParamGate(Gate):
    def __init__(self, values):
        super().__init__("array_param_gate", 1, [values])

    def validate_parameter(self, parameter):
        return parameter

    def _define(self):
        self.definition = QuantumCircuit(1)


def test_known_limitation_gate_definition_internals_follow_qiskit_deepcopy():
    """Documents a limitation: Gate definitions are not traversed.

    Mutable params of gates nested inside a ``Gate`` definition are shared
    exactly when Qiskit's own ``Instruction.__deepcopy__`` copies params
    shallowly (observed in Qiskit 2.0.3, not in 2.6.1).
    """
    probe = ArrayParamGate(np.array([1.0]))
    qiskit_copies_params_shallowly = copy.deepcopy(probe).params[0] is probe.params[0]
    body = QuantumCircuit(1)
    body.append(ArrayParamGate(np.array([1.0, 2.0])), [0])
    circuit = QuantumCircuit(1)
    circuit.append(body.to_gate(), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.definition.data[0].operation.params[0][0] = 99.0
    original_values = circuit.data[0].operation.definition.data[0].operation.params[0].tolist()

    assert (original_values == [99.0, 2.0]) is qiskit_copies_params_shallowly
    if qiskit.__version__.startswith("2.0."):
        assert qiskit_copies_params_shallowly


def test_known_limitation_control_flow_in_manual_gate_definition_is_shared():
    """Documents a limitation: a control-flow block placed in a ``Gate``
    definition by assigning ``definition`` directly is not isolated, so its
    instruction objects are shared with the original (both tested versions).
    """
    body = QuantumCircuit(1, 1)
    with body.if_test((body.clbits[0], 1)):
        body.append(Instruction("custom", 1, 0, []), [0])
    gate = Gate("manual_gate", 1, [])
    gate.definition = body
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.definition.data[0].operation.blocks[0].data[0].operation.label = "edited"

    assert circuit.data[0].operation.definition.data[0].operation.blocks[0].data[0].operation.label == "edited"


def test_known_limitation_pauli_evolution_operator_is_shared():
    """Documents a limitation: ``PauliEvolutionGate.operator`` is an attribute
    outside ``params``, which Qiskit copies shallowly, so in-place edits to it
    on the mutant change the original (both tested versions).
    """
    circuit = QuantumCircuit(1)
    circuit.append(PauliEvolutionGate(SparsePauliOp(["Z"], coeffs=[1.0]), time=0.5), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.operator.coeffs[0] = 7.0

    assert circuit.data[0].operation.operator.coeffs.tolist() == [7.0]


def test_known_limitation_instruction_subclass_attribute_is_shared():
    """Documents a limitation: attributes of user-defined ``Instruction``
    subclasses outside ``params`` and ``definition`` are copied shallowly by
    Qiskit, so in-place edits on the mutant change the original (both tested
    versions).
    """

    class TaggedInstruction(Instruction):
        def __init__(self):
            super().__init__("tagged_attribute", 1, 0, [])
            self.tags = ["original"]

    circuit = QuantumCircuit(1)
    circuit.append(TaggedInstruction(), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant.data[0].operation.tags.append("mutant")

    assert circuit.data[0].operation.tags == ["original", "mutant"]


def test_custom_gate_edit_on_mutant_does_not_change_original():
    body = QuantumCircuit(1, name="custom")
    body.rx(0.5, 0)
    circuit = QuantumCircuit(1)
    circuit.append(body.to_gate(), [0])
    circuit.h(0)

    mutant = remove_instruction(circuit, 1)
    mutant_gate = mutant.data[0].operation
    mutant_gate.definition.h(0)
    mutant_gate.label = "edited"

    assert op_names(mutant.data[0].operation.definition) == ["rx", "h"]
    assert mutant.data[0].operation.label == "edited"
    assert op_names(circuit.data[0].operation.definition) == ["rx"]
    assert circuit.data[0].operation.label is None
