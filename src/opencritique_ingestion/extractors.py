"""Format extractors producing DocumentGraph nodes."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from opencritique_schema.document_graph import (
    INGESTION_TOOLCHAIN_ID,
    INGESTION_TOOLCHAIN_VERSION,
    DocumentGraph,
    DocumentNode,
    ExtractionUncertainty,
    NodeKind,
    PageImageVerificationHook,
)

from .pdf_security import extract_pdf_text_pages, scan_pdf_security

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_FIGURE_RE = re.compile(r"(?im)^(Figure\s+\d+[A-Za-z]?)\b.*$")
_TABLE_RE = re.compile(r"(?im)^(Table\s+\d+[A-Za-z]?)\b.*$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$", re.MULTILINE)
_CITATION_RE = re.compile(r"\[(\d+)\]|\(([^()]+\d{4}[^()]*)\)")
_BIB_RE = re.compile(r"(?im)^(?:##?\s*)?Bibliography\s*$")
_EQ_RE = re.compile(r"\$\$([^$]+)\$\$|\$([^$]+)\$")
_TEX_SECTION_RE = re.compile(r"\\(?P<kind>subsubsection|subsection|section)\*?\{(?P<title>[^}]+)\}")
_TEX_BLOCK_RE = re.compile(
    r"\\begin\{(?P<kind>theorem|lemma|proposition|corollary|proof|align\*?|equation\*?)\}(?P<body>.*?)\\end\{(?P=kind)\}",
    re.DOTALL,
)
_TEX_CITE_RE = re.compile(r"\\cite[pt]?\{([^}]+)\}")
_TEX_BIBITEM_RE = re.compile(
    r"\\bibitem(?:\[[^\]]+\])?\{(?P<key>[^}]+)\}(?P<body>.*?)(?=\\bibitem|\Z)",
    re.DOTALL,
)
_PDF_BLOCK_SPLIT_RE = re.compile(r"\n\s*\n+")


def _clean_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _section_path(stack: list[tuple[int, str]]) -> str:
    return " > ".join(title for _, title in stack)


def _markdown_table_blocks(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    blocks: list[tuple[int, int, str]] = []
    start: int | None = None
    for idx, line in enumerate(lines):
        is_row = line.strip().startswith("|") and line.strip().endswith("|")
        if is_row and start is None:
            start = idx
        elif not is_row and start is not None:
            blocks.append((start, idx, "\n".join(lines[start:idx])))
            start = None
    if start is not None:
        blocks.append((start, len(lines), "\n".join(lines[start:])))
    return blocks


def _parse_markdown_table(text: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def ingest_path(
    path: Path,
    *,
    manuscript_version_id: str,
) -> DocumentGraph:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return ingest_markdown(data.decode("utf-8"), manuscript_version_id=manuscript_version_id)
    if suffix in {".tex", ".latex"}:
        return ingest_latex(data.decode("utf-8"), manuscript_version_id=manuscript_version_id)
    if suffix == ".pdf":
        return ingest_pdf(data, manuscript_version_id=manuscript_version_id)
    raise ValueError(f"unsupported ingestion format: {suffix}")


def ingest_bytes(
    data: bytes,
    *,
    manuscript_version_id: str,
    media_type: str,
) -> DocumentGraph:
    mt = media_type.lower()
    if mt in {"text/markdown", "text/x-markdown"}:
        return ingest_markdown(data.decode("utf-8"), manuscript_version_id=manuscript_version_id)
    if mt in {"application/x-tex", "application/x-latex", "text/x-tex"}:
        return ingest_latex(data.decode("utf-8"), manuscript_version_id=manuscript_version_id)
    if mt == "application/pdf":
        return ingest_pdf(data, manuscript_version_id=manuscript_version_id)
    raise ValueError(f"unsupported media type: {media_type}")


def ingest_markdown(text: str, *, manuscript_version_id: str) -> DocumentGraph:
    text = _clean_text(text)
    nodes: list[DocumentNode] = []
    page = 1
    nodes.append(
        DocumentNode(
            node_id="page-1",
            kind=NodeKind.PAGE,
            page_start=page,
            page_end=page,
            text=text,
            extraction_confidence=1.0,
            extraction_uncertainty=ExtractionUncertainty.NONE,
        )
    )
    stack: list[tuple[int, str]] = []
    for idx, match in enumerate(_HEADING_RE.finditer(text), start=1):
        level = len(match.group(1))
        title = match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        nodes.append(
            DocumentNode(
                node_id=f"section-{idx}",
                kind=NodeKind.TEXT_BLOCK,
                page_start=page,
                page_end=page,
                label=title,
                text=match.group(0).strip(),
                extraction_confidence=1.0,
                extraction_uncertainty=ExtractionUncertainty.NONE,
                attributes={
                    "heading_level": level,
                    "section_depth": len(stack),
                    "has_children": True,
                },
            )
        )
    current_path = ""
    paragraph_index = 0
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped:
            continue
        if _HEADING_RE.fullmatch(stripped):
            match = _HEADING_RE.fullmatch(stripped)
            assert match is not None
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_path = _section_path(stack)
            continue
        if _FIGURE_RE.fullmatch(stripped) or _TABLE_RE.fullmatch(stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            continue
        paragraph_index += 1
        nodes.append(
            DocumentNode(
                node_id=f"paragraph-{paragraph_index}",
                kind=NodeKind.TEXT_BLOCK,
                page_start=page,
                page_end=page,
                label=current_path or None,
                text=stripped,
                extraction_confidence=1.0,
                extraction_uncertainty=ExtractionUncertainty.NONE,
                attributes={
                    "section_path_depth": (
                        current_path.count(">") + 1 if current_path else 0
                    )
                },
            )
        )
    for idx, match in enumerate(_FIGURE_RE.finditer(text), start=1):
        nodes.append(
            DocumentNode(
                node_id=f"figure-{idx}",
                kind=NodeKind.FIGURE,
                page_start=page,
                page_end=page,
                label=match.group(1),
                text=match.group(0).strip(),
                extraction_confidence=0.9,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"anchor_kind": "figure_caption"},
            )
        )
    table_captions = list(_TABLE_RE.finditer(text))
    for idx, match in enumerate(table_captions, start=1):
        nodes.append(
            DocumentNode(
                node_id=f"table-label-{idx}",
                kind=NodeKind.TABLE,
                page_start=page,
                page_end=page,
                label=match.group(1),
                text=match.group(0).strip(),
                extraction_confidence=0.9,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"anchor_kind": "table_caption"},
            )
        )
    for idx, (_, _, block) in enumerate(_markdown_table_blocks(text), start=1):
        header, body = _parse_markdown_table(block)
        if not header:
            continue
        nodes.append(
            DocumentNode(
                node_id=f"table-body-{idx}",
                kind=NodeKind.TABLE,
                page_start=page,
                page_end=page,
                label=(
                    table_captions[idx - 1].group(1)
                    if idx - 1 < len(table_captions)
                    else f"table-body-{idx}"
                ),
                text=block,
                extraction_confidence=1.0,
                extraction_uncertainty=ExtractionUncertainty.NONE,
                attributes={
                    "row_count": len(body),
                    "column_count": len(header),
                    "header_present": True,
                },
            )
        )
    for idx, match in enumerate(_EQ_RE.finditer(text), start=1):
        body = (match.group(1) or match.group(2) or "").strip()
        nodes.append(
            DocumentNode(
                node_id=f"equation-{idx}",
                kind=NodeKind.EQUATION,
                page_start=page,
                page_end=page,
                text=body,
                extraction_confidence=1.0,
                extraction_uncertainty=ExtractionUncertainty.NONE,
                attributes={"source": "markdown_math"},
            )
        )
    bib_match = _BIB_RE.search(text)
    if bib_match:
        bib_block = text[bib_match.end() :]
        for idx, line in enumerate(bib_block.splitlines(), start=1):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                entry = line.lstrip("-* ").strip()
                nodes.append(
                    DocumentNode(
                        node_id=f"bib-{idx}",
                        kind=NodeKind.CITATION,
                        page_start=page,
                        page_end=page,
                        label=f"bib-{idx}",
                        text=entry,
                        extraction_confidence=1.0,
                        extraction_uncertainty=ExtractionUncertainty.NONE,
                        attributes={
                            "role": "bibliography_entry",
                            "has_year": bool(re.search(r"\b(19|20)\d{2}\b", entry)),
                        },
                    )
                )
    for idx, match in enumerate(_CITATION_RE.finditer(text), start=1):
        label = match.group(1) or match.group(2) or match.group(0)
        nodes.append(
            DocumentNode(
                node_id=f"cite-inline-{idx}",
                kind=NodeKind.CITATION,
                page_start=page,
                page_end=page,
                label=str(label),
                text=match.group(0),
                extraction_confidence=0.85,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"role": "inline_citation"},
            )
        )
    return DocumentGraph(
        manuscript_version_id=manuscript_version_id,
        ingestion_toolchain=INGESTION_TOOLCHAIN_ID,
        ingestion_toolchain_version=INGESTION_TOOLCHAIN_VERSION,
        nodes=nodes,
        created_at=datetime.now(UTC),
    )


def ingest_latex(text: str, *, manuscript_version_id: str) -> DocumentGraph:
    text = _clean_text(text)
    nodes: list[DocumentNode] = [
        DocumentNode(
            node_id="page-1",
            kind=NodeKind.PAGE,
            page_start=1,
            page_end=1,
            text=text,
            extraction_confidence=0.95,
            extraction_uncertainty=ExtractionUncertainty.LOW,
            attributes={"source_format": "tex"},
        )
    ]
    section_stack: list[tuple[int, str]] = []
    for idx, match in enumerate(_TEX_SECTION_RE.finditer(text), start=1):
        kind = match.group("kind")
        title = match.group("title").strip()
        level = {"section": 1, "subsection": 2, "subsubsection": 3}[kind]
        while section_stack and section_stack[-1][0] >= level:
            section_stack.pop()
        section_stack.append((level, title))
        nodes.append(
            DocumentNode(
                node_id=f"tex-section-{idx}",
                kind=NodeKind.TEXT_BLOCK,
                page_start=1,
                page_end=1,
                label=title,
                text=match.group(0),
                extraction_confidence=0.95,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"heading_level": level, "section_depth": len(section_stack)},
            )
        )
    for idx, match in enumerate(_TEX_BLOCK_RE.finditer(text), start=1):
        kind = match.group("kind")
        body = match.group("body").strip()
        if not body:
            continue
        if kind.startswith(("equation", "align")):
            nodes.append(
                DocumentNode(
                    node_id=f"tex-eq-{idx}",
                    kind=NodeKind.EQUATION,
                    page_start=1,
                    page_end=1,
                    text=body,
                    extraction_confidence=0.92,
                    extraction_uncertainty=ExtractionUncertainty.LOW,
                    attributes={"source": kind, "source_preserved": True},
                )
            )
            continue
        nodes.append(
            DocumentNode(
                node_id=f"tex-block-{idx}",
                kind=NodeKind.TEXT_BLOCK,
                page_start=1,
                page_end=1,
                label=kind,
                text=body,
                extraction_confidence=0.88,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"tex_environment": kind},
            )
        )
    # Inline math as equation-as-source (subset).
    for idx, match in enumerate(re.finditer(r"\$([^$]+)\$", text), start=1):
        nodes.append(
            DocumentNode(
                node_id=f"tex-inline-eq-{idx}",
                kind=NodeKind.EQUATION,
                page_start=1,
                page_end=1,
                text=match.group(1).strip(),
                extraction_confidence=0.85,
                extraction_uncertainty=ExtractionUncertainty.MODERATE,
                attributes={"source": "latex_inline_math"},
            )
        )
    for idx, match in enumerate(_TEX_CITE_RE.finditer(text), start=1):
        keys = [item.strip() for item in match.group(1).split(",") if item.strip()]
        nodes.append(
            DocumentNode(
                node_id=f"tex-cite-{idx}",
                kind=NodeKind.CITATION,
                page_start=1,
                page_end=1,
                label=",".join(keys),
                text=match.group(0),
                extraction_confidence=0.95,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"role": "inline_citation", "key_count": len(keys)},
            )
        )
    for idx, match in enumerate(_TEX_BIBITEM_RE.finditer(text), start=1):
        nodes.append(
            DocumentNode(
                node_id=f"tex-bib-{idx}",
                kind=NodeKind.CITATION,
                page_start=1,
                page_end=1,
                label=match.group("key").strip(),
                text=match.group("body").strip(),
                extraction_confidence=0.9,
                extraction_uncertainty=ExtractionUncertainty.LOW,
                attributes={"role": "bibliography_entry"},
            )
        )
    return DocumentGraph(
        manuscript_version_id=manuscript_version_id,
        ingestion_toolchain=INGESTION_TOOLCHAIN_ID,
        ingestion_toolchain_version=INGESTION_TOOLCHAIN_VERSION,
        nodes=nodes,
        created_at=datetime.now(UTC),
    )


def ingest_pdf(data: bytes, *, manuscript_version_id: str) -> DocumentGraph:
    findings = scan_pdf_security(data)
    hooks: list[PageImageVerificationHook] = []
    nodes: list[DocumentNode] = []
    if any(f.severity == "block" and f.fail_closed for f in findings):
        nodes.append(
            DocumentNode(
                node_id="page-blocked",
                kind=NodeKind.PAGE,
                page_start=1,
                page_end=1,
                text=None,
                extraction_confidence=0.0,
                extraction_uncertainty=ExtractionUncertainty.SECURITY_BLOCKED,
            )
        )
        hooks.append(
            PageImageVerificationHook(
                hook_id="pdf-page-1",
                page=1,
                status="blocked",
                notes="Fail-closed: PDF security findings blocked extraction.",
            )
        )
        return DocumentGraph(
            manuscript_version_id=manuscript_version_id,
            ingestion_toolchain=INGESTION_TOOLCHAIN_ID,
            ingestion_toolchain_version=INGESTION_TOOLCHAIN_VERSION,
            nodes=nodes,
            page_image_hooks=hooks,
            security_findings=findings,
            created_at=datetime.now(UTC),
        )

    pages = extract_pdf_text_pages(data)
    for page_num, page_text in enumerate(pages, start=1):
        normalized_page_text = _clean_text(page_text)
        digest = hashlib.sha256(normalized_page_text.encode("utf-8")).hexdigest()
        text_present = bool(normalized_page_text.strip())
        uncertainty = (
            ExtractionUncertainty.HIGH if not text_present else ExtractionUncertainty.MODERATE
        )
        nodes.append(
            DocumentNode(
                node_id=f"pdf-page-{page_num}",
                kind=NodeKind.PAGE,
                page_start=page_num,
                page_end=page_num,
                text=normalized_page_text or None,
                extraction_confidence=0.6 if text_present else 0.2,
                extraction_uncertainty=uncertainty,
                attributes={"text_sha256": digest, "text_present": text_present},
            )
        )
        for block_idx, block in enumerate(_PDF_BLOCK_SPLIT_RE.split(normalized_page_text), start=1):
            snippet = block.strip()
            if not snippet:
                continue
            nodes.append(
                DocumentNode(
                    node_id=f"pdf-page-{page_num}-block-{block_idx}",
                    kind=NodeKind.TEXT_BLOCK,
                    page_start=page_num,
                    page_end=page_num,
                    text=snippet,
                    extraction_confidence=0.55,
                    extraction_uncertainty=ExtractionUncertainty.MODERATE,
                    attributes={"source": "pdf_text_layer"},
                )
            )
        hooks.append(
            PageImageVerificationHook(
                hook_id=f"pdf-render-{page_num}",
                page=page_num,
                status="pending" if text_present else "unavailable",
                notes=(
                    "Compare extracted text against a rendered page image before trusting "
                    "fine-grained anchors."
                    if text_present
                    else "No reliable text layer extracted; rendered page verification required."
                ),
                ocr_text_hash=digest if text_present else None,
            )
        )
    if not nodes:
        nodes.append(
            DocumentNode(
                node_id="pdf-empty",
                kind=NodeKind.PAGE,
                page_start=1,
                page_end=1,
                extraction_confidence=0.0,
                extraction_uncertainty=ExtractionUncertainty.HIGH,
            )
        )
    return DocumentGraph(
        manuscript_version_id=manuscript_version_id,
        ingestion_toolchain=INGESTION_TOOLCHAIN_ID,
        ingestion_toolchain_version=INGESTION_TOOLCHAIN_VERSION,
        nodes=nodes,
        page_image_hooks=hooks,
        security_findings=findings,
        created_at=datetime.now(UTC),
    )
