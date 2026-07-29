"""Document graph alpha: pages, equations, figures, tables, citations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import AnchorResolutionStatus, ArtifactReference, BoundingBox


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ExtractionUncertainty(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"
    SECURITY_BLOCKED = "security_blocked"


class NodeKind(str, Enum):
    PAGE = "page"
    EQUATION = "equation"
    FIGURE = "figure"
    TABLE = "table"
    CITATION = "citation"
    TEXT_BLOCK = "text_block"


class SecurityFindingKind(str, Enum):
    HIDDEN_TEXT = "hidden_text"
    OVERLAY_OBFUSCATION = "overlay_obfuscation"
    SCRIPT_PAYLOAD = "script_payload"
    SUSPICIOUS_FONT_SIZE = "suspicious_font_size"
    JAVA_SCRIPT_ACTION = "javascript_action"
    EXTERNAL_STREAM = "external_stream"


class PageImageVerificationHook(StrictModel):
    """Hook for comparing extracted text against a rendered page image."""

    hook_id: str
    page: int = Field(ge=1)
    rendered_image: ArtifactReference | None = None
    ocr_text_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    visual_diff_score: float | None = Field(default=None, ge=0, le=1)
    status: Literal["pending", "matched", "mismatched", "unavailable", "blocked"] = "pending"
    notes: str = ""


class SecurityFinding(StrictModel):
    finding_id: str
    kind: SecurityFindingKind
    page: int | None = Field(default=None, ge=1)
    severity: Literal["info", "warn", "block"] = "warn"
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    fail_closed: bool = True


class DocumentNode(StrictModel):
    node_id: str
    kind: NodeKind
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    label: str | None = None
    text: str | None = None
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    extraction_uncertainty: ExtractionUncertainty = ExtractionUncertainty.UNKNOWN
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def pages_ordered(self) -> DocumentNode:
        if self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        return self


class DocumentGraph(StrictModel):
    graph_version: str = "0.1"
    manuscript_version_id: str
    ingestion_toolchain: str
    ingestion_toolchain_version: str
    nodes: list[DocumentNode]
    page_image_hooks: list[PageImageVerificationHook] = Field(default_factory=list)
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def unique_nodes(self) -> DocumentGraph:
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("document graph node_id values must be unique")
        return self

    def blocked(self) -> bool:
        return any(
            f.severity == "block" and f.fail_closed for f in self.security_findings
        )


class AnchorResolutionSurface(StrictModel):
    """Explicit uncertainty surface for anchor resolution against a document graph."""

    submitted_text: str | None = None
    submitted_page: int | None = None
    submitted_object_label: str | None = None
    status: AnchorResolutionStatus
    matched_node_ids: list[str] = Field(default_factory=list)
    extraction_uncertainty: ExtractionUncertainty
    security_blocked: bool = False
    rationale: str


def resolve_against_graph(
    *,
    graph: DocumentGraph,
    source_text: str | None = None,
    page: int | None = None,
    object_label: str | None = None,
) -> AnchorResolutionSurface:
    if graph.blocked():
        return AnchorResolutionSurface(
            submitted_text=source_text,
            submitted_page=page,
            submitted_object_label=object_label,
            status=AnchorResolutionStatus.UNRESOLVED,
            matched_node_ids=[],
            extraction_uncertainty=ExtractionUncertainty.SECURITY_BLOCKED,
            security_blocked=True,
            rationale="Document graph has fail-closed security findings; resolution blocked.",
        )

    exact: list[str] = []
    label_hits: list[str] = []
    page_hits: list[str] = []
    uncertainties: list[ExtractionUncertainty] = []

    for node in graph.nodes:
        uncertainties.append(node.extraction_uncertainty)
        if source_text and node.text and source_text == node.text:
            exact.append(node.node_id)
        if object_label and node.label and object_label.casefold() == node.label.casefold():
            label_hits.append(node.node_id)
        if page is not None and node.page_start <= page <= node.page_end:
            page_hits.append(node.node_id)

    def _worst(values: list[ExtractionUncertainty]) -> ExtractionUncertainty:
        order = [
            ExtractionUncertainty.SECURITY_BLOCKED,
            ExtractionUncertainty.HIGH,
            ExtractionUncertainty.UNKNOWN,
            ExtractionUncertainty.MODERATE,
            ExtractionUncertainty.LOW,
            ExtractionUncertainty.NONE,
        ]
        for level in order:
            if level in values:
                return level
        return ExtractionUncertainty.UNKNOWN

    worst = _worst(uncertainties) if uncertainties else ExtractionUncertainty.UNKNOWN

    if len(exact) == 1:
        return AnchorResolutionSurface(
            submitted_text=source_text,
            submitted_page=page,
            submitted_object_label=object_label,
            status=AnchorResolutionStatus.EXACT,
            matched_node_ids=exact,
            extraction_uncertainty=worst,
            rationale="Exact text match against a single document node.",
        )
    if len(exact) > 1:
        return AnchorResolutionSurface(
            submitted_text=source_text,
            submitted_page=page,
            submitted_object_label=object_label,
            status=AnchorResolutionStatus.AMBIGUOUS,
            matched_node_ids=sorted(set(exact)),
            extraction_uncertainty=worst,
            rationale="Exact text matched multiple nodes; left ambiguous.",
        )
    if len(label_hits) == 1:
        return AnchorResolutionSurface(
            submitted_text=source_text,
            submitted_page=page,
            submitted_object_label=object_label,
            status=AnchorResolutionStatus.FUZZY_CANDIDATE,
            matched_node_ids=label_hits,
            extraction_uncertainty=worst,
            rationale="Object label matched a single node; extraction uncertainty preserved.",
        )
    if len(label_hits) > 1:
        return AnchorResolutionSurface(
            submitted_text=source_text,
            submitted_page=page,
            submitted_object_label=object_label,
            status=AnchorResolutionStatus.AMBIGUOUS,
            matched_node_ids=sorted(set(label_hits)),
            extraction_uncertainty=worst,
            rationale="Object label matched multiple nodes.",
        )
    if page is not None and len(page_hits) == 1 and not source_text and not object_label:
        return AnchorResolutionSurface(
            submitted_text=source_text,
            submitted_page=page,
            submitted_object_label=object_label,
            status=AnchorResolutionStatus.FUZZY_CANDIDATE,
            matched_node_ids=page_hits,
            extraction_uncertainty=worst,
            rationale="Page-only candidate; extraction uncertainty preserved.",
        )
    return AnchorResolutionSurface(
        submitted_text=source_text,
        submitted_page=page,
        submitted_object_label=object_label,
        status=AnchorResolutionStatus.UNRESOLVED,
        matched_node_ids=[],
        extraction_uncertainty=worst,
        rationale="No confident match; unresolved without inventing anchors.",
    )


INGESTION_TOOLCHAIN_ID = "opencritique-document-graph"
INGESTION_TOOLCHAIN_VERSION = "0.1.0-alpha"


def ingest_to_graph(
    *,
    manuscript_version_id: str,
    path: str | None = None,
    data: bytes | None = None,
    media_type: str | None = None,
) -> DocumentGraph:
    """Wire real extractors into the document-graph module.

    Prefer this entrypoint over constructing graphs by hand when ingesting
    Markdown, LaTeX, or PDF samples.
    """
    from pathlib import Path

    from opencritique_ingestion import ingest_bytes, ingest_path

    if path is not None:
        return ingest_path(Path(path), manuscript_version_id=manuscript_version_id)
    if data is None or media_type is None:
        raise ValueError("ingest_to_graph requires path or (data, media_type)")
    return ingest_bytes(data, manuscript_version_id=manuscript_version_id, media_type=media_type)

