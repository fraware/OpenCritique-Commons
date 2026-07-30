"""Verified claim-authorization envelopes (PR 41 / fail-closed)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from opencritique_evaluation.claim_auth_verify import (
    DEFAULT_MATCHER_VERSION,
    build_claim_authorization_decision,
    envelope_content_digest,
    sign_claim_authorization_decision,
    verify_claim_authorization,
)
from opencritique_evaluation.models import (
    BenchmarkCaseRef,
    BenchmarkEvidenceClass,
    BenchmarkManifest,
    ClaimAuthorization,
    ClaimScope,
    EvaluationMetrics,
    EvaluationResult,
    MatcherConfig,
    MetricValue,
    ReferenceCompleteness,
    SystemManifest,
)
from opencritique_evaluation.scorecard import build_scorecard
from opencritique_evaluation.signing import generate_keypair
from opencritique_evaluation.trust import (
    KeyRole,
    KeyStatus,
    RevocationRecord,
    TrustPolicyMode,
    TrustStore,
    VerificationFailureReason,
    build_trusted_key_record,
    write_trust_store,
)


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


def _metrics() -> EvaluationMetrics:
    return EvaluationMetrics(
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
    )


def _result_for(
    manifest: BenchmarkManifest,
    *,
    auth: ClaimAuthorization | None = None,
    envelope=None,
) -> EvaluationResult:
    resolved = auth if auth is not None else manifest.claim_authorization()
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
        matcher_version=DEFAULT_MATCHER_VERSION,
        case_evaluations=[],
        metrics=_metrics(),
        claim_authorization=resolved,
        claim_authorization_envelope=envelope,
        performance_claim_authorized=resolved.performance_claim_authorized,
        claim_boundary="test boundary",
    )


def _issue_envelope(
    tmp_path: Path,
    manifest: BenchmarkManifest,
    *,
    claim_scope: ClaimScope = ClaimScope.PUBLIC_DOMAIN_BOUNDED,
    role: KeyRole = KeyRole.TEST,
    channels: list[str] | None = None,
    issued_at: datetime | None = None,
    not_after: datetime | None = None,
    case_set_hash: str | None = None,
    revoke: bool = False,
) -> tuple:
    priv = tmp_path / "claim_auth.pem"
    pub = tmp_path / "claim_auth.pub.pem"
    generate_keypair(priv, pub)
    now = datetime.now(UTC)
    issued = issued_at or (now - timedelta(hours=1))
    expires = not_after or (now + timedelta(days=30))
    rec = build_trusted_key_record(
        public_key_path=pub,
        role=role,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=365),
        channels=channels or ["development", "test"],
        notes="ephemeral claim-auth test key",
    )
    store = TrustStore(
        store_id="oc-claim-auth-test",
        keys=[rec],
        revocations=(
            [
                RevocationRecord(
                    revocation_id="rev-1",
                    key_id=rec.key_id,
                    revoked_at=now,
                    reason="test revocation",
                )
            ]
            if revoke
            else []
        ),
        published_channels=["test"],
    )
    store_path = tmp_path / "claim-trust-store.json"
    write_trust_store(store, store_path)

    decision_manifest = manifest
    if case_set_hash is not None:
        decision_manifest = manifest.model_copy(update={"case_set_hash": case_set_hash})

    decision = build_claim_authorization_decision(
        claim_scope=claim_scope,
        benchmark=decision_manifest,
        matcher_version=DEFAULT_MATCHER_VERSION,
        matcher_config=MatcherConfig(),
        authority_id=rec.key_id,
        issued_at=issued,
        not_after=expires,
    )
    # Decision must bind to the *live* benchmark hashes; when forging a wrong
    # case_set_hash we keep the decision's case_set_hash as the forged value.
    if case_set_hash is not None:
        decision = decision.model_copy(update={"case_set_hash": case_set_hash})

    envelope = sign_claim_authorization_decision(
        decision, priv, key_id_override=rec.key_id
    )
    digest = envelope_content_digest(envelope)
    envelope_path = tmp_path / "claim-auth-envelope.json"
    envelope_path.write_text(envelope.model_dump_json(indent=2) + "\n", encoding="utf-8")
    live = manifest.model_copy(
        update={
            "signed_authorization_manifest_digest": digest,
            "signed_authorization_manifest_path": str(envelope_path),
        }
    )
    return live, envelope, store, store_path, rec


def test_forged_digest_alone_does_not_authorize_public() -> None:
    """Break the historical fixture pattern: ``"a"*64`` is not authorization."""
    manifest = _manifest(
        signed_authorization_manifest_digest="a" * 64,
        signed_authorization_manifest_path="governance/auth/missing.json",
    )
    auth = manifest.claim_authorization()
    assert auth.claim_scope == ClaimScope.NONE
    assert auth.performance_claim_authorized is False
    assert auth.authorization_verified is False
    scorecard = build_scorecard(_result_for(manifest))
    assert "scientific scorecard" not in scorecard.headline
    assert "non-performance" in scorecard.headline


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
        ("domain_scope", None),
        ("use_scope", None),
        ("expert_adjudicated", False),
    ):
        manifest = _manifest(**{field: value})
        auth = manifest.claim_authorization()
        assert auth.claim_scope == ClaimScope.NONE, field
        assert auth.performance_claim_authorized is False, field


def test_valid_test_key_envelope_authorizes_under_development_policy(
    tmp_path: Path,
) -> None:
    live, envelope, store, _store_path, _rec = _issue_envelope(tmp_path, _manifest())
    auth = live.claim_authorization(
        envelope=envelope,
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert auth.claim_scope == ClaimScope.PUBLIC_DOMAIN_BOUNDED
    assert auth.authorization_verified is True
    assert auth.performance_claim_authorized is True

    result = _result_for(live, auth=auth, envelope=envelope)
    scorecard = build_scorecard(
        result,
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert "independently evaluated scientific scorecard" in scorecard.headline
    assert scorecard.result.performance_claim_authorized is True


def test_comparative_requires_verified_envelope_and_manifest_flag(
    tmp_path: Path,
) -> None:
    ready_manifest = _manifest(comparative_authorization=True)
    live, envelope, store, _, _ = _issue_envelope(
        tmp_path,
        ready_manifest,
        claim_scope=ClaimScope.PUBLIC_COMPARATIVE,
    )
    auth = live.claim_authorization(
        envelope=envelope,
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert auth.claim_scope == ClaimScope.PUBLIC_COMPARATIVE

    incomplete = _manifest(
        comparative_authorization=True,
        matcher_audit_complete=False,
    )
    assert incomplete.claim_authorization().claim_scope == ClaimScope.NONE


def test_under_minimum_case_count_blocks_public_scope() -> None:
    manifest = _manifest(cases=_cases(10), minimum_public_claim_cases=40)
    assert manifest.claim_authorization().claim_scope == ClaimScope.NONE


def test_binding_mismatch_case_set_hash_fails(tmp_path: Path) -> None:
    live, envelope, store, _, _ = _issue_envelope(
        tmp_path,
        _manifest(),
        case_set_hash="f" * 64,
    )
    # Live manifest still has case_set_hash = "b"*64; decision forged to "f"*64.
    report = verify_claim_authorization(
        envelope,
        benchmark=live,
        matcher_version=DEFAULT_MATCHER_VERSION,
        matcher_config=MatcherConfig(),
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        expected_digest=live.signed_authorization_manifest_digest,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.BINDING_MISMATCH
    auth = live.claim_authorization(
        envelope=envelope,
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert auth.claim_scope == ClaimScope.NONE


def test_revoked_key_fails(tmp_path: Path) -> None:
    live, envelope, store, _, _ = _issue_envelope(tmp_path, _manifest(), revoke=True)
    report = verify_claim_authorization(
        envelope,
        benchmark=live,
        matcher_version=DEFAULT_MATCHER_VERSION,
        matcher_config=MatcherConfig(),
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        expected_digest=live.signed_authorization_manifest_digest,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.REVOKED_KEY


def test_expired_decision_fails(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    live, envelope, store, _, _ = _issue_envelope(
        tmp_path,
        _manifest(),
        issued_at=now - timedelta(days=10),
        not_after=now - timedelta(days=1),
    )
    report = verify_claim_authorization(
        envelope,
        benchmark=live,
        matcher_version=DEFAULT_MATCHER_VERSION,
        matcher_config=MatcherConfig(),
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        at=now,
        expected_digest=live.signed_authorization_manifest_digest,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.DECISION_EXPIRED


def test_online_release_role_not_permitted_for_claim_envelopes(
    tmp_path: Path,
) -> None:
    live, envelope, store, _, _ = _issue_envelope(
        tmp_path,
        _manifest(),
        role=KeyRole.ONLINE_RELEASE,
        channels=["development", "production"],
    )
    report = verify_claim_authorization(
        envelope,
        benchmark=live,
        matcher_version=DEFAULT_MATCHER_VERSION,
        matcher_config=MatcherConfig(),
        trust_store=store,
        policy_mode=TrustPolicyMode.PRODUCTION,
        expected_digest=live.signed_authorization_manifest_digest,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.ROLE_NOT_PERMITTED


def test_crafted_evaluation_result_public_scope_without_envelope_coerces() -> None:
    manifest = _manifest()
    crafted = EvaluationResult(
        result_id="ocresult_forged",
        benchmark=manifest,
        system=SystemManifest(
            system_id="sys_forged",
            version="0.0.1",
            display_name="Forged System",
            configuration_hash="c" * 64,
        ),
        submission_id="ocsub_forged",
        matcher_version=DEFAULT_MATCHER_VERSION,
        case_evaluations=[],
        metrics=_metrics(),
        claim_authorization=ClaimAuthorization(
            claim_scope=ClaimScope.PUBLIC_DOMAIN_BOUNDED,
            authorization_verified=True,
            expert_natural_evidence=True,
            rights_cleared_cases=True,
            protected_holdout=True,
            independent_evaluation=True,
            matcher_audit_complete=True,
            frozen_scoring_policy=True,
            signed_authorization_manifest_digest="a" * 64,
            domain_scope="physics.peer-review",
            use_scope="public-scientific-reporting",
        ),
        claim_authorization_envelope=None,
        performance_claim_authorized=True,
        claim_boundary="forged",
    )
    assert crafted.claim_authorization.claim_scope == ClaimScope.NONE
    assert crafted.performance_claim_authorized is False
    scorecard = build_scorecard(crafted)
    assert "scientific scorecard" not in scorecard.headline
    assert "non-performance" in scorecard.headline


def test_scorecard_signing_path_cannot_headline_without_verified_auth(
    tmp_path: Path,
) -> None:
    """Integrity signing remains distinct; authorization gates the headline."""
    manifest = _manifest()
    # Direct construction with public scope + false verified flag is coerced.
    result = EvaluationResult(
        result_id="ocresult_unsigned_auth",
        benchmark=manifest,
        system=SystemManifest(
            system_id="sys_unsigned",
            version="0.0.1",
            display_name="Unsigned Auth System",
            configuration_hash="c" * 64,
        ),
        submission_id="ocsub_unsigned",
        matcher_version=DEFAULT_MATCHER_VERSION,
        case_evaluations=[],
        metrics=_metrics(),
        claim_authorization=ClaimAuthorization(
            claim_scope=ClaimScope.PUBLIC_COMPARATIVE,
            authorization_verified=False,
        ),
        claim_boundary="must not headline",
    )
    scorecard = build_scorecard(result)
    assert "scientific scorecard" not in scorecard.headline

    live, envelope, store, _, _ = _issue_envelope(tmp_path, manifest)
    auth = live.claim_authorization(
        envelope=envelope,
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    authorized = _result_for(live, auth=auth, envelope=envelope)
    ok_card = build_scorecard(
        authorized,
        trust_store=store,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert "independently evaluated scientific scorecard" in ok_card.headline
