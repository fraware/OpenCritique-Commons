"""Wave 3: ingestion extractors and document-graph wiring."""

from __future__ import annotations

from pathlib import Path

from opencritique_ingestion import ingest_path
from opencritique_schema.document_graph import (
    ExtractionUncertainty,
    NodeKind,
    ingest_to_graph,
    resolve_against_graph,
)
from opencritique_schema.models import AnchorResolutionStatus

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "corpus" / "samples"


def test_markdown_sample_ingestion() -> None:
    path = SAMPLES / "sample-figtable-01" / "manuscript.md"
    graph = ingest_path(path, manuscript_version_id="ocver_ingest_fig_v1")
    kinds = {n.kind for n in graph.nodes}
    assert NodeKind.PAGE in kinds
    assert NodeKind.TABLE in kinds
    assert NodeKind.FIGURE in kinds
    assert NodeKind.CITATION in kinds
    assert any(
        node.kind == NodeKind.TABLE
        and node.label == "Table 2"
        and node.text == "Table 2 reports point estimates for each adjusted risk ratio."
        for node in graph.nodes
    )
    assert any(
        node.kind == NodeKind.TABLE
        and node.attributes.get("column_count") == 3
        and node.attributes.get("row_count") == 3
        for node in graph.nodes
    )
    surface = resolve_against_graph(
        graph=graph,
        source_text="Table 2 reports point estimates for each adjusted risk ratio.",
    )
    assert surface.status == AnchorResolutionStatus.EXACT


def test_latex_sample_ingestion() -> None:
    path = SAMPLES / "sample-theory-01" / "manuscript.tex"
    graph = ingest_to_graph(path=str(path), manuscript_version_id="ocver_ingest_tex_v1")
    assert any(n.kind == NodeKind.EQUATION for n in graph.nodes)
    assert any(n.kind == NodeKind.TEXT_BLOCK for n in graph.nodes)
    assert any(
        n.kind == NodeKind.TEXT_BLOCK and n.label == "Bound" for n in graph.nodes
    )


def test_pdf_malicious_fail_closed() -> None:
    # Minimal malicious-ish PDF bytes with /JavaScript marker.
    data = b"%PDF-1.4\n1 0 obj<< /JavaScript (evil) >>endobj\n%%EOF\n"
    graph = ingest_to_graph(
        data=data,
        media_type="application/pdf",
        manuscript_version_id="ocver_ingest_pdf_bad_v1",
    )
    assert graph.blocked()
    surface = resolve_against_graph(graph=graph, source_text="anything")
    assert surface.security_blocked is True
    assert surface.extraction_uncertainty == ExtractionUncertainty.SECURITY_BLOCKED


def test_pdf_benign_text_layer() -> None:
    data = b"%PDF-1.4\nBT (Hello sample PDF text) Tj ET\n%%EOF\n"
    graph = ingest_to_graph(
        data=data,
        media_type="application/pdf",
        manuscript_version_id="ocver_ingest_pdf_ok_v1",
    )
    assert not graph.blocked()
    assert graph.nodes
    assert graph.page_image_hooks
    assert graph.page_image_hooks[0].status in {"unavailable", "pending", "matched"}
    assert any(node.kind == NodeKind.TEXT_BLOCK for node in graph.nodes)


def test_all_shipped_samples_ingest_to_graph() -> None:
    sample_paths = sorted(SAMPLES.glob("*/manuscript.*"))
    assert sample_paths
    for sample_path in sample_paths:
        graph = ingest_path(sample_path, manuscript_version_id=f"smoke-{sample_path.stem}")
        assert graph.nodes, sample_path
        assert not graph.blocked(), sample_path
