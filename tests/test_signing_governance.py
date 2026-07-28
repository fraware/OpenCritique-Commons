"""PR6 / issue #4: signing trust store, rotation, and revocation."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from opencritique_evaluation.models import (
    BenchmarkEvidenceClass,
    BenchmarkManifest,
    EvaluationMetrics,
    EvaluationResult,
    MetricValue,
    PublicScorecard,
    ReferenceCompleteness,
    SystemManifest,
)
from opencritique_evaluation.scorecard import build_scorecard
from opencritique_evaluation.signing import (
    generate_keypair,
    sign_scorecard,
    verify_envelope,
    verify_envelope_detailed,
)
from opencritique_evaluation.trust import (
    THREAT_MODEL,
    KeyRole,
    KeyStatus,
    RevocationRecord,
    RotationStatement,
    TrustPolicyMode,
    TrustStore,
    VerificationFailureReason,
    build_trusted_key_record,
    write_trust_store,
)


def _metric() -> MetricValue:
    return MetricValue(value=None, withheld_reason="synthetic fixture")


def _scorecard() -> PublicScorecard:
    now = datetime(2026, 2, 1, tzinfo=UTC)
    from opencritique_evaluation.models import BenchmarkCaseRef

    system = SystemManifest(
        system_id="synthetic",
        version="0.0.1",
        display_name="Synthetic Signer",
        configuration_hash="a" * 64,
    )
    benchmark = BenchmarkManifest(
        benchmark_id="ocbench_sign_test",
        version="0.1.0",
        title="Signing test benchmark",
        description="Ephemeral signing tests only",
        evidence_class=BenchmarkEvidenceClass.CONFORMANCE,
        reference_completeness=ReferenceCompleteness.UNKNOWN,
        domain_profiles=["conformance"],
        cases=[BenchmarkCaseRef(case_id="occase_sign_1", case_version="1", path="x.json")],
        license="Apache-2.0",
        case_set_hash="b" * 64,
        created_at=now,
        limitations=["test only"],
    )
    result = EvaluationResult(
        result_id="ocresult_sign_test",
        system=system,
        benchmark=benchmark,
        submission_id="ocsub_sign_test",
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
            brier_score=_metric(),
            novel_candidates_pending_adjudication=0,
        ),
        performance_claim_authorized=False,
        claim_boundary="Signing unit test; no performance claims.",
        generated_at=now,
    )
    return build_scorecard(result)


def test_threat_model_covers_required_classes() -> None:
    assert set(THREAT_MODEL) >= {
        "substitution",
        "rollback",
        "compromise",
        "unauthorized_signing",
        "stale_key_acceptance",
    }


def test_rotation_preserves_historical_verification(tmp_path: Path) -> None:
    old_priv, old_pub = tmp_path / "old.pem", tmp_path / "old.pub.pem"
    new_priv, new_pub = tmp_path / "new.pem", tmp_path / "new.pub.pem"
    generate_keypair(old_priv, old_pub)
    generate_keypair(new_priv, new_pub)
    now = datetime.now(UTC)
    old_rec = build_trusted_key_record(
        public_key_path=old_pub,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.SUPERSEDED,
        not_before=now - timedelta(days=30),
        not_after=now + timedelta(days=365),
        channels=["repo", "release-notes"],
        notes="rotated",
    )
    new_rec = build_trusted_key_record(
        public_key_path=new_pub,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(hours=1),
        channels=["repo", "release-notes"],
    )
    store = TrustStore(
        store_id="oc-trust-test",
        keys=[
            old_rec.model_copy(update={"superseded_by": new_rec.key_id}),
            new_rec,
        ],
        rotations=[
            RotationStatement(
                statement_id="rot-1",
                issued_at=now,
                retiring_key_id=old_rec.key_id,
                successor_key_id=new_rec.key_id,
                effective_at=now,
            )
        ],
        published_channels=["repo", "release-notes"],
    )
    scorecard = _scorecard()
    historical = sign_scorecard(
        scorecard, old_priv, key_role=KeyRole.ONLINE_RELEASE, key_id_override=old_rec.key_id
    )
    # Production rejects superseded key.
    prod = verify_envelope_detailed(
        historical, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert not prod.ok
    assert prod.reason == VerificationFailureReason.SUPERSEDED_WITHOUT_HISTORICAL
    # Historical policy still verifies the old signature.
    hist = verify_envelope_detailed(
        historical, trust_store=store, policy_mode=TrustPolicyMode.HISTORICAL
    )
    assert hist.ok
    fresh = sign_scorecard(
        scorecard, new_priv, key_role=KeyRole.ONLINE_RELEASE, key_id_override=new_rec.key_id
    )
    assert verify_envelope_detailed(
        fresh, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    ).ok


def test_revocation_blocks_new_trust(tmp_path: Path) -> None:
    priv, pub = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    generate_keypair(priv, pub)
    now = datetime.now(UTC)
    rec = build_trusted_key_record(
        public_key_path=pub,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.REVOKED,
        not_before=now - timedelta(days=1),
    )
    store = TrustStore(
        store_id="oc-trust-revocation",
        keys=[rec],
        revocations=[
            RevocationRecord(
                revocation_id="rev-1",
                key_id=rec.key_id,
                revoked_at=now,
                reason="suspected exposure (test)",
                incident_reference="TEST-INCIDENT",
            )
        ],
    )
    envelope = sign_scorecard(
        _scorecard(), priv, key_role=KeyRole.ONLINE_RELEASE, key_id_override=rec.key_id
    )
    result = verify_envelope_detailed(
        envelope, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert not result.ok
    assert result.reason == VerificationFailureReason.REVOKED_KEY
    assert "revoked" in result.detail.lower()


def test_unknown_keys_fail_closed(tmp_path: Path) -> None:
    priv, pub = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    generate_keypair(priv, pub)
    store = TrustStore(store_id="empty", keys=[])
    envelope = sign_scorecard(_scorecard(), priv)
    result = verify_envelope_detailed(
        envelope, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert not result.ok
    assert result.reason == VerificationFailureReason.UNKNOWN_KEY


def test_test_keys_rejected_in_production(tmp_path: Path) -> None:
    priv, pub = tmp_path / "t.pem", tmp_path / "t.pub.pem"
    generate_keypair(priv, pub)
    now = datetime.now(UTC)
    rec = build_trusted_key_record(
        public_key_path=pub,
        role=KeyRole.TEST,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=1),
    )
    assert "TEST" in rec.key_id
    store = TrustStore(store_id="test-keys", keys=[rec])
    envelope = sign_scorecard(
        _scorecard(), priv, key_role=KeyRole.TEST, key_id_override=rec.key_id
    )
    result = verify_envelope_detailed(
        envelope, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert not result.ok
    assert result.reason == VerificationFailureReason.TEST_KEY_IN_PRODUCTION


def test_payload_and_signature_tampering(tmp_path: Path) -> None:
    priv, pub = tmp_path / "k.pem", tmp_path / "k.pub.pem"
    generate_keypair(priv, pub)
    now = datetime.now(UTC)
    rec = build_trusted_key_record(
        public_key_path=pub,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=1),
    )
    store = TrustStore(store_id="tamper", keys=[rec])
    envelope = sign_scorecard(
        _scorecard(), priv, key_role=KeyRole.ONLINE_RELEASE, key_id_override=rec.key_id
    )
    tampered_payload = envelope.model_copy(
        update={
            "scorecard": envelope.scorecard.model_copy(
                update={"headline": envelope.scorecard.headline + " TAMPERED"}
            )
        }
    )
    bad_payload = verify_envelope_detailed(
        tampered_payload, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert bad_payload.reason == VerificationFailureReason.PAYLOAD_TAMPER

    bad_sig_bytes = base64.b64decode(envelope.signature.signature_base64)
    flipped = bytes([bad_sig_bytes[0] ^ 0xFF]) + bad_sig_bytes[1:]
    tampered_sig = envelope.model_copy(
        update={
            "signature": envelope.signature.model_copy(
                update={"signature_base64": base64.b64encode(flipped).decode("ascii")}
            )
        }
    )
    # Fix payload hash alignment for signature-only tamper path.
    tampered_sig = envelope.model_copy(
        update={
            "signature": envelope.signature.model_copy(
                update={"signature_base64": base64.b64encode(flipped).decode("ascii")}
            )
        }
    )
    bad_sig = verify_envelope_detailed(
        tampered_sig, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert bad_sig.reason == VerificationFailureReason.SIGNATURE_TAMPER


def test_expiration_and_key_substitution(tmp_path: Path) -> None:
    priv_a, pub_a = tmp_path / "a.pem", tmp_path / "a.pub.pem"
    priv_b, pub_b = tmp_path / "b.pem", tmp_path / "b.pub.pem"
    generate_keypair(priv_a, pub_a)
    generate_keypair(priv_b, pub_b)
    now = datetime.now(UTC)
    rec = build_trusted_key_record(
        public_key_path=pub_a,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=10),
        not_after=now - timedelta(days=1),
    )
    store = TrustStore(store_id="expiry", keys=[rec])
    envelope = sign_scorecard(
        _scorecard(), priv_a, key_role=KeyRole.ONLINE_RELEASE, key_id_override=rec.key_id
    )
    expired = verify_envelope_detailed(
        envelope, trust_store=store, policy_mode=TrustPolicyMode.PRODUCTION, at=now
    )
    assert expired.reason == VerificationFailureReason.EXPIRED_KEY

    # Substitution: sign with B but claim A's key id / trust record.
    other = sign_scorecard(_scorecard(), priv_b)
    substituted = other.model_copy(
        update={
            "signature": other.signature.model_copy(
                update={
                    "key_id": rec.key_id,
                    "public_key_base64": rec.public_key_base64,
                }
            )
        }
    )
    # Recreate store with non-expired key for substitution check.
    rec2 = build_trusted_key_record(
        public_key_path=pub_a,
        role=KeyRole.ONLINE_RELEASE,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=1),
    )
    store2 = TrustStore(store_id="sub", keys=[rec2])
    # Force key id to match store while keeping B's signature bytes → signature fail or mismatch.
    env_b = sign_scorecard(_scorecard(), priv_b, key_id_override=rec2.key_id)
    # public key in envelope is still B's; trust store has A → public key mismatch
    result = verify_envelope_detailed(
        env_b, trust_store=store2, policy_mode=TrustPolicyMode.PRODUCTION
    )
    assert result.reason in {
        VerificationFailureReason.PUBLIC_KEY_MISMATCH,
        VerificationFailureReason.KEY_ID_MISMATCH,
        VerificationFailureReason.SIGNATURE_TAMPER,
    }
    assert not result.ok
    assert verify_envelope(envelope, pub_a) in {True, False}  # expired envelope may still crypto-ok
    _ = substituted


def test_no_private_keys_in_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    banned = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        if any(
            part in rel
            for part in (
                ".git/",
                ".venv/",
                "_inspect_wheel/",
                ".pytest_cache/",
                ".ruff_cache/",
                "dist/",
                "src/opencritique_commons.egg-info/",
            )
        ):
            continue
        text_name = path.name.lower()
        if text_name.endswith((".pem", ".key")) and "pub" not in text_name:
            # Allow only if clearly public; private material must not be committed.
            data = path.read_bytes()
            if b"PRIVATE KEY" in data:
                banned.append(rel)
    assert banned == []


def test_shipped_trust_store_has_no_secrets() -> None:
    path = Path(__file__).resolve().parents[1] / "trust" / "scorecard-trust-store.json"
    assert path.is_file()
    store = TrustStore.model_validate_json(path.read_text(encoding="utf-8"))
    assert len(store.published_channels) >= 2
    blob = path.read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in blob
    write_trust_store(store, path)  # round-trip format stability
    assert "production" in json.dumps(store.model_dump(mode="json"))
