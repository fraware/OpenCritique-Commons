"""Conversion-loss profile stub for a third adapter.

Copy into ``src/opencritique_adapters/<slug>_loss.py``. Expand field fates to
match your upstream contract. Keep ``performance_claims_authorized=false``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .contract import (
    EXAMPLE_CONTRACT_FIELDS,
    EXAMPLE_FIXTURE_KIND,
    EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED,
    EXAMPLE_UPSTREAM_COMMIT_PIN,
    EXAMPLE_UPSTREAM_CONTRACT_VERSION,
    EXAMPLE_UPSTREAM_REPOSITORY,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldFate(StrictModel):
    field_path: str
    fate: str  # preserved | normalized | provisional | omitted | unresolved
    notes: str


class ExampleConversionLossReport(StrictModel):
    report_version: str = "0.1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    upstream_contract_version: str = EXAMPLE_UPSTREAM_CONTRACT_VERSION
    upstream_repository: str = EXAMPLE_UPSTREAM_REPOSITORY
    upstream_commit_pin: str = EXAMPLE_UPSTREAM_COMMIT_PIN
    fixture_kind: str = EXAMPLE_FIXTURE_KIND
    performance_claims_authorized: bool = EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED
    compatibility_matrix: list[dict[str, str]] = Field(default_factory=list)
    field_inventory: dict[str, tuple[str, ...]] = Field(
        default_factory=lambda: dict(EXAMPLE_CONTRACT_FIELDS)
    )
    omitted_field_summary: list[str] = Field(default_factory=list)
    notes: list[str] = Field(
        default_factory=lambda: [
            "Skeleton loss report. Replace with measured field fates once "
            "sample fixtures exist. Production section stays NOT READY until "
            "authentic exports land.",
        ]
    )

    @field_validator("performance_claims_authorized")
    @classmethod
    def _claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return False


def build_example_conversion_loss_report() -> ExampleConversionLossReport:
    """Return a claims-locked placeholder report for scaffolding tests."""
    matrix = [
        {
            "upstream_field": path,
            "fate": "provisional",
            "opencritique_target": "SubmittedConcern (TBD)",
        }
        for group, fields in EXAMPLE_CONTRACT_FIELDS.items()
        for path in (f"{group}.{name}" for name in fields)
    ]
    return ExampleConversionLossReport(
        compatibility_matrix=matrix,
        omitted_field_summary=[],
    )
