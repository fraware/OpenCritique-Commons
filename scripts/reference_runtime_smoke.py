from __future__ import annotations

import argparse
from pathlib import Path

from fastapi.testclient import TestClient

from opencritique_ingestion import ingest_path
from opencritique_registry.api import create_app
from opencritique_registry.artifacts import LocalArtifactStore
from opencritique_registry.auth import issue_token
from opencritique_registry.cli import _artifact_references
from opencritique_registry.config import RegistrySettings
from opencritique_registry.db import make_engine, make_session_factory
from opencritique_registry.db_models import PrincipalORM
from opencritique_registry.migrate import upgrade_head
from opencritique_registry.schemas import (
    CaseRegistration,
    DataUse,
    GrantBasis,
    PrincipalRole,
    RightsGrantInput,
)
from opencritique_registry.service import RegistryService
from opencritique_schema.models import CaseBundle
from opencritique_verification import check_citation_presence, check_table_consistency


def _load_reference_case(root: Path) -> CaseBundle:
    path = root / "cases" / "reference" / "REF-01" / "case.json"
    return CaseBundle.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()

    settings = RegistrySettings.from_env().with_overrides(
        database_url=args.database_url,
        artifact_root=args.artifact_root,
    )
    project_root = args.project_root.resolve()
    upgrade_head(settings.database_url)
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    store = LocalArtifactStore(settings.artifact_root, settings.max_artifact_bytes)
    bundle = _load_reference_case(project_root)

    with factory.begin() as session:
        if session.get(PrincipalORM, "opencritique-admin") is None:
            session.add(
                PrincipalORM(
                    actor_id="opencritique-admin",
                    role=PrincipalRole.ADMIN.value,
                    display_name="OpenCritique Administrator",
                    active=True,
                )
            )
            session.flush()
        admin_token = issue_token(session, actor_id="opencritique-admin").token
        if session.get(PrincipalORM, "adjudicator-smoke") is None:
            session.add(
                PrincipalORM(
                    actor_id="adjudicator-smoke",
                    role=PrincipalRole.ADJUDICATOR.value,
                    display_name="Smoke Adjudicator",
                    active=True,
                )
            )
            session.flush()
        adjudicator_token = issue_token(session, actor_id="adjudicator-smoke").token
        registry = RegistryService(session, store)
        for artifact in _artifact_references(bundle):
            source = (project_root / artifact.uri).resolve()
            view = registry.put_artifact(
                data=source.read_bytes(),
                media_type=artifact.media_type,
                rights_classification=bundle.manuscript.rights_classification,
                actor_id="opencritique-admin",
            )
            assert view.sha256 == artifact.sha256
        registration = CaseRegistration(
            bundle=bundle,
            grants=[
                RightsGrantInput(
                    use=use,
                    basis=GrantBasis.PROJECT_CREATED,
                    authority="Reference runtime smoke fixture",
                    scope="Engineering runtime smoke only.",
                )
                for use in (
                    DataUse.OPERATIONAL_PROCESSING,
                    DataUse.RETENTION,
                    DataUse.EXPERT_ADJUDICATION,
                    DataUse.BENCHMARK_EVALUATION,
                    DataUse.PUBLIC_RELEASE,
                )
            ],
        )
        registry.register_case(registration, "opencritique-admin")

    app = create_app(
        settings=settings,
        initialize=False,
    )
    client = TestClient(app)
    ready = client.get("/readyz")
    assert ready.status_code == 200, ready.text
    seed = client.post(
        "/v1/cases/occase_sample_rc_01/versions/1.0.0/tasks/seed",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"concern_ids": ["occon_sample_rc_01_k1"]},
    )
    assert seed.status_code == 201, seed.text
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
    submitted = client.post(
        f"/v1/tasks/{task_id}/submit",
        headers={"Authorization": f"Bearer {adjudicator_token}"},
        json={
            "validity": "qualified",
            "severity": "major",
            "confidence": 0.72,
            "reasoning": (
                "Smoke test adjudication over the owned sample reference case."
            ),
            "evidence_ids": ["ocevd_sample_rc_01_e1"],
            "counterposition_assessment": (
                "The sample defense does not close the reporting gap."
            ),
            "requested_followup": [],
            "anchors_reviewed": True,
            "conflict_declaration": {"status": "none", "description": ""},
        },
    )
    assert submitted.status_code == 201, submitted.text

    graph = ingest_path(
        project_root
        / "corpus"
        / "samples"
        / "sample-figtable-01"
        / "manuscript.md",
        manuscript_version_id="runtime-smoke-figtable-v1",
    )
    assert check_table_consistency(
        graph=graph,
        claimed_values={"arm_a": 1.20, "arm_b": 0.85},
    ).status == "pass"
    assert check_citation_presence(
        graph=graph,
        required_markers=["Smith, A. et al. (2020)"],
    ).status == "pass"
    print("reference runtime smoke OK")


if __name__ == "__main__":
    main()
