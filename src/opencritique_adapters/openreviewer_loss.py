"""Cross-adapter semantic-loss analysis for OpenReviewer vs Coarse."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .contract import COARSE_UPSTREAM_CONTRACT_VERSION
from .openreviewer import (
    OPENREVIEWER_CONTRACT_VERSION,
    OPENREVIEWER_FIXTURE_KIND,
    OPENREVIEWER_PERFORMANCE_CLAIMS_AUTHORIZED,
    OpenReviewerReview,
    convert_openreviewer_benchmark,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdapterLossProfile(StrictModel):
    adapter_id: str
    contract_version: str
    preserved: list[str]
    normalized: list[str]
    withheld_unavailable: list[str]
    lost_or_omitted: list[str]


class CrossAdapterConformanceReport(StrictModel):
    report_version: str = "0.1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    fixture_kind: str = OPENREVIEWER_FIXTURE_KIND
    performance_claims_authorized: bool = OPENREVIEWER_PERFORMANCE_CLAIMS_AUTHORIZED
    profiles: list[AdapterLossProfile]
    disclosure: str = (
        "Adapter conformance compares information preservation only. "
        "It does not validate reviewer quality or authorize performance claims."
    )


def openreviewer_loss_profile() -> AdapterLossProfile:
    return AdapterLossProfile(
        adapter_id="openreviewer",
        contract_version=OPENREVIEWER_CONTRACT_VERSION,
        preserved=[
            "markdown body (via provenance hash)",
            "finding title/body when structured",
            "weakness bullets parsed from markdown",
            "venue_template",
            "recommendation_score when present (system metadata only)",
        ],
        normalized=[
            "markdown weakness bullets → SubmittedConcern",
            "absent severity → informational placeholder with explicit unavailable note",
            "absent confidence → 0.0 with explicit unavailable note",
        ],
        withheld_unavailable=[
            "severity when not supplied by OpenReviewer",
            "confidence when not supplied",
            "quote/page anchors when not supplied",
            "claim validity",
            "concern taxonomy beyond adapter.openreviewer.unclassified",
        ],
        lost_or_omitted=[
            "narrative strengths / questions sections (not mapped to concerns)",
            "PDF extraction artifacts",
            "model sampling randomness (fixtures are frozen)",
        ],
    )


def coarse_loss_profile() -> AdapterLossProfile:
    return AdapterLossProfile(
        adapter_id="coarse",
        contract_version=COARSE_UPSTREAM_CONTRACT_VERSION,
        preserved=[
            "detailed_comments title/quote/feedback",
            "comment numbers via provenance material",
            "severity and confidence enums",
        ],
        normalized=["severity enum → Severity", "confidence enum → float"],
        withheld_unavailable=["verified claims", "expert taxonomy"],
        lost_or_omitted=["overall_feedback", "comment status", "review-level metadata"],
    )


def build_cross_adapter_report() -> CrossAdapterConformanceReport:
    return CrossAdapterConformanceReport(
        profiles=[coarse_loss_profile(), openreviewer_loss_profile()]
    )


def report_to_markdown(report: CrossAdapterConformanceReport) -> str:
    lines = [
        "# Cross-adapter conformance report",
        "",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        f"- Fixture kind: `{report.fixture_kind}`",
        f"- Performance claims authorized: **{report.performance_claims_authorized}**",
        "",
        report.disclosure,
        "",
    ]
    for profile in report.profiles:
        lines.extend(
            [
                f"## `{profile.adapter_id}` (`{profile.contract_version}`)",
                "",
                "### Preserved",
                "",
                *[f"- {item}" for item in profile.preserved],
                "",
                "### Normalized",
                "",
                *[f"- {item}" for item in profile.normalized],
                "",
                "### Withheld / unavailable",
                "",
                *[f"- {item}" for item in profile.withheld_unavailable],
                "",
                "### Lost or omitted",
                "",
                *[f"- {item}" for item in profile.lost_or_omitted],
                "",
            ]
        )
    return "\n".join(lines)


def write_cross_adapter_report(docs_dir: Path) -> dict[str, Path]:
    report = build_cross_adapter_report()
    docs_dir.mkdir(parents=True, exist_ok=True)
    md = docs_dir / "cross-adapter-conformance.md"
    js = docs_dir / "cross-adapter-conformance.json"
    md.write_text(report_to_markdown(report), encoding="utf-8")
    js.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"markdown": md, "json": js}


def assert_original_reconstructible(review_path: Path) -> str:
    raw = review_path.read_bytes()
    review = OpenReviewerReview.model_validate_json(raw)
    digest = __import__("hashlib").sha256(raw).hexdigest()
    if review.original_sha256 and review.original_sha256 != digest:
        raise AssertionError("stored provenance hash does not match file bytes")
    return digest


def convert_and_check(
    *,
    manifest: Path,
    benchmark_root: Path,
    mapping: Path,
) -> int:
    submission = convert_openreviewer_benchmark(
        benchmark_manifest_path=manifest,
        benchmark_root=benchmark_root,
        map_path=mapping,
    )
    return sum(len(case.concerns) for case in submission.cases)
