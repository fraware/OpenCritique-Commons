"""Versioned schema identifiers for every persistent OpenCritique object.

Frozen for v0.5.0a1. Renames or identifier changes require a major schema bump
and an ADR; see docs/schema-compatibility.md and ADR-0002.

This module stays free of adapter/registry/FastAPI imports so
`opencritique_schema` remains a leaf dependency.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from .models import (
    Adjudication,
    Anchor,
    CaseBundle,
    Claim,
    Concern,
    Counterposition,
    EvidenceItem,
    Manuscript,
    ManuscriptVersion,
    Resolution,
    RunManifest,
)

# Package release that freezes these identifiers.
SCHEMA_FREEZE_RELEASE = "0.5.0a1"

# Normative record schema_version embedded in RecordBase objects.
RECORD_SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class SchemaEntry:
    """Registry entry for one persistent object type."""

    schema_id: str
    schema_version: str
    model: type[BaseModel]
    persistent: bool
    description: str


def _entry(
    name: str,
    model: type[BaseModel],
    *,
    version: str = RECORD_SCHEMA_VERSION,
    persistent: bool = True,
    description: str = "",
) -> SchemaEntry:
    return SchemaEntry(
        schema_id=f"opencritique.{name}",
        schema_version=version,
        model=model,
        persistent=persistent,
        description=description or f"OpenCritique {name} schema",
    )


# Core schema package objects (always available; no cross-package imports).
_CORE_ENTRIES: tuple[SchemaEntry, ...] = (
    _entry("Manuscript", Manuscript, description="Manuscript identity and rights metadata"),
    _entry("ManuscriptVersion", ManuscriptVersion),
    _entry("Anchor", Anchor),
    _entry("Claim", Claim),
    _entry("Concern", Concern),
    _entry("EvidenceItem", EvidenceItem),
    _entry("Counterposition", Counterposition),
    _entry("Adjudication", Adjudication),
    _entry("Resolution", Resolution),
    _entry("RunManifest", RunManifest),
    _entry("CaseBundle", CaseBundle),
)

SCHEMA_REGISTRY: dict[str, SchemaEntry] = {entry.schema_id: entry for entry in _CORE_ENTRIES}


class SchemaRegistryError(Exception):
    """Base typed error for schema registry operations."""


class UnknownSchemaError(SchemaRegistryError):
    def __init__(self, schema_id: str) -> None:
        self.schema_id = schema_id
        super().__init__(f"unknown schema id: {schema_id}")


class SchemaValidationError(SchemaRegistryError):
    """Malformed fixture or payload failed typed validation."""

    def __init__(self, schema_id: str, errors: list[dict[str, Any]]) -> None:
        self.schema_id = schema_id
        self.errors = errors
        super().__init__(f"schema validation failed for {schema_id}: {len(errors)} error(s)")


def register_schema(entry: SchemaEntry) -> SchemaEntry:
    """Register or replace a schema entry (used by freeze inventory assembly)."""
    SCHEMA_REGISTRY[entry.schema_id] = entry
    return entry


def register_models(
    models: Iterable[tuple[str, type[BaseModel], str]],
    *,
    version: str = "0.1",
) -> None:
    for name, model, description in models:
        register_schema(_entry(name, model, version=version, description=description))


def load_extended_registry() -> dict[str, SchemaEntry]:
    """Assemble the full v0.5 freeze inventory across packages."""
    from opencritique_acquisition.models import AcquisitionLedger
    from opencritique_adapters.coarse import CoarseBenchmarkMap, CoarseReview
    from opencritique_evaluation.models import (
        BenchmarkManifest,
        EvaluationResult,
        EvaluationSubmission,
        MatcherSensitivityReport,
        NovelConcernDetermination,
        NovelConcernQueue,
        PublicScorecard,
        SignedScorecardEnvelope,
        SystemManifest,
    )

    register_models(
        [
            ("BenchmarkManifest", BenchmarkManifest, "Benchmark manifest"),
            ("SystemManifest", SystemManifest, "System under evaluation"),
            ("EvaluationSubmission", EvaluationSubmission, "Evaluation submission"),
            ("EvaluationResult", EvaluationResult, "Evaluation result"),
            ("PublicScorecard", PublicScorecard, "Public scorecard"),
            ("MatcherSensitivityReport", MatcherSensitivityReport, "Matcher sensitivity"),
            ("NovelConcernQueue", NovelConcernQueue, "Novel concern queue"),
            (
                "NovelConcernDetermination",
                NovelConcernDetermination,
                "Append-only novel-concern determination",
            ),
            ("SignedScorecardEnvelope", SignedScorecardEnvelope, "Signed scorecard"),
            ("AcquisitionLedger", AcquisitionLedger, "Acquisition ledger"),
            ("CoarseBenchmarkMap", CoarseBenchmarkMap, "Coarse benchmark map"),
            ("CoarseReview", CoarseReview, "Coarse review export"),
        ],
        version="0.1",
    )
    return SCHEMA_REGISTRY


def list_schemas(*, persistent_only: bool = False) -> list[SchemaEntry]:
    entries = sorted(SCHEMA_REGISTRY.values(), key=lambda item: item.schema_id)
    if persistent_only:
        return [item for item in entries if item.persistent]
    return entries


def get_schema(schema_id: str) -> SchemaEntry:
    try:
        return SCHEMA_REGISTRY[schema_id]
    except KeyError as exc:
        raise UnknownSchemaError(schema_id) from exc


def schema_id_for_model(model: type[BaseModel] | BaseModel) -> str:
    cls = model if isinstance(model, type) else type(model)
    for entry in SCHEMA_REGISTRY.values():
        if entry.model is cls:
            return entry.schema_id
    raise UnknownSchemaError(cls.__name__)


def validate_payload(schema_id: str, payload: dict[str, Any] | str | bytes) -> BaseModel:
    entry = get_schema(schema_id)
    try:
        if isinstance(payload, (str, bytes)):
            return entry.model.model_validate_json(payload)
        return entry.model.model_validate(payload)
    except ValidationError as exc:
        raise SchemaValidationError(schema_id, exc.errors()) from exc


def export_json_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON Schema documents keyed by model class name."""
    return {
        entry.model.__name__: entry.model.model_json_schema()
        for entry in list_schemas()
    }
