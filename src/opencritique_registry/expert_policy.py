"""Versioned expert program policy objects (issue #14).

Loads enforceable qualification, compensation-linkage, attribution, and
calibration-seed policies from ``governance/policies/``. Does not store payment
secrets. Thresholds authorize eligibility only — never public ranking.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpertPolicyError(ValueError):
    code: str = "expert_policy_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class DomainQualificationThreshold(StrictModel):
    domain_profile: str = Field(min_length=1)
    min_calibration_cases: int = Field(ge=1)
    min_validity_agreement: float = Field(ge=0.0, le=1.0)
    max_mean_severity_distance: float = Field(ge=0.0)
    false_critical_ceiling: float = Field(ge=0.0, le=1.0)
    expiry_days: int = Field(ge=1)


class QualificationRevocationPolicy(StrictModel):
    false_critical_breach: str
    undisclosed_conflict: str
    recalibration_required_after_expiry: bool = True


class ExpertQualificationPolicy(StrictModel):
    policy_id: str = "expert-qualification-thresholds"
    policy_version: str
    issue: int = 14
    performance_claims_authorized: bool = False
    notes: str = ""
    domains: list[DomainQualificationThreshold] = Field(min_length=1)
    revocation: QualificationRevocationPolicy

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value

    def threshold_for(self, domain_profile: str) -> DomainQualificationThreshold:
        for item in self.domains:
            if item.domain_profile == domain_profile:
                return item
        raise ExpertPolicyError(
            f"no qualification threshold for domain_profile={domain_profile!r}",
            code="unknown_domain",
        )


class CalibrationTaskSeed(StrictModel):
    seed_id: str
    domain_profile: str
    case_id: str
    case_version: str
    corpus_path: str
    fixture_review: str


class CalibrationTaskSeedsPolicy(StrictModel):
    policy_id: str = "calibration-task-seeds"
    policy_version: str
    issue: int = 14
    performance_claims_authorized: bool = False
    source_class: str
    notes: str = ""
    tasks: list[CalibrationTaskSeed] = Field(min_length=1)

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value

    @model_validator(mode="after")
    def sample_only_until_natural(self) -> CalibrationTaskSeedsPolicy:
        if self.source_class not in {
            "maintainer_owned_sample_corpus",
            "rights_cleared_natural_corpus",
        }:
            raise ExpertPolicyError(
                f"unsupported calibration source_class={self.source_class!r}",
                code="bad_source_class",
            )
        return self


class CompensationScheduleSlot(StrictModel):
    """Compensation linkage without payment secrets or credentials."""

    task_class: str
    unit: str
    amount_minor: int | None = Field(
        default=None,
        description="Nullable until a funded schedule is adopted; never a secret.",
    )
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    external_payout_ref_allowed: bool = True
    notes: str = ""


class ExpertCompensationPolicy(StrictModel):
    policy_id: str = "expert-compensation-terms"
    policy_version: str
    issue: int = 14
    performance_claims_authorized: bool = False
    payment_secrets_prohibited: bool = True
    schedule: list[CompensationScheduleSlot] = Field(min_length=1)
    notes: str = ""

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value

    @model_validator(mode="after")
    def no_secrets_flag(self) -> ExpertCompensationPolicy:
        if not self.payment_secrets_prohibited:
            raise ExpertPolicyError(
                "payment_secrets_prohibited must remain true",
                code="secrets_policy",
            )
        return self


class ExpertAttributionPolicy(StrictModel):
    policy_id: str = "expert-attribution-policy"
    policy_version: str
    issue: int = 14
    performance_claims_authorized: bool = False
    default_public_attribution: bool = False
    opt_in_required: bool = True
    conflict_disclosure_required: bool = True
    notes: str = ""

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value

    @model_validator(mode="after")
    def enforce_opt_in(self) -> ExpertAttributionPolicy:
        if not self.opt_in_required:
            raise ExpertPolicyError("opt_in_required must remain true", code="attribution")
        if not self.conflict_disclosure_required:
            raise ExpertPolicyError(
                "conflict_disclosure_required must remain true",
                code="conflict_required",
            )
        if self.default_public_attribution:
            raise ExpertPolicyError(
                "default_public_attribution must remain false (opt-in only)",
                code="attribution_default",
            )
        return self


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "governance" / "policies"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_qualification_policy(
    path: Path | None = None,
) -> ExpertQualificationPolicy:
    target = path or (POLICY_DIR / "expert-qualification-thresholds.v0.1.json")
    return ExpertQualificationPolicy.model_validate(_load_json(target))


def load_calibration_seeds_policy(
    path: Path | None = None,
) -> CalibrationTaskSeedsPolicy:
    target = path or (POLICY_DIR / "calibration-task-seeds.v0.1.json")
    return CalibrationTaskSeedsPolicy.model_validate(_load_json(target))


def load_compensation_policy(
    path: Path | None = None,
) -> ExpertCompensationPolicy:
    target = path or (POLICY_DIR / "expert-compensation-terms.v0.1.json")
    return ExpertCompensationPolicy.model_validate(_load_json(target))


def load_attribution_policy(
    path: Path | None = None,
) -> ExpertAttributionPolicy:
    target = path or (POLICY_DIR / "expert-attribution-policy.v0.1.json")
    return ExpertAttributionPolicy.model_validate(_load_json(target))


def qualification_expiry_at(
    *,
    valid_from: datetime | None = None,
    domain_profile: str,
    policy: ExpertQualificationPolicy | None = None,
) -> datetime:
    """Compute expiry for a newly granted qualification from policy thresholds."""
    active = policy or load_qualification_policy()
    threshold = active.threshold_for(domain_profile)
    start = valid_from or datetime.now(UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return start + timedelta(days=threshold.expiry_days)


def is_qualification_expired(
    *,
    expires_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    if expires_at is None:
        return False
    current = now or datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return expires_at <= current


def require_conflict_disclosure(status: str, description: str = "") -> None:
    """Fail closed when conflict disclosure is missing or incomplete."""
    if status not in {"none", "disclosed", "disqualifying"}:
        raise ExpertPolicyError(
            f"invalid conflict declaration status={status!r}",
            code="conflict_invalid",
        )
    if status == "disclosed" and not description.strip():
        raise ExpertPolicyError(
            "disclosed conflicts require a non-empty description",
            code="conflict_description_required",
        )
    if status == "disqualifying":
        raise ExpertPolicyError(
            "disqualifying conflict requires reassignment",
            code="conflict_disqualifying",
        )


def assert_calibration_seeds_resolvable(
    policy: CalibrationTaskSeedsPolicy | None = None,
    *,
    repo_root: Path | None = None,
) -> list[CalibrationTaskSeed]:
    """Ensure seed paths exist so studio/registry can load sample calibration packs."""
    active = policy or load_calibration_seeds_policy()
    root = repo_root or ROOT
    missing: list[str] = []
    for task in active.tasks:
        corpus = root / task.corpus_path
        review = root / task.fixture_review
        if not corpus.exists():
            missing.append(task.corpus_path)
        if not review.is_file():
            missing.append(task.fixture_review)
    if missing:
        raise ExpertPolicyError(
            "calibration seed paths missing: " + ", ".join(sorted(set(missing))),
            code="seed_paths_missing",
        )
    return list(active.tasks)
