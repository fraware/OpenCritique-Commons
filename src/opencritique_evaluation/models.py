from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
    model_validator,
)

from opencritique_schema.models import Severity

if TYPE_CHECKING:
    from .trust import TrustPolicyMode, TrustStore


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BenchmarkEvidenceClass(str, Enum):
    CONFORMANCE = "conformance"
    SYNTHETIC_SCIENTIFIC = "synthetic_scientific"
    EXPERT_NATURAL = "expert_natural"
    LIVE_PRIVATE = "live_private"


class ReferenceCompleteness(str, Enum):
    COMPLETE_SEEDED = "complete_seeded"
    PARTIAL_NATURAL = "partial_natural"
    UNKNOWN = "unknown"


class ClaimScope(str, Enum):
    """Signed authorization scope for scientific performance language."""

    NONE = "none"
    PRIVATE_METHOD_REPORT = "private_method_report"
    PUBLIC_DOMAIN_BOUNDED = "public_domain_bounded"
    PUBLIC_COMPARATIVE = "public_comparative"


_PUBLIC_CLAIM_SCOPES = frozenset(
    {
        ClaimScope.PUBLIC_DOMAIN_BOUNDED,
        ClaimScope.PUBLIC_COMPARATIVE,
    }
)


class ClaimAuthorizationDecision(StrictModel):
    """Immutable claim-authorization decision payload (signed inside an envelope)."""

    claim_scope: ClaimScope
    authorized_metrics: list[str] = Field(default_factory=list)
    benchmark_id: str
    benchmark_version: str
    case_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    scoring_policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    matcher_version: str
    matcher_config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    domain_scope: str = Field(min_length=1)
    use_scope: str = Field(min_length=1)
    issued_at: datetime
    not_after: datetime
    authority_id: str = Field(min_length=1)
    predecessor_id: str | None = None

    @model_validator(mode="after")
    def validity_interval(self) -> ClaimAuthorizationDecision:
        if self.not_after <= self.issued_at:
            raise ValueError("not_after must be after issued_at")
        return self


class SignedClaimAuthorizationEnvelope(StrictModel):
    """Ed25519-signed claim authorization decision."""

    envelope_version: str = "0.1"
    decision: ClaimAuthorizationDecision
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(min_length=1, description="Ed25519 signature (base64)")
    key_id: str = Field(min_length=1)
    signed_at: datetime
    algorithm: Literal["Ed25519"] = "Ed25519"


class ClaimAuthorization(StrictModel):
    """Structured claim authorization; prefer ``claim_scope`` over the bool.

    Public scopes are a derived view of a successfully verified
    ``SignedClaimAuthorizationEnvelope``. Digest strings alone do not authorize.
    """

    claim_scope: ClaimScope
    expert_natural_evidence: bool = False
    rights_cleared_cases: bool = False
    protected_holdout: bool = False
    independent_evaluation: bool = False
    matcher_audit_complete: bool = False
    frozen_scoring_policy: bool = False
    signed_authorization_manifest_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    signed_authorization_manifest_path: str | None = None
    domain_scope: str | None = None
    use_scope: str | None = None
    authorization_verified: bool = False
    verification_report_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    @model_validator(mode="before")
    @classmethod
    def drop_derived_performance_flag(cls, data: object) -> object:
        """Ignore transitional bool on input so JSON round-trips stay valid."""
        if isinstance(data, dict) and "performance_claim_authorized" in data:
            data = dict(data)
            data.pop("performance_claim_authorized", None)
        return data

    @computed_field  # type: ignore[prop-decorator]
    @property
    def performance_claim_authorized(self) -> bool:
        """Transitional: true only for verified public scientific scopes."""
        return (
            self.claim_scope in _PUBLIC_CLAIM_SCOPES and self.authorization_verified
        )

    @classmethod
    def none(cls) -> ClaimAuthorization:
        return cls(claim_scope=ClaimScope.NONE)


class BenchmarkCaseRef(StrictModel):
    case_id: str
    case_version: str
    path: str


class BenchmarkManifest(StrictModel):
    benchmark_id: str
    version: str
    title: str
    description: str
    evidence_class: BenchmarkEvidenceClass
    reference_completeness: ReferenceCompleteness
    domain_profiles: list[str] = Field(min_length=1)
    cases: list[BenchmarkCaseRef] = Field(min_length=1)
    independent_evaluation: bool = False
    expert_adjudicated: bool = False
    minimum_public_claim_cases: int = Field(default=40, ge=1)
    rights_cleared_cases: bool = False
    protected_holdout: bool = False
    matcher_audit_complete: bool = False
    frozen_scoring_policy: bool = False
    signed_authorization_manifest_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    signed_authorization_manifest_path: str | None = None
    domain_scope: str | None = None
    use_scope: str | None = None
    comparative_authorization: bool = False
    license: str
    source_url: HttpUrl | None = None
    case_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_cases(self) -> BenchmarkManifest:
        keys = [(item.case_id, item.case_version) for item in self.cases]
        if len(keys) != len(set(keys)):
            raise ValueError("benchmark case references must be unique")
        return self

    def claim_authorization(
        self,
        *,
        envelope: SignedClaimAuthorizationEnvelope | None = None,
        trust_store: TrustStore | None = None,
        trust_store_path: Path | None = None,
        policy_mode: TrustPolicyMode | None = None,
        at: datetime | None = None,
        matcher_version: str | None = None,
        matcher_config: MatcherConfig | None = None,
        scoring_policy_version: str = "scoring-policy-v0.1",
        base_path: Path | None = None,
    ) -> ClaimAuthorization:
        """Resolve structured authorization; LIVE_PRIVATE never yields public_*.

        Public scopes require a **cryptographically verified** claim-authorization
        envelope bound to this benchmark. A non-empty 64-hex digest alone is not
        sufficient (fail closed).
        """
        from .claim_auth_verify import (
            DEFAULT_MATCHER_VERSION,
            derived_claim_authorization,
            load_claim_authorization_envelope,
            verify_claim_authorization,
        )

        expert_natural = self.evidence_class == BenchmarkEvidenceClass.EXPERT_NATURAL
        live_private = self.evidence_class == BenchmarkEvidenceClass.LIVE_PRIVATE
        has_scopes = bool(
            (self.domain_scope or "").strip() and (self.use_scope or "").strip()
        )
        public_prereqs = (
            expert_natural
            and self.expert_adjudicated
            and self.independent_evaluation
            and self.rights_cleared_cases
            and self.protected_holdout
            and self.matcher_audit_complete
            and self.frozen_scoring_policy
            and has_scopes
            and len(self.cases) >= self.minimum_public_claim_cases
        )

        if live_private:
            return ClaimAuthorization(
                claim_scope=ClaimScope.PRIVATE_METHOD_REPORT,
                expert_natural_evidence=expert_natural,
                rights_cleared_cases=self.rights_cleared_cases,
                protected_holdout=self.protected_holdout,
                independent_evaluation=self.independent_evaluation,
                matcher_audit_complete=self.matcher_audit_complete,
                frozen_scoring_policy=self.frozen_scoring_policy,
                signed_authorization_manifest_digest=(
                    self.signed_authorization_manifest_digest
                ),
                signed_authorization_manifest_path=(
                    self.signed_authorization_manifest_path
                ),
                domain_scope=self.domain_scope,
                use_scope=self.use_scope,
                authorization_verified=False,
            )

        loaded = envelope
        if loaded is None and self.signed_authorization_manifest_path:
            path = Path(self.signed_authorization_manifest_path)
            if not path.is_absolute() and base_path is not None:
                path = base_path / path
            if path.is_file():
                try:
                    loaded = load_claim_authorization_envelope(path)
                except (OSError, ValueError):
                    loaded = None

        if not public_prereqs or loaded is None:
            return ClaimAuthorization(
                claim_scope=ClaimScope.NONE,
                expert_natural_evidence=expert_natural,
                rights_cleared_cases=self.rights_cleared_cases,
                protected_holdout=self.protected_holdout,
                independent_evaluation=self.independent_evaluation,
                matcher_audit_complete=self.matcher_audit_complete,
                frozen_scoring_policy=self.frozen_scoring_policy,
                signed_authorization_manifest_digest=(
                    self.signed_authorization_manifest_digest
                ),
                signed_authorization_manifest_path=(
                    self.signed_authorization_manifest_path
                ),
                domain_scope=self.domain_scope,
                use_scope=self.use_scope,
                authorization_verified=False,
            )

        report = verify_claim_authorization(
            loaded,
            benchmark=self,
            matcher_version=matcher_version or DEFAULT_MATCHER_VERSION,
            matcher_config=matcher_config or MatcherConfig(),
            scoring_policy_version=scoring_policy_version,
            trust_store=trust_store,
            trust_store_path=trust_store_path,
            policy_mode=policy_mode,
            at=at,
            expected_digest=self.signed_authorization_manifest_digest,
        )
        return derived_claim_authorization(
            self,
            envelope=loaded,
            report=report,
            comparative_authorized=self.comparative_authorization,
        )

    def performance_claim_authorized(self) -> bool:
        """Transitional bool: verified public scopes only (never LIVE_PRIVATE)."""
        return self.claim_authorization().performance_claim_authorized


class ByokConfig(StrictModel):
    """Bring-your-own-key deployment descriptor (no credential retention)."""

    provider_id: str = Field(min_length=1)
    retain_credentials: Literal[False] = False
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def reject_secret_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            banned = {
                "api_key",
                "secret",
                "secrets",
                "credential",
                "credentials",
                "credential_reference",
                "token",
                "password",
                "private_key",
            }
            for key in data:
                lowered = str(key).lower()
                if lowered in banned or "secret" in lowered or lowered.endswith("_key"):
                    if lowered in {"provider_id"}:
                        continue
                    raise ValueError(
                        f"BYOK configs must not persist secret field {key!r}"
                    )
            if data.get("retain_credentials") is True:
                raise ValueError("BYOK configs must not retain credentials")
        return data


class SystemManifest(StrictModel):
    system_id: str
    version: str
    display_name: str
    description: str = ""
    repository_url: HttpUrl | None = None
    license: str | None = None
    code_commit: str | None = None
    model_identifiers: list[str] = Field(default_factory=list)
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_mode: Literal["external", "local", "hosted", "byok"] = "external"
    byok: ByokConfig | None = None
    output_contract: Literal["opencritique-evaluation-v0.1"] = "opencritique-evaluation-v0.1"
    declared_cost_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    declared_cost_minor: int | None = Field(default=None, ge=0)
    declared_latency_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def cost_pair(self) -> SystemManifest:
        if (self.declared_cost_currency is None) != (self.declared_cost_minor is None):
            raise ValueError("declared cost currency and amount must be provided together")
        return self

    @model_validator(mode="after")
    def byok_mode_consistency(self) -> SystemManifest:
        if self.execution_mode == "byok" and self.byok is None:
            raise ValueError("execution_mode=byok requires a byok config")
        if self.execution_mode != "byok" and self.byok is not None:
            raise ValueError("byok config is only valid when execution_mode=byok")
        return self


class SubmittedAnchor(StrictModel):
    page: int | None = Field(default=None, ge=1)
    source_text: str | None = None
    object_label: str | None = None

    @model_validator(mode="after")
    def nonempty(self) -> SubmittedAnchor:
        if self.page is None and not (self.source_text or "").strip() and not (
            self.object_label or ""
        ).strip():
            raise ValueError("submitted anchor requires a page, source_text, or object_label")
        return self


class SubmittedConcern(StrictModel):
    local_id: str
    title: str = Field(min_length=3)
    summary: str = Field(min_length=10)
    concern_type: str = Field(min_length=3)
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    anchors: list[SubmittedAnchor] = Field(min_length=1)
    evidence_summary: str = ""


class CaseSubmission(StrictModel):
    case_id: str
    case_version: str
    concerns: list[SubmittedConcern] = Field(default_factory=list)
    abstained: bool = False
    failure: str | None = None

    @model_validator(mode="after")
    def abstention_consistency(self) -> CaseSubmission:
        if self.abstained and self.concerns:
            raise ValueError("abstained case submission cannot contain concerns")
        if self.failure and self.concerns:
            raise ValueError("failed case submission cannot contain concerns")
        return self


class EvaluationSubmission(StrictModel):
    submission_id: str
    system: SystemManifest
    benchmark_id: str
    benchmark_version: str
    cases: list[CaseSubmission]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def unique_cases(self) -> EvaluationSubmission:
        keys = [(item.case_id, item.case_version) for item in self.cases]
        if len(keys) != len(set(keys)):
            raise ValueError("submission case identities must be unique")
        return self


class AnchorResolutionStatus(str, Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    OBJECT_LABEL = "object_label"
    PAGE_ONLY = "page_only"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class AnchorResolution(StrictModel):
    submitted_index: int
    status: AnchorResolutionStatus
    reference_anchor_ids: list[str] = Field(default_factory=list)


class ConcernMatch(StrictModel):
    submitted_local_id: str
    reference_concern_id: str
    score: float = Field(ge=0, le=1)
    anchor_score: float = Field(ge=0, le=1)
    type_score: float = Field(ge=0, le=1)
    lexical_score: float = Field(ge=0, le=1)


class CaseEvaluation(StrictModel):
    case_id: str
    case_version: str
    submitted_count: int
    eligible_reference_count: int
    matches: list[ConcernMatch]
    unmatched_submitted_ids: list[str]
    missed_reference_ids: list[str]
    anchor_resolutions: dict[str, list[AnchorResolution]]
    abstained: bool
    failure: str | None


class MetricValue(StrictModel):
    value: float | int | None
    numerator: float | int | None = None
    denominator: float | int | None = None
    withheld_reason: str | None = None


class EvaluationMetrics(StrictModel):
    cases_total: int
    cases_completed: int
    cases_abstained: int
    cases_failed: int
    submitted_concerns: int
    eligible_reference_concerns: int
    matched_concerns: int
    unmatched_submitted: int
    missed_reference: int
    anchor_resolution_rate: MetricValue
    precision: MetricValue
    recall: MetricValue
    severity_weighted_precision: MetricValue
    severity_weighted_recall: MetricValue
    false_critical_per_manuscript: MetricValue
    reference_match_brier_score: MetricValue
    novel_candidates_pending_adjudication: int


class MatcherConfig(StrictModel):
    config_id: str = "default-v0.2"
    anchor_weight: float = Field(default=0.50, ge=0, le=1)
    type_weight: float = Field(default=0.30, ge=0, le=1)
    lexical_weight: float = Field(default=0.20, ge=0, le=1)
    threshold: float = Field(default=0.55, ge=0, le=1)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> MatcherConfig:
        total = self.anchor_weight + self.type_weight + self.lexical_weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError("matcher weights must sum to 1.0")
        return self


class SensitivityRun(StrictModel):
    config: MatcherConfig
    matched_pairs: list[tuple[str, str, str, str]]
    matched_count: int
    precision: float | None
    recall: float | None


class MatcherSensitivityReport(StrictModel):
    report_version: str = "0.1"
    benchmark_id: str
    benchmark_version: str
    submission_id: str
    baseline_config: MatcherConfig
    runs: list[SensitivityRun] = Field(min_length=2)
    stable_pairs: list[tuple[str, str, str, str]]
    unstable_pairs: list[tuple[str, str, str, str]]
    baseline_retention_rate: float = Field(ge=0, le=1)
    match_count_min: int
    match_count_max: int
    precision_min: float | None
    precision_max: float | None
    recall_min: float | None
    recall_max: float | None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NovelCandidateState(str, Enum):
    PENDING = "pending_expert_adjudication"
    ACCEPTED_NOVEL = "accepted_novel"
    MATCHED_EXISTING = "matched_existing"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    QUALIFIED = "qualified"
    UNRESOLVED = "unresolved"


class NovelDeterminationOutcome(str, Enum):
    """Immutable novel-concern determination outcomes (issue #2)."""

    CONFIRMED = "confirmed"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class NovelConcernCandidate(StrictModel):
    candidate_id: str
    result_id: str
    submission_id: str
    case_id: str
    case_version: str
    concern: SubmittedConcern
    anchor_resolutions: list[AnchorResolution]
    state: NovelCandidateState = NovelCandidateState.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NovelConcernQueue(StrictModel):
    queue_version: str = "0.1"
    result_id: str
    submission_id: str
    candidates: list[NovelConcernCandidate]
    source_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_submission_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NovelPrimaryDecision(StrictModel):
    adjudicator_id: str
    slot: Literal["primary", "secondary", "tie_break"]
    validity: NovelDeterminationOutcome
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(min_length=1)
    blinded_fields: list[str] = Field(default_factory=list)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class NovelConcernDetermination(StrictModel):
    """Append-only determination record for a novel-concern candidate."""

    determination_id: str
    schema_id: str = "opencritique.NovelConcernDetermination"
    schema_version: str = "0.1"
    candidate_id: str
    result_id: str
    submission_id: str
    case_id: str
    case_version: str
    outcome: NovelDeterminationOutcome
    severity: Severity | None = None
    requires_tie_break: bool = False
    finalized: bool = False
    policy_version: str
    scoring_policy_version: str | None = None
    rationale: str = Field(min_length=1)
    decision_ids: list[str] = Field(default_factory=list)
    candidate_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_submission_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    matcher_version: str
    matcher_config_id: str
    benchmark_id: str
    benchmark_version: str
    successor_benchmark_version: str | None = None
    successor_case_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    predecessor_scorecard_id: str | None = None
    predecessor_scorecard_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    recompute_scorecard_id: str | None = None
    recompute_scorecard_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvaluationResult(StrictModel):
    result_id: str
    benchmark: BenchmarkManifest
    system: SystemManifest
    submission_id: str
    matcher_version: str
    matcher_config: MatcherConfig = Field(default_factory=MatcherConfig)
    case_evaluations: list[CaseEvaluation]
    metrics: EvaluationMetrics
    claim_authorization: ClaimAuthorization = Field(default_factory=ClaimAuthorization.none)
    claim_authorization_envelope: SignedClaimAuthorizationEnvelope | None = None
    performance_claim_authorized: bool = False
    claim_boundary: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    predecessor_result_id: str | None = None
    scoring_policy_version: str = "scoring-policy-v0.1"

    @model_validator(mode="after")
    def sync_performance_claim_flag(self) -> EvaluationResult:
        """Fail closed: public scopes require an attached verified envelope."""
        auth = self.claim_authorization
        scope = auth.claim_scope
        has_envelope = self.claim_authorization_envelope is not None
        if scope in _PUBLIC_CLAIM_SCOPES and (
            not has_envelope or not auth.authorization_verified
        ):
            # Crafted public scopes without a verified envelope coerce to NONE.
            object.__setattr__(
                self,
                "claim_authorization",
                ClaimAuthorization(
                    claim_scope=ClaimScope.NONE,
                    expert_natural_evidence=auth.expert_natural_evidence,
                    rights_cleared_cases=auth.rights_cleared_cases,
                    protected_holdout=auth.protected_holdout,
                    independent_evaluation=auth.independent_evaluation,
                    matcher_audit_complete=auth.matcher_audit_complete,
                    frozen_scoring_policy=auth.frozen_scoring_policy,
                    signed_authorization_manifest_digest=(
                        auth.signed_authorization_manifest_digest
                    ),
                    signed_authorization_manifest_path=(
                        auth.signed_authorization_manifest_path
                    ),
                    domain_scope=auth.domain_scope,
                    use_scope=auth.use_scope,
                    authorization_verified=False,
                    verification_report_digest=auth.verification_report_digest,
                ),
            )
            object.__setattr__(self, "performance_claim_authorized", False)
            return self
        expected = self.claim_authorization.performance_claim_authorized
        if self.performance_claim_authorized != expected:
            object.__setattr__(self, "performance_claim_authorized", expected)
        return self


class PublicScorecard(StrictModel):
    scorecard_version: str = "0.1"
    scorecard_id: str | None = None
    result: EvaluationResult
    headline: str
    disclosure: str
    predecessor_scorecard_id: str | None = None
    predecessor_scorecard_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reference_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    scoring_policy_version: str | None = None
    immutable: bool = True


class ScorecardSignature(StrictModel):
    signature_version: str = "0.1"
    algorithm: Literal["Ed25519"] = "Ed25519"
    key_id: str
    public_key_base64: str
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature_base64: str
    signed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    key_role: Literal["offline_root", "online_release", "test"] | None = None
    not_before: datetime | None = None
    not_after: datetime | None = None

    @model_validator(mode="after")
    def validity_interval(self) -> ScorecardSignature:
        if (
            self.not_before is not None
            and self.not_after is not None
            and self.not_after <= self.not_before
        ):
            raise ValueError("signature not_after must be after not_before")
        return self


class SignedScorecardEnvelope(StrictModel):
    envelope_version: str = "0.1"
    scorecard: PublicScorecard
    signature: ScorecardSignature
