"""bootstrap-sample-workspace CLI seeds principals, REF cases, and claimable tasks."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from opencritique_registry.api import create_app
from opencritique_registry.cli import app
from opencritique_registry.config import RegistrySettings

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "cases" / "reference"


def test_bootstrap_sample_workspace_seeds_claimable_tasks(tmp_path: Path) -> None:
    db = tmp_path / "bootstrap.db"
    artifacts = tmp_path / "artifacts"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "bootstrap-sample-workspace",
            "--cases-path",
            str(REF),
            "--project-root",
            str(ROOT),
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--artifact-root",
            str(artifacts),
            "--studio-host",
            "127.0.0.1",
            "--studio-port",
            "8000",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Sample workspace ready" in result.stdout
    assert "Studio URL: http://127.0.0.1:8000/studio" in result.stdout
    assert "Claim adjudication" in result.stdout
    assert "Non-claims:" in result.stdout

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    admin_idx = lines.index("Administrator token (shown once):")
    adjudicator_idx = lines.index("Adjudicator token (shown once):")
    admin_token = lines[admin_idx + 1]
    adjudicator_token = lines[adjudicator_idx + 1]
    assert admin_token and admin_token != adjudicator_token

    settings = RegistrySettings(
        database_url=f"sqlite:///{db.as_posix()}",
        artifact_root=artifacts,
    )
    client = TestClient(create_app(settings=settings, initialize=False))
    claimed = client.post(
        "/v1/tasks/claim",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
        json={},
    )
    assert claimed.status_code == 200, claimed.text
    task_id = claimed.json()["task_id"]
    payload = client.get(
        f"/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
    )
    assert payload.status_code == 200, payload.text
    assert payload.json()["case_id"].startswith("occase_sample_rc_")

    # Idempotent re-run should still succeed and re-issue tokens.
    again = runner.invoke(
        app,
        [
            "bootstrap-sample-workspace",
            "--cases-path",
            str(REF),
            "--project-root",
            str(ROOT),
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--artifact-root",
            str(artifacts),
        ],
    )
    assert again.exit_code == 0, again.stdout + again.stderr
    assert "Sample workspace ready" in again.stdout
