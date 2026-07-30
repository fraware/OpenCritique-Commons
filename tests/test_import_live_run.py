"""import-live-run: private live Coarse/OpenReviewer export → registry + Studio tasks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from opencritique_adapters.production_errors import ProductionPackageUnauthorizedError
from opencritique_registry.api import create_app
from opencritique_registry.cli import app
from opencritique_registry.config import RegistrySettings
from opencritique_registry.live_import import (
    build_live_case_bundle,
    import_live_run,
    redact_secrets,
)
from opencritique_runners.coarse import run_coarse_review, write_coarse_export
from opencritique_runners.pipeline import mock_review_from_fixture

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "coarse" / "reviews" / "econ-01.json"
OR_FIXTURE = ROOT / "fixtures" / "openreviewer" / "reviews" / "orv-01.json"
MANUSCRIPT = ROOT / "corpus" / "samples" / "sample-econ-01" / "manuscript.md"
OR_MANUSCRIPT = ROOT / "corpus" / "samples" / "sample-ml-01" / "manuscript.md"


@pytest.fixture(autouse=True)
def _byok_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCRITIQUE_BYOK_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("OPENCRITIQUE_BYOK_PROVIDER_ID", "openai")


def _write_mocked_coarse_export(tmp_path: Path) -> Path:
    review, _prov, markdown = run_coarse_review(
        manuscript=MANUSCRIPT,
        review_paper=mock_review_from_fixture(FIXTURE),
        load_env=False,
    )
    out = tmp_path / "coarse-review.json"
    write_coarse_export(
        review,
        out,
        markdown=markdown,
        markdown_output=tmp_path / "coarse-review.md",
    )
    return out


def test_redact_secrets_strips_key_material() -> None:
    text = "auth failed for sk-abcdefghijklmnopqrstuvwxyz012345 and Bearer tokensecretvalue99"
    redacted = redact_secrets(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in redacted
    assert "[REDACTED]" in redacted


def test_build_live_case_bundle_from_coarse(tmp_path: Path) -> None:
    export = _write_mocked_coarse_export(tmp_path)
    bundle, kind, data = build_live_case_bundle(
        export_path=export,
        manuscript_path=MANUSCRIPT,
    )
    assert kind == "coarse"
    assert data
    assert bundle.known_ambiguities
    assert any("evidence_class=private_live" in note for note in bundle.known_ambiguities)
    assert bundle.concerns
    assert bundle.case_id.startswith("occase_live_")


def test_import_live_run_seeds_claimable_tasks(tmp_path: Path) -> None:
    export = _write_mocked_coarse_export(tmp_path)
    db = tmp_path / "live.db"
    artifacts = tmp_path / "artifacts"
    result = import_live_run(
        from_path=export,
        manuscript=MANUSCRIPT,
        database_url=f"sqlite:///{db.as_posix()}",
        artifact_root=artifacts,
    )
    assert result.claims_authorized is False
    assert result.evidence_class == "private_live"
    assert result.seeded_tasks >= 2
    assert result.case_id.startswith("occase_live_")

    settings = RegistrySettings(
        database_url=f"sqlite:///{db.as_posix()}",
        artifact_root=artifacts,
    )
    client = TestClient(create_app(settings=settings, initialize=False))
    claimable = client.get(
        "/v1/tasks/claimable",
        headers={"Authorization": f"Bearer {result.adjudicator_token}"},
    )
    assert claimable.status_code == 200, claimable.text
    rows = claimable.json()
    assert len(rows) >= 1
    assert rows[0]["case_id"] == result.case_id
    assert rows[0]["concern_title"]
    assert rows[0].get("evidence_class") == "private_live"

    claimed = client.post(
        "/v1/tasks/claim",
        headers={"Authorization": f"Bearer {result.adjudicator_token}"},
        json={},
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["case_id"] == result.case_id


def test_import_live_run_cli(tmp_path: Path) -> None:
    export = _write_mocked_coarse_export(tmp_path)
    db = tmp_path / "cli.db"
    artifacts = tmp_path / "artifacts"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "import-live-run",
            "--from",
            str(export),
            "--manuscript",
            str(MANUSCRIPT),
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--artifact-root",
            str(artifacts),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "evidence_class=private_live" in result.stdout
    assert "Studio URL:" in result.stdout
    assert "NOT AUTHORIZED" in result.stdout
    assert "fixtures/*/production" in result.stdout


def test_import_openreviewer_export_via_live_run(tmp_path: Path) -> None:
    if not OR_MANUSCRIPT.is_file():
        pytest.skip("sample-ml-01 manuscript missing")
    # Normalize fixture into a private live-shaped export under tmp (not production).
    payload = json.loads(OR_FIXTURE.read_text(encoding="utf-8"))
    payload.pop("opencritique_fixture", None)
    payload["performance_claims_authorized"] = False
    payload["opencritique_provenance"] = {
        "upstream": "maxidl/openreviewer",
        "upstream_repository": "https://github.com/maxidl/openreviewer",
        "execution_mode": "import",
        "evidence_class": "private_live",
        "performance_claims_authorized": False,
        "imported_at": "2026-07-29T00:00:00Z",
        "notes": ["test"],
    }
    export = tmp_path / "or-export.json"
    export.write_text(json.dumps(payload), encoding="utf-8")
    db = tmp_path / "or.db"
    artifacts = tmp_path / "artifacts"
    result = import_live_run(
        from_path=export,
        manuscript=OR_MANUSCRIPT,
        database_url=f"sqlite:///{db.as_posix()}",
        artifact_root=artifacts,
    )
    assert result.export_kind == "openreviewer"
    assert result.evidence_class == "private_live"
    assert result.seeded_tasks >= 2


def test_refuse_import_targeting_production_path(tmp_path: Path) -> None:
    dest = ROOT / "fixtures" / "coarse" / "production" / "reviews" / "must-not-import.json"
    with pytest.raises(ProductionPackageUnauthorizedError):
        build_live_case_bundle(export_path=dest, manuscript_path=MANUSCRIPT)
