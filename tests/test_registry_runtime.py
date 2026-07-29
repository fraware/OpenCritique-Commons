from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from opencritique_registry.api import create_app
from opencritique_registry.auth import issue_token
from opencritique_registry.config import RegistrySettings
from opencritique_registry.db import make_session_factory
from opencritique_registry.db_models import PrincipalORM


def test_settings_reject_invalid_database_url(tmp_path: Path) -> None:
    settings = RegistrySettings(
        database_url="mysql://example.invalid/db",
        artifact_root=tmp_path / "artifacts",
    )
    try:
        settings.validated()
    except ValueError as exc:
        assert "sqlite or postgresql+psycopg" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid database URL to fail")


def test_settings_reject_file_artifact_root(tmp_path: Path) -> None:
    root_file = tmp_path / "artifacts.txt"
    root_file.write_text("not-a-directory", encoding="utf-8")
    settings = RegistrySettings(
        database_url=f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}",
        artifact_root=root_file,
    )
    try:
        settings.validated()
    except ValueError as exc:
        assert "directory path" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid artifact root to fail")


def test_byok_requires_provider_and_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENCRITIQUE_BYOK_API_KEY", raising=False)
    settings = RegistrySettings(
        database_url=f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        execution_mode="byok",
        byok_provider_id="provider-x",
    )
    try:
        settings.validated()
    except ValueError as exc:
        assert "OPENCRITIQUE_BYOK_API_KEY" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing BYOK API key to fail")


def test_readyz_reports_database_and_artifact_status(tmp_path: Path) -> None:
    settings = RegistrySettings(
        database_url=f"sqlite:///{(tmp_path / 'ready.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
    )
    with TestClient(create_app(settings, initialize=True)) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert str(tmp_path / "artifacts") in payload["checks"]["artifact_root"]


def test_byok_secrets_are_not_persisted_in_registry_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCRITIQUE_BYOK_API_KEY", "sk-runtime-secret")
    settings = RegistrySettings(
        database_url=f"sqlite:///{(tmp_path / 'byok.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        execution_mode="byok",
        byok_provider_id="openai-compatible",
    )
    app = create_app(settings, initialize=True)
    factory = make_session_factory(app.state.engine)
    with factory.begin() as session:
        session.add(
            PrincipalORM(
                actor_id="contributor-1",
                role="contributor",
                display_name="Contributor",
                active=True,
            )
        )
        session.flush()
        token = issue_token(session, actor_id="contributor-1").token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    upload = client.post(
        "/v1/artifacts?media_type=text/markdown&rights_classification=restricted",
        headers=headers,
        content=b"# Sample\n\nOwned BYOK intake sample.\n",
    )
    assert upload.status_code == 201, upload.text
    sha256 = upload.json()["sha256"]
    create = client.post(
        "/v1/intakes",
        headers=headers,
        json={
            "title": "BYOK sample intake",
            "source_artifact_sha256": sha256,
            "domain_profile": "economics_statistics",
            "language": "en",
            "rights_classification": "restricted",
            "requested_uses": ["operational_processing"],
            "rights_attestation": {
                "authority_type": "self_authored",
                "authority_statement": (
                    "Maintainer-authored BYOK intake fixture for "
                    "non-persistent secret testing."
                ),
                "public_source_url": None,
                "coauthor_consent_status": "not_applicable",
                "attests_accuracy": True,
                "attests_authority": True,
            },
            "contains_sensitive_data": False,
            "contains_personal_data": False,
            "redistribution_allowed": False,
            "notes": "No model credentials are stored in the intake.",
        },
    )
    assert create.status_code == 201, create.text
    with factory() as session:
        rows = list(
            session.execute(
                text("SELECT rights_attestation, notes FROM case_intakes")
            ).all()
        )
        audit_rows = list(session.execute(text("SELECT event_data FROM audit_events")).all())
    serialized = "\n".join(
        str(value)
        for row in rows + audit_rows
        for value in row
        if value is not None
    )
    assert "sk-runtime-secret" not in serialized
    provider_id = settings.byok_provider_id
    assert provider_id is not None
    assert provider_id not in os.getenv("OPENCRITIQUE_BYOK_API_KEY", "")
