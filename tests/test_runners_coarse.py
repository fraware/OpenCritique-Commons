"""Coarse live runner — mocked upstream only (no paid API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from opencritique_adapters.production_errors import ProductionPackageUnauthorizedError
from opencritique_runners.coarse import run_coarse_review, write_coarse_export
from opencritique_runners.mapping import map_coarse_review
from opencritique_runners.pipeline import mock_review_from_fixture, run_coarse_pipeline
from opencritique_runners.provenance import LiveProvenance
from opencritique_schema.cli import app as root_app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "coarse" / "reviews" / "econ-01.json"
MANUSCRIPT = ROOT / "corpus" / "samples" / "sample-econ-01" / "manuscript.md"


@pytest.fixture(autouse=True)
def _byok_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCRITIQUE_BYOK_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("OPENCRITIQUE_BYOK_PROVIDER_ID", "openai")


def test_map_coarse_review_stamps_provenance() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload.pop("opencritique_fixture", None)
    provenance = LiveProvenance(model_id="openai/gpt-4o", manuscript_path=str(MANUSCRIPT))
    mapped = map_coarse_review(payload, provenance=provenance)
    dumped = mapped.model_dump(mode="json")
    assert dumped["opencritique_provenance"]["performance_claims_authorized"] is False
    assert dumped["opencritique_provenance"]["evidence_class"] == "private_live"
    assert dumped["opencritique_provenance"]["execution_mode"] == "byok"
    assert dumped["detailed_comments"]


def test_refuse_write_to_production_fixtures(tmp_path: Path) -> None:
    review, _prov, _md = run_coarse_review(
        manuscript=MANUSCRIPT,
        review_paper=mock_review_from_fixture(FIXTURE),
        load_env=False,
    )
    dest = ROOT / "fixtures" / "coarse" / "production" / "reviews" / "must-not-write.json"
    with pytest.raises(ProductionPackageUnauthorizedError, match="fixtures"):
        write_coarse_export(review, dest)


def test_run_coarse_review_mocked(tmp_path: Path) -> None:
    review, provenance, markdown = run_coarse_review(
        manuscript=MANUSCRIPT,
        model="openai/gpt-4o",
        review_paper=mock_review_from_fixture(FIXTURE),
        load_env=False,
    )
    out = write_coarse_export(
        review,
        tmp_path / "review.json",
        markdown=markdown,
        markdown_output=tmp_path / "review.md",
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["performance_claims_authorized"] is False
    assert payload["opencritique_provenance"]["upstream"] == "Davidvandijcke/coarse"
    assert provenance.performance_claims_authorized is False
    assert (tmp_path / "review.md").is_file()


def test_pipeline_coarse_with_gold_mocked(tmp_path: Path) -> None:
    out_dir = tmp_path / "pipeline"
    result = run_coarse_pipeline(
        manuscript=MANUSCRIPT,
        out_dir=out_dir,
        review_paper=mock_review_from_fixture(FIXTURE),
        load_env=False,
    )
    assert result.claims_authorized is False
    assert result.handoff is None
    assert result.submission_path is not None and result.submission_path.is_file()
    assert result.evaluation_path is not None and result.evaluation_path.is_file()
    assert result.scorecard_json is not None and result.scorecard_json.is_file()
    evaluation = json.loads(result.evaluation_path.read_text(encoding="utf-8"))
    assert evaluation["performance_claim_authorized"] is False


def test_pipeline_handoff_without_gold(tmp_path: Path) -> None:
    orphan = tmp_path / "orphan.md"
    orphan.write_text("# Orphan note\n\nNo gold binding.\n", encoding="utf-8")
    result = run_coarse_pipeline(
        manuscript=orphan,
        out_dir=tmp_path / "out",
        review_paper=mock_review_from_fixture(FIXTURE),
        load_env=False,
    )
    assert result.handoff is not None
    assert "import-live-run" in result.handoff
    assert result.submission_path is None
    assert result.claims_authorized is False
    handoff_path = tmp_path / "out" / "handoff.json"
    payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert payload["evidence_class"] == "private_live"
    assert payload["performance_claims_authorized"] is False
    assert "import-live-run" in payload["next"]


def test_cli_coarse_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "runs" / "coarse" / "cli.json"
    monkeypatch.setattr(
        "opencritique_runners.cli.run_coarse_review",
        lambda **kwargs: run_coarse_review(
            manuscript=kwargs["manuscript"],
            model=kwargs.get("model", "openai/gpt-4o"),
            skip_cost_gate=kwargs.get("skip_cost_gate", True),
            review_paper=mock_review_from_fixture(FIXTURE),
            load_env=False,
        ),
    )
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "runners",
            "coarse",
            "--manuscript",
            str(MANUSCRIPT),
            "--output",
            str(out),
            "--model",
            "openai/gpt-4o",
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert "NOT AUTHORIZED" in result.output


def test_cli_fails_closed_without_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENCRITIQUE_BYOK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "opencritique_runners.cli.load_operator_env",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        "opencritique_runners.env.load_operator_env",
        lambda **_kwargs: False,
    )
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "runners",
            "coarse",
            "--manuscript",
            str(MANUSCRIPT),
            "--output",
            str(tmp_path / "out.json"),
        ],
    )
    assert result.exit_code != 0
    combined = f"{result.output}\n{result.exception}"
    assert "BYOK" in combined or "API_KEY" in combined
