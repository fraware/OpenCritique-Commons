"""OpenReviewer live runner — import mode (no GPU / no HF download)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from opencritique_adapters.production_errors import ProductionPackageUnauthorizedError
from opencritique_runners.hf_local import (
    OpenReviewerHFUnavailableError,
    run_openreviewer_hf_local,
)
from opencritique_runners.openreviewer import (
    OpenReviewerProvenance,
    import_openreviewer_export,
    write_openreviewer_live_export,
)
from opencritique_runners.paths import (
    assert_not_production_fixtures_path,
    assert_package_not_private_runs,
)
from opencritique_schema.cli import app as root_app

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ORV = ROOT / "fixtures" / "openreviewer" / "reviews" / "orv-01.json"


def test_import_openreviewer_shaped_fixture(tmp_path: Path) -> None:
    export = import_openreviewer_export(SAMPLE_ORV)
    assert export.opencritique_provenance.evidence_class == "private_live"
    assert export.opencritique_provenance.execution_mode == "import"
    assert export.opencritique_provenance.performance_claims_authorized is False
    assert export.markdown.strip()
    assert export.original_sha256 is not None
    out = write_openreviewer_live_export(export, tmp_path / "out.json")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["opencritique_provenance"]["performance_claims_authorized"] is False
    assert loaded["opencritique_provenance"]["evidence_class"] == "private_live"
    assert loaded["performance_claims_authorized"] is False


def test_import_space_ish_markdown_json(tmp_path: Path) -> None:
    payload = {
        "review": (
            "# Review\n\n## Summary\n\nA solid contribution on sample data.\n\n"
            "## Weaknesses\n\n"
            "- Evaluation protocol may leak statistics across folds in training.\n\n"
            "## Rating\n\n5: marginally below the acceptance threshold\n"
        )
    }
    source = tmp_path / "space-export.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    export = import_openreviewer_export(source, venue_template="ICLR2025")
    assert export.venue_template == "ICLR2025"
    assert export.recommendation_score == 5.0
    assert export.findings
    assert export.opencritique_provenance.performance_claims_authorized is False


def test_import_plain_markdown_file(tmp_path: Path) -> None:
    md = tmp_path / "review.md"
    md.write_text(
        "# Review\n\n## Weaknesses\n\n- Missing ablation on the core hyperparameter choice.\n",
        encoding="utf-8",
    )
    export = import_openreviewer_export(md, title="Imported Space paste")
    assert export.title == "Imported Space paste"
    assert any("ablation" in f.body.lower() for f in export.findings)


def test_provenance_rejects_claims_unlock() -> None:
    with pytest.raises(ValueError, match="performance_claims_authorized"):
        OpenReviewerProvenance(
            execution_mode="import",
            imported_at="2026-07-29T00:00:00Z",
            performance_claims_authorized=True,
        )


def test_refuse_write_to_production_fixtures() -> None:
    export = import_openreviewer_export(SAMPLE_ORV)
    dest = (
        ROOT / "fixtures" / "openreviewer" / "production" / "reviews" / "must-not-write.json"
    )
    with pytest.raises(ProductionPackageUnauthorizedError, match="fixtures"):
        write_openreviewer_live_export(export, dest)
    with pytest.raises(ProductionPackageUnauthorizedError, match="fixtures"):
        assert_not_production_fixtures_path(dest)


def test_refuse_stage_from_runs(tmp_path: Path) -> None:
    runs_pkg = tmp_path / "runs" / "openreviewer" / "package"
    runs_pkg.mkdir(parents=True)
    with pytest.raises(ProductionPackageUnauthorizedError, match="runs"):
        assert_package_not_private_runs(runs_pkg)


def test_cli_from_export(tmp_path: Path) -> None:
    out = tmp_path / "runs" / "openreviewer" / "cli-out.json"
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "runners",
            "openreviewer",
            "--from-export",
            str(SAMPLE_ORV),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert "NOT AUTHORIZED" in result.output
    assert "claims_authorized=False" in result.output
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["opencritique_provenance"]["performance_claims_authorized"] is False


def test_cli_refuses_production_output() -> None:
    dest = ROOT / "fixtures" / "coarse" / "production" / "reviews" / "nope.json"
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "runners",
            "openreviewer",
            "--from-export",
            str(SAMPLE_ORV),
            "--output",
            str(dest),
        ],
    )
    assert result.exit_code == 2
    assert "fixtures" in result.output.lower() or "refusing" in result.output.lower()


def test_hf_local_unavailable_without_extra(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper.md"
    manuscript.write_text("x" * 250, encoding="utf-8")
    with patch(
        "opencritique_runners.hf_local._require_hf_stack",
        side_effect=OpenReviewerHFUnavailableError("missing extra"),
    ):
        with pytest.raises(OpenReviewerHFUnavailableError, match="missing extra"):
            run_openreviewer_hf_local(manuscript)


def test_stage_intake_refuses_runs_tree(tmp_path: Path) -> None:
    from opencritique_adapters.production_intake import stage_validated_package

    pkg = tmp_path / "runs" / "coarse" / "pkg"
    pkg.mkdir(parents=True)
    with pytest.raises(ProductionPackageUnauthorizedError, match="runs"):
        stage_validated_package(
            pkg,
            tmp_path / "dest",
            expected_adapter="coarse",
            dry_run=True,
        )
