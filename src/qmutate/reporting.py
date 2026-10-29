"""Structured and text reports for mutation runs."""

from qmutate.runner import RunReport

REPORT_SCHEMA_VERSION = 1

_SURVIVOR_NOTE = (
    "Surviving mutants may be equivalent to the original; qmutate does not detect equivalence."
)


def report_to_dict(report: RunReport) -> dict[str, object]:
    """Return a structured, JSON-compatible representation of ``report``.

    Schema version 1 has three keys, always in this order:

    * ``"schema_version"``: the integer ``1``.
    * ``"summary"``: ``total``, ``killed``, ``survived``, ``errors``,
      ``not_run``, ``executed``, ``eligible``, ``score`` and ``error_rate``,
      in that order, taken from ``report.metrics()``. ``score`` and
      ``error_rate`` are ratios with full float precision, or ``None`` when
      undefined.
    * ``"mutants"``: one entry per result, in index order, with ``index``,
      ``name``, ``outcome``, ``skip_reason`` and ``error_type``, in that
      order. ``outcome`` is one of ``"killed"``, ``"survived"``,
      ``"error"`` and ``"not_run"``; ``skip_reason`` is set only for
      ``"not_run"`` and ``error_type`` only for ``"error"``.

    Every value is a plain ``str``, ``int``, ``float``, ``None``, ``list`` or
    ``dict``, so the result can be passed to ``json.dumps``. Circuits are not
    included, and neither are versions, timestamps or other environment
    details. The same ``RunReport`` always gives an equal dictionary with the
    same key order; the exact bytes of any JSON encoding are not specified.

    Raises:
        TypeError: If ``report`` is not a ``RunReport``.
    """
    if not isinstance(report, RunReport):
        raise TypeError(f"report must be a RunReport, got {type(report).__name__}")
    metrics = report.metrics()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": {
            "total": metrics.total,
            "killed": metrics.killed,
            "survived": metrics.survived,
            "errors": metrics.errors,
            "not_run": metrics.not_run,
            "executed": metrics.executed,
            "eligible": metrics.eligible,
            "score": metrics.score,
            "error_rate": metrics.error_rate,
        },
        "mutants": [
            {
                "index": result.candidate.index,
                "name": result.candidate.name,
                "outcome": result.outcome.value,
                "skip_reason": (
                    None
                    if result.candidate.skip_reason is None
                    else result.candidate.skip_reason.value
                ),
                "error_type": result.error_type,
            }
            for result in report.results
        ],
    }


def format_text_report(report: RunReport) -> str:
    """Return a human-readable summary of ``report``.

    The text is built only from ``report_to_dict(report)``, so it cannot
    disagree with the structured report. Rates are shown as percentages
    rounded to two decimals; an undefined rate is shown as ``undefined``.
    The table lists every candidate in index order, with the skip reason or
    error type as its detail, and columns are padded by character count, so
    wide Unicode characters may not line up visually. Lines are separated by
    ``"\\n"`` without a trailing newline or trailing spaces.

    Raises:
        TypeError: If ``report`` is not a ``RunReport``.
    """
    data = report_to_dict(report)
    summary = data["summary"]
    mutants = data["mutants"]

    total = summary["total"]
    lines = [
        f"qmutate removal mutants: {total} candidate{'' if total == 1 else 's'}",
        f"killed {summary['killed']} | survived {summary['survived']} | "
        f"error {summary['errors']} | not run {summary['not_run']}",
    ]
    if summary["score"] is None:
        lines.append(
            "mutation score: undefined (no killed or survived mutants; "
            "error and not_run excluded)"
        )
    else:
        lines.append(
            f"mutation score: {summary['score'] * 100:.2f}% "
            f"({summary['killed']} of {summary['eligible']} killed; "
            "error and not_run excluded)"
        )
    if summary["error_rate"] is None:
        lines.append("error rate: undefined (no mutants executed)")
    else:
        lines.append(
            f"error rate: {summary['error_rate'] * 100:.2f}% "
            f"({summary['errors']} of {summary['executed']} executed)"
        )

    lines.append("")
    if mutants:
        rows = [("index", "instruction", "outcome", "detail")]
        for mutant in mutants:
            detail = mutant["skip_reason"] or mutant["error_type"] or ""
            rows.append((str(mutant["index"]), mutant["name"], mutant["outcome"], detail))
        widths = [max(len(row[column]) for row in rows) for column in range(4)]
        for row in rows:
            cells = [cell.ljust(width) for cell, width in zip(row, widths)]
            lines.append("  ".join(cells).rstrip())
    else:
        lines.append("No top-level instructions.")

    if summary["survived"]:
        lines.append("")
        lines.append(_SURVIVOR_NOTE)
    return "\n".join(lines)
