"""Approved source-profile contract for rights-gated corpus imports (issue #7).

Natural imports remain blocked until a rights-cleared external case arrives.
This module encodes the profile so the first cleared case can land in one
command without inventing manuscripts.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from .models import (
    AcquisitionLedger,
    AcquisitionStatus,
    import_source,
    load_ledger,
    save_ledger,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SourceProfileKind(str, Enum):
    SAMPLE = "sample"
    NATURAL = "natural"


class ApprovedProfileError(ValueError):
    code: str = "approved_profile_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ApprovedSourceProfile(StrictModel):
    """Machine-checkable grant profile for a single external or sample import."""

    profile_version: str = "0.1"
    profile_kind: SourceProfileKind
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    paper_url: HttpUrl
    declared_license: str = Field(min_length=1)
    license_evidence_url: HttpUrl
    grant_authority: str = Field(min_length=1)
    grant_scope: str = Field(min_length=1)
    evaluation_use_authorized: bool
    redistribution_authorized: bool
    natural_manuscript_imported: bool
    performance_claims_authorized: bool = False
    case_id: str = Field(min_length=1)
    case_version: str = Field(min_length=1)
    manuscript_path: str = Field(min_length=1)
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights_record_path: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value

    @model_validator(mode="after")
    def profile_consistency(self) -> ApprovedSourceProfile:
        if not self.evaluation_use_authorized:
            raise ApprovedProfileError(
                "approved profile requires evaluation_use_authorized=true",
                code="evaluation_use_required",
            )
        if self.profile_kind == SourceProfileKind.SAMPLE:
            if self.natural_manuscript_imported:
                raise ApprovedProfileError(
                    "sample profile cannot set natural_manuscript_imported=true",
                    code="sample_natural_contamination",
                )
        elif self.profile_kind == SourceProfileKind.NATURAL:
            if not self.natural_manuscript_imported:
                raise ApprovedProfileError(
                    "natural profile requires natural_manuscript_imported=true",
                    code="natural_flag_required",
                )
            if not self.redistribution_authorized:
                raise ApprovedProfileError(
                    "natural public-corpus import requires redistribution_authorized",
                    code="redistribution_required",
                )
            if "public availability" in self.grant_scope.lower():
                raise ApprovedProfileError(
                    "grant_scope must not rely on public availability alone",
                    code="public_availability_insufficient",
                )
        return self


def parse_approved_profile(data: dict[str, Any]) -> ApprovedSourceProfile:
    """Validate profile JSON and raise typed ApprovedProfileError on reject paths."""
    try:
        profile = ApprovedSourceProfile.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "performance_claims_authorized" in message:
            raise ApprovedProfileError(
                "performance_claims_authorized must remain false",
                code="claims_unauthorized",
            ) from exc
        if "sample profile cannot set natural_manuscript_imported" in message:
            raise ApprovedProfileError(
                "sample profile cannot set natural_manuscript_imported=true",
                code="sample_natural_contamination",
            ) from exc
        if "natural profile requires natural_manuscript_imported" in message:
            raise ApprovedProfileError(
                "natural profile requires natural_manuscript_imported=true",
                code="natural_flag_required",
            ) from exc
        if "redistribution_authorized" in message:
            raise ApprovedProfileError(
                "natural public-corpus import requires redistribution_authorized",
                code="redistribution_required",
            ) from exc
        if "public availability" in message:
            raise ApprovedProfileError(
                "grant_scope must not rely on public availability alone",
                code="public_availability_insufficient",
            ) from exc
        if "evaluation_use_authorized" in message:
            raise ApprovedProfileError(
                "approved profile requires evaluation_use_authorized=true",
                code="evaluation_use_required",
            ) from exc
        raise ApprovedProfileError(f"invalid approved profile: {exc}") from exc
    return profile


def load_approved_profile(path: Path) -> ApprovedSourceProfile:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ApprovedProfileError(f"invalid approved profile at {path}: {exc}") from exc
    return parse_approved_profile(payload)


def verify_manuscript_hash(profile: ApprovedSourceProfile, repo_root: Path) -> Path:
    manuscript = (repo_root / profile.manuscript_path).resolve()
    root = repo_root.resolve()
    try:
        manuscript.relative_to(root)
    except ValueError as exc:
        raise ApprovedProfileError(
            f"manuscript_path escapes repository root: {profile.manuscript_path}",
            code="path_escape",
        ) from exc
    if not manuscript.is_file():
        raise ApprovedProfileError(
            f"manuscript missing: {profile.manuscript_path}",
            code="manuscript_missing",
        )
    digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    if digest != profile.source_artifact_sha256:
        raise ApprovedProfileError(
            f"manuscript hash mismatch for {profile.manuscript_path}: "
            f"declared {profile.source_artifact_sha256}, actual {digest}",
            code="hash_mismatch",
        )
    return manuscript


def verify_rights_record(
    profile: ApprovedSourceProfile,
    repo_root: Path,
) -> dict[str, Any] | None:
    if not profile.rights_record_path:
        if profile.profile_kind == SourceProfileKind.NATURAL:
            raise ApprovedProfileError(
                "natural profile requires rights_record_path",
                code="rights_record_required",
            )
        return None
    path = (repo_root / profile.rights_record_path).resolve()
    root = repo_root.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ApprovedProfileError(
            f"rights_record_path escapes repository root: {profile.rights_record_path}",
            code="path_escape",
        ) from exc
    if not path.is_file():
        raise ApprovedProfileError(
            f"rights record missing: {profile.rights_record_path}",
            code="rights_record_missing",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("case_id") != profile.case_id:
        raise ApprovedProfileError(
            "rights record case_id does not match profile",
            code="rights_case_mismatch",
        )
    if data.get("source_artifact_sha256") != profile.source_artifact_sha256:
        raise ApprovedProfileError(
            "rights record source_artifact_sha256 does not match profile",
            code="rights_hash_mismatch",
        )
    if data.get("evaluation_use_authorized") is not True:
        raise ApprovedProfileError(
            "rights record lacks evaluation_use_authorized",
            code="rights_eval_denied",
        )
    if data.get("performance_claims_authorized") is True:
        raise ApprovedProfileError(
            "rights record must keep performance_claims_authorized=false",
            code="claims_unauthorized",
        )
    if (
        profile.profile_kind == SourceProfileKind.NATURAL
        and data.get("natural_manuscript_imported") is not True
    ):
        raise ApprovedProfileError(
            "natural rights record must set natural_manuscript_imported=true",
            code="natural_flag_required",
        )
    if (
        profile.profile_kind == SourceProfileKind.SAMPLE
        and data.get("natural_manuscript_imported") is True
    ):
        raise ApprovedProfileError(
            "sample rights record cannot set natural_manuscript_imported=true",
            code="sample_natural_contamination",
        )
    return data


def reject_outside_approved_profile(profile: ApprovedSourceProfile, repo_root: Path) -> None:
    """Fail closed for any profile that does not satisfy the approved contract."""
    verify_manuscript_hash(profile, repo_root)
    verify_rights_record(profile, repo_root)


def import_approved_profile(
    profile: ApprovedSourceProfile,
    *,
    ledger_path: Path,
    repo_root: Path,
    dry_run: bool = False,
) -> AcquisitionLedger:
    """Import one cleared case into the acquisition ledger via the approved profile.

    Natural imports are accepted only when the profile is complete and hashes bind.
    Does not fabricate manuscript bytes.
    """
    reject_outside_approved_profile(profile, repo_root)
    ledger = (
        load_ledger(ledger_path)
        if ledger_path.is_file()
        else AcquisitionLedger(sources=[], total_imported_cases=0)
    )
    if any(item.source_id == profile.source_id for item in ledger.sources):
        existing = next(item for item in ledger.sources if item.source_id == profile.source_id)
        if existing.status == AcquisitionStatus.IMPORTED:
            raise ApprovedProfileError(
                f"source_id already imported: {profile.source_id}",
                code="duplicate_source",
            )
    if dry_run:
        return ledger
    updated = import_source(
        ledger,
        source_id=profile.source_id,
        title=profile.title,
        paper_url=str(profile.paper_url),
        declared_license=profile.declared_license,
        license_evidence_url=str(profile.license_evidence_url),
        imported_case_count=1,
        grant_authority=profile.grant_authority,
        grant_scope=profile.grant_scope,
        notes=list(profile.notes)
        + [
            f"profile_kind={profile.profile_kind.value}",
            f"case_id={profile.case_id}@{profile.case_version}",
            f"manuscript={profile.manuscript_path}",
        ],
    )
    if updated.performance_claims_authorized:
        raise ApprovedProfileError(
            "refusing to persist ledger with performance claims authorized",
            code="claims_unauthorized",
        )
    save_ledger(ledger_path, updated)
    return updated


def dump_approved_profile_schema() -> dict[str, Any]:
    return ApprovedSourceProfile.model_json_schema()
