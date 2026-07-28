from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AcquisitionStatus(str, Enum):
    DISCOVERED = "discovered"
    METADATA_VERIFIED = "metadata_verified"
    LICENSE_REVIEW_REQUIRED = "license_review_required"
    CONTACT_REQUIRED = "contact_required"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"
    IMPORTED = "imported"


class AcquisitionSource(StrictModel):
    source_id: str
    title: str
    paper_url: HttpUrl
    code_url: HttpUrl | None = None
    dataset_url: HttpUrl | None = None
    status: AcquisitionStatus
    declared_license: str | None = None
    license_evidence_url: HttpUrl | None = None
    redistribution_authorized: bool = False
    evaluation_use_authorized: bool = False
    imported_case_count: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_rights_gate(self) -> "AcquisitionSource":
        if self.status == AcquisitionStatus.IMPORTED:
            if not self.evaluation_use_authorized:
                raise ValueError("imported source requires evaluation-use authorization")
            if self.imported_case_count < 1:
                raise ValueError("imported source must declare at least one imported case")
        elif self.imported_case_count:
            raise ValueError("non-imported source cannot declare imported cases")
        if self.redistribution_authorized and not self.declared_license:
            raise ValueError("redistribution authorization requires a declared license")
        return self


class AcquisitionLedger(StrictModel):
    ledger_version: str = "0.1"
    sources: list[AcquisitionSource]
    total_imported_cases: int = 0
    performance_claims_authorized: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def consistency(self) -> "AcquisitionLedger":
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValueError("acquisition source IDs must be unique")
        actual = sum(item.imported_case_count for item in self.sources)
        if actual != self.total_imported_cases:
            raise ValueError("total_imported_cases does not match source records")
        if actual == 0 and self.performance_claims_authorized:
            raise ValueError("empty acquisition ledger cannot authorize performance claims")
        return self
