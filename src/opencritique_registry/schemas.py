from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from opencritique_schema.models import (
    Adjudication,
    AnchorType,
    CaseBundle,
    ConflictDeclaration,
    FollowupRequest,
    RightsClassification,
    Severity,
    UncertaintySource,
    ValidityDecision,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrincipalRole(str, Enum):
    ADMIN = "admin"
    CASE_MANAGER = "case_manager"
    ADJUDICATOR = "adjudicator"
    CONTRIBUTOR = "contributor"
    DEVELOPER = "developer"
    AUDITOR = "auditor"
    PUBLIC = "public"


class DataUse(str, Enum):
    OPERATIONAL_PROCESSING = "operational_processing"
    RETENTION = "retention"
    EXPERT_ADJUDICATION = "expert_adjudication"
    BENCHMARK_EVALUATION = "benchmark_evaluation"
    PUBLIC_RELEASE = "public_release"
    OPEN_MODEL_TRAINING = "open_model_training"


class GrantBasis(str, Enum):
    PROJECT_CREATED = "project_created"
    PUBLIC_LICENSE = "public_license"
    CONTRIBUTOR_CONSENT = "contributor_consent"
    INSTITUTIONAL_AGREEMENT = "institutional_agreement"
    OPERATIONAL_NECESSITY = "operational_necessity"


class GrantStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TaskSlot(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TIE_BREAK = "tie_break"


class TaskStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PrincipalCreate(StrictModel):
    actor_id: str = Field(min_length=1)
    role: PrincipalRole
    display_name: str | None = None


class PrincipalView(StrictModel):
    actor_id: str
    role: PrincipalRole
    display_name: str | None
    active: bool


class TokenCreate(StrictModel):
    actor_id: str
    expires_at: datetime | None = None


class TokenIssued(StrictModel):
    token_id: str
    token: str
    actor_id: str
    expires_at: datetime | None


class RightsGrantInput(StrictModel):
    use: DataUse
    basis: GrantBasis
    authority: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    expires_at: datetime | None = None


class RightsGrantView(StrictModel):
    grant_id: str
    case_id: str
    case_version: str
    use: DataUse
    basis: GrantBasis
    authority: str
    scope: str
    status: GrantStatus
    granted_by: str
    created_at: datetime
    revoked_at: datetime | None
    expires_at: datetime | None


class CaseRegistration(StrictModel):
    bundle: CaseBundle
    grants: list[RightsGrantInput] = Field(default_factory=list)


class CaseView(StrictModel):
    case_id: str
    case_version: str
    case_type: str
    rights_classification: RightsClassification
    bundle_hash: str
    imported_at: datetime
    imported_by: str


class ArtifactView(StrictModel):
    sha256: str
    media_type: str
    byte_size: int
    rights_classification: RightsClassification
    download_path: str


class TaskSeedRequest(StrictModel):
    concern_ids: list[str] | None = None


class TaskView(StrictModel):
    task_id: str
    case_id: str
    case_version: str
    concern_id: str
    slot: TaskSlot
    status: TaskStatus
    assigned_to: str | None
    claimed_at: datetime | None
    completed_at: datetime | None


class BlindedClaim(StrictModel):
    claim_id: str
    statement: str
    claim_type: str
    explicitness: str
    scope: str
    anchor_ids: list[str]
    reconstruction_notes: str
    approval_status: str


class BlindedAnchor(StrictModel):
    anchor_id: str
    anchor_type: AnchorType
    page_start: int | None
    page_end: int | None
    bounding_boxes: list[dict[str, Any]]
    section_path: list[str]
    source_text: str | None
    normalized_text: str | None
    object_label: str | None
    object_coordinates: dict[str, str | int | float]
    extraction_confidence: float | None
    rendered_artifact_sha256: str | None
    resolution_status: str


class BlindedEvidence(StrictModel):
    evidence_id: str
    evidence_type: str
    supports: str
    description: str
    anchor_ids: list[str]
    method: str
    reproducibility_status: str
    limitations: str
    independence_group: str
    artifact_sha256: str | None
    source_label: Literal["blinded_source"] = "blinded_source"


class BlindedCounterposition(StrictModel):
    counterposition_id: str
    statement: str
    supporting_anchor_ids: list[str]
    supporting_evidence_ids: list[str]
    residual_disagreement: str
    adequacy_status: str
    source_label: Literal["blinded_counterposition"] = "blinded_counterposition"


class PriorAdjudicationView(StrictModel):
    slot: TaskSlot
    validity: ValidityDecision
    severity: Severity
    confidence: float
    reasoning: str
    evidence_ids: list[str]
    counterposition_assessment: str
    requested_followup: list[FollowupRequest]


class BlindedTaskPayload(StrictModel):
    task_id: str
    slot: TaskSlot
    case_id: str
    case_version: str
    case_type: str
    manuscript_title: str | None
    domain_profile: str
    language: str
    manuscript_artifact_sha256: str
    rendered_artifact_sha256: str | None
    concern_id: str
    concern_title: str
    concern_summary: str
    concern_type: str
    proposed_consequence: str
    proposed_resolution: str | None
    uncertainty_sources: list[UncertaintySource]
    claims: list[BlindedClaim]
    anchors: list[BlindedAnchor]
    evidence: list[BlindedEvidence]
    counterpositions: list[BlindedCounterposition]
    prior_adjudications: list[PriorAdjudicationView] = Field(default_factory=list)
    blinded_fields: list[str]


class AdjudicationSubmissionInput(StrictModel):
    validity: ValidityDecision
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=20)
    evidence_ids: list[str] = Field(default_factory=list)
    counterposition_assessment: str = Field(min_length=1)
    requested_followup: list[FollowupRequest] = Field(default_factory=list)
    anchors_reviewed: bool
    conflict_declaration: ConflictDeclaration


class SubmissionView(StrictModel):
    adjudication: Adjudication
    task: TaskView


class DeterminationView(StrictModel):
    determination_id: str
    case_id: str
    case_version: str
    concern_id: str
    policy_version: str
    status: str
    severity: Severity | None
    requires_tie_break: bool
    rationale: str
    submission_ids: list[str]
    created_at: datetime


class AppealRecordInput(StrictModel):
    concern_id: str = Field(min_length=1)
    determination_id: str = Field(min_length=1)
    record_type: Literal["appeal", "correction"]
    rationale: str = Field(min_length=10)
    requested_by: str = Field(min_length=1)
    predecessor_record_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AppealRecordView(StrictModel):
    record_id: str
    case_id: str
    case_version: str
    concern_id: str
    determination_id: str
    record_type: Literal["appeal", "correction"]
    predecessor_record_id: str | None
    requested_by: str
    rationale: str
    payload: dict[str, Any]
    created_at: datetime


class TokenRevoked(StrictModel):
    token_id: str
    revoked_at: datetime


class AuditEventView(StrictModel):
    event_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    event_data: dict[str, Any]
    created_at: datetime
