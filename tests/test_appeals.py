from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from opencritique_registry.api import create_app
from opencritique_registry.auth import issue_token
from opencritique_registry.config import RegistrySettings
from opencritique_registry.db import make_session_factory
from opencritique_registry.db_models import DeterminationORM, PrincipalORM


def test_append_only_appeals_and_corrections_api(tmp_path: Path) -> None:
    settings = RegistrySettings(
        database_url=f"sqlite:///{(tmp_path / 'appeals.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
    )
    app = create_app(settings, initialize=True)
    factory = make_session_factory(app.state.engine)
    with factory.begin() as session:
        session.add(
            PrincipalORM(
                actor_id="case-manager",
                role="case_manager",
                display_name="Case Manager",
                active=True,
            )
        )
        session.add(
            DeterminationORM(
                determination_id="ocdet_test_1",
                case_id="occase_sample_rc_01",
                case_version="1.0.0",
                concern_id="occon_sample_rc_01_k1",
                policy_version="adjudication-v0.2",
                status="under_review",
                severity="major",
                requires_tie_break=False,
                rationale="Seed determination for appeal testing.",
                submission_ids=[],
            )
        )
        session.flush()
        token = issue_token(session, actor_id="case-manager").token

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/v1/appeals",
        headers=headers,
        json={
            "concern_id": "occon_sample_rc_01_k1",
            "determination_id": "ocdet_test_1",
            "record_type": "appeal",
            "requested_by": "sample-author",
            "rationale": "Please review whether the variance caveat is overstated.",
            "payload": {"channel": "studio"},
        },
    )
    assert created.status_code == 201, created.text
    appeal = created.json()
    assert appeal["record_type"] == "appeal"

    correction = client.post(
        "/v1/appeals",
        headers=headers,
        json={
            "concern_id": "occon_sample_rc_01_k1",
            "determination_id": "ocdet_test_1",
            "record_type": "correction",
            "requested_by": "case-manager",
            "rationale": "Append a metadata correction without mutating the original record.",
            "predecessor_record_id": appeal["record_id"],
            "payload": {"field": "rationale"},
        },
    )
    assert correction.status_code == 201, correction.text
    listing = client.get("/v1/concerns/occon_sample_rc_01_k1/appeals", headers=headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()
    assert [item["record_type"] for item in items] == ["appeal", "correction"]
    assert items[1]["predecessor_record_id"] == items[0]["record_id"]
