"""qmutate: mutation testing foundations for quantum circuits."""

from importlib.metadata import version

from qmutate.equivalence import (
    ClassifiedReport,
    EquivalenceModel,
    EquivalenceResult,
    EquivalenceVerdict,
    UnknownReason,
    check_equivalence,
    classify_report,
)
from qmutate.generator import (
    CandidateStatus,
    RemovalCandidate,
    SkipReason,
    generate_removal_mutants,
)
from qmutate.metrics import AdjustedMetrics, MutationMetrics, mutation_score
from qmutate.mutation import remove_instruction
from qmutate.reporting import format_text_report, report_to_dict
from qmutate.runner import (
    BaselineFailedError,
    MutantOutcome,
    MutantResult,
    RunReport,
    run_removal_mutants,
)
from qmutate.sampling import (
    DistributionComparison,
    DistributionOracle,
    SamplingVerdict,
    compare_counts,
    distribution_oracle,
    family_delta,
    sample_counts,
    shots_for_threshold,
)

__all__ = [
    "AdjustedMetrics",
    "BaselineFailedError",
    "CandidateStatus",
    "ClassifiedReport",
    "DistributionComparison",
    "DistributionOracle",
    "EquivalenceModel",
    "EquivalenceResult",
    "EquivalenceVerdict",
    "MutantOutcome",
    "MutantResult",
    "MutationMetrics",
    "RemovalCandidate",
    "RunReport",
    "SamplingVerdict",
    "SkipReason",
    "UnknownReason",
    "check_equivalence",
    "classify_report",
    "compare_counts",
    "distribution_oracle",
    "family_delta",
    "format_text_report",
    "generate_removal_mutants",
    "mutation_score",
    "remove_instruction",
    "report_to_dict",
    "run_removal_mutants",
    "sample_counts",
    "shots_for_threshold",
]
__version__ = version("qmutate")
