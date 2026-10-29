"""Finite-shot comparison of sampled measurement distributions.

The comparison is based on the total variation distance between two sets of
measurement counts and a confidence bound for it. Every statistical statement
in this module is conditional on these assumptions:

* A1: each sample, considered on its own with its seed treated as random,
  consists of independent, identically distributed shots from the circuit's
  fixed output distribution. Whether this holds depends on the sampler and on
  how seeds are used; qmutate cannot verify it. The default sampler draws
  from Qiskit's ``BasicSimulator``, and a custom sampler is responsible for
  satisfying A1 itself.
* A2: both samples use the same outcome space of ``num_clbits`` classical
  bits, so ``k = 2**num_clbits`` bounds the number of possible outcomes.
* A3: seeds are chosen independently of the circuits and of any results.
  Repeating a run with new seeds until a result looks acceptable breaks A3
  and voids every guarantee.
* A4: each circuit's output distribution does not change between samples.

Under A1 and A2, a sample of ``n`` shots is within total variation distance
``epsilon(n) = (sqrt((k - 1) / n) + sqrt(2 * log(1 / delta) / n)) / 2`` of
its distribution with probability at least ``1 - delta``. Two samples are
both within their margins with probability at least ``1 - 2 * delta`` by the
union bound, which needs no independence between the samples. On that event
the true distance lies in ``[distance - threshold, distance + threshold]``
with ``threshold = epsilon(n_a) + epsilon(n_b)``. These are bounds, not
exact confidence levels, and the bound is conservative, so small
differences are often not detected.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from numbers import Integral
from types import MappingProxyType

from qiskit.circuit import ClassicalRegister, Clbit, QuantumCircuit
from qiskit.providers.basic_provider import BasicSimulator

from qmutate.mutation import _contained_kinds, _isolated_copy

Sampler = Callable[[QuantumCircuit, int, int], Mapping[str, int]]


class SamplingVerdict(StrEnum):
    """Outcome of comparing two sampled distributions."""

    DISTINGUISHED = "distinguished"
    WITHIN_TOLERANCE = "within_tolerance"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class DistributionComparison:
    """Comparison of two sets of counts over ``num_clbits`` classical bits.

    Only the inputs are stored; every other value is derived from them.

    Attributes:
        shots_a: Total number of shots in the first set of counts.
        shots_b: Total number of shots in the second set of counts.
        num_clbits: Number of classical bits in every outcome.
        delta: Failure probability allowed for each sample's margin, in
            ``(0, 1)``.
        tolerance: Distance ``epsilon`` treated as practically equal, in
            ``[0, 1)``.
        distance: Observed total variation distance, in ``[0, 1]``.

    Derived values:
        * ``threshold`` is the sum of both samples' margins.
        * ``lower_bound`` is ``max(0, distance - threshold)`` and
          ``upper_bound`` is ``min(1, distance + threshold)``. Under A1-A4 the
          true distance lies between them with probability at least
          ``1 - 2 * delta``.
        * ``informative`` is ``threshold < 1``. When it is false, the verdict
          is always ``INCONCLUSIVE``.
        * ``verdict`` is ``WITHIN_TOLERANCE`` when ``upper_bound <= tolerance``,
          ``DISTINGUISHED`` when ``lower_bound > tolerance``, and
          ``INCONCLUSIVE`` otherwise. With ``tolerance == 0`` the verdict is
          never ``WITHIN_TOLERANCE``.

    Under A1-A4, ``DISTINGUISHED`` when the true distance is at most
    ``tolerance``, and ``WITHIN_TOLERANCE`` when it is greater, each happen
    with probability at most ``2 * delta``. A true distance above
    ``tolerance + 2 * threshold`` gives ``DISTINGUISHED``, and one below
    ``tolerance - 2 * threshold`` gives ``WITHIN_TOLERANCE``, each with
    probability at least ``1 - 2 * delta``. ``WITHIN_TOLERANCE`` never means
    the circuits are equivalent.

    Raises:
        TypeError: If a field has the wrong type (``bool`` is rejected).
        ValueError: If a field is outside its range.
    """

    shots_a: int
    shots_b: int
    num_clbits: int
    delta: float
    tolerance: float
    distance: float

    def __post_init__(self) -> None:
        _require_positive_int("shots_a", self.shots_a)
        _require_positive_int("shots_b", self.shots_b)
        _require_positive_int("num_clbits", self.num_clbits)
        _require_open_unit("delta", self.delta)
        _require_tolerance(self.tolerance)
        _require_number("distance", self.distance)
        if not 0 <= self.distance <= 1:
            raise ValueError(f"distance must be in [0, 1], got {self.distance}")

    @property
    def threshold(self) -> float:
        """Sum of both samples' margins."""
        return _threshold(self.shots_a, self.shots_b, self.num_clbits, self.delta)

    @property
    def lower_bound(self) -> float:
        """``max(0, distance - threshold)``."""
        return max(0.0, self.distance - self.threshold)

    @property
    def upper_bound(self) -> float:
        """``min(1, distance + threshold)``."""
        return min(1.0, self.distance + self.threshold)

    @property
    def informative(self) -> bool:
        """Whether ``threshold < 1``, so that a decision is possible at all."""
        return self.threshold < 1

    @property
    def verdict(self) -> SamplingVerdict:
        """Verdict obtained by comparing the bounds with ``tolerance``."""
        if self.upper_bound <= self.tolerance:
            return SamplingVerdict.WITHIN_TOLERANCE
        if self.lower_bound > self.tolerance:
            return SamplingVerdict.DISTINGUISHED
        return SamplingVerdict.INCONCLUSIVE


def compare_counts(
    counts_a: Mapping[str, int],
    counts_b: Mapping[str, int],
    *,
    num_clbits: int,
    delta: float = 0.01,
    tolerance: float = 0.0,
) -> DistributionComparison:
    """Compare two sets of measurement counts.

    Keys are bit strings over ``num_clbits`` classical bits. Spaces, as
    Qiskit places between registers, are removed before the length is
    checked. Both sets must come from circuits with the same classical-bit
    layout; this function only sees the counts and cannot check it.

    Values must be non-negative integers (``bool`` is rejected) and each set
    must contain at least one shot. The shot totals of the two sets may
    differ.

    Raises:
        TypeError: If the counts or options have the wrong type.
        ValueError: If a key is not a bit string of length ``num_clbits``, a
            key repeats after removing spaces, a count is negative, a set is
            empty, or an option is outside its range.
    """
    _require_positive_int("num_clbits", num_clbits)
    _require_open_unit("delta", delta)
    _require_tolerance(tolerance)
    first = _normalized_counts(counts_a, num_clbits, "counts_a")
    second = _normalized_counts(counts_b, num_clbits, "counts_b")
    shots_a = sum(first.values())
    shots_b = sum(second.values())
    distance = 0.5 * sum(
        abs(first.get(key, 0) / shots_a - second.get(key, 0) / shots_b)
        for key in sorted(set(first) | set(second))
    )
    return DistributionComparison(
        shots_a, shots_b, num_clbits, delta, tolerance, min(1.0, distance)
    )


def sample_counts(
    circuit: QuantumCircuit, *, shots: int, seed: int, sampler: Sampler | None = None
) -> dict[str, int]:
    """Sample ``circuit`` and return counts keyed by bit strings without spaces.

    The circuit is copied with the isolation rules of ``remove_instruction``
    before it is passed to the sampler, so it is not modified. Every
    classical bit must belong to exactly one register: for other layouts,
    Qiskit's count keys omit or mislabel bits. Keys order the classical bits
    as ``circuit.clbits`` does, with bit 0 rightmost.

    The default sampler runs Qiskit's ``BasicSimulator`` with
    ``seed_simulator=seed``. A custom ``sampler`` is called as
    ``sampler(circuit_copy, shots, seed)`` and must return counts with
    exactly ``shots`` shots; it is responsible for satisfying assumption A1.
    Errors raised by the sampler propagate unchanged.

    Raises:
        TypeError: If an argument has the wrong type.
        ValueError: If ``shots`` or ``seed`` is out of range, the circuit has
            no classical bits or an unsupported classical-bit layout, or the
            sampler returns invalid counts.
    """
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError(f"circuit must be a QuantumCircuit, got {type(circuit).__name__}")
    _require_positive_int("shots", shots)
    _require_seed(seed)
    _require_sampler(sampler)
    _require_register_layout(circuit)
    run = _basic_simulator_sampler if sampler is None else sampler
    counts = _normalized_counts(
        run(_isolated_copy(circuit), shots, seed), circuit.num_clbits, "sampler output"
    )
    total = sum(counts.values())
    if total != shots:
        raise ValueError(f"sampler returned {total} shots, expected {shots}")
    return counts


def shots_for_threshold(target: float, num_clbits: int, delta: float = 0.01) -> int:
    """Return the smallest shot count ``n`` with ``threshold(n, n) <= target``.

    ``threshold(n, n)`` is the threshold ``compare_counts`` reports for two
    samples of ``n`` shots, so comparing two samples of the returned size
    always reports a threshold of at most ``target``. A smaller target
    detects smaller differences but needs more shots.

    Raises:
        TypeError: If an argument has the wrong type.
        ValueError: If ``target`` is not in ``(0, 1)`` or another argument is
            out of range.
    """
    _require_open_unit("target", target)
    _require_positive_int("num_clbits", num_clbits)
    _require_open_unit("delta", delta)
    scale = _outcome_root(num_clbits) + math.sqrt(2 * math.log(1 / delta))
    shots = max(1, math.ceil((scale / target) ** 2))
    while shots > 1 and _threshold(shots - 1, shots - 1, num_clbits, delta) <= target:
        shots -= 1
    while _threshold(shots, shots, num_clbits, delta) > target:
        shots += 1
    return shots


def family_delta(alpha: float, num_samples: int) -> float:
    """Return ``alpha / num_samples``, a per-sample ``delta`` for a whole run.

    Under A1-A4, if every one of ``num_samples`` samples uses this ``delta``,
    the probability that any of them falls outside its margin is at most
    ``alpha`` by the union bound, so no verdict computed from those samples
    is a false ``DISTINGUISHED`` or a false ``WITHIN_TOLERANCE`` except with
    probability at most ``alpha``. For a run with ``distribution_oracle``,
    ``num_samples`` is the number of generated candidates plus two: one for
    the reference sample and one for the runner's baseline call.

    Raises:
        TypeError: If an argument has the wrong type.
        ValueError: If ``alpha`` is not in ``(0, 1)`` or ``num_samples`` is
            less than 1.
    """
    _require_open_unit("alpha", alpha)
    _require_positive_int("num_samples", num_samples)
    return alpha / num_samples


@dataclass(frozen=True, eq=False)
class DistributionOracle:
    """Oracle that fails a circuit whose sampled distribution is distinguished.

    Create it with ``distribution_oracle``. Calling it with a circuit samples
    that circuit with seed ``seed + 1`` and compares the counts with the
    reference counts, which were sampled with seed ``seed``. It raises
    ``AssertionError`` exactly when the verdict is ``DISTINGUISHED``, so in
    ``run_removal_mutants`` a mutant is killed only when it is distinguished;
    ``WITHIN_TOLERANCE`` and ``INCONCLUSIVE`` mutants survive. The oracle
    keeps no changing state, so results do not depend on the call order.

    Every call uses the same seed ``seed + 1``. That does not affect the
    guarantees, which rely only on each sample's own margin, but the samples
    of different circuits are correlated. Circuits with the same output
    distribution often receive identical counts, but not always: for
    example, ``BasicSimulator`` samples circuits with only final measurements
    in one step and simulates other circuits shot by shot, so removing an
    instruction can change how random numbers are used without changing the
    distribution.

    Attributes:
        shots: Shots per sample.
        seed: Seed of the reference sample; calls use ``seed + 1``.
        delta: Per-sample failure probability.
        tolerance: Tolerance ``epsilon`` of the verdict.
        reference_counts: Read-only reference counts.
        clbits: Classical bits of the reference circuit, in order.
        cregs: Classical registers of the reference circuit, in order.
        sampler: The custom sampler, or ``None`` for ``BasicSimulator``.
    """

    shots: int
    seed: int
    delta: float
    tolerance: float
    reference_counts: Mapping[str, int]
    clbits: tuple[Clbit, ...]
    cregs: tuple[ClassicalRegister, ...]
    sampler: Sampler | None = None

    def __post_init__(self) -> None:
        _require_positive_int("shots", self.shots)
        _require_seed(self.seed)
        _require_open_unit("delta", self.delta)
        _require_tolerance(self.tolerance)
        _require_sampler(self.sampler)
        if not isinstance(self.clbits, tuple) or not all(
            isinstance(bit, Clbit) for bit in self.clbits
        ):
            raise TypeError("clbits must be a tuple of Clbit")
        if not self.clbits:
            raise ValueError("clbits must not be empty")
        if not isinstance(self.cregs, tuple) or not all(
            isinstance(register, ClassicalRegister) for register in self.cregs
        ):
            raise TypeError("cregs must be a tuple of ClassicalRegister")
        counts = _normalized_counts(self.reference_counts, len(self.clbits), "reference_counts")
        if sum(counts.values()) != self.shots:
            raise ValueError(f"reference_counts must contain exactly {self.shots} shots")
        object.__setattr__(self, "reference_counts", MappingProxyType(counts))
        _require_informative(self.shots, self.num_clbits, self.delta)

    @property
    def num_clbits(self) -> int:
        """Number of classical bits in every outcome."""
        return len(self.clbits)

    @property
    def threshold(self) -> float:
        """Threshold of every comparison, for two samples of ``shots`` shots."""
        return _threshold(self.shots, self.shots, self.num_clbits, self.delta)

    @property
    def informative(self) -> bool:
        """Whether ``threshold < 1``; always true for a constructed oracle."""
        return self.threshold < 1

    def __call__(self, circuit: QuantumCircuit) -> None:
        """Sample ``circuit`` and raise ``AssertionError`` if it is distinguished.

        Raises:
            AssertionError: If the verdict is ``DISTINGUISHED``.
            TypeError: If ``circuit`` is not a ``QuantumCircuit``.
            ValueError: If ``circuit`` does not have the reference's
                classical bits and registers, in the same order.
        """
        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(f"circuit must be a QuantumCircuit, got {type(circuit).__name__}")
        if tuple(circuit.clbits) != self.clbits or tuple(circuit.cregs) != self.cregs:
            raise ValueError(
                "circuit does not have the reference's classical bits and registers in the "
                "same order"
            )
        counts = sample_counts(circuit, shots=self.shots, seed=self.seed + 1, sampler=self.sampler)
        comparison = compare_counts(
            self.reference_counts,
            counts,
            num_clbits=self.num_clbits,
            delta=self.delta,
            tolerance=self.tolerance,
        )
        if comparison.verdict is SamplingVerdict.DISTINGUISHED:
            raise AssertionError(
                f"sampled distribution is distinguished from the reference: distance "
                f"{comparison.distance:.6f}, threshold {comparison.threshold:.6f}, interval "
                f"[{comparison.lower_bound:.6f}, {comparison.upper_bound:.6f}] above tolerance "
                f"{self.tolerance} (shots {self.shots}, delta {self.delta})"
            )


def distribution_oracle(
    reference: QuantumCircuit,
    *,
    shots: int,
    seed: int,
    delta: float = 0.01,
    tolerance: float = 0.0,
    sampler: Sampler | None = None,
) -> DistributionOracle:
    """Sample ``reference`` once and return an oracle that compares against it.

    The reference is sampled with seed ``seed``; every call of the returned
    oracle samples its circuit with ``seed + 1``. Sampler errors while
    sampling the reference propagate unchanged.

    Used with ``run_removal_mutants``, the oracle measures how detectable
    mutants are at this shot count, not how good another test suite is. A
    survived mutant is either ``WITHIN_TOLERANCE`` or ``INCONCLUSIVE``, so
    report ``shots``, ``threshold``, ``delta`` and ``tolerance`` with the
    score. The runner first calls the oracle on the original circuit; if
    that baseline comparison is ``DISTINGUISHED``, which under A1-A4 happens
    with probability at most ``2 * delta``, the run stops with
    ``BaselineFailedError`` and produces no report or score. Changing seeds
    until the baseline passes breaks assumption A3 and voids the guarantees.

    For a whole run, ``family_delta(alpha, generated + 2)`` bounds the
    probability of any false ``DISTINGUISHED`` or false ``WITHIN_TOLERANCE``
    by ``alpha`` under A1-A4.

    Raises:
        TypeError: If an argument has the wrong type.
        ValueError: If an argument is out of range, ``reference`` has no
            classical bits, an unsupported classical-bit layout or no
            measurement, or the settings give a threshold of 1 or more.
    """
    if not isinstance(reference, QuantumCircuit):
        raise TypeError(f"reference must be a QuantumCircuit, got {type(reference).__name__}")
    _require_positive_int("shots", shots)
    _require_seed(seed)
    _require_open_unit("delta", delta)
    _require_tolerance(tolerance)
    _require_sampler(sampler)
    _require_register_layout(reference)
    copy = _isolated_copy(reference)
    if not any("measurement" in _contained_kinds(instruction.operation) for instruction in copy.data):
        raise ValueError("reference measures nothing, so its samples carry no information")
    _require_informative(shots, reference.num_clbits, delta)
    counts = sample_counts(reference, shots=shots, seed=seed, sampler=sampler)
    return DistributionOracle(
        shots=shots,
        seed=seed,
        delta=delta,
        tolerance=tolerance,
        reference_counts=counts,
        clbits=tuple(reference.clbits),
        cregs=tuple(reference.cregs),
        sampler=sampler,
    )


def _basic_simulator_sampler(circuit: QuantumCircuit, shots: int, seed: int) -> Mapping[str, int]:
    """Sample ``circuit`` with Qiskit's ``BasicSimulator``."""
    result = BasicSimulator().run(circuit, shots=shots, seed_simulator=seed).result()
    return result.get_counts()


def _outcome_root(num_clbits: int) -> float:
    """Return ``sqrt(2**num_clbits - 1)``."""
    if num_clbits <= 1000:
        return math.sqrt(2**num_clbits - 1)
    return math.exp(0.5 * math.log(2**num_clbits - 1))


def _margin(shots: int, num_clbits: int, delta: float) -> float:
    """One sample's total variation margin ``epsilon``."""
    return 0.5 * (
        _outcome_root(num_clbits) / math.sqrt(shots) + math.sqrt(2 * math.log(1 / delta) / shots)
    )


def _threshold(shots_a: int, shots_b: int, num_clbits: int, delta: float) -> float:
    """Sum of two samples' margins."""
    return _margin(shots_a, num_clbits, delta) + _margin(shots_b, num_clbits, delta)


def _normalized_counts(counts: Mapping[str, int], num_clbits: int, name: str) -> dict[str, int]:
    """Validate ``counts`` and return them with spaces removed from the keys."""
    if not isinstance(counts, Mapping):
        raise TypeError(f"{name} must be a mapping, got {type(counts).__name__}")
    normalized: dict[str, int] = {}
    for key, value in counts.items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be str, got {type(key).__name__}")
        bits = key.replace(" ", "")
        if len(bits) != num_clbits or any(bit not in "01" for bit in bits):
            raise ValueError(f"{name} key {key!r} is not a bit string of length {num_clbits}")
        if bits in normalized:
            raise ValueError(f"{name} key {key!r} repeats an outcome after removing spaces")
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise TypeError(f"{name} values must be int, got {type(value).__name__}")
        if value < 0:
            raise ValueError(f"{name} value for {key!r} is negative")
        normalized[bits] = int(value)
    if sum(normalized.values()) == 0:
        raise ValueError(f"{name} must contain at least one shot")
    return dict(sorted(normalized.items()))


def _require_register_layout(circuit: QuantumCircuit) -> None:
    """Require classical bits that each belong to exactly one register."""
    if circuit.num_clbits == 0:
        raise ValueError("circuit has no classical bits to sample")
    membership: dict[Clbit, int] = {}
    for register in circuit.cregs:
        for bit in register:
            membership[bit] = membership.get(bit, 0) + 1
    if any(membership.get(bit, 0) != 1 for bit in circuit.clbits):
        raise ValueError(
            "every classical bit must belong to exactly one register; other layouts give "
            "count keys that omit or mislabel bits"
        )


def _require_informative(shots: int, num_clbits: int, delta: float) -> None:
    """Require a threshold below 1 for two samples of ``shots`` shots."""
    threshold = _threshold(shots, shots, num_clbits, delta)
    if threshold >= 1:
        raise ValueError(
            f"threshold {threshold:.4f} is at least 1 for {shots} shots, so no verdict could be "
            f"reached; shots_for_threshold suggests at least "
            f"{shots_for_threshold(0.5, num_clbits, delta)} shots for 0.5"
        )


def _require_positive_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"{name} must be at least 1, got {value}")


def _require_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"seed must be an int, got {type(seed).__name__}")
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")


def _require_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a float, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")


def _require_open_unit(name: str, value: float) -> None:
    _require_number(name, value)
    if not 0 < value < 1:
        raise ValueError(f"{name} must be in (0, 1), got {value}")


def _require_tolerance(value: float) -> None:
    _require_number("tolerance", value)
    if not 0 <= value < 1:
        raise ValueError(f"tolerance must be in [0, 1), got {value}")


def _require_sampler(sampler: Sampler | None) -> None:
    if sampler is not None and not callable(sampler):
        raise TypeError(f"sampler must be callable or None, got {type(sampler).__name__}")
