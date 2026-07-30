"""Holdout set custody artifacts (PR 43).

Scientific gate #7 requires a verified ``HoldoutCustodyAttestation`` signed over a
``HoldoutSetManifest`` digest and an append-only access-log head hash. Ledger
``IMPORTED`` counts and protocol markdown alone do **not** unlock the gate; the
attested holdout set itself must contain ≥40 natural cases.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from opencritique_schema.canonical import content_hash

from .models import StrictModel

_HEX64 = r"^[0-9a-f]{64}$"
_OPAQUE_LOCATOR = r"^(urn:|vault:|enc:|opaque:)[^\s]+$"


class HoldoutCaseRecord(StrictModel):
    """One natural case frozen into a holdout set (id + content digest)."""

    case_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=_HEX64)


class HoldoutRefreshRetirementPolicy(StrictModel):
    """Refresh / retirement policy bound into the holdout manifest."""

    refresh_cadence: str = Field(min_length=1)
    retirement_rule: str = Field(min_length=1)
    notes: str = ""


class HoldoutContaminationDeclaration(StrictModel):
    """Contamination declaration fields for a holdout set."""

    contaminated: bool = False
    declared_at: datetime | None = None
    declared_by: str | None = None
    details: str = ""
    affected_case_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def contaminated_requires_context(self) -> HoldoutContaminationDeclaration:
        if self.contaminated:
            if self.declared_at is None:
                raise ValueError("contaminated holdout requires declared_at")
            if not (self.declared_by or "").strip():
                raise ValueError("contaminated holdout requires declared_by")
            if not (self.details or "").strip():
                raise ValueError("contaminated holdout requires details")
        return self


class HoldoutSetManifest(StrictModel):
    """Frozen holdout set: case digests, custodian, opaque locator, policies.

    ``private_locator_ref`` must be an opaque encrypted/private locator
    (``urn:`` / ``vault:`` / ``enc:`` / ``opaque:``). Plaintext manuscript or
    filesystem paths are rejected so they never enter the public tree.
    """

    manifest_version: Literal["0.1"] = "0.1"
    holdout_id: str = Field(min_length=1)
    cases: list[HoldoutCaseRecord] = Field(default_factory=list)
    freeze_time: datetime
    custodian_id: str = Field(min_length=1)
    developer_exclusion_list: list[str] = Field(default_factory=list)
    private_locator_ref: str = Field(
        min_length=1,
        pattern=_OPAQUE_LOCATOR,
        description=(
            "Opaque encrypted/private locator reference. Never a plaintext "
            "manuscript or filesystem path in the public tree."
        ),
    )
    refresh_retirement_policy: HoldoutRefreshRetirementPolicy
    contamination: HoldoutContaminationDeclaration = Field(
        default_factory=HoldoutContaminationDeclaration
    )
    notes: str = ""

    @field_validator("developer_exclusion_list")
    @classmethod
    def unique_exclusions(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("developer_exclusion_list must be unique")
        return cleaned

    @model_validator(mode="after")
    def unique_case_ids(self) -> HoldoutSetManifest:
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("holdout case_id values must be unique")
        return self

    @property
    def natural_case_count(self) -> int:
        return len(self.cases)


class HoldoutAccessAction(str, Enum):
    CREATE = "create"
    READ = "read"
    EXPORT = "export"
    ROTATE = "rotate"
    RETIRE = "retire"
    DECLARE_CONTAMINATION = "declare_contamination"
    OTHER = "other"


class HoldoutAccessLogEntry(StrictModel):
    """Append-only access record for a holdout set."""

    sequence: int = Field(ge=0)
    actor: str = Field(min_length=1)
    action: HoldoutAccessAction
    timestamp: datetime
    purpose: str = Field(min_length=1)


class HoldoutAccessLog(StrictModel):
    """Append-only custody access log (head hash is attested)."""

    log_version: Literal["0.1"] = "0.1"
    holdout_id: str = Field(min_length=1)
    entries: list[HoldoutAccessLogEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def append_only_sequence(self) -> HoldoutAccessLog:
        expected = 0
        prev_ts: datetime | None = None
        for entry in self.entries:
            if entry.sequence != expected:
                raise ValueError(
                    "access log sequences must be contiguous starting at 0 "
                    f"(expected {expected}, got {entry.sequence})"
                )
            if prev_ts is not None and entry.timestamp < prev_ts:
                raise ValueError("access log timestamps must be non-decreasing")
            expected += 1
            prev_ts = entry.timestamp
        return self


def holdout_manifest_content_hash(manifest: HoldoutSetManifest) -> str:
    """SHA-256 of the canonical holdout set manifest (signed as subject)."""
    return content_hash(manifest)


def access_log_head_hash(log: HoldoutAccessLog) -> str:
    """SHA-256 of the current append-only access log (log head)."""
    return content_hash(log)


__all__ = [
    "HoldoutAccessAction",
    "HoldoutAccessLog",
    "HoldoutAccessLogEntry",
    "HoldoutCaseRecord",
    "HoldoutContaminationDeclaration",
    "HoldoutRefreshRetirementPolicy",
    "HoldoutSetManifest",
    "access_log_head_hash",
    "holdout_manifest_content_hash",
]
