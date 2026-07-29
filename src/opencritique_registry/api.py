from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from opencritique_schema.models import CaseBundle, RightsClassification

from .artifacts import (
    ArtifactStoreConfigurationError,
    ArtifactStoreWriteError,
    LocalArtifactStore,
)
from .audit import record_event
from .auth import (
    PrincipalContext,
    current_principal,
    get_session,
    issue_token,
    require_roles,
    revoke_token,
)
from .config import RegistrySettings
from .db import make_engine, make_session_factory
from .db_models import ArtifactORM, AuditEventORM, CaseORM
from .expert_api import router as expert_router
from .matcher_audit_api import router as matcher_audit_router
from .migrate import upgrade_head
from .schemas import (
    AdjudicationSubmissionInput,
    AppealRecordInput,
    AppealRecordView,
    ArtifactView,
    AuditEventView,
    BlindedTaskPayload,
    CaseRegistration,
    CaseView,
    ClaimableTaskView,
    DeterminationView,
    PrincipalCreate,
    PrincipalRole,
    PrincipalView,
    RightsGrantInput,
    RightsGrantView,
    SubmissionView,
    TaskSeedRequest,
    TaskView,
    TokenCreate,
    TokenIssued,
    TokenRevoked,
)
from .service import RegistryService
from .studio import install_studio_routes
from .timeutils import as_utc


def create_app(settings: RegistrySettings | None = None, *, initialize: bool = False) -> FastAPI:
    settings = (settings or RegistrySettings.from_env()).validated()
    engine = make_engine(settings.database_url)
    if initialize:
        upgrade_head(settings.database_url)

    artifact_store = LocalArtifactStore(settings.artifact_root, settings.max_artifact_bytes)

    def readiness_report() -> tuple[dict[str, object], bool]:
        checks: dict[str, object] = {
            "execution_mode": settings.execution_mode,
            "performance_claims_authorized": settings.performance_claims_authorized,
        }
        ready = True
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["database"] = f"error: {exc}"
            ready = False
        try:
            artifact_store.ensure_root()
            checks["artifact_root"] = str(settings.artifact_root)
        except ArtifactStoreConfigurationError as exc:
            checks["artifact_root"] = f"error: {exc}"
            ready = False
        return {
            "status": "ok" if ready else "error",
            "version": "0.5.0-alpha",
            "checks": checks,
        }, ready

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        payload, ready = readiness_report()
        if not ready:
            raise RuntimeError(f"registry startup validation failed: {payload['checks']}")
        yield

    app = FastAPI(
        title="OpenCritique Registry and Adjudication API",
        version="0.5.0-alpha",
        lifespan=lifespan,
        description=(
            "Immutable case registry, granular data-use authorization, and blinded scientific "
            "concern adjudication, expert calibration, rights-cleared intake, "
            "and claim reconstruction."
        ),
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.artifact_store = artifact_store

    def service(session: Session = Depends(get_session)) -> RegistryService:
        return RegistryService(session, app.state.artifact_store)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.5.0-alpha"}

    @app.get("/readyz")
    def readyz(response: Response) -> dict[str, object]:
        payload, ready = readiness_report()
        if not ready:
            response.status_code = 503
        return payload

    @app.get("/v1/me", response_model=PrincipalView)
    def me(principal: PrincipalContext = Depends(current_principal)) -> PrincipalView:
        return PrincipalView(
            actor_id=principal.actor_id,
            role=principal.role,
            display_name=principal.display_name,
            active=True,
        )

    @app.post("/v1/principals", response_model=PrincipalView, status_code=201)
    def create_principal(
        data: PrincipalCreate,
        principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADMIN)),
        registry: RegistryService = Depends(service),
    ) -> PrincipalView:
        return registry.create_principal(data, principal.actor_id)

    @app.post("/v1/tokens", response_model=TokenIssued, status_code=201)
    def create_token(
        data: TokenCreate,
        principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADMIN)),
        session: Session = Depends(get_session),
    ) -> TokenIssued:
        issued = issue_token(session, actor_id=data.actor_id, expires_at=data.expires_at)
        record_event(
            session,
            actor_id=principal.actor_id,
            action="token.issued",
            target_type="token",
            target_id=issued.token_id,
            event_data={"principal": data.actor_id},
        )
        return issued

    @app.post("/v1/tokens/{token_id}/revoke", response_model=TokenRevoked)
    def revoke_api_token(
        token_id: str,
        principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADMIN)),
        session: Session = Depends(get_session),
    ) -> TokenRevoked:
        revoked_at = revoke_token(session, token_id)
        record_event(
            session,
            actor_id=principal.actor_id,
            action="token.revoked",
            target_type="token",
            target_id=token_id,
        )
        return TokenRevoked(token_id=token_id, revoked_at=as_utc(revoked_at))

    @app.post("/v1/artifacts", response_model=ArtifactView, status_code=201)
    async def upload_artifact(
        request: Request,
        media_type: str = Query(min_length=1),
        rights_classification: RightsClassification = Query(),
        principal: PrincipalContext = Depends(
            require_roles(
                PrincipalRole.ADMIN,
                PrincipalRole.CASE_MANAGER,
                PrincipalRole.CONTRIBUTOR,
            )
        ),
        registry: RegistryService = Depends(service),
    ) -> ArtifactView:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid content-length") from exc
            if declared_length > settings.max_artifact_bytes:
                raise HTTPException(
                    status_code=413, detail="artifact exceeds configured size limit"
                )
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > settings.max_artifact_bytes:
                raise HTTPException(
                    status_code=413, detail="artifact exceeds configured size limit"
                )
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise HTTPException(status_code=422, detail="artifact body is empty")
        if (
            principal.role == PrincipalRole.CONTRIBUTOR
            and rights_classification == RightsClassification.PUBLIC
        ):
            raise HTTPException(
                status_code=403,
                detail="contributors cannot self-classify uploads as public",
            )
        try:
            return registry.put_artifact(
                data=data,
                media_type=media_type,
                rights_classification=rights_classification,
                actor_id=principal.actor_id,
            )
        except ArtifactStoreWriteError as exc:
            raise HTTPException(
                status_code=507,
                detail=f"artifact storage unavailable: {exc}",
            ) from exc

    @app.get("/v1/artifacts/{sha256}")
    def download_artifact(
        sha256: str,
        principal: PrincipalContext = Depends(current_principal),
        session: Session = Depends(get_session),
    ) -> Response:
        registry = RegistryService(session, app.state.artifact_store)
        row = session.get(ArtifactORM, sha256)
        if row is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        if not registry.can_read_artifact(sha256, principal.actor_id, principal.role):
            raise HTTPException(status_code=403, detail="artifact access denied")
        data = app.state.artifact_store.read(sha256)
        return Response(
            content=data,
            media_type=row.media_type,
            headers={"ETag": sha256, "Content-Length": str(len(data))},
        )

    @app.post("/v1/cases", response_model=CaseView, status_code=201)
    def register_case(
        data: CaseRegistration,
        principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
        ),
        registry: RegistryService = Depends(service),
    ) -> CaseView:
        return registry.register_case(data, principal.actor_id)

    @app.get("/v1/cases/{case_id}/versions/{case_version}", response_model=CaseBundle)
    def get_case(
        case_id: str,
        case_version: str,
        principal: PrincipalContext = Depends(current_principal),
        session: Session = Depends(get_session),
    ) -> CaseBundle:
        row = session.scalar(
            select(CaseORM).where(
                CaseORM.case_id == case_id,
                CaseORM.case_version == case_version,
            )
        )
        if row is None:
            raise HTTPException(status_code=404, detail="case version not found")
        registry = RegistryService(session, app.state.artifact_store)
        if not registry.can_read_case(
            case_id=case_id,
            case_version=case_version,
            actor_id=principal.actor_id,
            role=principal.role,
        ):
            raise HTTPException(status_code=403, detail="case access denied")
        return CaseBundle.model_validate(row.bundle_json)

    @app.get(
        "/v1/cases/{case_id}/versions/{case_version}/grants",
        response_model=list[RightsGrantView],
    )
    def list_grants(
        case_id: str,
        case_version: str,
        _principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER, PrincipalRole.AUDITOR)
        ),
        registry: RegistryService = Depends(service),
    ) -> list[RightsGrantView]:
        return registry.list_grants(case_id=case_id, case_version=case_version)

    @app.post(
        "/v1/cases/{case_id}/versions/{case_version}/grants",
        response_model=RightsGrantView,
        status_code=201,
    )
    def create_grant(
        case_id: str,
        case_version: str,
        data: RightsGrantInput,
        principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
        ),
        registry: RegistryService = Depends(service),
    ) -> RightsGrantView:
        return registry.add_grant(
            case_id=case_id,
            case_version=case_version,
            data=data,
            actor_id=principal.actor_id,
        )

    @app.post("/v1/grants/{grant_id}/revoke", response_model=RightsGrantView)
    def revoke_grant(
        grant_id: str,
        principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
        ),
        registry: RegistryService = Depends(service),
    ) -> RightsGrantView:
        return registry.revoke_grant(grant_id, principal.actor_id)

    @app.get(
        "/v1/cases/{case_id}/versions/{case_version}/tasks",
        response_model=list[TaskView],
    )
    def list_tasks(
        case_id: str,
        case_version: str,
        _principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER, PrincipalRole.AUDITOR)
        ),
        registry: RegistryService = Depends(service),
    ) -> list[TaskView]:
        return registry.list_tasks(case_id=case_id, case_version=case_version)

    @app.post(
        "/v1/cases/{case_id}/versions/{case_version}/tasks/seed",
        response_model=list[TaskView],
        status_code=201,
    )
    def seed_tasks(
        case_id: str,
        case_version: str,
        data: TaskSeedRequest,
        principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
        ),
        registry: RegistryService = Depends(service),
    ) -> list[TaskView]:
        return registry.seed_tasks(
            case_id=case_id,
            case_version=case_version,
            concern_ids=data.concern_ids,
            actor_id=principal.actor_id,
        )

    @app.post("/v1/tasks/claim", response_model=TaskView)
    def claim_task(
        principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
        registry: RegistryService = Depends(service),
    ) -> TaskView:
        return registry.claim_task(principal.actor_id)

    @app.get("/v1/tasks/claimable", response_model=list[ClaimableTaskView])
    def list_claimable_tasks(
        limit: int = Query(50, ge=1, le=200),
        principal: PrincipalContext = Depends(
            require_roles(
                PrincipalRole.ADJUDICATOR,
                PrincipalRole.ADMIN,
                PrincipalRole.CASE_MANAGER,
                PrincipalRole.AUDITOR,
            )
        ),
        registry: RegistryService = Depends(service),
    ) -> list[ClaimableTaskView]:
        _ = principal
        return registry.list_claimable_tasks(limit=limit)

    @app.get("/v1/tasks/{task_id}", response_model=BlindedTaskPayload)
    def task_payload(
        task_id: str,
        principal: PrincipalContext = Depends(
            require_roles(
                PrincipalRole.ADJUDICATOR,
                PrincipalRole.ADMIN,
                PrincipalRole.CASE_MANAGER,
                PrincipalRole.AUDITOR,
            )
        ),
        registry: RegistryService = Depends(service),
    ) -> BlindedTaskPayload:
        return registry.task_payload(task_id, principal.actor_id, principal.role)

    @app.post("/v1/tasks/{task_id}/submit", response_model=SubmissionView, status_code=201)
    def submit_task(
        task_id: str,
        data: AdjudicationSubmissionInput,
        principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
        registry: RegistryService = Depends(service),
    ) -> SubmissionView:
        adjudication, task, _determination = registry.submit_adjudication(
            task_id=task_id,
            data=data,
            actor_id=principal.actor_id,
        )
        return SubmissionView(adjudication=adjudication, task=task)

    @app.get("/v1/concerns/{concern_id}/determination", response_model=DeterminationView)
    def get_determination(
        concern_id: str,
        principal: PrincipalContext = Depends(current_principal),
        session: Session = Depends(get_session),
    ) -> DeterminationView:
        registry = RegistryService(session, app.state.artifact_store)
        view = registry.latest_determination(concern_id)
        if not registry.can_read_case(
            case_id=view.case_id,
            case_version=view.case_version,
            actor_id=principal.actor_id,
            role=principal.role,
            concern_id=concern_id,
        ):
            raise HTTPException(status_code=403, detail="determination access denied")
        return view

    @app.get("/v1/concerns/{concern_id}/appeals", response_model=list[AppealRecordView])
    def list_appeals(
        concern_id: str,
        principal: PrincipalContext = Depends(current_principal),
        registry: RegistryService = Depends(service),
    ) -> list[AppealRecordView]:
        determination = registry.latest_determination(concern_id)
        if not registry.can_read_case(
            case_id=determination.case_id,
            case_version=determination.case_version,
            actor_id=principal.actor_id,
            role=principal.role,
            concern_id=concern_id,
        ):
            raise HTTPException(status_code=403, detail="appeal access denied")
        return registry.list_appeal_records(concern_id)

    @app.post("/v1/appeals", response_model=AppealRecordView, status_code=201)
    def create_appeal(
        data: AppealRecordInput,
        principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
        ),
        registry: RegistryService = Depends(service),
    ) -> AppealRecordView:
        return registry.create_appeal_record(data, principal.actor_id)

    @app.get("/v1/audit-events", response_model=list[AuditEventView])
    def audit_events(
        target_type: str | None = None,
        target_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        _principal: PrincipalContext = Depends(
            require_roles(PrincipalRole.ADMIN, PrincipalRole.AUDITOR)
        ),
        session: Session = Depends(get_session),
    ) -> list[AuditEventView]:
        query = select(AuditEventORM).order_by(AuditEventORM.created_at.desc()).limit(limit)
        if target_type is not None:
            query = query.where(AuditEventORM.target_type == target_type)
        if target_id is not None:
            query = query.where(AuditEventORM.target_id == target_id)
        rows = session.scalars(query).all()
        return [
            AuditEventView(
                event_id=row.event_id,
                actor_id=row.actor_id,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                event_data=row.event_data,
                created_at=as_utc(row.created_at),
            )
            for row in rows
        ]

    app.include_router(expert_router)
    app.include_router(matcher_audit_router)
    install_studio_routes(app)
    return app


app = create_app()
