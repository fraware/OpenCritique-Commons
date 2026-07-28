"""PR8: document graph alpha + hidden-text security fixtures."""

from __future__ import annotations

from pathlib import Path

from opencritique_schema.document_graph import (
    INGESTION_TOOLCHAIN_VERSION,
    DocumentGraph,
    DocumentNode,
    ExtractionUncertainty,
    NodeKind,
    PageImageVerificationHook,
    SecurityFindingKind,
    resolve_against_graph,
)
from opencritique_schema.models import AnchorResolutionStatus, ArtifactReference

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "document_graph"


def _artifact(name: str) -> ArtifactReference:
    return ArtifactReference(
        uri=f"synthetic://docgraph/{name}",
        sha256="c" * 64,
        media_type="image/png",
        byte_size=10,
    )


def test_graph_with_page_equation_figure_table_citation() -> None:
    graph = DocumentGraph(
        manuscript_version_id="ocver_docgraph_demo_v1",
        ingestion_toolchain="opencritique-document-graph",
        ingestion_toolchain_version=INGESTION_TOOLCHAIN_VERSION,
        nodes=[
            DocumentNode(
                node_id="page-1",
                kind=NodeKind.PAGE,
                page_start=1,
                page_end=1,
                text="Synthetic page one body.",
                extraction_uncertainty=ExtractionUncertainty.LOW,
            ),
            DocumentNode(
                node_id="eq-1",
                kind=NodeKind.EQUATION,
                page_start=1,
                page_end=1,
                label="(1)",
                text="E = mc^2",
                extraction_uncertainty=ExtractionUncertainty.MODERATE,
            ),
            DocumentNode(
                node_id="fig-1",
                kind=NodeKind.FIGURE,
                page_start=2,
                page_end=2,
                label="Figure 1",
                extraction_uncertainty=ExtractionUncertainty.HIGH,
            ),
            DocumentNode(
                node_id="tab-1",
                kind=NodeKind.TABLE,
                page_start=2,
                page_end=2,
                label="Table 1",
                text="a,b,c",
                extraction_uncertainty=ExtractionUncertainty.LOW,
            ),
            DocumentNode(
                node_id="cite-1",
                kind=NodeKind.CITATION,
                page_start=3,
                page_end=3,
                label="[12]",
                text="Synthetic citation marker [12].",
                extraction_uncertainty=ExtractionUncertainty.NONE,
            ),
        ],
        page_image_hooks=[
            PageImageVerificationHook(
                hook_id="hook-1",
                page=1,
                rendered_image=_artifact("page-1.png"),
                status="pending",
            )
        ],
    )
    assert {n.kind for n in graph.nodes} >= {
        NodeKind.PAGE,
        NodeKind.EQUATION,
        NodeKind.FIGURE,
        NodeKind.TABLE,
        NodeKind.CITATION,
    }
    surface = resolve_against_graph(graph=graph, source_text="E = mc^2")
    assert surface.status == AnchorResolutionStatus.EXACT
    assert surface.extraction_uncertainty in {
        ExtractionUncertainty.MODERATE,
        ExtractionUncertainty.HIGH,
        ExtractionUncertainty.LOW,
        ExtractionUncertainty.NONE,
        ExtractionUncertainty.UNKNOWN,
    }


def test_uncertain_extraction_remains_uncertain() -> None:
    graph = DocumentGraph(
        manuscript_version_id="ocver_uncertain_v1",
        ingestion_toolchain="opencritique-document-graph",
        ingestion_toolchain_version=INGESTION_TOOLCHAIN_VERSION,
        nodes=[
            DocumentNode(
                node_id="fig-x",
                kind=NodeKind.FIGURE,
                page_start=1,
                page_end=1,
                label="Figure X",
                extraction_uncertainty=ExtractionUncertainty.HIGH,
            )
        ],
    )
    surface = resolve_against_graph(graph=graph, object_label="Figure X")
    assert surface.status == AnchorResolutionStatus.FUZZY_CANDIDATE
    assert surface.extraction_uncertainty == ExtractionUncertainty.HIGH
    assert surface.matched_node_ids == ["fig-x"]


def test_hidden_text_fixture_fail_closed() -> None:
    path = FIXTURES / "hidden_text_malicious.json"
    assert path.is_file()
    graph = DocumentGraph.model_validate_json(path.read_text(encoding="utf-8"))
    assert graph.blocked()
    surface = resolve_against_graph(
        graph=graph, source_text="visible benign caption text"
    )
    assert surface.security_blocked is True
    assert surface.status == AnchorResolutionStatus.UNRESOLVED
    assert surface.extraction_uncertainty == ExtractionUncertainty.SECURITY_BLOCKED
    kinds = {f.kind for f in graph.security_findings}
    assert SecurityFindingKind.HIDDEN_TEXT in kinds


def test_docs_version_toolchain() -> None:
    docs = (ROOT / "docs" / "document-graph-alpha.md").read_text(encoding="utf-8")
    assert INGESTION_TOOLCHAIN_VERSION in docs
    assert "opencritique-document-graph" in docs
