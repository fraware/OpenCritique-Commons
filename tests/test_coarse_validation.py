"""PR5 / issue #3: Coarse adapter validation against synthetic contract fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from opencritique_adapters.coarse import CoarseReview, convert_coarse_benchmark
from opencritique_adapters.coarse_loss import build_conversion_loss_report, write_report_artifacts
from opencritique_adapters.contract import (
    COARSE_PERFORMANCE_CLAIMS_AUTHORIZED,
    COARSE_UPSTREAM_CONTRACT_VERSION,
)
from opencritique_schema.coarse_adapter import convert_coarse_review

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "coarse"
BENCH = ROOT / "benchmarks" / "coarse-synth-v0.1"
MAP = FIXTURES / "maps" / "synth-map.json"
MANIFEST = BENCH / "manifest.json"
DOCS = ROOT / "docs"


def test_upstream_contract_is_pinned() -> None:
    meta = json.loads((FIXTURES / "UPSTREAM_CONTRACT.json").read_text(encoding="utf-8"))
    assert meta["upstream_contract_version"] == COARSE_UPSTREAM_CONTRACT_VERSION
    assert meta["performance_claims_authorized"] is False
    assert meta["genuine_production_exports_available"] is False
    assert COARSE_PERFORMANCE_CLAIMS_AUTHORIZED is False


def test_at_least_ten_sample_reviews_validate() -> None:
    reviews = sorted((FIXTURES / "reviews").glob("*.json"))
    assert len(reviews) >= 10
    domains = set()
    for path in reviews:
        review = CoarseReview.model_validate_json(path.read_text(encoding="utf-8"))
        assert review.detailed_comments
        assert "[SAMPLE]" in review.title
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["opencritique_fixture"]["confidential_manuscript_text"] is False
        assert raw["opencritique_fixture"]["performance_claims_authorized"] is False
        assert raw["opencritique_fixture"]["sample_adapter_contract_id"] == (
            "opencritique-sample-adapter-contract-v1"
        )
        domains.add(review.domain)
    # Domain coverage required by issue #3 (sample stand-ins until production exports).
    assert "economics" in domains or "statistics" in domains
    assert "machine_learning" in domains
    assert "mathematics" in domains or "theoretical_cs" in domains


def test_upstream_contract_has_no_pretend_git_sha() -> None:
    meta = json.loads((FIXTURES / "UPSTREAM_CONTRACT.json").read_text(encoding="utf-8"))
    assert meta["sample_adapter_contract_id"] == "opencritique-sample-adapter-contract-v1"
    assert meta["upstream_commit_pin"] is None
    pin = meta.get("upstream_commit_pin")
    assert pin is None or not (
        isinstance(pin, str) and len(pin) == 40 and all(c in "0123456789abcdef" for c in pin)
    )


def test_deterministic_conversion_without_manual_json_edits() -> None:
    first = convert_coarse_benchmark(
        benchmark_manifest_path=MANIFEST,
        benchmark_root=BENCH,
        map_path=MAP,
    )
    second = convert_coarse_benchmark(
        benchmark_manifest_path=MANIFEST,
        benchmark_root=BENCH,
        map_path=MAP,
    )
    # submission_id embeds created_at indirectly via cases only — compare case payloads.
    assert [c.model_dump(mode="json") for c in first.cases] == [
        c.model_dump(mode="json") for c in second.cases
    ]
    assert first.system.system_id == "coarse"
    assert first.system.code_commit
    assert len(first.cases) >= 10
    for case in first.cases:
        if case.abstained or case.failure:
            continue
        for concern in case.concerns:
            assert concern.concern_type == "adapter.coarse.unclassified"
            assert "provisional" in concern.evidence_summary.lower() or "unverified" in (
                concern.evidence_summary.lower()
            )


def test_every_detailed_comment_recoverable() -> None:
    submission = convert_coarse_benchmark(
        benchmark_manifest_path=MANIFEST,
        benchmark_root=BENCH,
        map_path=MAP,
    )
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    by_case = {(c.case_id, c.case_version): c for c in submission.cases}
    for entry in mapping["cases"]:
        review_path = (MAP.parent / entry["review_path"]).resolve()
        review = CoarseReview.model_validate_json(review_path.read_text(encoding="utf-8"))
        converted = by_case[(entry["case_id"], entry["case_version"])]
        assert len(converted.concerns) == len(review.detailed_comments)
        titles = {c.title for c in converted.concerns}
        for comment in review.detailed_comments:
            assert comment.title in titles
            assert any(
                a.source_text == comment.quote
                for c in converted.concerns
                for a in c.anchors
            )


def test_unresolved_quotes_remain_unresolved() -> None:
    review_path = FIXTURES / "reviews" / "stats-03.json"
    review = CoarseReview.model_validate_json(review_path.read_text(encoding="utf-8"))
    anchors, claims, concerns = convert_coarse_review(
        review.model_dump(mode="json"),
        manuscript_version_id="ocver_synth_stats_03_v1",
        run_id="ocrun_synth_stats_03",
        extracted_text="completely unrelated synthetic body text",
    )
    assert anchors
    assert all(a.resolution_status.value == "unresolved" for a in anchors)
    assert all(c.approval_status == "candidate" for c in claims)
    assert concerns


def test_conversion_loss_report_public_artifacts() -> None:
    extracted = json.loads((FIXTURES / "extracted_texts.json").read_text(encoding="utf-8"))
    report = build_conversion_loss_report(
        benchmark_manifest_path=MANIFEST,
        benchmark_root=BENCH,
        map_path=MAP,
        extracted_texts=extracted,
    )
    assert report.performance_claims_authorized is False
    assert report.upstream_contract_version == COARSE_UPSTREAM_CONTRACT_VERSION
    assert len(report.cases) >= 10
    assert report.aggregate_quote_stats.total >= 10
    assert report.aggregate_quote_stats.unresolved >= 1
    # Exact and normalized tracked separately.
    assert report.aggregate_quote_stats.exact_rate is not None
    assert report.aggregate_quote_stats.normalized_rate is not None
    paths = write_report_artifacts(report, DOCS)
    assert paths["markdown"].is_file()
    assert paths["json"].is_file()
    md = paths["markdown"].read_text(encoding="utf-8")
    assert "Performance claims authorized: **False**" in md
    assert "Exact" in md and "Normalized" in md
