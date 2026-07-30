"""Holdout set custody model (PR 43)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from opencritique_evaluation.attestations import (
    AttestationRecordStatus,
    EvidenceAttestationKind,
    HoldoutCustodyAttestation,
    SignedEvidenceEnvelope,
)
from opencritique_evaluation.evidence_verify import (
    sign_evidence_attestation,
    verify_evidence_envelope,
)
from opencritique_evaluation.holdout_custody import (
    HoldoutAccessAction,
    HoldoutAccessLog,
    HoldoutAccessLogEntry,
    HoldoutCaseRecord,
    HoldoutContaminationDeclaration,
    HoldoutRefreshRetirementPolicy,
    HoldoutSetManifest,
    access_log_head_hash,
    holdout_manifest_content_hash,
)
from opencritique_evaluation.signing import generate_keypair
from opencritique_evaluation.trust import (
    KeyRole,
    KeyStatus,
    TrustPolicyMode,
    TrustStore,
    VerificationFailureReason,
    build_trusted_key_record,
    write_trust_store,
)


def _policy() -> HoldoutRefreshRetirementPolicy:
    return HoldoutRefreshRetirementPolicy(
        refresh_cadence="annual_or_on_contamination",
        retirement_rule="retire_on_contamination_or_custodian_rotation",
    )


def _manifest(*, n_cases: int = 40) -> HoldoutSetManifest:
    now = datetime.now(UTC)
    return HoldoutSetManifest(
        holdout_id="holdout-natural-v1",
        cases=[
            HoldoutCaseRecord(case_id=f"case-{i:03d}", content_hash=f"{i:064x}")
            for i in range(n_cases)
        ],
        freeze_time=now - timedelta(days=1),
        custodian_id="custodian-ops-1",
        developer_exclusion_list=["dev-alice", "dev-bob"],
        private_locator_ref="vault:holdout/natural-v1/ciphertext",
        refresh_retirement_policy=_policy(),
    )


def _access_log(holdout_id: str) -> HoldoutAccessLog:
    now = datetime.now(UTC)
    return HoldoutAccessLog(
        holdout_id=holdout_id,
        entries=[
            HoldoutAccessLogEntry(
                sequence=0,
                actor="custodian-ops-1",
                action=HoldoutAccessAction.CREATE,
                timestamp=now - timedelta(hours=2),
                purpose="freeze holdout set",
            ),
            HoldoutAccessLogEntry(
                sequence=1,
                actor="custodian-ops-1",
                action=HoldoutAccessAction.READ,
                timestamp=now - timedelta(hours=1),
                purpose="custody audit",
            ),
        ],
    )


def _attestation_from(
    manifest: HoldoutSetManifest,
    log: HoldoutAccessLog,
    *,
    natural_case_count: int | None = None,
    status: AttestationRecordStatus = AttestationRecordStatus.ATTESTED,
    blocked_reason: str | None = None,
    contamination_declared: bool = False,
) -> HoldoutCustodyAttestation:
    now = datetime.now(UTC)
    manifest_hash = holdout_manifest_content_hash(manifest)
    log_hash = access_log_head_hash(log)
    count = (
        natural_case_count
        if natural_case_count is not None
        else manifest.natural_case_count
    )
    return HoldoutCustodyAttestation(
        attestation_id="attest-holdout-test",
        subject_hashes={
            "holdout_manifest": manifest_hash,
            "access_log_head": log_hash,
        },
        authority_id="pending",
        issued_at=now - timedelta(hours=1),
        not_after=now + timedelta(days=30),
        verification_status=status,
        blocked_reason=blocked_reason
        if status == AttestationRecordStatus.BLOCKED
        else None,
        holdout_id=manifest.holdout_id,
        holdout_manifest_hash=manifest_hash,
        access_log_head_hash=log_hash,
        natural_case_count=count,
        freeze_time=manifest.freeze_time,
        custodian_id=manifest.custodian_id,
        developer_exclusion_list=list(manifest.developer_exclusion_list),
        private_locator_ref=manifest.private_locator_ref,
        contamination_declared=contamination_declared,
        contamination_details="",
        refresh_policy=manifest.refresh_retirement_policy.refresh_cadence,
        retirement_policy=manifest.refresh_retirement_policy.retirement_rule,
    )


def _issue(
    tmp_path: Path, attestation: HoldoutCustodyAttestation
) -> tuple[SignedEvidenceEnvelope, Path]:
    priv = tmp_path / "evidence.pem"
    pub = tmp_path / "evidence.pub.pem"
    generate_keypair(priv, pub)
    now = datetime.now(UTC)
    rec = build_trusted_key_record(
        public_key_path=pub,
        role=KeyRole.TEST,
        status=KeyStatus.ACTIVE,
        not_before=now - timedelta(days=1),
        not_after=now + timedelta(days=365),
        channels=["development", "test"],
        notes="ephemeral holdout evidence key",
    )
    store = TrustStore(
        store_id="oc-holdout-test",
        keys=[rec],
        published_channels=["test"],
    )
    store_path = tmp_path / "holdout-trust-store.json"
    write_trust_store(store, store_path)
    payload = attestation.model_copy(update={"authority_id": rec.key_id})
    envelope = sign_evidence_attestation(
        payload, priv, key_id_override=rec.key_id
    )
    return envelope, store_path


def test_manifest_rejects_plaintext_manuscript_path() -> None:
    with pytest.raises(ValidationError):
        HoldoutSetManifest(
            holdout_id="h1",
            cases=[],
            freeze_time=datetime.now(UTC),
            custodian_id="c1",
            private_locator_ref="/data/manuscripts/holdout.pdf",
            refresh_retirement_policy=_policy(),
        )


def test_manifest_and_log_hashes_stable() -> None:
    manifest = _manifest(n_cases=3)
    log = _access_log(manifest.holdout_id)
    assert len(holdout_manifest_content_hash(manifest)) == 64
    assert len(access_log_head_hash(log)) == 64
    assert holdout_manifest_content_hash(manifest) == holdout_manifest_content_hash(
        manifest
    )


def test_access_log_requires_contiguous_sequences() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        HoldoutAccessLog(
            holdout_id="h1",
            entries=[
                HoldoutAccessLogEntry(
                    sequence=1,
                    actor="a",
                    action=HoldoutAccessAction.CREATE,
                    timestamp=now,
                    purpose="skip",
                )
            ],
        )


def test_contamination_declaration_requires_context() -> None:
    with pytest.raises(ValidationError):
        HoldoutContaminationDeclaration(contaminated=True, details="")


def test_attested_payload_requires_manifest_and_log_head_binding() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        HoldoutCustodyAttestation(
            attestation_id="bad",
            subject_hashes={},
            authority_id="auth",
            issued_at=now - timedelta(hours=1),
            not_after=now + timedelta(days=1),
            verification_status=AttestationRecordStatus.ATTESTED,
            holdout_id="h1",
            holdout_manifest_hash="a" * 64,
            access_log_head_hash="b" * 64,
            natural_case_count=40,
            freeze_time=now,
            custodian_id="c1",
            private_locator_ref="vault:x",
            refresh_policy="annual",
            retirement_policy="on_contamination",
        )


def test_verified_attestation_with_40_cases_passes(tmp_path: Path) -> None:
    manifest = _manifest(n_cases=40)
    log = _access_log(manifest.holdout_id)
    attestation = _attestation_from(manifest, log)
    envelope, store_path = _issue(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.HOLDOUT_CUSTODY,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        subject_binding_check={
            "require_minimum_natural_cases": 40,
            "require_custody_fields": True,
            "holdout_manifest_hash": holdout_manifest_content_hash(manifest),
            "access_log_head_hash": access_log_head_hash(log),
            "freeze_time": manifest.freeze_time,
        },
    )
    assert report.ok is True
    assert report.binding_ok is True
    assert report.bindings["natural_case_count"] == "40"


def test_attested_39_cases_fails_minimum_even_if_signed(tmp_path: Path) -> None:
    manifest = _manifest(n_cases=39)
    log = _access_log(manifest.holdout_id)
    attestation = _attestation_from(manifest, log)
    envelope, store_path = _issue(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.HOLDOUT_CUSTODY,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        subject_binding_check={
            "require_minimum_natural_cases": 40,
            "require_custody_fields": True,
        },
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.BINDING_MISMATCH
    assert "natural_case_count_below_minimum" in report.detail


def test_ledger_count_alone_does_not_satisfy_gate_binding(tmp_path: Path) -> None:
    """Signed attestation with zero holdout cases fails even if a ledger had 40."""
    manifest = _manifest(n_cases=0)
    log = _access_log(manifest.holdout_id)
    attestation = _attestation_from(manifest, log, natural_case_count=0)
    envelope, store_path = _issue(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.HOLDOUT_CUSTODY,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        subject_binding_check={
            "require_minimum_natural_cases": 40,
            "require_custody_fields": True,
            # Intentionally do NOT bind to a forged ledger count of 40.
        },
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.BINDING_MISMATCH


def test_manifest_log_head_mismatch_fails(tmp_path: Path) -> None:
    manifest = _manifest(n_cases=40)
    log = _access_log(manifest.holdout_id)
    attestation = _attestation_from(manifest, log)
    envelope, store_path = _issue(tmp_path, attestation)
    report = verify_evidence_envelope(
        envelope,
        expected_kind=EvidenceAttestationKind.HOLDOUT_CUSTODY,
        trust_store_path=store_path,
        policy_mode=TrustPolicyMode.DEVELOPMENT,
        subject_binding_check={
            "require_minimum_natural_cases": 40,
            "require_custody_fields": True,
            "holdout_manifest_hash": "f" * 64,
        },
    )
    assert report.ok is False
    assert report.reason == VerificationFailureReason.BINDING_MISMATCH
    assert "holdout_manifest_hash" in report.detail


def test_scientific_gate_detail_notes_attested_minimum_not_ledger() -> None:
    import importlib.util
    import sys

    root = Path(__file__).resolve().parents[1]
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    path = root / "scripts" / "check_v09_scientific_gates.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    results = module.evaluate_scientific_gates()
    by_name = {item.name: item for item in results}
    result = by_name["holdout_custody"]
    assert result.passed is False
    assert "missing_attestation" in result.detail
    assert "attested_holdout_minimum=40" in result.detail
    assert "informational only" in result.detail
