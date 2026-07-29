from __future__ import annotations

from collections import Counter

from .models import Adjudication, ConcernStatus, Severity, ValidityDecision

_SEVERITY_ORDER = {
    Severity.INFORMATIONAL: 0,
    Severity.MINOR: 1,
    Severity.MODERATE: 2,
    Severity.MAJOR: 3,
    Severity.CRITICAL: 4,
}


def determine_status(adjudications: list[Adjudication]) -> ConcernStatus:
    """Apply adjudication-policy-v0.1 to a completed adjudication set.

    Two agreeing primary decisions determine the status. Confirmed/qualified and
    qualified/qualified yield qualified. Confirmed/rejected and rejected/qualified
    require a tie-break; if no third decision is present, the result is unresolved.
    """
    if len(adjudications) < 2:
        return ConcernStatus.UNDER_REVIEW
    decisions = [item.validity for item in adjudications]
    counts = Counter(decisions)
    for decision, count in counts.items():
        if count >= 2:
            return ConcernStatus(decision.value)
    first_two = set(decisions[:2])
    if first_two == {ValidityDecision.CONFIRMED, ValidityDecision.QUALIFIED}:
        return ConcernStatus.QUALIFIED
    if len(adjudications) >= 3:
        return ConcernStatus(adjudications[-1].validity.value)
    return ConcernStatus.UNRESOLVED


def conservative_severity(adjudications: list[Adjudication]) -> Severity | None:
    if not adjudications:
        return None
    severities = [item.severity for item in adjudications]
    if len(set(severities)) == 1:
        return severities[0]
    ordered = sorted(severities, key=lambda s: _SEVERITY_ORDER[s])
    if _SEVERITY_ORDER[ordered[-1]] - _SEVERITY_ORDER[ordered[0]] <= 1:
        return ordered[0]
    return None
