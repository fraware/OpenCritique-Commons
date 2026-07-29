from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from opencritique_registry.api import create_app
from opencritique_registry.auth import issue_token
from opencritique_registry.cli import app as cli_app
from opencritique_registry.config import RegistrySettings
from opencritique_registry.db import make_session_factory
from opencritique_registry.db_models import PrincipalORM

ROOT = Path(__file__).resolve().parents[1]


def test_studio_html_has_landmarks_and_labels() -> None:
    html = (ROOT / "src" / "opencritique_registry" / "studio_assets" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "<main id=\"main-content\">" in html
    assert 'aria-labelledby="auth-heading"' in html
    assert 'label for="token"' in html
    assert 'aria-live="polite"' in html
    assert "Matcher audit" in html
    assert "Skip to main workflow" in html
    assert "Load appeals" in html


def test_studio_and_matcher_audit_routes_load() -> None:
    client = TestClient(create_app(initialize=False))
    studio = client.get("/studio")
    assert studio.status_code == 200
    assert "Adjudication Studio" in studio.text
    assert "Content-Security-Policy" in studio.headers
    proto = client.get("/v1/matcher-audit/protocol")
    assert proto.status_code == 200
    assert proto.json()["protocol_id"]


def test_studio_sample_adjudication_workflow(tmp_path: Path) -> None:
    db = tmp_path / "studio.db"
    artifacts = tmp_path / "artifacts"
    runner = CliRunner()
    boot = runner.invoke(
        cli_app,
        [
            "bootstrap-admin",
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--artifact-root",
            str(artifacts),
            "--actor-id",
            "opencritique-admin",
        ],
    )
    assert boot.exit_code == 0, boot.stdout + boot.stderr
    admin_token = boot.stdout.strip().splitlines()[-1]
    imported = runner.invoke(
        cli_app,
        [
            "import-reference",
            str(ROOT / "cases" / "reference"),
            "--project-root",
            str(ROOT),
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--artifact-root",
            str(artifacts),
            "--actor-id",
            "opencritique-admin",
        ],
    )
    assert imported.exit_code == 0, imported.stdout + imported.stderr
    app = create_app(
        settings=RegistrySettings(
            database_url=f"sqlite:///{db.as_posix()}",
            artifact_root=artifacts,
        ),
        initialize=False,
    )
    factory = make_session_factory(app.state.engine)
    with factory.begin() as session:
        session.add(
            PrincipalORM(
                actor_id="adjudicator-1",
                role="adjudicator",
                display_name="Adjudicator",
                active=True,
            )
        )
        session.flush()
        adjudicator_token = issue_token(session, actor_id="adjudicator-1").token
    client = TestClient(app)
    seeded = client.post(
        "/v1/cases/occase_sample_rc_01/versions/1.0.0/tasks/seed",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"concern_ids": ["occon_sample_rc_01_k1"]},
    )
    assert seeded.status_code == 201, seeded.text
    claimed = client.post(
        "/v1/tasks/claim",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
        json={},
    )
    assert claimed.status_code == 200, claimed.text
    payload = client.get(
        f"/v1/tasks/{claimed.json()['task_id']}",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
    )
    assert payload.status_code == 200, payload.text
    assert payload.json()["concern_id"] == "occon_sample_rc_01_k1"
    submitted = client.post(
        f"/v1/tasks/{claimed.json()['task_id']}/submit",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
        json={
            "validity": "qualified",
            "severity": "major",
            "confidence": 0.71,
            "reasoning": (
                "The sample note omits cluster-robust alternatives "
                "and finite-sample caveats."
            ),
            "evidence_ids": ["ocevd_sample_rc_01_e1"],
            "counterposition_assessment": (
                "The stylized illustration defense does not remove "
                "the reporting gap."
            ),
            "requested_followup": [],
            "anchors_reviewed": True,
            "conflict_declaration": {"status": "none", "description": ""},
        },
    )
    assert submitted.status_code == 201, submitted.text
    mine = client.get(
        "/v1/my-tasks",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
    )
    assert mine.status_code == 200, mine.text
    assert mine.json()
