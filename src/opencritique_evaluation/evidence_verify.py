"""Cryptographic verification of scientific evidence attestation envelopes (PR 42).

Mirrors ``verify_claim_authorization``. A valid signature establishes integrity
relative to a trusted ``evidence_authority`` (or ``offline_root``) key; it does
**not** establish scientific correctness of underlying measurements.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from opencritique_schema.canonical import content_hash

from .attestations import (
    AttestationRecordStatus,
    EvidenceAttestation,
    EvidenceAttestationKind,
    ExpertStaffingAttestation,
    HoldoutCustodyAttestation,
    IndependentEvaluationAttestation,
    MatcherAuditCompletionAttestation,
    NaturalCorpusAttestation,
    ReviewerExportAuthenticityAttestation,
    SignedEvidenceEnvelope,
)
from .models import StrictModel
from .trust import (
    EVIDENCE_AUTHORITY_SIGNING_ROLES,
    KeyRole,
    TrustPolicyMode,
    TrustStore,
    VerificationFailureReason,
    evaluate_key_policy,
    key_id_from_raw_public,
    load_trust_store,
)

_EVIDENCE_DEV_ROLES: frozenset[KeyRole] = EVIDENCE_AUTHORITY_SIGNING_ROLES | {
    KeyRole.TEST,
}

SignatureStatus = Literal["missing", "valid", "invalid", "unchecked"]
RevocationStatus = Literal["not_revoked", "revoked", "unknown"]


class EvidenceVerificationReport(StrictModel):
    """Machine-readable row emitted by scientific gates for each attestation check."""

    ok: bool
    reason: VerificationFailureReason | None = None
    detail: str = ""
    artifact_path: str | None = None
    content_hash: str | None = None
    signature_status: SignatureStatus = "unchecked"
    authority_id: str | None = None
    key_id: str | None = None
    key_role: KeyRole | None = None
    attestation_kind: EvidenceAttestationKind | None = None
    bindings: dict[str, str] = {}
    binding_ok: bool = False
    revocation_status: RevocationStatus = "unknown"
    policy_mode: TrustPolicyMode
    report_digest: str | None = None


def canonical_attestation_bytes(attestation: EvidenceAttestation) -> bytes:
    return json.dumps(
        attestation.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def envelope_content_digest(envelope: SignedEvidenceEnvelope) -> str:
    return content_hash(envelope)


def load_evidence_envelope(path: Path) -> SignedEvidenceEnvelope:
    return SignedEvidenceEnvelope.model_validate_json(path.read_text(encoding="utf-8"))


def sign_evidence_attestation(
    attestation: EvidenceAttestation,
    private_key_path: Path,
    *,
    key_id_override: str | None = None,
    signed_at: datetime | None = None,
) -> SignedEvidenceEnvelope:
    private_key = serialization.load_pem_private_key(
        private_key_path.read_bytes(), password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    public_key = private_key.public_key()
    payload = canonical_attestation_bytes(attestation)
    signature = private_key.sign(payload)
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = key_id_override or key_id_from_raw_public(raw_public)
    return SignedEvidenceEnvelope(
        attestation=attestation,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        signature=base64.b64encode(signature).decode("ascii"),
        key_id=key_id,
        signed_at=signed_at or datetime.now(UTC),
    )


def _with_digest(report: EvidenceVerificationReport) -> EvidenceVerificationReport:
    return report.model_copy(
        update={"report_digest": content_hash(report.model_dump(mode="json"))}
    )


def _fail(
    *,
    reason: VerificationFailureReason,
    detail: str,
    policy_mode: TrustPolicyMode,
    artifact_path: str | None = None,
    content_hash_value: str | None = None,
    signature_status: SignatureStatus = "unchecked",
    authority_id: str | None = None,
    key_id: str | None = None,
    key_role: KeyRole | None = None,
    attestation_kind: EvidenceAttestationKind | None = None,
    bindings: dict[str, str] | None = None,
    binding_ok: bool = False,
    revocation_status: RevocationStatus = "unknown",
) -> EvidenceVerificationReport:
    return _with_digest(
        EvidenceVerificationReport(
            ok=False,
            reason=reason,
            detail=detail,
            artifact_path=artifact_path,
            content_hash=content_hash_value,
            signature_status=signature_status,
            authority_id=authority_id,
            key_id=key_id,
            key_role=key_role,
            attestation_kind=attestation_kind,
            bindings=bindings or {},
            binding_ok=binding_ok,
            revocation_status=revocation_status,
            policy_mode=policy_mode,
        )
    )


def _ok(
    *,
    policy_mode: TrustPolicyMode,
    artifact_path: str | None,
    content_hash_value: str,
    authority_id: str,
    key_id: str,
    key_role: KeyRole | None,
    attestation_kind: EvidenceAttestationKind,
    bindings: dict[str, str],
    revocation_status: RevocationStatus,
) -> EvidenceVerificationReport:
    return _with_digest(
        EvidenceVerificationReport(
            ok=True,
            artifact_path=artifact_path,
            content_hash=content_hash_value,
            signature_status="valid",
            authority_id=authority_id,
            key_id=key_id,
            key_role=key_role,
            attestation_kind=attestation_kind,
            bindings=bindings,
            binding_ok=True,
            revocation_status=revocation_status,
            policy_mode=policy_mode,
        )
    )


def missing_attestation_report(
    *,
    expected_path: str,
    attestation_kind: EvidenceAttestationKind,
    policy_mode: TrustPolicyMode = TrustPolicyMode.PRODUCTION,
    detail: str | None = None,
) -> EvidenceVerificationReport:
    return _fail(
        reason=VerificationFailureReason.MISSING_ATTESTATION,
        detail=detail
        or (
            f"missing_attestation: expected signed envelope at {expected_path}; "
            "Boolean JSON / presence checks do not unlock scientific gates"
        ),
        policy_mode=policy_mode,
        artifact_path=expected_path,
        signature_status="missing",
        attestation_kind=attestation_kind,
        revocation_status="unknown",
    )


def verify_evidence_envelope(
    envelope: SignedEvidenceEnvelope | None,
    *,
    expected_kind: EvidenceAttestationKind | None = None,
    trust_store: TrustStore | None = None,
    trust_store_path: Path | None = None,
    policy_mode: TrustPolicyMode | None = None,
    at: datetime | None = None,
    artifact_path: str | None = None,
    expected_bindings: dict[str, str] | None = None,
    subject_binding_check: dict[str, Any] | None = None,
) -> EvidenceVerificationReport:
    """Verify an evidence envelope and optionally cross-bind subjects.

    ``expected_bindings`` compares named digests against ``attestation.subject_hashes``.
    ``subject_binding_check`` carries gate-specific live subjects (case IDs, artifact
    hashes, adjudicator IDs, etc.) validated against attestation fields.
    """
    mode = policy_mode or TrustPolicyMode.PRODUCTION
    now = at or datetime.now(UTC)

    if envelope is None:
        return missing_attestation_report(
            expected_path=artifact_path or "<missing>",
            attestation_kind=expected_kind or EvidenceAttestationKind.NATURAL_CORPUS,
            policy_mode=mode,
        )

    attestation = envelope.attestation
    kind = attestation.attestation_kind
    content_digest = envelope_content_digest(envelope)

    if expected_kind is not None and kind != expected_kind:
        return _fail(
            reason=VerificationFailureReason.BINDING_MISMATCH,
            detail=(
                f"attestation_kind={kind.value} does not match "
                f"expected={expected_kind.value}"
            ),
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="unchecked",
            authority_id=attestation.authority_id,
            key_id=envelope.key_id,
            attestation_kind=kind,
        )

    payload = canonical_attestation_bytes(attestation)
    payload_digest = hashlib.sha256(payload).hexdigest()
    if payload_digest != envelope.payload_sha256:
        return _fail(
            reason=VerificationFailureReason.PAYLOAD_TAMPER,
            detail="canonical attestation digest does not match envelope.payload_sha256",
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="invalid",
            authority_id=attestation.authority_id,
            key_id=envelope.key_id,
            attestation_kind=kind,
        )

    if attestation.verification_status != AttestationRecordStatus.ATTESTED:
        return _fail(
            reason=VerificationFailureReason.ATTESTATION_BLOCKED,
            detail=(
                f"attestation verification_status={attestation.verification_status.value}"
                + (
                    f"; blocked_reason={attestation.blocked_reason}"
                    if attestation.blocked_reason
                    else ""
                )
            ),
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="unchecked",
            authority_id=attestation.authority_id,
            key_id=envelope.key_id,
            attestation_kind=kind,
        )

    loaded_store = trust_store
    if loaded_store is None and trust_store_path is not None:
        loaded_store = load_trust_store(trust_store_path)

    if loaded_store is None:
        return _fail(
            reason=VerificationFailureReason.UNKNOWN_KEY,
            detail=f"{mode.value} evidence verification requires an explicit trust store",
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="unchecked",
            authority_id=attestation.authority_id,
            key_id=envelope.key_id,
            attestation_kind=kind,
        )

    key_id = envelope.key_id
    record = loaded_store.get(key_id)
    permitted = (
        _EVIDENCE_DEV_ROLES
        if mode in {TrustPolicyMode.DEVELOPMENT, TrustPolicyMode.TEST}
        else EVIDENCE_AUTHORITY_SIGNING_ROLES
    )
    policy = evaluate_key_policy(
        record,
        key_id=key_id,
        policy_mode=mode,
        at=envelope.signed_at if mode == TrustPolicyMode.HISTORICAL else now,
        store=loaded_store,
        permitted_roles=permitted,
    )
    if not policy.ok:
        assert policy.reason is not None
        rev_status: RevocationStatus = (
            "revoked"
            if policy.reason == VerificationFailureReason.REVOKED_KEY
            else "unknown"
        )
        return _fail(
            reason=policy.reason,
            detail=policy.detail,
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="unchecked",
            authority_id=attestation.authority_id,
            key_id=key_id,
            key_role=policy.key_role,
            attestation_kind=kind,
            revocation_status=rev_status,
        )
    assert record is not None

    try:
        raw_public = base64.b64decode(record.public_key_base64, validate=True)
    except ValueError:
        return _fail(
            reason=VerificationFailureReason.PUBLIC_KEY_MISMATCH,
            detail="trust store public_key_base64 is not valid base64",
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="invalid",
            authority_id=attestation.authority_id,
            key_id=key_id,
            key_role=record.role,
            attestation_kind=kind,
            revocation_status="not_revoked",
        )

    if now < attestation.issued_at:
        return _fail(
            reason=VerificationFailureReason.DECISION_NOT_YET_VALID,
            detail="attestation issued_at is in the future",
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="unchecked",
            authority_id=attestation.authority_id,
            key_id=key_id,
            key_role=record.role,
            attestation_kind=kind,
            revocation_status="not_revoked",
        )
    if now > attestation.not_after:
        return _fail(
            reason=VerificationFailureReason.DECISION_EXPIRED,
            detail="attestation not_after has passed",
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="unchecked",
            authority_id=attestation.authority_id,
            key_id=key_id,
            key_role=record.role,
            attestation_kind=kind,
            revocation_status="not_revoked",
        )

    public_key = Ed25519PublicKey.from_public_bytes(raw_public)
    try:
        public_key.verify(base64.b64decode(envelope.signature, validate=True), payload)
    except (InvalidSignature, ValueError):
        return _fail(
            reason=VerificationFailureReason.SIGNATURE_TAMPER,
            detail="Ed25519 signature verification failed",
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="invalid",
            authority_id=attestation.authority_id,
            key_id=key_id,
            key_role=record.role,
            attestation_kind=kind,
            revocation_status="not_revoked",
        )

    bindings: dict[str, str] = {}
    binding_errors: list[str] = []

    if expected_bindings:
        for name, expected_digest in expected_bindings.items():
            actual = attestation.subject_hashes.get(name)
            bindings[name] = actual or ""
            if actual != expected_digest:
                binding_errors.append(name)

    if subject_binding_check:
        extra_errors = _check_subject_bindings(attestation, subject_binding_check, bindings)
        binding_errors.extend(extra_errors)

    if binding_errors:
        return _fail(
            reason=VerificationFailureReason.BINDING_MISMATCH,
            detail="subject binding mismatch: " + ", ".join(binding_errors),
            policy_mode=mode,
            artifact_path=artifact_path,
            content_hash_value=content_digest,
            signature_status="valid",
            authority_id=attestation.authority_id,
            key_id=key_id,
            key_role=record.role,
            attestation_kind=kind,
            bindings=bindings,
            binding_ok=False,
            revocation_status="not_revoked",
        )

    return _ok(
        policy_mode=mode,
        artifact_path=artifact_path,
        content_hash_value=content_digest,
        authority_id=attestation.authority_id,
        key_id=key_id,
        key_role=record.role,
        attestation_kind=kind,
        bindings=bindings,
        revocation_status="not_revoked",
    )


def _check_subject_bindings(
    attestation: EvidenceAttestation,
    check: dict[str, Any],
    bindings: dict[str, str],
) -> list[str]:
    """Gate-specific live-subject cross-binds. Returns mismatch field names."""
    errors: list[str] = []

    if isinstance(attestation, NaturalCorpusAttestation):
        expected_ids = set(check.get("natural_case_ids") or [])
        attested_ids = set(attestation.natural_case_ids)
        bindings["natural_case_ids"] = ",".join(sorted(attested_ids))
        if expected_ids and attested_ids != expected_ids:
            errors.append("natural_case_ids")
        expected_count = check.get("natural_case_count")
        if expected_count is not None:
            bindings["natural_case_count"] = str(attestation.natural_case_count)
            if attestation.natural_case_count != int(expected_count):
                errors.append("natural_case_count")

    elif isinstance(attestation, ReviewerExportAuthenticityAttestation):
        adapter = check.get("adapter")
        if adapter is not None:
            bindings["adapter"] = attestation.adapter
            if attestation.adapter != adapter:
                errors.append("adapter")
        expected_hashes = list(check.get("artifact_content_hashes") or [])
        if expected_hashes:
            bindings["artifact_content_hashes"] = ",".join(
                attestation.artifact_content_hashes
            )
            if sorted(attestation.artifact_content_hashes) != sorted(expected_hashes):
                errors.append("artifact_content_hashes")
        expected_count = check.get("export_count")
        if expected_count is not None:
            bindings["export_count"] = str(attestation.export_count)
            if attestation.export_count != int(expected_count):
                errors.append("export_count")

    elif isinstance(attestation, ExpertStaffingAttestation):
        expected_ids = set(check.get("independent_adjudicator_ids") or [])
        attested_ids = set(attestation.independent_adjudicator_ids)
        bindings["independent_adjudicator_ids"] = ",".join(sorted(attested_ids))
        if expected_ids and attested_ids != expected_ids:
            errors.append("independent_adjudicator_ids")
        expected_domains = set(check.get("domain_profiles") or [])
        attested_domains = set(attestation.domain_profiles)
        bindings["domain_profiles"] = ",".join(sorted(attested_domains))
        if expected_domains and attested_domains != expected_domains:
            errors.append("domain_profiles")

    elif isinstance(attestation, MatcherAuditCompletionAttestation):
        expected_sessions = set(check.get("session_ids") or [])
        attested_sessions = set(attestation.session_ids)
        bindings["session_ids"] = ",".join(sorted(attested_sessions))
        if expected_sessions and attested_sessions != expected_sessions:
            errors.append("session_ids")
        expected_count = check.get("completed_decision_count")
        if expected_count is not None:
            bindings["completed_decision_count"] = str(
                attestation.completed_decision_count
            )
            if attestation.completed_decision_count != int(expected_count):
                errors.append("completed_decision_count")

    elif isinstance(attestation, HoldoutCustodyAttestation):
        expected_count = check.get("natural_case_count")
        if expected_count is not None:
            bindings["natural_case_count"] = str(attestation.natural_case_count)
            if attestation.natural_case_count != int(expected_count):
                errors.append("natural_case_count")
        expected_holdout = check.get("holdout_id")
        if expected_holdout is not None:
            bindings["holdout_id"] = attestation.holdout_id or ""
            if attestation.holdout_id != expected_holdout:
                errors.append("holdout_id")

    elif isinstance(attestation, IndependentEvaluationAttestation):
        expected_ids = set(check.get("benchmark_ids") or [])
        attested_ids = set(attestation.benchmark_ids)
        bindings["benchmark_ids"] = ",".join(sorted(attested_ids))
        if expected_ids and attested_ids != expected_ids:
            errors.append("benchmark_ids")
        if check.get("require_independent") and not attestation.independent_evaluation:
            errors.append("independent_evaluation")
            bindings["independent_evaluation"] = "false"

    return errors


__all__ = [
    "EvidenceVerificationReport",
    "canonical_attestation_bytes",
    "envelope_content_digest",
    "load_evidence_envelope",
    "missing_attestation_report",
    "sign_evidence_attestation",
    "verify_evidence_envelope",
]
