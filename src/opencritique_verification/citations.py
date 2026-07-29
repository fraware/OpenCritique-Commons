"""Citation presence checks against bibliography / citation nodes."""

from __future__ import annotations

from typing import Any

from opencritique_schema.document_graph import DocumentGraph, NodeKind

from .base import VerifierResult, build_verifier_result


def check_citation_presence(
    *,
    graph: DocumentGraph,
    required_markers: list[str] | None = None,
    verifier_id: str = "citation-presence-v1",
) -> VerifierResult:
    cites = [n for n in graph.nodes if n.kind == NodeKind.CITATION]
    inline = [n for n in cites if n.attributes.get("role") == "inline_citation"]
    bibliography = [n for n in cites if n.attributes.get("role") == "bibliography_entry"]
    labels = {(n.label or "").strip() for n in cites if n.label}
    texts = {(n.text or "").strip() for n in cites if n.text}
    required = required_markers or []
    payload: dict[str, Any] = {
        "manuscript_version_id": graph.manuscript_version_id,
        "citation_count": len(cites),
        "inline_citation_count": len(inline),
        "bibliography_entry_count": len(bibliography),
        "labels": sorted(labels),
        "required_markers": required,
    }
    missing_inline = [
        marker
        for marker in required
        if not any(marker in (n.label or "") or marker in (n.text or "") for n in inline)
    ]
    missing_bibliography = [
        marker
        for marker in required
        if not any(marker in (n.label or "") or marker in (n.text or "") for n in bibliography)
    ]
    unresolved_references = sorted(
        label
        for label in {item for item in labels if item}
        if label not in {(n.label or "").strip() for n in bibliography}
        and "," not in label
    )
    payload["missing_inline"] = missing_inline
    payload["missing_bibliography"] = missing_bibliography
    payload["unresolved_references"] = unresolved_references
    missing_anywhere = [
        marker
        for marker in required
        if marker not in labels and not any(marker in text for text in texts)
    ]
    payload["missing_anywhere"] = missing_anywhere
    if required and missing_anywhere:
        return build_verifier_result(
            verifier_id=verifier_id,
            status="fail",
            summary=(
                "Citation verification failed: "
                f"missing markers={missing_anywhere}"
            ),
            payload=payload,
        )
    if not cites:
        return build_verifier_result(
            verifier_id=verifier_id,
            status="fail",
            summary="No citation nodes present in document graph",
            payload=payload,
        )
    status = "pass" if not unresolved_references else "fail"
    summary = (
        f"Citation presence passed with {len(cites)} citation node(s)"
        if status == "pass"
        else f"Citation verification found unresolved references: {unresolved_references}"
    )
    return build_verifier_result(
        verifier_id=verifier_id,
        status=status,
        summary=summary,
        payload=payload,
    )
