"""Per-metric claim authorization (PR 45).

``ClaimAuthorizationDecision.authorized_metrics`` is authoritative. Completeness
gates and the hard ``partial_natural`` / precision-calibration invariant are
applied when deriving the effective metric permissions used by scorecards.
"""

from __future__ import annotations

from .models import (
    AuthorizedMetric,
    ClaimMetricId,
    CompletenessRequirement,
    MetricAuthStatus,
    MetricValue,
    ReferenceCompleteness,
)

# Scientific performance families (cost/latency are operational, not scientific).
SCIENTIFIC_METRIC_IDS: frozenset[ClaimMetricId] = frozenset(
    {
        ClaimMetricId.ANCHOR_INTEGRITY,
        ClaimMetricId.SEEDED_DEFECT_RECALL,
        ClaimMetricId.REFERENCE_RECALL,
        ClaimMetricId.CRITICAL_PRECISION,
        ClaimMetricId.MAJOR_PRECISION,
        ClaimMetricId.CALIBRATION,
        ClaimMetricId.FALSE_CRITICAL_RATE,
    }
)

PRECISION_CALIBRATION_METRIC_IDS: frozenset[ClaimMetricId] = frozenset(
    {
        ClaimMetricId.CRITICAL_PRECISION,
        ClaimMetricId.MAJOR_PRECISION,
        ClaimMetricId.CALIBRATION,
        ClaimMetricId.FALSE_CRITICAL_RATE,
    }
)

# Reference sets that are complete enough for precision / calibration claims.
COMPLETE_FOR_PRECISION: frozenset[ReferenceCompleteness] = frozenset(
    {
        ReferenceCompleteness.COMPLETE_SEEDED,
        ReferenceCompleteness.ADJUDICATED_OUTPUT_COMPLETE,
    }
)

INCOMPLETE_REFERENCE: frozenset[ReferenceCompleteness] = frozenset(
    {
        ReferenceCompleteness.PARTIAL_NATURAL,
        ReferenceCompleteness.DISCOVERY_OPEN,
        ReferenceCompleteness.UNKNOWN,
    }
)

# Completeness levels that may never authorize precision/calibration families.
PRECISION_FORBIDDEN_COMPLETENESS: frozenset[ReferenceCompleteness] = frozenset(
    {
        ReferenceCompleteness.PARTIAL_NATURAL,
        ReferenceCompleteness.DISCOVERY_OPEN,
        ReferenceCompleteness.UNKNOWN,
    }
)

_REQUIREMENT_SATISFIED_BY: dict[CompletenessRequirement, frozenset[ReferenceCompleteness]] = {
    CompletenessRequirement.ANY: frozenset(ReferenceCompleteness),
    CompletenessRequirement.COMPLETE_SEEDED: frozenset(
        {ReferenceCompleteness.COMPLETE_SEEDED}
    ),
    CompletenessRequirement.ADJUDICATED_OUTPUT_COMPLETE: frozenset(
        {
            ReferenceCompleteness.COMPLETE_SEEDED,
            ReferenceCompleteness.ADJUDICATED_OUTPUT_COMPLETE,
        }
    ),
    CompletenessRequirement.PARTIAL_NATURAL: frozenset(
        {
            ReferenceCompleteness.COMPLETE_SEEDED,
            ReferenceCompleteness.ADJUDICATED_OUTPUT_COMPLETE,
            ReferenceCompleteness.PARTIAL_NATURAL,
        }
    ),
    CompletenessRequirement.DISCOVERY_OPEN: frozenset(
        {
            ReferenceCompleteness.COMPLETE_SEEDED,
            ReferenceCompleteness.ADJUDICATED_OUTPUT_COMPLETE,
            ReferenceCompleteness.PARTIAL_NATURAL,
            ReferenceCompleteness.DISCOVERY_OPEN,
        }
    ),
}


def completeness_satisfies(
    actual: ReferenceCompleteness,
    requirement: CompletenessRequirement,
) -> bool:
    return actual in _REQUIREMENT_SATISFIED_BY[requirement]


def is_scientific_metric(metric_id: ClaimMetricId) -> bool:
    return metric_id in SCIENTIFIC_METRIC_IDS


def any_scientific_metric_authorized(metrics: list[AuthorizedMetric]) -> bool:
    return any(
        item.status == MetricAuthStatus.AUTHORIZED and is_scientific_metric(item.metric_id)
        for item in metrics
    )


def metric_status_map(
    metrics: list[AuthorizedMetric],
) -> dict[ClaimMetricId, AuthorizedMetric]:
    """Last entry wins for duplicate metric_id (defensive)."""
    return {item.metric_id: item for item in metrics}


def lookup_metric_auth(
    metrics: list[AuthorizedMetric],
    metric_id: ClaimMetricId,
) -> AuthorizedMetric | None:
    return metric_status_map(metrics).get(metric_id)


def metric_is_authorized(
    metrics: list[AuthorizedMetric],
    metric_id: ClaimMetricId,
) -> bool:
    entry = lookup_metric_auth(metrics, metric_id)
    return entry is not None and entry.status == MetricAuthStatus.AUTHORIZED


def recall_metric_id(completeness: ReferenceCompleteness) -> ClaimMetricId:
    if completeness in COMPLETE_FOR_PRECISION:
        return ClaimMetricId.SEEDED_DEFECT_RECALL
    return ClaimMetricId.REFERENCE_RECALL


def resolve_authorized_metrics(
    declared: list[AuthorizedMetric],
    *,
    reference_completeness: ReferenceCompleteness,
) -> list[AuthorizedMetric]:
    """Apply completeness gates and the precision/calibration invariant.

    Hard rule: ``partial_natural`` / ``discovery_open`` / ``unknown`` must not
    leave precision or calibration families as ``authorized``, regardless of the
    signed declaration.
    """
    resolved: list[AuthorizedMetric] = []
    for item in declared:
        limitations = list(item.limitations)
        status = item.status

        if status == MetricAuthStatus.AUTHORIZED:
            if not completeness_satisfies(
                reference_completeness, item.completeness_requirement
            ):
                status = MetricAuthStatus.WITHHELD
                limitations.append(
                    "withheld: benchmark reference_completeness "
                    f"({reference_completeness.value}) does not satisfy "
                    f"completeness_requirement ({item.completeness_requirement.value})"
                )

            if (
                item.metric_id in PRECISION_CALIBRATION_METRIC_IDS
                and reference_completeness in PRECISION_FORBIDDEN_COMPLETENESS
            ):
                status = MetricAuthStatus.WITHHELD
                limitations.append(
                    "withheld: precision/calibration families cannot be authorized "
                    f"when reference_completeness is {reference_completeness.value}"
                )

        resolved.append(
            item.model_copy(update={"status": status, "limitations": limitations})
        )
    return resolved


def withhold_metric_value(
    metric: MetricValue,
    *,
    reason: str,
) -> MetricValue:
    if metric.value is None and metric.withheld_reason:
        if reason in metric.withheld_reason:
            return metric
        return metric.model_copy(
            update={"withheld_reason": f"{metric.withheld_reason}; {reason}"}
        )
    return MetricValue(
        value=None,
        numerator=metric.numerator,
        denominator=metric.denominator,
        withheld_reason=reason,
    )


def default_authorized_metrics_for_completeness(
    completeness: ReferenceCompleteness,
    *,
    domain_scope: str | None = None,
    system_version: str | None = None,
) -> list[AuthorizedMetric]:
    """Convenience builder for tests / ceremony tooling (not auto-granted)."""
    if completeness in COMPLETE_FOR_PRECISION:
        req = (
            CompletenessRequirement.COMPLETE_SEEDED
            if completeness == ReferenceCompleteness.COMPLETE_SEEDED
            else CompletenessRequirement.ADJUDICATED_OUTPUT_COMPLETE
        )
        return [
            AuthorizedMetric(
                metric_id=ClaimMetricId.ANCHOR_INTEGRITY,
                status=MetricAuthStatus.AUTHORIZED,
                completeness_requirement=req,
                domain_scope=domain_scope,
                system_version=system_version,
            ),
            AuthorizedMetric(
                metric_id=ClaimMetricId.SEEDED_DEFECT_RECALL,
                status=MetricAuthStatus.AUTHORIZED,
                completeness_requirement=req,
                domain_scope=domain_scope,
                system_version=system_version,
            ),
            AuthorizedMetric(
                metric_id=ClaimMetricId.CRITICAL_PRECISION,
                status=MetricAuthStatus.AUTHORIZED,
                completeness_requirement=req,
                domain_scope=domain_scope,
                system_version=system_version,
            ),
            AuthorizedMetric(
                metric_id=ClaimMetricId.MAJOR_PRECISION,
                status=MetricAuthStatus.AUTHORIZED,
                completeness_requirement=req,
                domain_scope=domain_scope,
                system_version=system_version,
            ),
            AuthorizedMetric(
                metric_id=ClaimMetricId.CALIBRATION,
                status=MetricAuthStatus.AUTHORIZED,
                completeness_requirement=req,
                domain_scope=domain_scope,
                system_version=system_version,
            ),
            AuthorizedMetric(
                metric_id=ClaimMetricId.FALSE_CRITICAL_RATE,
                status=MetricAuthStatus.AUTHORIZED,
                completeness_requirement=req,
                domain_scope=domain_scope,
                system_version=system_version,
            ),
            AuthorizedMetric(
                metric_id=ClaimMetricId.REFERENCE_RECALL,
                status=MetricAuthStatus.NOT_APPLICABLE,
                completeness_requirement=CompletenessRequirement.PARTIAL_NATURAL,
                limitations=["not applicable on complete reference sets"],
                domain_scope=domain_scope,
                system_version=system_version,
            ),
        ]
    # Incomplete: recall-family only; precision/calibration withheld.
    withheld_limit = [f"withheld under reference_completeness={completeness.value}"]
    return [
        AuthorizedMetric(
            metric_id=ClaimMetricId.ANCHOR_INTEGRITY,
            status=MetricAuthStatus.AUTHORIZED,
            completeness_requirement=CompletenessRequirement.ANY,
            domain_scope=domain_scope,
            system_version=system_version,
        ),
        AuthorizedMetric(
            metric_id=ClaimMetricId.REFERENCE_RECALL,
            status=MetricAuthStatus.AUTHORIZED,
            completeness_requirement=CompletenessRequirement.PARTIAL_NATURAL,
            domain_scope=domain_scope,
            system_version=system_version,
        ),
        AuthorizedMetric(
            metric_id=ClaimMetricId.SEEDED_DEFECT_RECALL,
            status=MetricAuthStatus.NOT_APPLICABLE,
            completeness_requirement=CompletenessRequirement.COMPLETE_SEEDED,
            limitations=["seeded defect recall requires a complete seeded set"],
            domain_scope=domain_scope,
            system_version=system_version,
        ),
        AuthorizedMetric(
            metric_id=ClaimMetricId.CRITICAL_PRECISION,
            status=MetricAuthStatus.WITHHELD,
            completeness_requirement=CompletenessRequirement.ADJUDICATED_OUTPUT_COMPLETE,
            limitations=withheld_limit,
            domain_scope=domain_scope,
            system_version=system_version,
        ),
        AuthorizedMetric(
            metric_id=ClaimMetricId.MAJOR_PRECISION,
            status=MetricAuthStatus.WITHHELD,
            completeness_requirement=CompletenessRequirement.ADJUDICATED_OUTPUT_COMPLETE,
            limitations=withheld_limit,
            domain_scope=domain_scope,
            system_version=system_version,
        ),
        AuthorizedMetric(
            metric_id=ClaimMetricId.CALIBRATION,
            status=MetricAuthStatus.WITHHELD,
            completeness_requirement=CompletenessRequirement.ADJUDICATED_OUTPUT_COMPLETE,
            limitations=withheld_limit,
            domain_scope=domain_scope,
            system_version=system_version,
        ),
        AuthorizedMetric(
            metric_id=ClaimMetricId.FALSE_CRITICAL_RATE,
            status=MetricAuthStatus.WITHHELD,
            completeness_requirement=CompletenessRequirement.ADJUDICATED_OUTPUT_COMPLETE,
            limitations=withheld_limit,
            domain_scope=domain_scope,
            system_version=system_version,
        ),
    ]
