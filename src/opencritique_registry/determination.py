from __future__ import annotations

from dataclasses import dataclass

from opencritique_schema.models import Adjudication, ConcernStatus, Severity, ValidityDecision

from .schemas import TaskSlot

SEVERITY_ORDER = {
    Severity.INFORMATIONAL: 0,
    Severity.MINOR: 1,
    Severity.MODERATE: 2,
    Severity.MAJOR: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True)
class PolicyResult:
    status: ConcernStatus
    severity: Severity | None
    requires_tie_break: bool
    rationale: str


def _validity_from_two(
    left: ValidityDecision, right: ValidityDecision
) -> tuple[ConcernStatus, bool, str]:
    if left == right:
        return ConcernStatus(left.value), False, "The two primary adjudicators agree on validity."
    pair = {left, right}
    if pair == {ValidityDecision.CONFIRMED, ValidityDecision.QUALIFIED}:
        return (
            ConcernStatus.QUALIFIED,
            False,
            "Confirmed and qualified resolve conservatively to qualified.",
        )
    return (
        ConcernStatus.UNDER_REVIEW,
        True,
        "The primary validity decisions require tie-break adjudication.",
    )


def _severity_from_two(left: Severity, right: Severity) -> tuple[Severity | None, bool, str]:
    if left == right:
        return left, False, "The two primary adjudicators agree on severity."
    gap = abs(SEVERITY_ORDER[left] - SEVERITY_ORDER[right])
    if Severity.CRITICAL in {left, right}:
        return None, True, "Any contested critical classification requires tie-break adjudication."
    if gap <= 1:
        lower = min((left, right), key=lambda s: SEVERITY_ORDER[s])
        return lower, False, "Adjacent severity decisions resolve to the lower severity."
    return (
        None,
        True,
        "Severity decisions separated by two or more levels require tie-break adjudication.",
    )


def determine(
    submissions: list[tuple[TaskSlot, Adjudication]],
) -> PolicyResult:
    primaries = [
        item
        for slot, item in submissions
        if slot in {TaskSlot.PRIMARY, TaskSlot.SECONDARY}
    ]
    ties = [item for slot, item in submissions if slot == TaskSlot.TIE_BREAK]
    if len(primaries) < 2:
        return PolicyResult(
            status=ConcernStatus.UNDER_REVIEW,
            severity=None,
            requires_tie_break=False,
            rationale="Two independent primary adjudications have not been completed.",
        )

    validity_status, validity_tie, validity_reason = _validity_from_two(
        primaries[0].validity, primaries[1].validity
    )
    severity, severity_tie, severity_reason = _severity_from_two(
        primaries[0].severity, primaries[1].severity
    )
    tie_required = validity_tie or severity_tie
    if tie_required and not ties:
        return PolicyResult(
            status=ConcernStatus.UNDER_REVIEW,
            severity=None if severity_tie else severity,
            requires_tie_break=True,
            rationale=f"{validity_reason} {severity_reason}",
        )
    if tie_required and ties:
        tie = ties[-1]
        return PolicyResult(
            status=ConcernStatus(tie.validity.value),
            severity=tie.severity,
            requires_tie_break=False,
            rationale=(
                f"Tie-break adjudication controls the contested dimensions. "
                f"Primary validity: {validity_reason} Primary severity: {severity_reason}"
            ),
        )
    return PolicyResult(
        status=validity_status,
        severity=severity,
        requires_tie_break=False,
        rationale=f"{validity_reason} {severity_reason}",
    )
