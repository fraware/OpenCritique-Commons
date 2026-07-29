from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from opencritique_schema.models import CaseBundle

from .artifacts import LocalArtifactStore
from .auth import issue_token
from .config import RegistrySettings
from .conformance import audit_registry
from .db import make_engine, make_session_factory
from .db_models import PrincipalORM
from .migrate import upgrade_head
from .schemas import (
    CaseRegistration,
    DataUse,
    GrantBasis,
    PrincipalRole,
    RightsGrantInput,
)
from .service import RegistryService

app = typer.Typer(no_args_is_help=True)


ExecutionModeOption = Annotated[
    str | None,
    typer.Option(help="Execution mode override: local, byok, or compose."),
]


def settings(
    database_url: str | None,
    artifact_root: Path | None,
    execution_mode: str | None,
) -> RegistrySettings:
    return RegistrySettings.from_env().with_overrides(
        database_url=database_url,
        artifact_root=artifact_root,
        execution_mode=execution_mode,  # type: ignore[arg-type]
    )


@app.command("init")
def init_registry(
    database_url: str | None = typer.Option(None),
    artifact_root: Path | None = typer.Option(None),
    execution_mode: ExecutionModeOption = None,
) -> None:
    cfg = settings(database_url, artifact_root, execution_mode)
    upgrade_head(cfg.database_url)
    LocalArtifactStore(cfg.artifact_root, cfg.max_artifact_bytes).ensure_root()
    typer.echo(f"Initialized registry at {cfg.database_url}")
    typer.echo(f"Artifact root: {cfg.artifact_root.resolve()}")
    typer.echo(f"Execution mode: {cfg.execution_mode}")


@app.command("bootstrap-admin")
def bootstrap_admin(
    actor_id: str = typer.Option("opencritique-admin"),
    display_name: str = typer.Option("OpenCritique Administrator"),
    database_url: str | None = typer.Option(None),
    artifact_root: Path | None = typer.Option(None),
    execution_mode: ExecutionModeOption = None,
) -> None:
    cfg = settings(database_url, artifact_root, execution_mode)
    upgrade_head(cfg.database_url)
    engine = make_engine(cfg.database_url)
    factory = make_session_factory(engine)
    with factory.begin() as session:
        row = session.get(PrincipalORM, actor_id)
        if row is None:
            row = PrincipalORM(
                actor_id=actor_id,
                role=PrincipalRole.ADMIN.value,
                display_name=display_name,
                active=True,
            )
            session.add(row)
            session.flush()
        elif row.role != PrincipalRole.ADMIN.value:
            raise typer.BadParameter("existing principal is not an administrator")
        issued = issue_token(session, actor_id=actor_id)
    typer.echo("Administrator token issued. It will not be displayed again:")
    typer.echo(issued.token)


@app.command("import-reference")
def import_reference(
    cases_path: Path = typer.Argument(..., exists=True, file_okay=False),
    project_root: Path = typer.Option(Path("."), exists=True, file_okay=False),
    actor_id: str = typer.Option("opencritique-admin"),
    database_url: str | None = typer.Option(None),
    artifact_root: Path | None = typer.Option(None),
    execution_mode: ExecutionModeOption = None,
) -> None:
    cfg = settings(database_url, artifact_root, execution_mode)
    upgrade_head(cfg.database_url)
    engine = make_engine(cfg.database_url)
    factory = make_session_factory(engine)
    store = LocalArtifactStore(cfg.artifact_root, cfg.max_artifact_bytes)
    files = sorted(cases_path.glob("REF-*/case.json"))
    if not files:
        raise typer.BadParameter("no REF-*/case.json files found")
    with factory.begin() as session:
        if session.get(PrincipalORM, actor_id) is None:
            raise typer.BadParameter(f"principal {actor_id!r} does not exist")
        registry = RegistryService(session, store)
        for path in files:
            bundle = CaseBundle.model_validate_json(path.read_text(encoding="utf-8"))
            for artifact in _artifact_references(bundle):
                source = (project_root / artifact.uri).resolve()
                if not source.is_file():
                    raise typer.BadParameter(f"missing fixture artifact: {source}")
                data = source.read_bytes()
                if len(data) != artifact.byte_size:
                    raise typer.BadParameter(f"byte-size mismatch for {source}")
                view = registry.put_artifact(
                    data=data,
                    media_type=artifact.media_type,
                    rights_classification=bundle.manuscript.rights_classification,
                    actor_id=actor_id,
                )
                if view.sha256 != artifact.sha256:
                    raise typer.BadParameter(f"hash mismatch for {source}")
            grants = [
                RightsGrantInput(
                    use=use,
                    basis=GrantBasis.PROJECT_CREATED,
                    authority="OpenCritique maintainer-owned sample-corpus authorship",
                    scope="Sample conformance fixture only; no reviewer-quality claims.",
                )
                for use in (
                    DataUse.OPERATIONAL_PROCESSING,
                    DataUse.RETENTION,
                    DataUse.EXPERT_ADJUDICATION,
                    DataUse.BENCHMARK_EVALUATION,
                    DataUse.PUBLIC_RELEASE,
                )
            ]
            registry.register_case(
                CaseRegistration(bundle=bundle, grants=grants), actor_id=actor_id
            )
            typer.echo(f"Imported {bundle.case_id}@{bundle.case_version}")


@app.command("conformance")
def registry_conformance(
    database_url: str | None = typer.Option(None),
    artifact_root: Path | None = typer.Option(None),
    execution_mode: ExecutionModeOption = None,
) -> None:
    cfg = settings(database_url, artifact_root, execution_mode)
    engine = make_engine(cfg.database_url)
    factory = make_session_factory(engine)
    store = LocalArtifactStore(cfg.artifact_root, cfg.max_artifact_bytes)
    with factory() as session:
        report = audit_registry(session, store)
    typer.echo(f"Artifacts: {report.checked_artifacts}")
    typer.echo(f"Cases: {report.checked_cases}")
    typer.echo(f"Tasks: {report.checked_tasks}")
    typer.echo(f"Submissions: {report.checked_submissions}")
    typer.echo(f"Determinations: {report.checked_determinations}")
    typer.echo(f"Grants: {report.checked_grants}")
    typer.echo(f"Expert profiles: {report.checked_expert_profiles}")
    typer.echo(f"Calibration attempts: {report.checked_calibration_attempts}")
    typer.echo(f"Calibration tasks: {report.checked_calibration_tasks}")
    typer.echo(f"Intakes: {report.checked_intakes}")
    typer.echo(f"Claim tasks: {report.checked_claim_tasks}")
    typer.echo(f"Contribution credits: {report.checked_credits}")
    typer.echo(f"Compensation records: {report.checked_compensation}")
    for warning in report.warnings:
        typer.echo(f"WARN {warning}")
    for failure in report.failures:
        typer.echo(f"FAIL {failure}", err=True)
    if report.failures:
        raise typer.Exit(code=1)
    typer.echo("PASS registry conformance")


@app.command("serve")
def serve(
    database_url: str | None = typer.Option(None),
    artifact_root: Path | None = typer.Option(None),
    execution_mode: ExecutionModeOption = None,
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
) -> None:
    import os

    cfg = settings(database_url, artifact_root, execution_mode)
    os.environ["OPENCRITIQUE_DATABASE_URL"] = cfg.database_url
    os.environ["OPENCRITIQUE_ARTIFACT_ROOT"] = str(cfg.artifact_root)
    os.environ["OPENCRITIQUE_EXECUTION_MODE"] = cfg.execution_mode
    uvicorn.run("opencritique_registry.api:app", host=host, port=port, reload=False)


def _artifact_references(bundle: CaseBundle):
    seen: set[str] = set()
    refs = []
    for version in bundle.manuscript_versions:
        candidates = [
            version.source_artifact,
            version.rendered_artifact,
            version.extracted_artifact,
        ]
        for item in candidates:
            if item and item.sha256 not in seen:
                refs.append(item)
                seen.add(item.sha256)
    for anchor in bundle.anchors:
        item = anchor.rendered_reference.artifact if anchor.rendered_reference else None
        if item and item.sha256 not in seen:
            refs.append(item)
            seen.add(item.sha256)
    for evidence in bundle.evidence:
        item = evidence.artifact_reference
        if item and item.sha256 not in seen:
            refs.append(item)
            seen.add(item.sha256)
    return refs
