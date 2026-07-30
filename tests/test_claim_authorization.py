"""Structured claim authorization scopes (PR C / scientific integrity)."""

from __future__ import annotations

from datetime import UTC, datetime

from opencritique_evaluation.models import (
    BenchmarkCaseRef,
    BenchmarkEvidenceClass,
    BenchmarkManifest,
    ClaimScope,
    EvaluationMetrics,
    EvaluationResult,
    MetricValue,
    ReferenceCompleteness,
    SystemManifest,
)
from opencritique_evaluation.scorecard import build_scorecard


def _cases(n: int) -> list[BenchmarkCaseRef]:
    return [
        BenchmarkCaseRef(
            case_id=f"occase_claim_{i:03d}",
            case_version="1",
            path=f"cases/{i:03d}.json",
        )
        for i in range(n)
    ]


def _manifest(**overrides: object) -> BenchmarkManifest:
    base: dict[str, object] = {
        "benchmark_id": "ocbench_claim_auth",
        "version": "0.1.0",
        "title": "Claim authorization fixture",
        "description": "Unit fixture for claim_scope resolution",
        "evidence_class": BenchmarkEvidenceClass.EXPERT_NATURAL,
        "reference_completeness": ReferenceCompleteness.COMPLETE_SEEDED,
        "domain_profiles": ["physics"],
        "cases": _cases(40),
        "independent_evaluation": True,
        "expert_adjudicated": True,
        "minimum_public_claim_cases": 40,
        "rights_cleared_cases": True,
        "protected_holdout": True,
        "matcher_audit_complete": True,
        "frozen_scoring_policy": True,
        "signed_authorization_manifest_digest": "a" * 64,
        "signed_authorization_manifest_path": "governance/auth/test-manifest.json",
        "domain_scope": "physics.peer-review",
        "use_scope": "public-scientific-reporting",
        "comparative_authorization": False,
        "license": "Apache-2.0",
        "case_set_hash": "b" * 64,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "limitations": ["fixture"],
    }
    base.update(overrides)
    return BenchmarkManifest.model_validate(base)


def _metric() -> MetricValue:
    return MetricValue(value=None, withheld_reason="fixture")


def _result_for(manifest: BenchmarkManifest) -> EvaluationResult:
    auth = manifest.claim_authorization()
    return EvaluationResult(
        result_id="ocresult_claim_auth",
        benchmark=manifest,
        system=SystemManifest(
            system_id="sys_claim",
            version="0.0.1",
            display_name="Claim Auth System",
            configuration_hash="c" * 64,
        ),
        submission_id="ocsub_claim",
        matcher_version="opencritique-matcher-v0.2",
        case_evaluations=[],
        metrics=EvaluationMetrics(
            cases_total=0,
            cases_completed=0,
            cases_abstained=0,
            cases_failed=0,
            submitted_concerns=0,
            eligible_reference_concerns=0,
            matched_concerns=0,
            unmatched_submitted=0,
            missed_reference=0,
            anchor_resolution_rate=_metric(),
            precision=_metric(),
            recall=_metric(),
            severity_weighted_precision=_metric(),
            severity_weighted_recall=_metric(),
            false_critical_per_manuscript=_metric(),
            reference_match_brier_score=_metric(),
            novel_candidates_pending_adjudication=0,
        ),
        claim_authorization=auth,
        performance_claim_authorized=auth.performance_claim_authorized,
        claim_boundary="test boundary",
    )


def test_live_private_never_public_authorized() -> None:
    manifest = _manifest(
        evidence_class=BenchmarkEvidenceClass.LIVE_PRIVATE,
        expert_adjudicated=True,
        independent_evaluation=True,
        rights_cleared_cases=True,
        protected_holdout=True,
        matcher_audit_complete=True,
        frozen_scoring_policy=True,
        signed_authorization_manifest_digest="d" * 64,
        domain_scope="lab.private",
        use_scope="internal-method-report",
        comparative_authorization=True,
    )
    auth = manifest.claim_authorization()
    assert auth.claim_scope == ClaimScope.PRIVATE_METHOD_REPORT
    assert auth.performance_claim_authorized is False
    assert manifest.performance_claim_authorized() is False
    scorecard = build_scorecard(_result_for(manifest))
    assert "scientific scorecard" not in scorecard.headline
    assert "private method report" in scorecard.headline


def test_expert_natural_missing_public_prereq_stays_below_public() -> None:
    for field, value in (
        ("rights_cleared_cases", False),
        ("protected_holdout", False),
        ("independent_evaluation", False),
        ("matcher_audit_complete", False),
        ("frozen_scoring_policy", False),
        ("signed_authorization_manifest_digest", None),
        ("domain_scope", None),
        ("use_scope", None),
        ("expert_adjudicated", False),
    ):
        manifest = _manifest(**{field: value})
        auth = manifest.claim_authorization()
        assert auth.claim_scope == ClaimScope.NONE, field
        assert auth.performance_claim_authorized is False, field
        assert manifest.performance_claim_authorized() is False, field


def test_full_public_prereqs_yield_domain_bounded_and_scientific_headline() -> None:
    manifest = _manifest()
    auth = manifest.claim_authorization()
    assert auth.claim_scope == ClaimScope.PUBLIC_DOMAIN_BOUNDED
    assert auth.performance_claim_authorized is True
    assert manifest.performance_claim_authorized() is True
    scorecard = build_scorecard(_result_for(manifest))
    assert "independently evaluated scientific scorecard" in scorecard.headline
    assert scorecard.result.performance_claim_authorized is True
    assert scorecard.result.claim_authorization.claim_scope == (
        ClaimScope.PUBLIC_DOMAIN_BOUNDED
    )


def test_comparative_authorization_requires_full_public_prereqs() -> None:
    ready = _manifest(comparative_authorization=True)
    assert ready.claim_authorization().claim_scope == ClaimScope.PUBLIC_COMPARATIVE
    incomplete = _manifest(
        comparative_authorization=True,
        matcher_audit_complete=False,
    )
    assert incomplete.claim_authorization().claim_scope == ClaimScope.NONE


def test_under_minimum_case_count_blocks_public_scope() -> None:
    manifest = _manifest(cases=_cases(10), minimum_public_claim_cases=40)
    assert manifest.claim_authorization().claim_scope == ClaimScope.NONE
