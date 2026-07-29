"""Document ingestion: Markdown / LaTeX / PDF → DocumentGraph."""

from __future__ import annotations

from .extractors import ingest_bytes, ingest_path
from .pdf_security import scan_pdf_security

__all__ = ["ingest_bytes", "ingest_path", "scan_pdf_security"]
