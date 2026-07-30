"""Signed scientific evidence attestation payloads (PR 42).

These records are the canonical subjects of ``SignedEvidenceEnvelope``.
Presence of Boolean JSON or ledger counts alone does **not** satisfy scientific
gates; gates must verify an envelope signed by ``evidence_authority`` (or
``offline_root``) against the trust store.

Matcher-audit volume accounting and full holdout custody models land in later
PRs; their attestation schemas are frozen here so gates can fail closed on
``missing_attestation`` until real evidence is issued.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import StrictModel


class EvidenceAttestationKind(str, Enum):
    NATURAL_CORPUS = "natural_corpus"
    REVIEWER_EXPORT_AUTHENTICITY = "reviewer_export_authenticity"
    EXPERT_STAFFING = "expert_staffing"
    MATCHER_AUDIT_COMPLETION = "matcher_audit_completion"
    HOLDOUT_CUSTODY = "holdout_custody"
    INDEPENDENT_EVALUATION = "independent_evaluation"


class AttestationRecordStatus(str, Enum):
    """Issuer-declared status of the attestation payload (not crypto verify)."""

    BLOCKED = "blocked"
    PENDING = "pending"
    ATTESTED = "attested"


_HEX64 = r"^[0-9a-f]{64}$"


class EvidenceAttestationBase(StrictModel):
    """Shared header for all scientific evidence attestations."""

    attestation_id: str = Field(min_length=1)
    attestation_kind: EvidenceAttestationKind
    subject_hashes: dict[str, str] = Field(
        default_factory=dict,
        description="Named subject digests (sha256 hex) bound by this attestation.",
    )
    authority_id: str = Field(min_length=1)
    issued_at: datetime
    not_after: datetime
    predecessor_id: str | None = None
    verification_status: AttestationRecordStatus = AttestationRecordStatus.BLOCKED
    blocked_reason: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validity_and_blocked(self) -> EvidenceAttestationBase:
        if self.not_after <= self.issued_at:
            raise ValueError("not_after must be after issued_at")
        for name, digest in self.subject_hashes.items():
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(f"subject_hashes[{name!r}] must be a 64-hex digest")
            if any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError(f"subject_hashes[{name!r}] must be lowercase hex")
        if self.verification_status == AttestationRecordStatus.BLOCKED and not (
            self.blocked_reason or ""
        ).strip():
            raise ValueError("blocked attestations require blocked_reason")
        if self.verification_status == AttestationRecordStatus.ATTESTED and (
            self.blocked_reason or ""
        ).strip():
            raise ValueError("attested payloads must not set blocked_reason")
        return self


class NaturalCorpusAttestation(EvidenceAttestationBase):
    """Attests rights-cleared natural corpus subjects (ledger case bindings)."""

    attestation_kind: Literal[EvidenceAttestationKind.NATURAL_CORPUS] = (
        EvidenceAttestationKind.NATURAL_CORPUS
    )
    ledger_path: str = Field(min_length=1)
    natural_case_ids: list[str] = Field(default_factory=list)
    natural_case_count: int = Field(default=0, ge=0)


class ReviewerExportAuthenticityAttestation(EvidenceAttestationBase):
    """Attests authentic production reviewer-export packages."""

    attestation_kind: Literal[
        EvidenceAttestationKind.REVIEWER_EXPORT_AUTHENTICITY
    ] = EvidenceAttestationKind.REVIEWER_EXPORT_AUTHENTICITY
    adapter: Literal["coarse", "openreviewer"]
    manifest_path: str = Field(min_length=1)
    artifact_content_hashes: list[str] = Field(default_factory=list)
    export_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def hash_shapes(self) -> ReviewerExportAuthenticityAttestation:
        for digest in self.artifact_content_hashes:
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("artifact_content_hashes entries must be 64-hex digests")
        return self


class ExpertStaffingAttestation(EvidenceAttestationBase):
    """Attests qualified independent adjudicators per domain profile."""

    attestation_kind: Literal[EvidenceAttestationKind.EXPERT_STAFFING] = (
        EvidenceAttestationKind.EXPERT_STAFFING
    )
    roster_path: str = Field(min_length=1)
    domain_profiles: list[str] = Field(default_factory=list)
    independent_adjudicator_ids: list[str] = Field(default_factory=list)
    min_domains_required: int = Field(default=2, ge=2)
    min_adjudicators_per_domain: int = Field(default=2, ge=1)


class MatcherAuditCompletionAttestation(EvidenceAttestationBase):
    """Attests completed matcher-audit accounting (volume rules in PR 44)."""

    attestation_kind: Literal[
        EvidenceAttestationKind.MATCHER_AUDIT_COMPLETION
    ] = EvidenceAttestationKind.MATCHER_AUDIT_COMPLETION
    session_ids: list[str] = Field(default_factory=list)
    judgment_set_hash: str | None = Field(default=None, pattern=_HEX64)
    completed_decision_count: int = Field(default=0, ge=0)
    evidence_class: str = "NATURAL"


class HoldoutCustodyAttestation(EvidenceAttestationBase):
    """Minimal holdout custody attestation (full custody model in PR 43)."""

    attestation_kind: Literal[EvidenceAttestationKind.HOLDOUT_CUSTODY] = (
        EvidenceAttestationKind.HOLDOUT_CUSTODY
    )
    holdout_id: str | None = None
    holdout_manifest_hash: str | None = Field(default=None, pattern=_HEX64)
    natural_case_count: int = Field(default=0, ge=0)
    freeze_time: datetime | None = None
    custodian_id: str | None = None


class IndependentEvaluationAttestation(EvidenceAttestationBase):
    """Attests independent evaluation of expert-natural benchmarks."""

    attestation_kind: Literal[
        EvidenceAttestationKind.INDEPENDENT_EVALUATION
    ] = EvidenceAttestationKind.INDEPENDENT_EVALUATION
    benchmark_ids: list[str] = Field(default_factory=list)
    benchmark_manifest_hashes: list[str] = Field(default_factory=list)
    independent_evaluation: bool = True

    @model_validator(mode="after")
    def hash_shapes(self) -> IndependentEvaluationAttestation:
        for digest in self.benchmark_manifest_hashes:
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError(
                    "benchmark_manifest_hashes entries must be 64-hex digests"
                )
        return self


EvidenceAttestation = Annotated[
    NaturalCorpusAttestation
    | ReviewerExportAuthenticityAttestation
    | ExpertStaffingAttestation
    | MatcherAuditCompletionAttestation
    | HoldoutCustodyAttestation
    | IndependentEvaluationAttestation,
    Field(discriminator="attestation_kind"),
]


class SignedEvidenceEnvelope(StrictModel):
    """Ed25519-signed scientific evidence attestation envelope."""

    envelope_version: str = "0.1"
    attestation: EvidenceAttestation
    payload_sha256: str = Field(pattern=_HEX64)
    signature: str = Field(min_length=1, description="Ed25519 signature (base64)")
    key_id: str = Field(min_length=1)
    signed_at: datetime
    algorithm: Literal["Ed25519"] = "Ed25519"


__all__ = [
    "AttestationRecordStatus",
    "EvidenceAttestation",
    "EvidenceAttestationBase",
    "EvidenceAttestationKind",
    "ExpertStaffingAttestation",
    "HoldoutCustodyAttestation",
    "IndependentEvaluationAttestation",
    "MatcherAuditCompletionAttestation",
    "NaturalCorpusAttestation",
    "ReviewerExportAuthenticityAttestation",
    "SignedEvidenceEnvelope",
]
