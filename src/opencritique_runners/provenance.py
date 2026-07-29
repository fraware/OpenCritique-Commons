"""Provenance stamps for private live upstream runs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# coarse-ink==1.8.0 on PyPI (tag v1.8.0 / Davidvandijcke/coarse).
COARSE_LIVE_COMMIT_PIN = "907c629369a8cf5b776dc1d23c618d2907de6d5b"
COARSE_LIVE_PACKAGE_PIN = "coarse-ink==1.8.0"
COARSE_UPSTREAM_REPOSITORY = "https://github.com/Davidvandijcke/coarse"
COARSE_UPSTREAM_SLUG = "Davidvandijcke/coarse"


class LiveProvenance(BaseModel):
    """Operator-local evidence metadata. Claims stay locked."""

    model_config = ConfigDict(extra="forbid")

    upstream: str = COARSE_UPSTREAM_SLUG
    upstream_repository: str = COARSE_UPSTREAM_REPOSITORY
    commit_pin: str = COARSE_LIVE_COMMIT_PIN
    package_pin: str = COARSE_LIVE_PACKAGE_PIN
    model_id: str
    execution_mode: Literal["byok"] = "byok"
    evidence_class: Literal["private_live"] = "private_live"
    performance_claims_authorized: bool = False
    manuscript_path: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("performance_claims_authorized")
    @classmethod
    def _claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return False

    def as_export_block(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
