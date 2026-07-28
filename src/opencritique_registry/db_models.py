from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PrincipalORM(Base):
    __tablename__ = "principals"

    actor_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiTokenORM(Base):
    __tablename__ = "api_tokens"

    token_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArtifactORM(Base):
    __tablename__ = "artifacts"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    rights_classification: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseORM(Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("case_id", "case_version", name="uq_case_version"),
        Index("ix_cases_rights", "rights_classification"),
    )

    registry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    case_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rights_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    imported_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ArtifactCaseLinkORM(Base):
    __tablename__ = "artifact_case_links"
    __table_args__ = (
        UniqueConstraint("case_id", "case_version", "sha256", name="uq_case_artifact"),
    )

    link_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(ForeignKey("artifacts.sha256"), index=True)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)


class ConcernIndexORM(Base):
    __tablename__ = "concern_index"

    concern_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_severity: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_confidence: Mapped[float] = mapped_column(nullable=False)
    concern_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class UseGrantORM(Base):
    __tablename__ = "use_grants"
    __table_args__ = (
        Index("ix_grant_lookup", "case_id", "case_version", "use_type", "status"),
    )

    grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    use_type: Mapped[str] = mapped_column(String(64), nullable=False)
    basis: Mapped[str] = mapped_column(String(64), nullable=False)
    authority: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdjudicationTaskORM(Base):
    __tablename__ = "adjudication_tasks"
    __table_args__ = (
        UniqueConstraint("case_id", "case_version", "concern_id", "slot", name="uq_task_slot"),
        Index("ix_task_claim", "status", "slot", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    concern_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdjudicationSubmissionORM(Base):
    __tablename__ = "adjudication_submissions"

    adjudication_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("adjudication_tasks.task_id"), unique=True, nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    concern_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    adjudicator_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeterminationORM(Base):
    __tablename__ = "determinations"
    __table_args__ = (
        Index("ix_determination_concern", "concern_id", "created_at"),
    )

    determination_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    concern_id: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(32))
    requires_tie_break: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    submission_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEventORM(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_target", "target_type", "target_id"),)

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExpertProfileORM(Base):
    __tablename__ = "expert_profiles"

    actor_id: Mapped[str] = mapped_column(
        ForeignKey("principals.actor_id"), primary_key=True
    )
    domains: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    methodologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    affiliation: Mapped[str | None] = mapped_column(String(255))
    biography: Mapped[str] = mapped_column(Text, nullable=False, default="")
    orcid: Mapped[str | None] = mapped_column(String(32))
    public_attribution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attribution_name: Mapped[str | None] = mapped_column(String(255))
    compensation_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="calibration")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CalibrationSetORM(Base):
    __tablename__ = "calibration_sets"
    __table_args__ = (Index("ix_calibration_set_domain", "domain_profile", "active"),)

    set_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    case_refs: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    min_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_threshold: Mapped[float] = mapped_column(nullable=False)
    max_false_critical: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CalibrationAttemptORM(Base):
    __tablename__ = "calibration_attempts"
    __table_args__ = (
        Index("ix_calibration_attempt_actor", "adjudicator_id", "created_at"),
    )

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    set_id: Mapped[str] = mapped_column(ForeignKey("calibration_sets.set_id"), index=True)
    adjudicator_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    score_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CalibrationTaskORM(Base):
    __tablename__ = "calibration_tasks"
    __table_args__ = (
        UniqueConstraint("attempt_id", "concern_id", name="uq_calibration_attempt_concern"),
        Index("ix_calibration_task_attempt", "attempt_id", "status"),
    )

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_attempts.attempt_id"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    concern_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CalibrationSubmissionORM(Base):
    __tablename__ = "calibration_submissions"

    submission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("calibration_tasks.task_id"), unique=True, nullable=False
    )
    adjudicator_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExpertQualificationORM(Base):
    __tablename__ = "expert_qualifications"
    __table_args__ = (
        Index("ix_qualification_lookup", "actor_id", "domain_profile", "status"),
    )

    qualification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    domain_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibration_attempts.attempt_id")
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseIntakeORM(Base):
    __tablename__ = "case_intakes"
    __table_args__ = (Index("ix_intake_status", "status", "created_at"),)

    intake_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_artifact_sha256: Mapped[str] = mapped_column(ForeignKey("artifacts.sha256"))
    domain_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    rights_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_uses: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rights_attestation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    contains_sensitive_data: Mapped[bool] = mapped_column(Boolean, nullable=False)
    contains_personal_data: Mapped[bool] = mapped_column(Boolean, nullable=False)
    redistribution_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("principals.actor_id"))
    review_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClaimReconstructionTaskORM(Base):
    __tablename__ = "claim_reconstruction_tasks"
    __table_args__ = (
        UniqueConstraint("intake_id", "slot", name="uq_claim_reconstruction_slot"),
        Index("ix_claim_task_claim", "status", "slot", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intake_id: Mapped[str] = mapped_column(ForeignKey("case_intakes.intake_id"), index=True)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("principals.actor_id"))
    anchor_context: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClaimReconstructionSubmissionORM(Base):
    __tablename__ = "claim_reconstruction_submissions"

    submission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("claim_reconstruction_tasks.task_id"), unique=True, nullable=False
    )
    intake_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    adjudicator_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClaimReconstructionDeterminationORM(Base):
    __tablename__ = "claim_reconstruction_determinations"
    __table_args__ = (Index("ix_claim_determination_intake", "intake_id", "created_at"),)

    determination_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    intake_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_claim_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    submission_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContributionCreditORM(Base):
    __tablename__ = "contribution_credits"
    __table_args__ = (
        UniqueConstraint("actor_id", "contribution_type", "target_id", name="uq_credit_target"),
        Index("ix_credit_actor", "actor_id", "created_at"),
    )

    credit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    contribution_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    public_name: Mapped[str | None] = mapped_column(String(255))
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    credit_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompensationRecordORM(Base):
    __tablename__ = "compensation_records"
    __table_args__ = (
        UniqueConstraint("task_type", "task_id", name="uq_compensation_task"),
        Index("ix_compensation_actor", "actor_id", "created_at"),
    )

    compensation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"))
    external_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NovelCandidateORM(Base):
    """Immutable snapshot of a novel-concern candidate (no in-place edits)."""

    __tablename__ = "novel_candidates"
    __table_args__ = (Index("ix_novel_candidate_case", "case_id", "case_version"),)

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    result_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    case_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_submission_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    matcher_version: Mapped[str] = mapped_column(String(128), nullable=False)
    matcher_config_id: Mapped[str] = mapped_column(String(128), nullable=False)
    benchmark_id: Mapped[str] = mapped_column(String(255), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NovelAdjudicationTaskORM(Base):
    __tablename__ = "novel_adjudication_tasks"
    __table_args__ = (
        UniqueConstraint("candidate_id", "slot", name="uq_novel_task_slot"),
        Index("ix_novel_task_claim", "status", "slot", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("novel_candidates.candidate_id"), nullable=False, index=True
    )
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NovelAdjudicationSubmissionORM(Base):
    __tablename__ = "novel_adjudication_submissions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("novel_adjudication_tasks.task_id"), unique=True, nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    adjudicator_id: Mapped[str] = mapped_column(ForeignKey("principals.actor_id"), index=True)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NovelDeterminationORM(Base):
    """Append-only novel-concern determinations; rows are never updated."""

    __tablename__ = "novel_determinations"
    __table_args__ = (Index("ix_novel_determination_candidate", "candidate_id", "created_at"),)

    determination_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("novel_candidates.candidate_id"), nullable=False
    )
    determination_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    determination_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requires_tie_break: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScorecardRecordORM(Base):
    """Immutable public scorecards; recomputes link predecessors."""

    __tablename__ = "scorecard_records"
    __table_args__ = (Index("ix_scorecard_predecessor", "predecessor_scorecard_id"),)

    scorecard_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scorecard_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    scorecard_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    benchmark_id: Mapped[str] = mapped_column(String(255), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scoring_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    predecessor_scorecard_id: Mapped[str | None] = mapped_column(String(64))
    predecessor_scorecard_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BenchmarkVersionORM(Base):
    """Append-only benchmark version registry; originals are never mutated."""

    __tablename__ = "benchmark_versions"
    __table_args__ = (
        UniqueConstraint("benchmark_id", "version", name="uq_benchmark_version"),
    )

    registry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    case_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    predecessor_version: Mapped[str | None] = mapped_column(String(64))
    created_from_determination_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
