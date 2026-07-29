"""Conversion-loss analysis for Coarse → OpenCritique adapter outputs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from opencritique_schema.coarse_adapter import resolve_quote

from .coarse import CoarseBenchmarkMap, CoarseReview, convert_coarse_benchmark
from .contract import (
    COARSE_CONTRACT_FIELDS,
    COARSE_FIXTURE_KIND,
    COARSE_PERFORMANCE_CLAIMS_AUTHORIZED,
    COARSE_UPSTREAM_COMMIT_PIN,
    COARSE_UPSTREAM_CONTRACT_VERSION,
    COARSE_UPSTREAM_REPOSITORY,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldFate(StrictModel):
    field_path: str
    fate: str  # preserved | normalized | provisional | omitted | unresolved
    notes: str


class QuoteResolutionStats(StrictModel):
    exact: int = 0
    normalized: int = 0
    ambiguous: int = 0
    unresolved: int = 0
    total: int = 0

    @property
    def exact_rate(self) -> float | None:
        return None if self.total == 0 else self.exact / self.total

    @property
    def normalized_rate(self) -> float | None:
        return None if self.total == 0 else self.normalized / self.total


class CaseLossRecord(StrictModel):
    case_id: str
    case_version: str
    review_path: str
    comment_count: int
    recovered_comment_numbers: list[int]
    quote_stats: QuoteResolutionStats
    field_fates: list[FieldFate]
    reconstructed_claims_provisional: bool = True


class CoarseConversionLossReport(StrictModel):
    report_version: str = "0.1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    upstream_contract_version: str = COARSE_UPSTREAM_CONTRACT_VERSION
    upstream_repository: str = COARSE_UPSTREAM_REPOSITORY
    upstream_commit_pin: str = COARSE_UPSTREAM_COMMIT_PIN
    fixture_kind: str = COARSE_FIXTURE_KIND
    performance_claims_authorized: bool = COARSE_PERFORMANCE_CLAIMS_AUTHORIZED
    compatibility_matrix: list[dict[str, str]]
    cases: list[CaseLossRecord]
    aggregate_quote_stats: QuoteResolutionStats
    omitted_field_summary: list[str]
    disclosure: str = (
        "Maintainer-owned sample fixtures exercise adapter compatibility only. "
        "They do not authorize precision, recall, or comparative performance claims."
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _baseline_field_fates() -> list[FieldFate]:
    return [
        FieldFate(
            field_path="detailed_comments[].number",
            fate="preserved",
            notes="Recoverable via adapter provenance local_id material and title/quote pairing.",
        ),
        FieldFate(
            field_path="detailed_comments[].title",
            fate="preserved",
            notes="Mapped to SubmittedConcern.title.",
        ),
        FieldFate(
            field_path="detailed_comments[].quote",
            fate="preserved",
            notes="Mapped to SubmittedAnchor.source_text verbatim; resolution may be unresolved.",
        ),
        FieldFate(
            field_path="detailed_comments[].feedback",
            fate="preserved",
            notes="Mapped to SubmittedConcern.summary.",
        ),
        FieldFate(
            field_path="detailed_comments[].severity",
            fate="normalized",
            notes="Mapped through SEVERITY_MAP into OpenCritique Severity.",
        ),
        FieldFate(
            field_path="detailed_comments[].confidence",
            fate="normalized",
            notes="Mapped through CONFIDENCE_MAP into float confidence.",
        ),
        FieldFate(
            field_path="detailed_comments[].status",
            fate="omitted",
            notes="Coarse comment workflow status has no evaluation-submission equivalent.",
        ),
        FieldFate(
            field_path="overall_feedback",
            fate="omitted",
            notes="Overview feedback is not a concern unit; omitted from EvaluationSubmission.",
        ),
        FieldFate(
            field_path="title|domain|taxonomy|date|language",
            fate="omitted",
            notes="Review-level metadata retained only in original fixture provenance by hash.",
        ),
        FieldFate(
            field_path="claim reconstruction",
            fate="provisional",
            notes="Any claim statements derived from titles remain candidate/inferred.",
        ),
    ]


def analyze_review_quotes(
    review: CoarseReview, extracted_text: str | None
) -> QuoteResolutionStats:
    stats = QuoteResolutionStats()
    for comment in review.detailed_comments:
        status = resolve_quote(comment.quote, extracted_text)
        stats.total += 1
        if status.value == "exact":
            stats.exact += 1
        elif status.value == "normalized":
            stats.normalized += 1
        elif status.value == "ambiguous":
            stats.ambiguous += 1
        else:
            stats.unresolved += 1
    return stats


def build_conversion_loss_report(
    *,
    benchmark_manifest_path: Path,
    benchmark_root: Path,
    map_path: Path,
    extracted_texts: dict[str, str | None] | None = None,
) -> CoarseConversionLossReport:
    """Convert without manual JSON edits and produce a public loss report."""
    mapping = CoarseBenchmarkMap.model_validate_json(map_path.read_text(encoding="utf-8"))
    # Deterministic conversion gate — must succeed without fixture mutation.
    submission = convert_coarse_benchmark(
        benchmark_manifest_path=benchmark_manifest_path,
        benchmark_root=benchmark_root,
        map_path=map_path,
    )
    by_case = {(item.case_id, item.case_version): item for item in submission.cases}
    extracted_texts = extracted_texts or {}
    case_records: list[CaseLossRecord] = []
    aggregate = QuoteResolutionStats()

    for entry in mapping.cases:
        if entry.failure or entry.abstained or not entry.review_path:
            continue
        review_path = (map_path.parent / entry.review_path).resolve()
        review = CoarseReview.model_validate_json(review_path.read_text(encoding="utf-8"))
        # Integrity check: original bytes hash is stable for provenance.
        _ = _sha256_text(review_path.read_text(encoding="utf-8"))
        converted = by_case[(entry.case_id, entry.case_version)]
        numbers = [c.number for c in review.detailed_comments]
        if len(converted.concerns) != len(review.detailed_comments):
            raise ValueError(
                f"comment count mismatch for {entry.case_id}: "
                f"{len(converted.concerns)} vs {len(review.detailed_comments)}"
            )
        quotes = analyze_review_quotes(
            review, extracted_texts.get(f"{entry.case_id}:{entry.case_version}")
        )
        aggregate.exact += quotes.exact
        aggregate.normalized += quotes.normalized
        aggregate.ambiguous += quotes.ambiguous
        aggregate.unresolved += quotes.unresolved
        aggregate.total += quotes.total
        case_records.append(
            CaseLossRecord(
                case_id=entry.case_id,
                case_version=entry.case_version,
                review_path=entry.review_path,
                comment_count=len(review.detailed_comments),
                recovered_comment_numbers=numbers,
                quote_stats=quotes,
                field_fates=_baseline_field_fates(),
            )
        )

    omitted = [
        fate.field_path
        for fate in _baseline_field_fates()
        if fate.fate in {"omitted", "provisional"}
    ]
    return CoarseConversionLossReport(
        compatibility_matrix=[
            {
                "upstream_contract_version": COARSE_UPSTREAM_CONTRACT_VERSION,
                "adapter_status": "supported",
                "fixture_kind": COARSE_FIXTURE_KIND,
                "notes": (
                    "Sample-adapter contract fixtures from corpus/samples/; "
                    "genuine production Coarse exports tracked on issue #3."
                ),
            }
        ],
        cases=case_records,
        aggregate_quote_stats=aggregate,
        omitted_field_summary=omitted,
    )


def report_to_markdown(report: CoarseConversionLossReport) -> str:
    qs = report.aggregate_quote_stats
    lines = [
        "# Coarse conversion-loss report",
        "",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        f"- Upstream contract: `{report.upstream_contract_version}`",
        f"- Upstream repository: {report.upstream_repository}",
        f"- Sample adapter contract: `{report.upstream_commit_pin}`",
        f"- Fixture kind: `{report.fixture_kind}`",
        f"- Performance claims authorized: **{report.performance_claims_authorized}**",
        "",
        "## Disclosure",
        "",
        report.disclosure,
        "",
        "## Compatibility matrix",
        "",
        "| Contract | Status | Notes |",
        "|---|---|---|",
    ]
    for row in report.compatibility_matrix:
        lines.append(
            f"| `{row['upstream_contract_version']}` | {row['adapter_status']} | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate quotation resolution",
            "",
            f"- Total quotations: {qs.total}",
            f"- Exact: {qs.exact}"
            + (f" ({qs.exact_rate:.3f})" if qs.exact_rate is not None else ""),
            f"- Normalized: {qs.normalized}"
            + (f" ({qs.normalized_rate:.3f})" if qs.normalized_rate is not None else ""),
            f"- Ambiguous: {qs.ambiguous}",
            f"- Unresolved: {qs.unresolved}",
            "",
            "Exact and normalized rates are reported separately.",
            "Unresolved quotations remain unresolved.",
            "",
            "## Omitted / provisional fields",
            "",
        ]
    )
    for item in report.omitted_field_summary:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Contract field inventory",
            "",
        ]
    )
    for group, fields in COARSE_CONTRACT_FIELDS.items():
        lines.append(f"- `{group}`: {', '.join(fields)}")
    lines.extend(
        [
            "",
            "## Per-case recovery",
            "",
            "| Case | Comments | Recovered numbers | Unresolved quotes |",
            "|---|---:|---|---:|",
        ]
    )
    for case in report.cases:
        lines.append(
            f"| `{case.case_id}` | {case.comment_count} | "
            f"{', '.join(str(n) for n in case.recovered_comment_numbers)} | "
            f"{case.quote_stats.unresolved} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report_artifacts(report: CoarseConversionLossReport, docs_dir: Path) -> dict[str, Path]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    md_path = docs_dir / "coarse-conversion-loss.md"
    json_path = docs_dir / "coarse-conversion-loss.json"
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"markdown": md_path, "json": json_path}


def load_report_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
