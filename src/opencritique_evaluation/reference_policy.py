"""Benchmark reference eligibility policy for scientific performance denominators.

Only adjudicated gold enters precision/recall denominators. This module is the
single source of truth for that filter and for policy-controlled gold weights.

Default scientific gold positives
---------------------------------
- ``CONFIRMED`` — weight 1.0
- ``QUALIFIED`` — weight 1.0 (weights are policy-controlled and may change)
- ``RESOLVED`` with ``resolution_disposition=manuscript_correction`` — weight 1.0
  (historical defect that was fixed in the manuscript)

Outside performance denominators
--------------------------------
- ``PROPOSED``, ``UNDER_REVIEW``, ``UNRESOLVED``
- ``REJECTED``, ``SUPERSEDED``
- ``RESOLVED`` with ``withdrawn`` / ``rejected`` disposition
- ``RESOLVED`` without a disposition (fail-closed until disposition is set)

Alignment
---------
Novel successor admission via
:func:`opencritique_evaluation.novel_determination.outcome_affects_precision_recall`
is CONFIRMED/QUALIFIED-oriented; this policy uses the same orientation for
live reference concerns, plus the resolved historical-defect split.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from opencritique_schema.models import Concern, ConcernStatus, ResolutionDisposition

# Statuses that are never gold positives under the default scientific policy.
NON_GOLD_STATUSES: frozenset[ConcernStatus] = frozenset(
    {
        ConcernStatus.PROPOSED,
        ConcernStatus.UNDER_REVIEW,
        ConcernStatus.UNRESOLVED,
        ConcernStatus.REJECTED,
        ConcernStatus.SUPERSEDED,
    }
)

# Adjudicated gold statuses with policy-controlled weights (initially 1.0).
DEFAULT_GOLD_STATUS_WEIGHTS: Mapping[ConcernStatus, float] = {
    ConcernStatus.CONFIRMED: 1.0,
    ConcernStatus.QUALIFIED: 1.0,
}

# RESOLVED concerns enter gold only with an explicit correction disposition.
RESOLVED_GOLD_DISPOSITIONS: frozenset[ResolutionDisposition] = frozenset(
    {
        ResolutionDisposition.MANUSCRIPT_CORRECTION,
    }
)

RESOLVED_NON_GOLD_DISPOSITIONS: frozenset[ResolutionDisposition] = frozenset(
    {
        ResolutionDisposition.WITHDRAWN,
        ResolutionDisposition.REJECTED,
    }
)

# Weight for eligible historical defects (RESOLVED + manuscript_correction).
RESOLVED_GOLD_WEIGHT: float = 1.0

EMPTY_GOLD_WITHHOLD_REASON = (
    "withheld: no eligible gold references under benchmark reference "
    "eligibility policy (confirmed/qualified, or resolved with "
    "manuscript_correction disposition); empty eligible set does not fall "
    "back to non-gold concerns"
)


def is_eligible_gold_reference(concern: Concern) -> bool:
    """Return whether a concern enters scientific performance denominators."""
    if concern.status in DEFAULT_GOLD_STATUS_WEIGHTS:
        return True
    if concern.status == ConcernStatus.RESOLVED:
        disposition = concern.resolution_disposition
        # Fail-closed: RESOLVED without disposition is not gold.
        return disposition in RESOLVED_GOLD_DISPOSITIONS
    return False


def gold_weight(concern: Concern) -> float:
    """Return the policy weight for an eligible gold concern.

    Raises ``ValueError`` if the concern is not eligible. Weights are
    policy-controlled; CONFIRMED and QUALIFIED are currently both 1.0.
    """
    if concern.status in DEFAULT_GOLD_STATUS_WEIGHTS:
        return float(DEFAULT_GOLD_STATUS_WEIGHTS[concern.status])
    if (
        concern.status == ConcernStatus.RESOLVED
        and concern.resolution_disposition in RESOLVED_GOLD_DISPOSITIONS
    ):
        return RESOLVED_GOLD_WEIGHT
    raise ValueError(
        f"concern {concern.concern_id} is not an eligible gold reference "
        f"(status={concern.status.value}, "
        f"disposition={concern.resolution_disposition})"
    )


def eligible_references(concerns: Iterable[Concern]) -> list[Concern]:
    """Filter concerns to the eligible gold set.

    Unlike the pre-policy engine fallback, an empty result stays empty: callers
    must withhold recall/precision rather than re-admit non-gold concerns.
    """
    return [item for item in concerns if is_eligible_gold_reference(item)]
