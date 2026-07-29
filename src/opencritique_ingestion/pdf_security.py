"""PDF security scanning and text-layer extraction (fail-closed)."""

from __future__ import annotations

import re

from opencritique_schema.document_graph import SecurityFinding, SecurityFindingKind

# Lightweight byte-level markers for common PDF active content.
_BLOCK_PATTERNS: list[tuple[SecurityFindingKind, bytes, str]] = [
    (SecurityFindingKind.JAVA_SCRIPT_ACTION, b"/JavaScript", "PDF contains /JavaScript action"),
    (SecurityFindingKind.JAVA_SCRIPT_ACTION, b"/JS", "PDF contains /JS action dictionary"),
    (SecurityFindingKind.SCRIPT_PAYLOAD, b"/OpenAction", "PDF contains /OpenAction"),
    (SecurityFindingKind.EXTERNAL_STREAM, b"/EmbeddedFile", "PDF contains embedded file stream"),
    (SecurityFindingKind.EXTERNAL_STREAM, b"/Launch", "PDF contains /Launch action"),
    (SecurityFindingKind.HIDDEN_TEXT, b"/Trapped", "PDF marks trapping metadata anomalies"),
]


def scan_pdf_security(data: bytes) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    if not data.startswith(b"%PDF"):
        findings.append(
            SecurityFinding(
                finding_id="pdf-not-pdf",
                kind=SecurityFindingKind.SCRIPT_PAYLOAD,
                severity="block",
                description="Bytes do not start with %PDF; refuse ingestion.",
                fail_closed=True,
            )
        )
        return findings
    for idx, (kind, needle, description) in enumerate(_BLOCK_PATTERNS, start=1):
        if needle in data:
            findings.append(
                SecurityFinding(
                    finding_id=f"pdf-sec-{idx}",
                    kind=kind,
                    page=1,
                    severity="block",
                    description=description,
                    evidence={"marker": needle.decode("latin-1", errors="replace")},
                    fail_closed=True,
                )
            )
    # Near-invisible text heuristic: Tj operators with tiny font sizes in content streams.
    if re.search(br"/\w+\s+0\.0?1\s+Tf", data) or b"0.01 Tf" in data:
        findings.append(
            SecurityFinding(
                finding_id="pdf-tiny-font",
                kind=SecurityFindingKind.SUSPICIOUS_FONT_SIZE,
                page=1,
                severity="block",
                description="Suspiciously small font size detected in content stream.",
                fail_closed=True,
            )
        )
    return findings


def extract_pdf_text_pages(data: bytes) -> list[str]:
    """Extract approximate text layers without executing PDF content.

    Prefer pypdf when installed; otherwise fall back to a conservative literal
    string harvest that never interprets operators beyond parentheses text.
    """
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]
    except ImportError:
        return _literal_pdf_strings(data)

    import io

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                pages.append("")
        if pages:
            return pages
    except Exception:  # noqa: BLE001 — malformed PDF falls back to literals
        pass
    return _literal_pdf_strings(data)


def _literal_pdf_strings(data: bytes) -> list[str]:
    """Best-effort harvest of printable PDF literal strings."""
    chunks = re.findall(rb"\((?:\\.|[^\\)]){1,500}\)", data)
    texts: list[str] = []
    for raw in chunks:
        inner = raw[1:-1]
        try:
            decoded = (
                inner.decode("latin-1")
                .replace("\\n", "\n")
                .replace("\\r", "\n")
                .replace("\\t", "\t")
            )
        except Exception:  # noqa: BLE001
            continue
        if any(ch.isalpha() for ch in decoded):
            texts.append(decoded)
    body = " ".join(texts)
    return [body] if body else [""]
