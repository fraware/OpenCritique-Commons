from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from opencritique_schema.models import (
    ClaimType,
    Explicitness,
    RightsClassification,
)

from .schemas import DataUse, StrictModel, TaskSlot, TaskStatus


class ExpertStatus(str, Enum):
    CALIBRATION = "calibration"
    ELIGIBLE = "eligible"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class QualificationStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CalibrationAttemptStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class IntakeStatus(str, Enum):
    SUBMITTED = "submitted"
    NEEDS_CHANGES = "needs_changes"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ClaimDeterminationStatus(str, Enum):
    ACCEPTED = "accepted"
    NEEDS_TIE_BREAK = "needs_tie_break"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class CompensationStatus(str, Enum):
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class ExpertProfileInput(StrictModel):
    domains: list[str] = Field(min_length=1)
    methodologies: list[str] = Field(default_factory=list)
    affiliation: str | None = None
    biography: str = ""
    orcid: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    public_attribution: bool = False
    attribution_name: str | None = None
    compensation_currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def attribution_is_explicit(self) -> ExpertProfileInput:
        if self.public_attribution and not (self.attribution_name or "").strip():
            raise ValueError("public attribution requires attribution_name")
        return self


class ExpertProfileView(ExpertProfileInput):
    actor_id: str
    status: ExpertStatus
    created_at: datetime
    updated_at: datetime


class CalibrationCaseRef(StrictModel):
    case_id: str
    case_version: str
    concern_id: str


class CalibrationSetInput(StrictModel):
    name: str = Field(min_length=1)
    domain_profile: str = Field(min_length=1)
    case_refs: list[CalibrationCaseRef] = Field(min_length=1)
    min_cases: int = Field(ge=1)
    pass_threshold: float = Field(ge=0.0, le=1.0, default=0.8)
    max_false_critical: int = Field(ge=0, default=0)
    active: bool = True

    @model_validator(mode="after")
    def min_cases_fit(self) -> CalibrationSetInput:
        if self.min_cases > len(self.case_refs):
            raise ValueError("min_cases cannot exceed number of case references")
        return self


class CalibrationSetView(CalibrationSetInput):
    set_id: str
    created_by: str
    created_at: datetime


class CalibrationScore(StrictModel):
    completed_cases: int
    validity_accuracy: float
    severity_exact_accuracy: float
    severity_mean_absolute_distance: float
    false_critical_count: int
    aggregate_score: float
    passed: bool


class CalibrationAttemptView(StrictModel):
    attempt_id: str
    set_id: str
    adjudicator_id: str
    status: CalibrationAttemptStatus
    score: CalibrationScore | None
    passed: bool | None
    created_at: datetime
    completed_at: datetime | None


class CalibrationTaskView(StrictModel):
    task_id: str
    attempt_id: str
    case_id: str
    case_version: str
    concern_id: str
    sequence: int
    status: TaskStatus
    completed_at: datetime | None


class CalibrationSubmissionView(StrictModel):
    submission_id: str
    task: CalibrationTaskView
    attempt: CalibrationAttemptView


class QualificationView(StrictModel):
    qualification_id: str
    actor_id: str
    domain_profile: str
    status: QualificationStatus
    source_attempt_id: str | None
    valid_from: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    created_by: str
    created_at: datetime


class RightsAuthorityType(str, Enum):
    SELF_AUTHORED = "self_authored"
    PUBLIC_LICENSE = "public_license"
    COAUTHOR_AUTHORIZED = "coauthor_authorized"
    INSTITUTIONAL_AGREEMENT = "institutional_agreement"
    OTHER = "other"


class CoauthorConsentStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    CONFIRMED = "confirmed"
    PENDING = "pending"
    UNKNOWN = "unknown"


class RightsAttestation(StrictModel):
    authority_type: RightsAuthorityType
    authority_statement: str = Field(min_length=20)
    public_source_url: str | None = None
    coauthor_consent_status: CoauthorConsentStatus
    attests_accuracy: Literal[True]
    attests_authority: Literal[True]

    @model_validator(mode="after")
    def public_license_needs_source(self) -> RightsAttestation:
        if self.authority_type == RightsAuthorityType.PUBLIC_LICENSE and not self.public_source_url:
            raise ValueError("public-license intake requires public_source_url")
        if (
            self.authority_type == RightsAuthorityType.SELF_AUTHORED
            and self.coauthor_consent_status == CoauthorConsentStatus.UNKNOWN
        ):
            raise ValueError("self-authored multi-party rights cannot be marked unknown")
        return self


class CaseIntakeInput(StrictModel):
    title: str = Field(min_length=1)
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    domain_profile: str = Field(min_length=1)
    language: str = Field(min_length=2)
    rights_classification: RightsClassification
    requested_uses: list[DataUse] = Field(min_length=1)
    rights_attestation: RightsAttestation
    contains_sensitive_data: bool = False
    contains_personal_data: bool = False
    redistribution_allowed: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def public_use_requires_permission(self) -> CaseIntakeInput:
        public_uses = {DataUse.PUBLIC_RELEASE, DataUse.OPEN_MODEL_TRAINING}
        if public_uses.intersection(self.requested_uses) and not self.redistribution_allowed:
            raise ValueError("public release or training use requires redistribution_allowed")
        if (
            self.rights_classification
            in {RightsClassification.CONFIDENTIAL, RightsClassification.RESTRICTED}
            and self.redistribution_allowed
        ):
            raise ValueError("confidential or restricted intake cannot permit redistribution")
        return self


class CaseIntakeReviewInput(StrictModel):
    status: Literal["accepted", "needs_changes", "rejected"]
    reason: str = Field(min_length=10)


class CaseIntakeView(CaseIntakeInput):
    intake_id: str
    submitted_by: str
    status: IntakeStatus
    reviewed_by: str | None
    review_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class ClaimAnchorContext(StrictModel):
    anchor_id: str
    page: int | None = Field(default=None, ge=1)
    section_path: list[str] = Field(default_factory=list)
    source_text: str | None = None
    object_label: str | None = None


class ClaimTaskSeedInput(StrictModel):
    anchor_context: list[ClaimAnchorContext] = Field(min_length=1)


class ClaimTaskView(StrictModel):
    task_id: str
    intake_id: str
    slot: TaskSlot
    status: TaskStatus
    assigned_to: str | None
    anchor_context: list[ClaimAnchorContext]
    claimed_at: datetime | None
    completed_at: datetime | None


class ClaimTaskPayload(StrictModel):
    task: ClaimTaskView
    title: str
    domain_profile: str
    language: str
    source_artifact_sha256: str
    prior_reconstructions: list[dict[str, Any]] = Field(default_factory=list)
    blinded_fields: list[str]


class ClaimReconstructionInput(StrictModel):
    statement: str = Field(min_length=10)
    claim_type: ClaimType
    explicitness: Explicitness
    scope: str = Field(min_length=3)
    anchor_ids: list[str] = Field(min_length=1)
    reconstruction_notes: str = ""

    @model_validator(mode="after")
    def inferred_needs_notes(self) -> ClaimReconstructionInput:
        if self.explicitness == Explicitness.INFERRED and not self.reconstruction_notes.strip():
            raise ValueError("inferred claim reconstruction requires notes")
        return self


class ClaimSubmissionView(StrictModel):
    submission_id: str
    task: ClaimTaskView
    claim: ClaimReconstructionInput


class ClaimDeterminationInput(StrictModel):
    status: ClaimDeterminationStatus
    canonical_claim: ClaimReconstructionInput | None = None
    selected_submission_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=20)

    @model_validator(mode="after")
    def accepted_needs_claim(self) -> ClaimDeterminationInput:
        if self.status == ClaimDeterminationStatus.ACCEPTED and self.canonical_claim is None:
            raise ValueError("accepted determination requires canonical_claim")
        return self


class ClaimDeterminationView(ClaimDeterminationInput):
    determination_id: str
    intake_id: str
    created_by: str
    created_at: datetime


class ContributionCreditView(StrictModel):
    credit_id: str
    actor_id: str
    contribution_type: str
    target_type: str
    target_id: str
    public_name: str | None
    public: bool
    metadata: dict[str, Any]
    created_at: datetime


class CompensationInput(StrictModel):
    actor_id: str
    task_type: Literal["adjudication", "calibration", "claim_reconstruction"]
    task_id: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    basis: str = Field(min_length=10)


class CompensationStatusInput(StrictModel):
    status: Literal["paid", "cancelled"]
    external_reference: str | None = None


class CompensationView(CompensationInput):
    compensation_id: str
    status: CompensationStatus
    approved_by: str
    external_reference: str | None
    created_at: datetime
    paid_at: datetime | None


class AgreementMetrics(StrictModel):
    paired_concerns: int
    validity_raw_agreement: float | None
    validity_cohens_kappa: float | None
    severity_exact_agreement: float | None
    severity_cohens_kappa: float | None
    severity_mean_absolute_distance: float | None
    contested_critical_rate: float | None
    tie_break_rate: float | None
    validity_distribution: dict[str, int]
    domain_breakdown: dict[str, dict[str, float | int | None]]


class CalibrationMetrics(StrictModel):
    attempts: int
    completed_attempts: int
    passed_attempts: int
    pass_rate: float | None
    active_qualifications: int


class CommunityMetrics(StrictModel):
    agreement: AgreementMetrics
    calibration: CalibrationMetrics
    contribution_credits: int
    approved_compensation_minor_by_currency: dict[str, int]
