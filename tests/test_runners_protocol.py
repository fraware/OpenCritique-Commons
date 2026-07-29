"""Focused tests for the live runner plugin Protocol (no paid API calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opencritique_adapters.coarse import (
    CoarseDetailedComment,
    CoarseOverviewFeedback,
    CoarseReview,
)
from opencritique_adapters.production_errors import ProductionPackageUnauthorizedError
from opencritique_runners.coarse import CoarseRunnerPlugin, coarse_runner_plugin
from opencritique_runners.openreviewer import (
    OpenReviewerLiveExport,
    OpenReviewerProvenance,
    OpenReviewerRunnerPlugin,
    openreviewer_runner_plugin,
)
from opencritique_runners.pipeline import mock_review_from_fixture
from opencritique_runners.protocol import LiveRunnerPlugin, RunnerRunResult
from opencritique_runners.provenance import LiveProvenance

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "coarse" / "reviews" / "econ-01.json"
MANUSCRIPT = ROOT / "corpus" / "samples" / "sample-econ-01" / "manuscript.md"


@pytest.fixture(autouse=True)
def _byok_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCRITIQUE_BYOK_API_KEY", "sk-test-not-a-real-key")


def test_coarse_plugin_satisfies_protocol() -> None:
    plugin = coarse_runner_plugin()
    assert isinstance(plugin, LiveRunnerPlugin)
    assert plugin.name == "coarse"
    assert plugin.live_extra == "live-coarse"


def test_openreviewer_plugin_satisfies_protocol() -> None:
    plugin = openreviewer_runner_plugin()
    assert isinstance(plugin, LiveRunnerPlugin)
    assert plugin.name == "openreviewer"
    assert plugin.live_extra == "live-openreviewer"


def test_coarse_plugin_run_and_write_with_injected_upstream(tmp_path: Path) -> None:
    plugin = CoarseRunnerPlugin()
    result = plugin.run(
        MANUSCRIPT,
        review_paper=mock_review_from_fixture(FIXTURE),
        load_env=False,
        model="openai/gpt-4o",
    )
    assert isinstance(result, RunnerRunResult)
    assert result.provenance.performance_claims_authorized is False
    assert isinstance(result.provenance, LiveProvenance)

    out = tmp_path / "runs" / "coarse" / "review.json"
    written = plugin.write_export(result, out, markdown_output=out.with_suffix(".md"))
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["performance_claims_authorized"] is False
    assert out.with_suffix(".md").is_file()


def test_coarse_plugin_refuses_production_path(tmp_path: Path) -> None:
    plugin = CoarseRunnerPlugin()
    review = CoarseReview(
        title="x",
        domain="d",
        taxonomy="t",
        date="2026-01-01",
        overall_feedback=CoarseOverviewFeedback(),
        detailed_comments=[
            CoarseDetailedComment(
                number=1,
                title="t",
                quote="quote text here",
                feedback="feedback text here",
            )
        ],
    )
    provenance = LiveProvenance(model_id="test/model")
    result = RunnerRunResult(review=review, provenance=provenance, markdown="")
    bad = tmp_path / "fixtures" / "coarse" / "production" / "reviews" / "x.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ProductionPackageUnauthorizedError):
        plugin.write_export(result, bad)


def test_openreviewer_plugin_write_export(tmp_path: Path) -> None:
    plugin = OpenReviewerRunnerPlugin()
    provenance = OpenReviewerProvenance(
        model_id="maxidl/Llama-OpenReviewer-8B",
        imported_at="2026-01-01T00:00:00Z",
    )
    export = OpenReviewerLiveExport(
        title="Imported",
        venue_template="ICLR2025",
        markdown="# Review\n\n## Weaknesses\n\n- Needs clearer claims.\n",
        findings=[],
        model_identifiers=["maxidl/Llama-OpenReviewer-8B"],
        opencritique_provenance=provenance,
    )
    result = RunnerRunResult(
        review=export,
        provenance=provenance,
        markdown=export.markdown,
    )
    out = tmp_path / "runs" / "openreviewer" / "export.json"
    written = plugin.write_export(result, out)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["performance_claims_authorized"] is False
    assert payload["opencritique_provenance"]["evidence_class"] == "private_live"
