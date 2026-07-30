from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .canonical import content_hash as compute_hash

ID = Annotated[str, StringConstraints(pattern=r"^oc[a-z]*_[A-Za-z0-9._-]+$")]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
URI = Annotated[str, StringConstraints(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ActorType(str, Enum):
    HUMAN = "human"
    SYSTEM = "system"
    TOOL = "tool"
    ORGANIZATION = "organization"


class ActorReference(StrictModel):
    actor_id: str
    actor_type: ActorType
    display_name: str | None = None


class RecordBase(StrictModel):
    id: ID
    schema_version: str = "0.1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: ActorReference
    content_hash: SHA256

    def expected_content_hash(self) -> str:
        return compute_hash(self)

    def verify_content_hash(self) -> bool:
        return self.content_hash == self.expected_content_hash()


class RightsClassification(str, Enum):
    PUBLIC = "public"
    CONTRIBUTED = "contributed"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class SourceFormat(str, Enum):
    PDF = "pdf"
    TEX = "tex"
    DOCX = "docx"
    MARKDOWN = "markdown"
    HTML = "html"
    OTHER = "other"


class ArtifactReference(StrictModel):
    uri: URI
    sha256: SHA256
    media_type: str
    byte_size: int = Field(ge=0)


class ArtifactSlice(StrictModel):
    artifact: ArtifactReference
    page: int | None = Field(default=None, ge=1)
    bounding_box: list[float] | None = Field(default=None, min_length=4, max_length=4)


class IngestionMetadata(StrictModel):
    method: str
    tool: str
    tool_version: str
    page_indexing: Literal["one-indexed"] = "one-indexed"
    notes: str = ""


class Manuscript(RecordBase):
    manuscript_id: ID
    title: str | None
    rights_classification: RightsClassification
    consent_policy_id: str
    current_version_id: ID

    @model_validator(mode="after")
    def ids_align(self) -> Manuscript:
        if self.id != self.manuscript_id:
            raise ValueError("id must equal manuscript_id")
        return self


class ManuscriptVersion(RecordBase):
    version_id: ID
    manuscript_id: ID
    previous_version_id: ID | None = None
    source_format: SourceFormat
    source_artifact: ArtifactReference
    rendered_artifact: ArtifactReference | None = None
    extracted_artifact: ArtifactReference | None = None
    language: str
    domain_profile: str
    page_count: int | None = Field(default=None, ge=1)
    ingestion_metadata: IngestionMetadata

    @model_validator(mode="after")
    def ids_align(self) -> ManuscriptVersion:
        if self.id != self.version_id:
            raise ValueError("id must equal version_id")
        return self


class AnchorType(str, Enum):
    TEXT_SPAN = "text_span"
    EQUATION = "equation"
    THEOREM = "theorem"
    FIGURE = "figure"
    PANEL = "panel"
    TABLE = "table"
    CELL = "cell"
    CITATION = "citation"
    BIBLIOGRAPHY_ENTRY = "bibliography_entry"
    CODE_REFERENCE = "code_reference"
    SECTION = "section"


class AnchorResolutionStatus(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY_CANDIDATE = "fuzzy_candidate"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    HUMAN_VERIFIED = "human_verified"


class BoundingBox(StrictModel):
    page: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float

    @model_validator(mode="after")
    def ordered(self) -> BoundingBox:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("bounding-box maxima must exceed minima")
        return self


class Anchor(RecordBase):
    anchor_id: ID
    manuscript_version_id: ID
    anchor_type: AnchorType
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    section_path: list[str] = Field(default_factory=list)
    source_text: str | None = None
    normalized_text: str | None = None
    object_label: str | None = None
    object_coordinates: dict[str, str | int | float] = Field(default_factory=dict)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rendered_reference: ArtifactSlice | None = None
    resolution_status: AnchorResolutionStatus

    @model_validator(mode="after")
    def validate_anchor(self) -> Anchor:
        if self.id != self.anchor_id:
            raise ValueError("id must equal anchor_id")
        if self.page_start and self.page_end and self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        has_text = bool(self.source_text)
        has_region = bool(self.bounding_boxes or self.rendered_reference)
        has_object = bool(self.object_label or self.object_coordinates)
        if not (has_text or has_region or has_object):
            raise ValueError("anchor needs text, a rendered region, or structured coordinates")
        if self.source_text and self.normalized_text is None:
            raise ValueError("text anchors must preserve normalized_text")
        return self


class ClaimType(str, Enum):
    THEORETICAL = "theoretical"
    EMPIRICAL = "empirical"
    STATISTICAL = "statistical"
    CAUSAL = "causal"
    METHODOLOGICAL = "methodological"
    NOVELTY = "novelty"
    INTERPRETIVE = "interpretive"
    REPRODUCIBILITY = "reproducibility"
    REPORTING = "reporting"
    SECURITY = "security"


class Explicitness(str, Enum):
    EXPLICIT = "explicit"
    STRONGLY_IMPLIED = "strongly_implied"
    INFERRED = "inferred"


class Claim(RecordBase):
    claim_id: ID
    manuscript_version_id: ID
    statement: str = Field(min_length=1)
    claim_type: ClaimType
    explicitness: Explicitness
    scope: str = Field(min_length=1)
    anchor_ids: list[ID] = Field(min_length=1)
    dependency_claim_ids: list[ID] = Field(default_factory=list)
    reconstruction_notes: str
    approval_status: Literal["candidate", "expert_approved", "rejected"] = "candidate"

    @model_validator(mode="after")
    def ids_align(self) -> Claim:
        if self.id != self.claim_id:
            raise ValueError("id must equal claim_id")
        if self.explicitness == Explicitness.INFERRED and not self.reconstruction_notes.strip():
            raise ValueError("inferred claims require reconstruction_notes")
        return self


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    INFORMATIONAL = "informational"


class VerificationGrade(str, Enum):
    V0 = "V0"
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"
    V5 = "V5"


class ConcernStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"


class ResolutionDisposition(str, Enum):
    """Disposition for RESOLVED concerns used by gold-reference eligibility.

    ``manuscript_correction`` marks an eligible historical defect. ``withdrawn``
    and ``rejected`` are not gold. Absent disposition is fail-closed (non-gold).
    """

    MANUSCRIPT_CORRECTION = "manuscript_correction"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"


class UncertaintySource(StrictModel):
    type: str
    description: str


class ConcernOriginType(str, Enum):
    HUMAN = "human"
    REVIEWER_SYSTEM = "reviewer_system"
    MUTATION_GENERATOR = "mutation_generator"
    REPLICATION = "replication"
    POST_PUBLICATION = "post_publication"


class ConcernOrigin(StrictModel):
    origin_type: ConcernOriginType
    origin_id: str
    run_id: ID | None = None
    original_severity: str | None = None
    original_confidence: str | float | None = None


class Concern(RecordBase):
    concern_id: ID
    manuscript_version_id: ID
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    concern_type: str = Field(min_length=1)
    claim_ids: list[ID] = Field(min_length=1)
    anchor_ids: list[ID] = Field(min_length=1)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    verification_grade: VerificationGrade
    status: ConcernStatus
    potential_consequence: str
    required_resolution: str | None = None
    resolution_disposition: ResolutionDisposition | None = None
    uncertainty_sources: list[UncertaintySource] = Field(default_factory=list)
    origin: ConcernOrigin

    @model_validator(mode="after")
    def validate_concern(self) -> Concern:
        if self.id != self.concern_id:
            raise ValueError("id must equal concern_id")
        if (
            self.severity in {Severity.CRITICAL, Severity.MAJOR}
            and not self.potential_consequence.strip()
        ):
            raise ValueError("major and critical concerns require potential_consequence")
        if (
            self.resolution_disposition is not None
            and self.status != ConcernStatus.RESOLVED
        ):
            raise ValueError(
                "resolution_disposition is only valid when status is resolved"
            )
        return self


class EvidenceType(str, Enum):
    MANUSCRIPT_TEXT = "manuscript_text"
    PAGE_RENDER = "page_render"
    EXTERNAL_SOURCE = "external_source"
    DETERMINISTIC_COMPUTATION = "deterministic_computation"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    SYMBOLIC_ANALYSIS = "symbolic_analysis"
    FORMAL_TOOL_OUTPUT = "formal_tool_output"
    CODE_EXECUTION = "code_execution"
    EXPERT_REASONING = "expert_reasoning"
    AUTHOR_RESPONSE = "author_response"
    PROCEDURAL = "procedural"


class EvidenceDirection(str, Enum):
    CONCERN = "concern"
    MANUSCRIPT_DEFENSE = "manuscript_defense"
    UNCERTAINTY = "uncertainty"
    PROCEDURAL_FACT = "procedural_fact"


class ReproducibilityStatus(str, Enum):
    REPRODUCIBLE = "reproducible"
    PARTIALLY_REPRODUCIBLE = "partially_reproducible"
    NON_REPRODUCIBLE = "non_reproducible"
    JUDGMENT_BASED = "judgment_based"


class ToolManifest(StrictModel):
    tool: str
    version: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    output_hash: SHA256 | None = None


class EvidenceItem(RecordBase):
    evidence_id: ID
    concern_id: ID
    evidence_type: EvidenceType
    supports: EvidenceDirection
    description: str = Field(min_length=1)
    artifact_reference: ArtifactReference | None = None
    anchor_ids: list[ID] = Field(default_factory=list)
    method: str
    producer: ActorReference
    tool_manifest: ToolManifest | None = None
    reproducibility_status: ReproducibilityStatus
    limitations: str
    independence_group: str

    @model_validator(mode="after")
    def ids_align(self) -> EvidenceItem:
        if self.id != self.evidence_id:
            raise ValueError("id must equal evidence_id")
        return self


class CounterpositionSource(str, Enum):
    AUTHOR = "author"
    ADJUDICATOR = "adjudicator"
    REVIEWER_SYSTEM = "reviewer_system"
    DOMAIN_TOOL = "domain_tool"
    PUBLISHED_SOURCE = "published_source"


class Counterposition(RecordBase):
    counterposition_id: ID
    concern_id: ID
    statement: str = Field(min_length=1)
    supporting_anchor_ids: list[ID] = Field(default_factory=list)
    supporting_evidence_ids: list[ID] = Field(default_factory=list)
    source: CounterpositionSource
    residual_disagreement: str
    adequacy_status: Literal["unreviewed", "adequate", "inadequate"] = "unreviewed"

    @model_validator(mode="after")
    def ids_align(self) -> Counterposition:
        if self.id != self.counterposition_id:
            raise ValueError("id must equal counterposition_id")
        return self


class ValidityDecision(str, Enum):
    CONFIRMED = "confirmed"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class ConflictDeclaration(StrictModel):
    status: Literal["none", "disclosed", "disqualifying"]
    description: str = ""


class FollowupRequest(StrictModel):
    request_type: str
    description: str
    blocking: bool = False


class Adjudication(RecordBase):
    adjudication_id: ID
    concern_id: ID
    adjudicator_id: str
    adjudication_round: int = Field(ge=1)
    blinded_fields: list[str]
    conflict_declaration: ConflictDeclaration
    validity: ValidityDecision
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
    evidence_ids: list[ID]
    counterposition_assessment: str
    requested_followup: list[FollowupRequest] = Field(default_factory=list)
    anchors_reviewed: bool

    @model_validator(mode="after")
    def validate_adjudication(self) -> Adjudication:
        if self.id != self.adjudication_id:
            raise ValueError("id must equal adjudication_id")
        if self.conflict_declaration.status == "disqualifying":
            raise ValueError("disqualified adjudicators cannot submit decisions")
        if not self.anchors_reviewed:
            raise ValueError("adjudicator must confirm anchor review")
        return self


class ResolutionType(str, Enum):
    MANUSCRIPT_REVISED = "manuscript_revised"
    EXPLANATION_ADDED = "explanation_added"
    ANALYSIS_RERUN = "analysis_rerun"
    CONCERN_WITHDRAWN = "concern_withdrawn"
    DISAGREEMENT_DOCUMENTED = "disagreement_documented"
    EXTERNAL_CORRECTION = "external_correction"
    UNRESOLVED = "unresolved"


class Resolution(RecordBase):
    resolution_id: ID
    concern_id: ID
    resolution_type: ResolutionType
    description: str
    from_version_id: ID
    to_version_id: ID | None = None
    verification_evidence_ids: list[ID] = Field(default_factory=list)

    @model_validator(mode="after")
    def ids_align(self) -> Resolution:
        if self.id != self.resolution_id:
            raise ValueError("id must equal resolution_id")
        return self


class RunCost(StrictModel):
    currency: str
    total: float = Field(ge=0)


class RunManifest(RecordBase):
    run_id: ID
    system_id: str
    system_version: str
    code_commit: str | None = None
    model_identifiers: list[str]
    prompt_hashes: list[SHA256]
    tool_versions: dict[str, str]
    input_hashes: list[SHA256]
    retrieval_snapshot_ids: list[str]
    configuration: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    cost: RunCost
    latency_seconds: float = Field(ge=0)
    randomness_configuration: dict[str, Any]
    output_hash: SHA256

    @model_validator(mode="after")
    def validate_run(self) -> RunManifest:
        if self.id != self.run_id:
            raise ValueError("id must equal run_id")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        return self


class MutationRecord(StrictModel):
    mutation_id: str
    source_version_id: ID
    mutated_version_id: ID
    operation_type: str
    operation_description: str
    affected_anchor_ids: list[ID]
    intended_concern_id: ID
    expected_severity_range: list[Severity]
    collateral_change_analysis: str
    validation_adjudicator_ids: list[str]


class CaseBundle(StrictModel):
    case_id: ID
    case_version: str
    policy_version: str
    case_type: Literal["natural", "controlled_mutation", "microcase", "adversarial"]
    manuscript: Manuscript
    manuscript_versions: list[ManuscriptVersion]
    anchors: list[Anchor]
    claims: list[Claim]
    concerns: list[Concern]
    evidence: list[EvidenceItem]
    counterpositions: list[Counterposition]
    adjudications: list[Adjudication]
    resolutions: list[Resolution] = Field(default_factory=list)
    run_manifests: list[RunManifest] = Field(default_factory=list)
    mutation: MutationRecord | None = None
    known_ambiguities: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def cross_validate(self) -> CaseBundle:
        version_ids = {x.version_id for x in self.manuscript_versions}
        anchor_map = {x.anchor_id: x for x in self.anchors}
        claim_map = {x.claim_id: x for x in self.claims}
        concern_map = {x.concern_id: x for x in self.concerns}
        evidence_map = {x.evidence_id: x for x in self.evidence}
        counter_by_concern: dict[str, list[Counterposition]] = {}
        adj_by_concern: dict[str, list[Adjudication]] = {}
        res_by_concern: dict[str, list[Resolution]] = {}

        if self.manuscript.current_version_id not in version_ids:
            raise ValueError("current manuscript version is absent")
        if any(v.manuscript_id != self.manuscript.manuscript_id for v in self.manuscript_versions):
            raise ValueError("manuscript version points to a different manuscript")

        for anchor in self.anchors:
            if anchor.manuscript_version_id not in version_ids:
                raise ValueError(f"anchor {anchor.id} points to an absent manuscript version")
        for claim in self.claims:
            if claim.manuscript_version_id not in version_ids:
                raise ValueError(f"claim {claim.id} points to an absent manuscript version")
            if any(aid not in anchor_map for aid in claim.anchor_ids):
                raise ValueError(f"claim {claim.id} references an absent anchor")
        for evidence in self.evidence:
            if evidence.concern_id not in concern_map:
                raise ValueError(f"evidence {evidence.id} references an absent concern")
            if any(aid not in anchor_map for aid in evidence.anchor_ids):
                raise ValueError(f"evidence {evidence.id} references an absent anchor")
        for counter in self.counterpositions:
            if counter.concern_id not in concern_map:
                raise ValueError(f"counterposition {counter.id} references an absent concern")
            if any(aid not in anchor_map for aid in counter.supporting_anchor_ids):
                raise ValueError(f"counterposition {counter.id} references an absent anchor")
            if any(eid not in evidence_map for eid in counter.supporting_evidence_ids):
                raise ValueError(f"counterposition {counter.id} references absent evidence")
            counter_by_concern.setdefault(counter.concern_id, []).append(counter)
        for adjudication in self.adjudications:
            if adjudication.concern_id not in concern_map:
                raise ValueError(f"adjudication {adjudication.id} references an absent concern")
            if any(eid not in evidence_map for eid in adjudication.evidence_ids):
                raise ValueError(f"adjudication {adjudication.id} references absent evidence")
            adj_by_concern.setdefault(adjudication.concern_id, []).append(adjudication)
        for resolution in self.resolutions:
            if resolution.concern_id not in concern_map:
                raise ValueError(f"resolution {resolution.id} references an absent concern")
            res_by_concern.setdefault(resolution.concern_id, []).append(resolution)

        final_states = {
            ConcernStatus.CONFIRMED,
            ConcernStatus.QUALIFIED,
            ConcernStatus.REJECTED,
            ConcernStatus.UNRESOLVED,
            ConcernStatus.RESOLVED,
        }
        for concern in self.concerns:
            if concern.manuscript_version_id not in version_ids:
                raise ValueError(f"concern {concern.id} points to an absent manuscript version")
            if any(cid not in claim_map for cid in concern.claim_ids):
                raise ValueError(f"concern {concern.id} references an absent claim")
            if any(aid not in anchor_map for aid in concern.anchor_ids):
                raise ValueError(f"concern {concern.id} references an absent anchor")
            linked_versions = {
                claim_map[cid].manuscript_version_id for cid in concern.claim_ids
            } | {anchor_map[aid].manuscript_version_id for aid in concern.anchor_ids}
            if linked_versions != {concern.manuscript_version_id}:
                raise ValueError(f"concern {concern.id} crosses manuscript versions")
            if concern.severity in {Severity.CRITICAL, Severity.MAJOR}:
                if not counter_by_concern.get(concern.concern_id):
                    raise ValueError(f"{concern.severity.value} concern lacks a counterposition")
            if concern.status in final_states and concern.severity in {
                Severity.CRITICAL,
                Severity.MAJOR,
            }:
                if len(adj_by_concern.get(concern.concern_id, [])) < 2:
                    raise ValueError("final major/critical concerns require two adjudications")
            if concern.verification_grade in {VerificationGrade.V4, VerificationGrade.V5}:
                if len(adj_by_concern.get(concern.concern_id, [])) < 2:
                    raise ValueError("V4/V5 concerns require two adjudications")
            if concern.verification_grade == VerificationGrade.V5:
                if not res_by_concern.get(concern.concern_id):
                    raise ValueError("V5 concerns require a resolution record")
            if concern.severity in {Severity.CRITICAL, Severity.MAJOR}:
                non_textual = any(
                    anchor_map[aid].anchor_type
                    in {
                        AnchorType.FIGURE,
                        AnchorType.PANEL,
                        AnchorType.TABLE,
                        AnchorType.CELL,
                        AnchorType.EQUATION,
                    }
                    for aid in concern.anchor_ids
                )
                if non_textual and not any(
                    anchor_map[aid].rendered_reference is not None for aid in concern.anchor_ids
                ):
                    raise ValueError("major/critical non-textual concern needs rendered evidence")

        if self.case_type == "controlled_mutation" and self.mutation is None:
            raise ValueError("controlled-mutation cases require mutation metadata")
        return self
