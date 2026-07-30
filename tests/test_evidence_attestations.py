"""Signed scientific evidence attestations (PR 42 / fail-closed gates)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from opencritique_evaluation.attestations import (
    AttestationRecordStatus,
    EvidenceAttestationKind,
    ExpertStaffingAttestation,
    NaturalCorpusAttestation,
    ReviewerExportAuthenticityAttestation,
    SignedEvidenceEnvelope,
)
from opencritique_evaluation.evidence_verify import (
    envelope_content_digest,
    sign_evidence_attestation,
    verify_evidence_envelope,
)
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


def _issue_envelope(
    tmp_path: Path,
    attestation,
    *,
    role: KeyRole = KeyRole.TEST,
    channels: list[str] | None = None,
    revoke: bool = False,
    tamper_payload: bool = False,
) -> tuple[SignedEvidenceEnvelope, Path, TrustStore]:
    priv = tmp_path / "evidence.pem"
    pub = tmp_path / "evidence.pub.pem"
    generate_keypair(priv, pub)
    now = datetime.now(UTC)
    rec = build_trusted_key_record(
        public_key_path=pub,
        role=role,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=365),
        channels=channels or ["development", "test"],
        notes="ephemeral evidence-authority test key",
    )
    store = TrustStore(
        store_id="oc-evidence-test",
        keys=[rec],
        revocations=(
            [
                RevocationRecord(
                    revocation_id="rev-ev-1",
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
    store_path = tmp_path / "evidence-trust-store.json"
    write_trust_store(store, store_path)

    payload = attestation.model_copy(update={"authority_id": rec.key_id})
    envelope = sign_evidence_attestation(
        payload, priv, key_id_override=rec.key_id
    )
    if tamper_payload:
        # Mutate after signing so digest/signature no longer match.
        mutated = envelope.attestation.model_copy(
            update={"notes": (envelope.attestation.notes or "") + " forged"}
        )
        envelope = envelope.model_copy(update={"attestation": mutated})
    return envelope, store_path, store


def _natural(
    *,
    status: AttestationRecordStatus = AttestationRecordStatus.ATTESTED,
    blocked_reason: str | None = None,
    case_ids: list[str] | None = None,
    count: int | None = None,
) -> NaturalCorpusAttestation:
    now = datetime.now(UTC)
    ids = case_ids if case_ids is not None else ["case-a", "case-b"]
    return NaturalCorpusAttestation(
        attestation_id="attest-natural-test",
        subject_hashes={"ledger": "a" * 64},
        authority_id="pending",
        issued_at=now - timedelta(hours=1),
        not_after=now + timedelta(days=30),
        verification_status=status,
        blocked_reason=blocked_reason
        if status == AttestationRecordStatus.BLOCKED
        else None,
        ledger_path="corpus/acquisition-ledger.json",
        natural_case_ids=ids,
        natural_case_count=count if count is not None else len(ids),
    )


def test_valid_test_key_envelope_verifies_under_development(tmp_path: Path) -> None:
    attestation = _natural()
    envelope, store_path, _store = _issue_envelope(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.NATURAL_CORPUS,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        artifact_path="test/natural.envelope.json",
        subject_binding_check={
            "natural_case_ids": ["case-a", "case-b"],
            "natural_case_count": 2,
        },
    )
    assert report.ok is True
    assert report.signature_status == "valid"
    assert report.binding_ok is True
    assert report.revocation_status == "not_revoked"
    assert report.report_digest is not None
    assert len(envelope_content_digest(envelope)) == 64


def test_forged_payload_fails_closed(tmp_path: Path) -> None:
    attestation = _natural()
    envelope, store_path, _ = _issue_envelope(
        tmp_path, attestation, tamper_payload=True
    )
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.NATURAL_CORPUS,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.PAYLOAD_TAMPER
    assert report.signature_status == "invalid"


def test_missing_envelope_is_missing_attestation() -> None:
    report = verify_evidence_envelope(
        None,
        expected_kind=EvidenceAttestationKind.EXPERT_STAFFING,
        policy_mode=TrustPolicyMode.PRODUCTION,
        artifact_path="governance/evidence/attestations/expert-staffing.envelope.json",
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.MISSING_ATTESTATION
    assert report.signature_status == "missing"
    assert "missing_attestation" in report.detail


def test_blocked_attestation_rejected_even_if_signed(tmp_path: Path) -> None:
    attestation = _natural(
        status=AttestationRecordStatus.BLOCKED,
        blocked_reason="still recruiting",
    )
    envelope, store_path, _ = _issue_envelope(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.ATTESTATION_BLOCKED


def test_binding_mismatch_on_case_ids(tmp_path: Path) -> None:
    attestation = _natural(case_ids=["case-a"], count=1)
    envelope, store_path, _ = _issue_envelope(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        subject_binding_check={
            "natural_case_ids": ["case-a", "case-forged"],
            "natural_case_count": 1,
        },
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.BINDING_MISMATCH
    assert report.signature_status == "valid"


def test_revoked_key_rejected(tmp_path: Path) -> None:
    attestation = _natural()
    envelope, store_path, _ = _issue_envelope(tmp_path, attestation, revoke=True)
    report = verify_evidence_envelope(
        envelope,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.REVOKED_KEY
    assert report.revocation_status == "revoked"


def test_test_key_rejected_in_production(tmp_path: Path) -> None:
    attestation = _natural()
    envelope, store_path, _ = _issue_envelope(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.PRODUCTION,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.TEST_KEY_IN_PRODUCTION


def test_wrong_role_rejected_in_production(tmp_path: Path) -> None:
    attestation = _natural()
    envelope, store_path, _ = _issue_envelope(
        tmp_path,
        attestation,
        role=KeyRole.ONLINE_RELEASE,
        channels=["production"],
    )
    report = verify_evidence_envelope(
        envelope,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.PRODUCTION,
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.ROLE_NOT_PERMITTED


def test_evidence_authority_role_accepted_in_production(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    attestation = ReviewerExportAuthenticityAttestation(
        attestation_id="attest-export-test",
        subject_hashes={"manifest": "b" * 64},
        authority_id="pending",
        issued_at=now - timedelta(hours=1),
        not_after=now + timedelta(days=30),
        verification_status=AttestationRecordStatus.ATTESTED,
        adapter="coarse",
        manifest_path="fixtures/coarse/production/MANIFEST.json",
        artifact_content_hashes=["c" * 64],
        export_count=1,
    )
    envelope, store_path, _ = _issue_envelope(
        tmp_path,
        attestation,
        role=KeyRole.EVIDENCE_AUTHORITY,
        channels=["production"],
    )
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.REVIEWER_EXPORT_AUTHENTICITY,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.PRODUCTION,
        subject_binding_check={
            "adapter": "coarse",
            "artifact_content_hashes": ["c" * 64],
            "export_count": 1,
        },
    )
    assert report.ok is True
    assert report.key_role == KeyRole.EVIDENCE_AUTHORITY


def test_staffing_binding_to_adjudicator_ids(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    attestation = ExpertStaffingAttestation(
        attestation_id="attest-staff-test",
        subject_hashes={"roster": "d" * 64},
        authority_id="pending",
        issued_at=now - timedelta(hours=1),
        not_after=now + timedelta(days=30),
        verification_status=AttestationRecordStatus.ATTESTED,
        roster_path="governance/evidence/natural-adjudication-staffing.json",
        domain_profiles=["physics", "biology"],
        independent_adjudicator_ids=["adj-1", "adj-2", "adj-3", "adj-4"],
    )
    envelope, store_path, _ = _issue_envelope(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.EXPERT_STAFFING,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        subject_binding_check={
            "domain_profiles": ["physics", "biology"],
            "independent_adjudicator_ids": ["adj-1", "adj-2", "adj-3", "adj-4"],
        },
    )
    assert report.ok is True
