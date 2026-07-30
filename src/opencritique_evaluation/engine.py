"""Deterministic evaluation orchestration for OpenCritique Commons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from opencritique_schema.models import Anchor, CaseBundle, Concern, Severity

from .matching import greedy_match, resolve_anchor
from .models import (
    AnchorResolution,
    AnchorResolutionStatus,
    BenchmarkManifest,
    CaseEvaluation,
    ClaimAuthorization,
    ClaimScope,
    EvaluationMetrics,
    EvaluationResult,
    EvaluationSubmission,
    MatcherConfig,
    MetricValue,
    ReferenceCompleteness,
    SubmittedConcern,
)
from .reference_policy import (
    EMPTY_GOLD_WITHHOLD_REASON,
    eligible_references,
    gold_weight,
)

MATCHER_VERSION = "opencritique-matcher-v0.2"

_INCOMPLETE_REFERENCE = frozenset(
    {
        ReferenceCompleteness.PARTIAL_NATURAL,
        ReferenceCompleteness.UNKNOWN,
    }
)

_SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.CRITICAL: 4.0,
    Severity.MAJOR: 3.0,
    Severity.MODERATE: 2.0,
    Severity.MINOR: 1.0,
    Severity.INFORMATIONAL: 0.5,
}


def load_manifest(path: Path) -> BenchmarkManifest:
    """Load and validate a frozen benchmark manifest."""
    return BenchmarkManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_case(benchmark_root: Path, relative_path: str) -> CaseBundle:
    """Load a case bundle relative to a benchmark root directory."""
    case_path = (benchmark_root / relative_path).resolve()
    root = benchmark_root.resolve()
    if not case_path.is_relative_to(root):
        raise ValueError(f"case path escapes benchmark root: {relative_path}")
    if not case_path.is_file():
        raise FileNotFoundError(f"case file not found: {case_path}")
    return CaseBundle.model_validate_json(case_path.read_text(encoding="utf-8"))


def _eligible_references(concerns: list[Concern]) -> list[Concern]:
    """Return gold-eligible references; empty stays empty (no non-gold fallback)."""
    return eligible_references(concerns)


def _severity_gold_weight(concern: Concern) -> float:
    return _SEVERITY_WEIGHT[concern.severity] * gold_weight(concern)


def _metric(numerator: float, denominator: float) -> MetricValue:
    if denominator <= 0:
        return MetricValue(
            value=None,
            numerator=numerator,
            denominator=denominator,
            withheld_reason="undefined: denominator is zero",
        )
    return MetricValue(
        value=round(numerator / denominator, 6),
        numerator=numerator,
        denominator=denominator,
    )


def _incomplete_withhold_reason(completeness: ReferenceCompleteness) -> str:
    return (
        "withheld: reference set is incomplete "
        f"({completeness.value}); unmatched submitted concerns are "
        "adjudication candidates, not automatic false positives"
    )


def _reference_recall_disclosure(completeness: ReferenceCompleteness) -> str:
    return (
        "reference recall only: gold reference set is incomplete "
        f"({completeness.value}); not true scientific recall"
    )


def _as_reference_recall(
    metric: MetricValue, completeness: ReferenceCompleteness
) -> MetricValue:
    disclosure = _reference_recall_disclosure(completeness)
    if metric.withheld_reason:
        reason = f"{metric.withheld_reason}; {disclosure}"
    else:
        reason = disclosure
    return metric.model_copy(update={"withheld_reason": reason})


def _withheld(
    reason: str,
    *,
    numerator: float | int | None = None,
    denominator: float | int | None = None,
) -> MetricValue:
    return MetricValue(
        value=None,
        numerator=numerator,
        denominator=denominator,
        withheld_reason=reason,
    )


def _resolve_submitted(
    submitted: SubmittedConcern,
    references: list[Concern],
    anchors_by_id: dict[str, Anchor],
) -> list[AnchorResolution]:
    reference_anchors = [
        anchors_by_id[anchor_id]
        for concern in references
        for anchor_id in concern.anchor_ids
        if anchor_id in anchors_by_id
    ]
    # Deduplicate while preserving order for deterministic resolution.
    seen: set[str] = set()
    unique_anchors: list[Anchor] = []
    for anchor in reference_anchors:
        if anchor.anchor_id in seen:
            continue
        seen.add(anchor.anchor_id)
        unique_anchors.append(anchor)
    if not unique_anchors:
        unique_anchors = list(anchors_by_id.values())

    resolutions: list[AnchorResolution] = []
    for index, submitted_anchor in enumerate(submitted.anchors):
        resolution = resolve_anchor(submitted_anchor, unique_anchors)
        resolutions.append(
            AnchorResolution(
                submitted_index=index,
                status=resolution.status,
                reference_anchor_ids=resolution.reference_anchor_ids,
            )
        )
    return resolutions


def _resolved_count(resolutions: list[AnchorResolution]) -> tuple[int, int]:
    total = len(resolutions)
    resolved = sum(
        1
        for item in resolutions
        if item.status
        in {
            AnchorResolutionStatus.EXACT,
            AnchorResolutionStatus.NORMALIZED,
            AnchorResolutionStatus.OBJECT_LABEL,
            AnchorResolutionStatus.PAGE_ONLY,
        }
    )
    return resolved, total


def _claim_boundary(
    benchmark: BenchmarkManifest, authorization: ClaimAuthorization
) -> str:
    scope = authorization.claim_scope
    if scope in {
        ClaimScope.PUBLIC_DOMAIN_BOUNDED,
        ClaimScope.PUBLIC_COMPARATIVE,
    }:
        return (
            "Performance claims are authorized under claim_scope="
            f"{scope.value}: evidence class {benchmark.evidence_class.value}, "
            f"domain_scope={authorization.domain_scope!r}, "
            f"use_scope={authorization.use_scope!r}, "
            f"independent evaluation={authorization.independent_evaluation}, "
            f"matcher_audit_complete={authorization.matcher_audit_complete}, "
            f"case count={len(benchmark.cases)}."
        )
    if scope == ClaimScope.PRIVATE_METHOD_REPORT:
        return (
            "Claim scope is private_method_report only. Private live / method-report "
            "evidence must not be framed as public scientific performance, precision, "
            "recall, or comparative reviewer-quality claims."
        )
    return (
        "Performance claims are not authorized. This record is an infrastructure or "
        "conformance evaluation only. Authorizing precision, recall, or comparative "
        "reviewer-quality statements requires EXPERT_NATURAL evidence, rights-cleared "
        "cases, protected holdout, independent evaluation, matcher-audit completion, "
        "frozen scoring policy, a signed authorization manifest, and explicit "
        "domain_scope and use_scope."
    )


def _result_id(
    *,
    benchmark: BenchmarkManifest,
    submission: EvaluationSubmission,
    matcher_config: MatcherConfig,
) -> str:
    material = json.dumps(
        {
            "benchmark_id": benchmark.benchmark_id,
            "benchmark_version": benchmark.version,
            "case_set_hash": benchmark.case_set_hash,
            "submission_id": submission.submission_id,
            "matcher_version": MATCHER_VERSION,
            "matcher_config": matcher_config.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"ocresult_{hashlib.sha256(material).hexdigest()[:24]}"


def evaluate(
    *,
    benchmark: BenchmarkManifest,
    benchmark_root: Path,
    submission: EvaluationSubmission,
    matcher_config: MatcherConfig | None = None,
) -> EvaluationResult:
    """Evaluate a frozen submission against a frozen benchmark."""
    config = matcher_config or MatcherConfig()
    if (
        submission.benchmark_id != benchmark.benchmark_id
        or submission.benchmark_version != benchmark.version
    ):
        raise ValueError("submission benchmark identity does not match the loaded manifest")

    benchmark_index = {(item.case_id, item.case_version): item for item in benchmark.cases}
    submission_index = {(item.case_id, item.case_version): item for item in submission.cases}
    unknown = set(submission_index) - set(benchmark_index)
    if unknown:
        raise ValueError(f"submission contains cases outside the benchmark: {sorted(unknown)}")

    case_evaluations: list[CaseEvaluation] = []
    submitted_concerns = 0
    eligible_reference_concerns = 0
    matched_concerns = 0
    unmatched_submitted = 0
    missed_reference = 0
    anchor_resolved = 0
    anchor_total = 0
    precision_weight_num = 0.0
    precision_weight_den = 0.0
    recall_weight_num = 0.0
    recall_weight_den = 0.0
    false_critical = 0
    completed_cases = 0
    abstained_cases = 0
    failed_cases = 0
    brier_sum = 0.0
    brier_count = 0

    for ref in benchmark.cases:
        key = (ref.case_id, ref.case_version)
        bundle = load_case(benchmark_root, ref.path)
        if (bundle.case_id, bundle.case_version) != key:
            raise ValueError(
                f"case identity mismatch for {ref.path}: "
                f"expected {key}, found {(bundle.case_id, bundle.case_version)}"
            )
        anchors_by_id = {item.anchor_id: item for item in bundle.anchors}
        eligible = _eligible_references(bundle.concerns)

        case_submission = submission_index.get(key)
        if case_submission is None or case_submission.abstained:
            abstained_cases += 1
            eligible_reference_concerns += len(eligible)
            missed_reference += len(eligible)
            recall_weight_den += sum(_severity_gold_weight(item) for item in eligible)
            case_evaluations.append(
                CaseEvaluation(
                    case_id=ref.case_id,
                    case_version=ref.case_version,
                    submitted_count=0,
                    eligible_reference_count=len(eligible),
                    matches=[],
                    unmatched_submitted_ids=[],
                    missed_reference_ids=[item.concern_id for item in eligible],
                    anchor_resolutions={},
                    abstained=True,
                    failure=None,
                )
            )
            continue

        if case_submission.failure:
            failed_cases += 1
            eligible_reference_concerns += len(eligible)
            missed_reference += len(eligible)
            recall_weight_den += sum(_severity_gold_weight(item) for item in eligible)
            case_evaluations.append(
                CaseEvaluation(
                    case_id=ref.case_id,
                    case_version=ref.case_version,
                    submitted_count=0,
                    eligible_reference_count=len(eligible),
                    matches=[],
                    unmatched_submitted_ids=[],
                    missed_reference_ids=[item.concern_id for item in eligible],
                    anchor_resolutions={},
                    abstained=False,
                    failure=case_submission.failure,
                )
            )
            continue

        completed_cases += 1
        resolutions: dict[str, list[AnchorResolution]] = {}
        for submitted in case_submission.concerns:
            resolutions[submitted.local_id] = _resolve_submitted(
                submitted, eligible, anchors_by_id
            )
            resolved, total = _resolved_count(resolutions[submitted.local_id])
            anchor_resolved += resolved
            anchor_total += total

        matches = greedy_match(
            case_submission.concerns,
            eligible,
            resolutions,
            config,
        )
        matched_submitted = {item.submitted_local_id for item in matches}
        matched_reference = {item.reference_concern_id for item in matches}
        unmatched_ids = [
            item.local_id
            for item in case_submission.concerns
            if item.local_id not in matched_submitted
        ]
        missed_ids = [
            item.concern_id for item in eligible if item.concern_id not in matched_reference
        ]

        submitted_concerns += len(case_submission.concerns)
        eligible_reference_concerns += len(eligible)
        matched_concerns += len(matches)
        unmatched_submitted += len(unmatched_ids)
        missed_reference += len(missed_ids)

        for submitted in case_submission.concerns:
            # Precision-family and Brier only score against complete reference sets;
            # on partial/unknown, unmatched submitted are adjudication candidates.
            if benchmark.reference_completeness != ReferenceCompleteness.COMPLETE_SEEDED:
                continue
            weight = _SEVERITY_WEIGHT[submitted.severity]
            outcome = 1.0 if submitted.local_id in matched_submitted else 0.0
            precision_weight_den += weight
            if submitted.local_id in matched_submitted:
                precision_weight_num += weight
            elif submitted.severity == Severity.CRITICAL:
                false_critical += 1
            brier_sum += (submitted.confidence - outcome) ** 2
            brier_count += 1

        for concern in eligible:
            weight = _severity_gold_weight(concern)
            recall_weight_den += weight
            if concern.concern_id in matched_reference:
                recall_weight_num += weight

        case_evaluations.append(
            CaseEvaluation(
                case_id=ref.case_id,
                case_version=ref.case_version,
                submitted_count=len(case_submission.concerns),
                eligible_reference_count=len(eligible),
                matches=matches,
                unmatched_submitted_ids=unmatched_ids,
                missed_reference_ids=missed_ids,
                anchor_resolutions=resolutions,
                abstained=False,
                failure=None,
            )
        )

    authorization = benchmark.claim_authorization()
    completeness = benchmark.reference_completeness
    incomplete = completeness in _INCOMPLETE_REFERENCE
    empty_gold = eligible_reference_concerns == 0
    withhold_reason = _incomplete_withhold_reason(completeness) if incomplete else None

    if empty_gold:
        # Fail-closed: never fall back to non-gold concerns for denominators.
        precision = _withheld(
            EMPTY_GOLD_WITHHOLD_REASON,
            numerator=float(matched_concerns),
            denominator=float(submitted_concerns),
        )
        severity_weighted_precision = _withheld(
            EMPTY_GOLD_WITHHOLD_REASON,
            numerator=precision_weight_num,
            denominator=precision_weight_den,
        )
        false_critical_metric = _withheld(
            EMPTY_GOLD_WITHHOLD_REASON,
            numerator=float(false_critical),
            denominator=float(max(completed_cases, 0)),
        )
        brier_metric = _withheld(EMPTY_GOLD_WITHHOLD_REASON)
        recall = _withheld(
            EMPTY_GOLD_WITHHOLD_REASON,
            numerator=float(matched_concerns),
            denominator=float(eligible_reference_concerns),
        )
        severity_weighted_recall = _withheld(
            EMPTY_GOLD_WITHHOLD_REASON,
            numerator=recall_weight_num,
            denominator=recall_weight_den,
        )
        if incomplete:
            recall = _as_reference_recall(recall, completeness)
            severity_weighted_recall = _as_reference_recall(
                severity_weighted_recall, completeness
            )
    elif incomplete:
        precision = _withheld(
            withhold_reason or "",
            numerator=float(matched_concerns),
            denominator=float(submitted_concerns),
        )
        severity_weighted_precision = _withheld(
            withhold_reason or "",
            numerator=precision_weight_num,
            denominator=precision_weight_den,
        )
        false_critical_metric = _withheld(
            withhold_reason or "",
            numerator=float(false_critical),
            denominator=float(max(completed_cases, 0)),
        )
        brier_metric = _withheld(withhold_reason or "")
        recall = _as_reference_recall(
            _metric(float(matched_concerns), float(eligible_reference_concerns)),
            completeness,
        )
        severity_weighted_recall = _as_reference_recall(
            _metric(recall_weight_num, recall_weight_den),
            completeness,
        )
    else:
        precision = _metric(float(matched_concerns), float(submitted_concerns))
        severity_weighted_precision = _metric(precision_weight_num, precision_weight_den)
        false_critical_metric = _metric(
            float(false_critical), float(max(completed_cases, 0))
        )
        brier_metric = (
            MetricValue(
                value=round(brier_sum / brier_count, 6),
                numerator=brier_sum,
                denominator=float(brier_count),
            )
            if brier_count
            else MetricValue(
                value=None,
                numerator=0,
                denominator=0,
                withheld_reason="undefined: no scored submitted concerns",
            )
        )
        recall = _metric(float(matched_concerns), float(eligible_reference_concerns))
        severity_weighted_recall = _metric(recall_weight_num, recall_weight_den)

    metrics = EvaluationMetrics(
        cases_total=len(benchmark.cases),
        cases_completed=completed_cases,
        cases_abstained=abstained_cases,
        cases_failed=failed_cases,
        submitted_concerns=submitted_concerns,
        eligible_reference_concerns=eligible_reference_concerns,
        matched_concerns=matched_concerns,
        unmatched_submitted=unmatched_submitted,
        missed_reference=missed_reference,
        anchor_resolution_rate=_metric(float(anchor_resolved), float(anchor_total)),
        precision=precision,
        recall=recall,
        severity_weighted_precision=severity_weighted_precision,
        severity_weighted_recall=severity_weighted_recall,
        false_critical_per_manuscript=false_critical_metric,
        reference_match_brier_score=brier_metric,
        novel_candidates_pending_adjudication=unmatched_submitted,
    )
    return EvaluationResult(
        result_id=_result_id(
            benchmark=benchmark, submission=submission, matcher_config=config
        ),
        benchmark=benchmark,
        system=submission.system,
        submission_id=submission.submission_id,
        matcher_version=MATCHER_VERSION,
        matcher_config=config,
        case_evaluations=case_evaluations,
        metrics=metrics,
        claim_authorization=authorization,
        performance_claim_authorized=authorization.performance_claim_authorized,
        claim_boundary=_claim_boundary(benchmark, authorization),
    )
