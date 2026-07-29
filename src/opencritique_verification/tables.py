"""Table consistency checks against manuscript table nodes."""

from __future__ import annotations

import re
from typing import Any

from opencritique_schema.document_graph import DocumentGraph, NodeKind

from .base import VerifierResult, build_verifier_result

_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _markdown_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    return rows


def check_table_consistency(
    *,
    graph: DocumentGraph,
    claimed_values: dict[str, float] | None = None,
    verifier_id: str = "table-consistency-v1",
) -> VerifierResult:
    """Check numeric cells are parseable and optional claimed values appear.

    Language-model-only verification is forbidden; this verifier inspects
    extracted table node text only.
    """
    tables = [n for n in graph.nodes if n.kind == NodeKind.TABLE]
    payload: dict[str, Any] = {
        "manuscript_version_id": graph.manuscript_version_id,
        "table_node_ids": [n.node_id for n in tables],
        "claimed_values": claimed_values or {},
    }
    if not tables:
        return build_verifier_result(
            verifier_id=verifier_id,
            status="fail",
            summary="No table nodes present in document graph",
            payload=payload,
        )

    parsed: dict[str, list[float]] = {}
    structural: dict[str, dict[str, Any]] = {}
    mismatches: list[str] = []
    for table in tables:
        nums = [float(m.group(0)) for m in _NUM_RE.finditer(table.text or "")]
        parsed[table.node_id] = nums
        rows = _markdown_rows(table.text or "")
        if not rows:
            structural[table.node_id] = {"rows": 0, "columns": 0}
            continue
        header = rows[0]
        body = rows[1:]
        row_lengths = [len(row) for row in rows]
        inconsistent = any(length != len(header) for length in row_lengths)
        subtotal_rows = 0
        for row in body:
            label = " ".join(row[:-1]).casefold()
            if "total" in label or "subtotal" in label:
                subtotal_rows += 1
                numeric_values = [
                    float(match.group(0))
                    for cell in row[1:]
                    for match in _NUM_RE.finditer(cell)
                ]
                for col_idx in range(1, len(row)):
                    prior_values: list[float] = []
                    for prior in body:
                        prior_label = " ".join(prior[:-1]).casefold()
                        if prior is row or "total" in prior_label or "subtotal" in prior_label:
                            break
                        if col_idx < len(prior):
                            prior_values.extend(
                                float(match.group(0))
                                for match in _NUM_RE.finditer(prior[col_idx])
                            )
                    if not prior_values or col_idx - 1 >= len(numeric_values):
                        continue
                    if abs(sum(prior_values) - numeric_values[col_idx - 1]) > 1e-9:
                        mismatches.append(f"{table.node_id}: subtotal mismatch in column {col_idx}")
        structural[table.node_id] = {
            "rows": len(body),
            "columns": len(header),
            "inconsistent_row_length": inconsistent,
            "subtotal_rows": subtotal_rows,
        }
        if inconsistent:
            mismatches.append(f"{table.node_id}: inconsistent row length")
    payload["parsed_numbers"] = parsed
    payload["structural_checks"] = structural

    missing: list[str] = []
    flat = [v for vals in parsed.values() for v in vals]
    for key, value in (claimed_values or {}).items():
        if not any(abs(v - value) < 1e-9 for v in flat):
            missing.append(key)
    payload["missing_claims"] = missing
    payload["mismatches"] = mismatches
    if missing or mismatches:
        return build_verifier_result(
            verifier_id=verifier_id,
            status="fail",
            summary=(
                "Table consistency failed; "
                f"missing claims={missing}, mismatches={mismatches}"
            ),
            payload=payload,
        )
    return build_verifier_result(
        verifier_id=verifier_id,
        status="pass",
        summary=f"Table consistency passed over {len(tables)} table node(s)",
        payload=payload,
    )
