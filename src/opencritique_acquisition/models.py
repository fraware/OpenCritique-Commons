from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, model_validator


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
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"


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
    grant_authority: str | None = None
    grant_scope: str | None = None
    withdrawn_at: datetime | None = None
    withdrawal_reason: str | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None

    @model_validator(mode="after")
    def enforce_rights_gate(self) -> AcquisitionSource:
        if self.status == AcquisitionStatus.IMPORTED:
            if not self.evaluation_use_authorized:
                raise ValueError("imported source requires evaluation-use authorization")
            if self.imported_case_count < 1:
                raise ValueError("imported source must declare at least one imported case")
            if not self.grant_authority or not self.grant_scope:
                raise ValueError("imported source requires grant_authority and grant_scope")
        elif self.status in {
            AcquisitionStatus.WITHDRAWN,
            AcquisitionStatus.CANCELLED,
        }:
            if self.imported_case_count:
                raise ValueError("withdrawn/cancelled sources cannot retain imported cases")
        elif self.imported_case_count:
            raise ValueError("non-imported source cannot declare imported cases")
        if self.redistribution_authorized and not self.declared_license:
            raise ValueError("redistribution authorization requires a declared license")
        if self.status == AcquisitionStatus.WITHDRAWN and not self.withdrawal_reason:
            raise ValueError("withdrawal requires a reason")
        if self.status == AcquisitionStatus.CANCELLED and not self.cancellation_reason:
            raise ValueError("cancellation requires a reason")
        return self


class AcquisitionLedger(StrictModel):
    ledger_version: str = "0.1"
    sources: list[AcquisitionSource]
    total_imported_cases: int = 0
    performance_claims_authorized: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def consistency(self) -> AcquisitionLedger:
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise ValueError("acquisition source IDs must be unique")
        actual = sum(
            item.imported_case_count
            for item in self.sources
            if item.status == AcquisitionStatus.IMPORTED
        )
        if actual != self.total_imported_cases:
            raise ValueError("total_imported_cases does not match source records")
        if actual == 0 and self.performance_claims_authorized:
            raise ValueError("empty acquisition ledger cannot authorize performance claims")
        return self


_HTTP = TypeAdapter(HttpUrl)


def load_ledger(path: Path) -> AcquisitionLedger:
    return AcquisitionLedger.model_validate_json(path.read_text(encoding="utf-8"))


def save_ledger(path: Path, ledger: AcquisitionLedger) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ledger.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def import_source(
    ledger: AcquisitionLedger,
    *,
    source_id: str,
    title: str,
    paper_url: str,
    declared_license: str,
    license_evidence_url: str,
    imported_case_count: int,
    grant_authority: str,
    grant_scope: str,
    notes: list[str] | None = None,
) -> AcquisitionLedger:
    if any(s.source_id == source_id for s in ledger.sources):
        raise ValueError(f"source_id already present: {source_id}")
    source = AcquisitionSource(
        source_id=source_id,
        title=title,
        paper_url=_HTTP.validate_python(paper_url),
        status=AcquisitionStatus.IMPORTED,
        declared_license=declared_license,
        license_evidence_url=_HTTP.validate_python(license_evidence_url),
        redistribution_authorized=True,
        evaluation_use_authorized=True,
        imported_case_count=imported_case_count,
        grant_authority=grant_authority,
        grant_scope=grant_scope,
        notes=notes or [],
    )
    sources = list(ledger.sources) + [source]
    return ledger.model_copy(
        update={
            "sources": sources,
            "total_imported_cases": sum(
                s.imported_case_count for s in sources if s.status == AcquisitionStatus.IMPORTED
            ),
            "generated_at": datetime.now(UTC),
        }
    )


def withdraw_source(
    ledger: AcquisitionLedger,
    *,
    source_id: str,
    reason: str,
) -> AcquisitionLedger:
    updated: list[AcquisitionSource] = []
    found = False
    for source in ledger.sources:
        if source.source_id != source_id:
            updated.append(source)
            continue
        found = True
        updated.append(
            source.model_copy(
                update={
                    "status": AcquisitionStatus.WITHDRAWN,
                    "imported_case_count": 0,
                    "evaluation_use_authorized": False,
                    "redistribution_authorized": False,
                    "withdrawn_at": datetime.now(UTC),
                    "withdrawal_reason": reason,
                    "notes": list(source.notes) + [f"withdrawn: {reason}"],
                }
            )
        )
    if not found:
        raise ValueError(f"unknown source_id: {source_id}")
    return ledger.model_copy(
        update={
            "sources": updated,
            "total_imported_cases": sum(
                s.imported_case_count for s in updated if s.status == AcquisitionStatus.IMPORTED
            ),
            "generated_at": datetime.now(UTC),
            "performance_claims_authorized": False,
        }
    )


def cancel_source(
    ledger: AcquisitionLedger,
    *,
    source_id: str,
    reason: str,
) -> AcquisitionLedger:
    updated: list[AcquisitionSource] = []
    found = False
    for source in ledger.sources:
        if source.source_id != source_id:
            updated.append(source)
            continue
        found = True
        updated.append(
            source.model_copy(
                update={
                    "status": AcquisitionStatus.CANCELLED,
                    "imported_case_count": 0,
                    "evaluation_use_authorized": False,
                    "redistribution_authorized": False,
                    "cancelled_at": datetime.now(UTC),
                    "cancellation_reason": reason,
                    "notes": list(source.notes) + [f"cancelled: {reason}"],
                }
            )
        )
    if not found:
        raise ValueError(f"unknown source_id: {source_id}")
    return ledger.model_copy(
        update={
            "sources": updated,
            "total_imported_cases": sum(
                s.imported_case_count for s in updated if s.status == AcquisitionStatus.IMPORTED
            ),
            "generated_at": datetime.now(UTC),
            "performance_claims_authorized": False,
        }
    )
