"""Proposed Phase 6A circuits and hand-written fault catalogue, as validated in preflight.

Every circuit is barrier-free. Instruction indices refer to the operation lists
in ``ORIGINALS`` exactly as written here; adding barriers would shift them.

Operations are tuples ``(name, *args)`` passed to the ``QuantumCircuit`` method
of that name. Fault edits are ``("replace", index, old, new)``,
``("remove", index, old)`` or ``("insert", index, new)``; ``old`` is checked
against the original operation unless it is ``None``, and an insert at
``index`` goes before the original operation at ``index``.

Each fault is ``(fault_id, circuit_id, category, tag, edits,
predicted_class, predicted_distribution, measurement_only)``. A predicted
distribution of ``None`` means the circuit's expected distribution.
"""

import cmath
import math

PI = math.pi
S2 = math.sqrt(2)
S3 = math.sqrt(3)

EQ = "EQ"
NE = "NE"
MG = "missing_gate"
OT = "other"


def meas(count):
    """Return measurements of qubit ``i`` into classical bit ``i``."""
    return [("measure", i, i) for i in range(count)]


def h(*qubits):
    """Return Hadamard operations on ``qubits``."""
    return [("h", q) for q in qubits]


def x(*qubits):
    """Return X operations on ``qubits``."""
    return [("x", q) for q in qubits]


ORACLE = [("x", 1), ("h", 2), ("ccx", 0, 1, 2), ("h", 2), ("x", 1)]
DIFFUSER = h(0, 1, 2) + x(0, 1, 2) + [("h", 2), ("ccx", 0, 1, 2), ("h", 2)] + x(0, 1, 2) + h(0, 1, 2)
CP_DECOMPOSITION = [("cp", PI / 4, 1, 2), ("cx", 0, 1), ("cp", -PI / 4, 1, 2), ("cx", 0, 1), ("cp", PI / 4, 0, 2)]

ORIGINALS = {
    "C1": (3, 3, [("h", 0), ("cx", 0, 1), ("cx", 1, 2)] + meas(3)),
    "C2": (5, 4, [("x", 4)] + h(0, 1, 2, 3, 4) + [("cx", 0, 4), ("cx", 1, 4), ("cx", 3, 4)] + h(0, 1, 2, 3) + meas(4)),
    "C3": (4, 3, [("x", 3)] + h(0, 1, 2, 3) + [("cx", 0, 3), ("cx", 1, 3), ("cx", 2, 3)] + h(0, 1, 2) + meas(3)),
    "C4": (3, 3, h(0, 1, 2) + ORACLE + DIFFUSER + ORACLE + DIFFUSER + meas(3)),
    "C5": (3, 3, [("x", 0), ("x", 2), ("h", 2), ("cp", PI / 2, 1, 2), ("cp", PI / 4, 0, 2), ("h", 1),
                  ("cp", PI / 2, 0, 1), ("h", 0), ("swap", 0, 2)] + meas(3)),
    "C6": (3, 3, [("ry", 2 * PI / 3, 0), ("h", 1), ("cx", 1, 2), ("cx", 0, 1), ("h", 0), ("cx", 1, 2),
                  ("cz", 0, 2)] + meas(3)),
}

C4_INDEX_MAP = {
    "initial H": (0, 3),
    "oracle 1": (3, 8),
    "diffuser 1": (8, 23),
    "oracle 2": (23, 28),
    "diffuser 2": (28, 43),
    "measurements": (43, 46),
}


def keys(width):
    """Return all bit strings of ``width`` bits, classical bit 0 rightmost."""
    return [format(k, f"0{width}b") for k in range(2 ** width)]


def by_key(width, probability):
    """Return a distribution built from ``probability(key)`` for every key."""
    return {key: probability(key) for key in keys(width)}


def bit(key, index):
    """Return whether classical bit ``index`` of ``key`` is 1."""
    return key[len(key) - 1 - index] == "1"


def point(key):
    """Return a distribution concentrated on ``key``."""
    return {key: 1.0}


def half(first, second):
    """Return probability one half on each of two keys."""
    return {first: 0.5, second: 0.5}


def quarter(*selected):
    """Return probability one quarter on each of four keys."""
    return {key: 0.25 for key in selected}


def grover(marked, marked_probability, other_probability):
    """Return a three-bit distribution with one distinguished outcome."""
    return by_key(3, lambda key: marked_probability if key == marked else other_probability)


EXPECTED_DISTRIBUTIONS = {
    "C1": half("000", "111"),
    "C2": point("1011"),
    "C3": point("111"),
    "C4": grover("101", 121 / 128, 1 / 128),
    "C5": by_key(3, lambda key: 1 / 8),
    "C6": by_key(3, lambda key: 3 / 16 if bit(key, 2) else 1 / 16),
}


def expected_states():
    """Return the documented pre-measurement statevectors as index-to-amplitude maps."""
    return {
        "C1": (3, {0: 1 / S2, 7: 1 / S2}),
        "C2": (5, {11: 1 / S2, 27: -1 / S2}),
        "C3": (4, {7: 1 / S2, 15: -1 / S2}),
        "C4": (3, {k: (11 if k == 5 else -1) / math.sqrt(128) for k in range(8)}),
        "C5": (3, {k: cmath.exp(1j * 5 * PI * k / 4) / math.sqrt(8) for k in range(8)}),
        "C6": (3, {k: (S3 / 4 if k >= 4 else 1 / 4) for k in range(8)}),
    }


SIN_01 = math.sin(0.1)
C6_F05_ONE = (1 - math.cos(2 * PI / 3 + 0.1)) / 2


def _c4_f09_edits():
    edits = []
    for start in (4, 24):
        edits += [("remove", start, ("h", 2)), ("replace", start + 1, ("ccx", 0, 1, 2), CP_DECOMPOSITION),
                  ("remove", start + 2, ("h", 2))]
    return edits


FAULTS = [
    ("C1-F01", "C1", "wrong gate", OT, [("replace", 0, ("h", 0), ("x", 0))], NE, point("111"), False),
    ("C1-F02", "C1", "wrong angle", OT, [("replace", 0, ("h", 0), ("ry", PI / 3, 0))], NE,
     {"000": 0.75, "111": 0.25}, False),
    ("C1-F03", "C1", "wrong angle", OT, [("replace", 0, ("h", 0), ("ry", PI / 2 + 0.1, 0))], NE,
     {"000": (1 - SIN_01) / 2, "111": (1 + SIN_01) / 2}, False),
    ("C1-F04", "C1", "swapped control/target", OT, [("replace", 1, ("cx", 0, 1), ("cx", 1, 0))], NE,
     half("000", "001"), False),
    ("C1-F05", "C1", "swapped control/target", OT, [("replace", 2, ("cx", 1, 2), ("cx", 2, 1))], NE,
     half("000", "011"), False),
    ("C1-F06", "C1", "wrong qubit", OT, [("replace", 2, ("cx", 1, 2), ("cx", 0, 2))], EQ, None, False),
    ("C1-F07", "C1", "missing gate", MG, [("remove", 2, ("cx", 1, 2))], NE, half("000", "011"), False),
    ("C1-F08", "C1", "missing gate", MG, [("remove", 0, ("h", 0))], NE, point("000"), False),
    ("C1-F09", "C1", "extra gate", OT, [("insert", 1, ("z", 0))], EQ, None, False),
    ("C1-F10", "C1", "extra gate", OT, [("insert", 3, ("x", 2))], NE, half("100", "011"), False),
    ("C1-F11", "C1", "measurement mapping", OT, [("replace", 5, ("measure", 2, 2), ("measure", 2, 1))], NE,
     half("000", "011"), True),
    ("C1-F12", "C1", "wrong gate", OT, [("replace", 1, ("cx", 0, 1), ("cy", 0, 1))], EQ, None, False),

    ("C2-F01", "C2", "missing gate / wrong oracle", MG, [("remove", 7, ("cx", 1, 4))], NE, point("1001"), False),
    ("C2-F02", "C2", "extra gate / wrong oracle", OT, [("insert", 9, ("cx", 2, 4))], NE, point("1111"), False),
    ("C2-F03", "C2", "wrong qubit", OT, [("replace", 6, ("cx", 0, 4), ("cx", 2, 4))], NE, point("1110"), False),
    ("C2-F04", "C2", "swapped control/target", OT, [("replace", 8, ("cx", 3, 4), ("cx", 4, 3))], NE,
     point("0011"), False),
    ("C2-F05", "C2", "missing gate", MG, [("remove", 0, ("x", 4))], NE, point("0000"), False),
    ("C2-F06", "C2", "missing gate", MG, [("remove", 11, ("h", 2))], NE, half("1011", "1111"), False),
    ("C2-F07", "C2", "extra gate", OT, [("insert", 9, ("z", 0))], NE, point("1010"), False),
    ("C2-F08", "C2", "wrong gate", OT, [("replace", 10, ("h", 1), ("x", 1))], NE, half("1011", "1001"), False),
    ("C2-F09", "C2", "wrong gate (rotation for H)", OT, [("replace", 1, ("h", 0), ("rx", PI / 2, 0))], NE,
     half("1011", "1010"), False),
    ("C2-F10", "C2", "measurement mapping", OT, [("replace", 15, ("measure", 2, 2), ("measure", 2, 3)),
                                                ("replace", 16, ("measure", 3, 3), ("measure", 3, 2))], NE,
     point("0111"), True),
    ("C2-F11", "C2", "extra gate", OT, [("insert", 13, ("z", 4))], EQ, None, False),

    ("C3-F01", "C3", "wrong oracle (constant)", OT, [("remove", 5, ("cx", 0, 3)), ("remove", 6, ("cx", 1, 3)),
                                                    ("remove", 7, ("cx", 2, 3))], NE, point("000"), False),
    ("C3-F02", "C3", "missing gate", MG, [("remove", 7, ("cx", 2, 3))], NE, point("011"), False),
    ("C3-F03", "C3", "wrong qubit", OT, [("replace", 7, ("cx", 2, 3), ("cx", 1, 3))], NE, point("001"), False),
    ("C3-F04", "C3", "swapped control/target", OT, [("replace", 5, ("cx", 0, 3), ("cx", 3, 0))], NE,
     point("110"), False),
    ("C3-F05", "C3", "missing gate", MG, [("remove", 0, ("x", 3))], NE, point("000"), False),
    ("C3-F06", "C3", "missing gate", MG, [("remove", 8, ("h", 0))], NE, half("111", "110"), False),
    ("C3-F07", "C3", "extra gate", OT, [("insert", 11, ("x", 1))], NE, point("101"), False),
    ("C3-F08", "C3", "wrong gate", OT, [("replace", 10, ("h", 2), ("z", 2))], NE, half("111", "011"), False),
    ("C3-F09", "C3", "wrong angle", OT, [("replace", 1, ("h", 0), ("ry", PI / 3, 0))], NE,
     {"111": (2 + S3) / 4, "110": (2 - S3) / 4}, False),
    ("C3-F10", "C3", "measurement mapping", OT, [("replace", 13, ("measure", 2, 2), ("measure", 2, 1))], NE,
     point("011"), True),
    ("C3-F11", "C3", "extra gate", OT, [("insert", 11, ("z", 3))], EQ, None, False),

    ("C4-F01", "C4", "wrong parameter (iterations)", OT, [("remove", i, None) for i in range(23, 43)], NE,
     grover("101", 25 / 32, 1 / 32), False),
    ("C4-F02", "C4", "wrong parameter (iterations)", OT, [("insert", 43, op) for op in ORACLE + DIFFUSER], NE,
     grover("101", 169 / 512, 49 / 512), False),
    ("C4-F03", "C4", "wrong qubit / wrong oracle", OT,
     [("replace", i, ("x", 1), ("x", 0)) for i in (3, 7, 23, 27)], NE, grover("110", 121 / 128, 1 / 128), False),
    ("C4-F04", "C4", "missing block", OT, [("remove", i, None) for i in range(28, 43)], NE,
     grover("101", 25 / 32, 1 / 32), False),
    ("C4-F05", "C4", "wrong oracle", OT, [("remove", i, ("x", 1)) for i in (3, 7, 23, 27)], NE,
     grover("111", 121 / 128, 1 / 128), False),
    ("C4-F06", "C4", "measurement mapping", OT, [("replace", 44, ("measure", 1, 1), ("measure", 1, 2)),
                                                ("replace", 45, ("measure", 2, 2), ("measure", 2, 1))], NE,
     grover("011", 121 / 128, 1 / 128), True),
    ("C4-F07", "C4", "extra gate", OT, [("insert", 43, ("x", 0))], NE, grover("100", 121 / 128, 1 / 128), False),
    ("C4-F08", "C4", "extra gate", OT, [("insert", 43, ("z", 0))], EQ, None, False),
    ("C4-F09", "C4", "wrong angle", OT, _c4_f09_edits(), NE, grover("101", 85 / 512, 61 / 512), False),
    ("C4-F10", "C4", "swapped control/target", OT,
     [("replace", i, ("ccx", 0, 1, 2), ("ccx", 0, 2, 1)) for i in (5, 25)], NE, by_key(3, lambda key: 1 / 8), False),
    ("C4-F11", "C4", "missing gate", MG, [("remove", 7, ("x", 1))], NE,
     by_key(3, lambda key: {"101": 49 / 128, "111": 25 / 128}.get(key, 9 / 128)), False),
    ("C4-F12", "C4", "missing gate", MG, [("remove", 3, ("x", 1))], EQ, None, False),

    ("C5-F01", "C5", "missing gate", MG, [("remove", 7, ("h", 0))], NE, quarter("100", "101", "110", "111"), False),
    ("C5-F02", "C5", "missing gate", MG, [("remove", 5, ("h", 1))], NE, quarter("000", "001", "100", "101"), False),
    ("C5-F03", "C5", "missing gate", MG, [("remove", 2, ("h", 2))], NE, quarter("001", "011", "101", "111"), False),
    ("C5-F04", "C5", "wrong gate", OT, [("replace", 5, ("h", 1), ("x", 1))], NE,
     quarter("010", "011", "110", "111"), False),
    ("C5-F05", "C5", "wrong angle", OT, [("replace", 5, ("h", 1), ("ry", PI / 3, 1))], NE,
     by_key(3, lambda key: 1 / 16 if bit(key, 1) else 3 / 16), False),
    ("C5-F06", "C5", "wrong qubit", OT, [("replace", 5, ("h", 1), ("h", 0))], NE, half("100", "101"), False),
    ("C5-F07", "C5", "extra gate", OT, [("insert", 9, ("h", 0))], NE,
     by_key(3, lambda key: (2 + S2) / 16 if bit(key, 0) else (2 - S2) / 16), False),
    ("C5-F08", "C5", "measurement mapping", OT, [("replace", 11, ("measure", 2, 2), ("measure", 2, 1))], NE,
     quarter("000", "001", "010", "011"), True),
    ("C5-F09", "C5", "missing gate", MG, [("remove", 8, ("swap", 0, 2))], EQ, None, False),
    ("C5-F10", "C5", "wrong qubit", OT, [("replace", 1, ("x", 2), ("x", 1))], EQ, None, False),
    ("C5-F11", "C5", "wrong angle", OT, [("replace", 4, ("cp", PI / 4, 0, 2), ("cp", PI / 2, 0, 2))], EQ, None, False),
    ("C5-F12", "C5", "wrong gate (state preparation)", OT, [("replace", 0, ("x", 0), ("ry", PI / 3, 0))], NE,
     by_key(3, lambda key: (1 + (S3 / 2) * math.cos(PI * int(key, 2) / 4)) / 8), False),

    ("C6-F01", "C6", "wrong order", OT, [("replace", 5, ("cx", 1, 2), ("cz", 0, 2)),
                                        ("replace", 6, ("cz", 0, 2), ("cx", 1, 2))], EQ, None, False),
    ("C6-F02", "C6", "missing gate", MG, [("remove", 5, ("cx", 1, 2))], NE,
     by_key(3, lambda key: 3 / 16 if bit(key, 2) != bit(key, 1) else 1 / 16), False),
    ("C6-F03", "C6", "missing gate", MG, [("remove", 6, ("cz", 0, 2))], EQ, None, False),
    ("C6-F04", "C6", "wrong angle", OT, [("replace", 0, ("ry", 2 * PI / 3, 0), ("ry", PI / 3, 0))], NE,
     by_key(3, lambda key: 1 / 16 if bit(key, 2) else 3 / 16), False),
    ("C6-F05", "C6", "wrong angle", OT, [("replace", 0, ("ry", 2 * PI / 3, 0), ("ry", 2 * PI / 3 + 0.1, 0))], NE,
     by_key(3, lambda key: C6_F05_ONE / 4 if bit(key, 2) else (1 - C6_F05_ONE) / 4), False),
    ("C6-F06", "C6", "swapped control/target", OT, [("replace", 2, ("cx", 1, 2), ("cx", 2, 1))], NE,
     {"000": (2 + S3) / 8, "110": (2 + S3) / 8, "001": (2 - S3) / 8, "111": (2 - S3) / 8}, False),
    ("C6-F07", "C6", "swapped control/target", OT, [("replace", 5, ("cx", 1, 2), ("cx", 2, 1))], NE,
     by_key(3, lambda key: 3 / 16 if bit(key, 1) else 1 / 16), False),
    ("C6-F08", "C6", "wrong qubit", OT, [("replace", 6, ("cz", 0, 2), ("cz", 1, 2))], EQ, None, False),
    ("C6-F09", "C6", "missing gate", MG, [("remove", 4, ("h", 0))], NE,
     {"000": 1 / 8, "010": 1 / 8, "101": 3 / 8, "111": 3 / 8}, False),
    ("C6-F10", "C6", "measurement mapping", OT, [("replace", 8, ("measure", 1, 1), ("measure", 1, 2)),
                                                ("replace", 9, ("measure", 2, 2), ("measure", 2, 1))], NE,
     by_key(3, lambda key: 3 / 16 if bit(key, 1) else 1 / 16), True),
    ("C6-F11", "C6", "extra gate", OT, [("insert", 7, ("x", 2))], NE,
     by_key(3, lambda key: 1 / 16 if bit(key, 2) else 3 / 16), False),
    ("C6-F12", "C6", "wrong gate", OT, [("replace", 6, ("cz", 0, 2), ("cx", 0, 2))], NE,
     by_key(3, lambda key: 3 / 16 if bit(key, 2) != bit(key, 0) else 1 / 16), False),
]

FORMER_RESERVES = ("C5-F12", "C6-F12")

SEED_SENSITIVE = {
    "C1-F03": ("T4", "T5"),
    "C2-F06": ("T2",),
    "C2-F08": ("T2",),
    "C2-F09": ("T2",),
    "C3-F06": ("T2",),
    "C3-F08": ("T2",),
    "C4-F09": ("T2",),
    "C4-F10": ("T2",),
    "C6-F05": ("T4", "T5"),
}

BORDERLINE = {"C3-F09": ("T3",)}

REDUNDANT_GROUPS = [
    ("C1-F05", "C1-F07", "C1-F11"),
    ("C3-F01", "C3-F05"),
    ("C3-F02", "C3-F10"),
    ("C4-F01", "C4-F04"),
    ("C6-F04", "C6-F11"),
    ("C6-F07", "C6-F10"),
]


def apply_edits(ops, edits):
    """Return ``ops`` with ``edits`` applied, checking every expected old operation."""
    before = {}
    replacements = {}
    removed = set()
    for edit in edits:
        kind = edit[0]
        if kind == "insert":
            _, index, new = edit
            if not 0 <= index <= len(ops):
                raise ValueError(f"insert index {index} is out of range")
            before.setdefault(index, []).append(new)
            continue
        index, old = edit[1], edit[2]
        if old is not None and ops[index] != old:
            raise ValueError(f"index {index} holds {ops[index]}, expected {old}")
        if index in removed or index in replacements:
            raise ValueError(f"index {index} is edited twice")
        if kind == "remove":
            removed.add(index)
        elif kind == "replace":
            replacements[index] = edit[3]
        else:
            raise ValueError(f"unknown edit {kind}")
    result = []
    for index, op in enumerate(ops):
        result.extend(before.get(index, []))
        if index in removed:
            continue
        new = replacements.get(index, op)
        result.extend(new if isinstance(new, list) else [new])
    result.extend(before.get(len(ops), []))
    return result


def build(num_qubits, num_clbits, ops):
    """Return a barrier-free ``QuantumCircuit`` with one quantum and one classical register."""
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(num_qubits, num_clbits)
    for name, *args in ops:
        getattr(circuit, name)(*args)
    return circuit


def build_original(circuit_id):
    """Return the original circuit ``circuit_id``."""
    num_qubits, num_clbits, ops = ORIGINALS[circuit_id]
    return build(num_qubits, num_clbits, ops)


def build_fault(fault):
    """Return the circuit of a ``FAULTS`` entry."""
    num_qubits, num_clbits, ops = ORIGINALS[fault[1]]
    return build(num_qubits, num_clbits, apply_edits(ops, fault[4]))
