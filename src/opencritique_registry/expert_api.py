from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import PrincipalContext, current_principal, get_session, require_roles
from .db_models import AdjudicationTaskORM
from .expert_schemas import (
    CalibrationAttemptView,
    CalibrationSetInput,
    CalibrationSetView,
    CalibrationSubmissionView,
    CalibrationTaskView,
    CaseIntakeInput,
    CaseIntakeReviewInput,
    CaseIntakeView,
    ClaimDeterminationInput,
    ClaimDeterminationView,
    ClaimReconstructionInput,
    ClaimSubmissionView,
    ClaimTaskPayload,
    ClaimTaskSeedInput,
    ClaimTaskView,
    CommunityMetrics,
    CompensationInput,
    CompensationStatusInput,
    CompensationView,
    ContributionCreditView,
    ExpertProfileInput,
    ExpertProfileView,
    QualificationView,
)
from .expert_service import ExpertProgramService
from .schemas import (
    AdjudicationSubmissionInput,
    BlindedTaskPayload,
    PrincipalRole,
    TaskStatus,
    TaskView,
)
from .service import _task_view

router = APIRouter()


def expert_service(
    request: Request, session: Session = Depends(get_session)
) -> ExpertProgramService:
    return ExpertProgramService(session, request.app.state.artifact_store)


@router.put("/v1/experts/{actor_id}/profile", response_model=ExpertProfileView)
def upsert_expert_profile(
    actor_id: str,
    data: ExpertProfileInput,
    principal: PrincipalContext = Depends(current_principal),
    service: ExpertProgramService = Depends(expert_service),
) -> ExpertProfileView:
    if principal.actor_id != actor_id and principal.role not in {
        PrincipalRole.ADMIN,
        PrincipalRole.CASE_MANAGER,
    }:
        raise HTTPException(status_code=403, detail="profile access denied")
    return service.upsert_profile(actor_id, data, principal.actor_id)


@router.get("/v1/experts/{actor_id}/profile", response_model=ExpertProfileView)
def expert_profile(
    actor_id: str,
    principal: PrincipalContext = Depends(current_principal),
    service: ExpertProgramService = Depends(expert_service),
) -> ExpertProfileView:
    if principal.actor_id != actor_id and principal.role not in {
        PrincipalRole.ADMIN,
        PrincipalRole.CASE_MANAGER,
        PrincipalRole.AUDITOR,
    }:
        raise HTTPException(status_code=403, detail="profile access denied")
    return service.profile(actor_id)


@router.get("/v1/experts/{actor_id}/qualifications", response_model=list[QualificationView])
def expert_qualifications(
    actor_id: str,
    principal: PrincipalContext = Depends(current_principal),
    service: ExpertProgramService = Depends(expert_service),
) -> list[QualificationView]:
    if principal.actor_id != actor_id and principal.role not in {
        PrincipalRole.ADMIN,
        PrincipalRole.CASE_MANAGER,
        PrincipalRole.AUDITOR,
    }:
        raise HTTPException(status_code=403, detail="qualification access denied")
    return service.qualifications(actor_id)


@router.post("/v1/calibration-sets", response_model=CalibrationSetView, status_code=201)
def create_calibration_set(
    data: CalibrationSetInput,
    principal: PrincipalContext = Depends(
        require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> CalibrationSetView:
    return service.create_calibration_set(data, principal.actor_id)


@router.post(
    "/v1/calibration-sets/{set_id}/attempts",
    response_model=CalibrationAttemptView,
    status_code=201,
)
def start_calibration_attempt(
    set_id: str,
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    service: ExpertProgramService = Depends(expert_service),
) -> CalibrationAttemptView:
    return service.start_calibration(set_id, principal.actor_id)


@router.get(
    "/v1/calibration-attempts/{attempt_id}/tasks",
    response_model=list[CalibrationTaskView],
)
def calibration_tasks(
    attempt_id: str,
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    service: ExpertProgramService = Depends(expert_service),
) -> list[CalibrationTaskView]:
    return service.calibration_tasks(attempt_id, principal.actor_id)


@router.get("/v1/calibration-tasks/{task_id}", response_model=BlindedTaskPayload)
def calibration_task_payload(
    task_id: str,
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    service: ExpertProgramService = Depends(expert_service),
) -> BlindedTaskPayload:
    return service.calibration_payload(task_id, principal.actor_id)


@router.post(
    "/v1/calibration-tasks/{task_id}/submit",
    response_model=CalibrationSubmissionView,
    status_code=201,
)
def submit_calibration_task(
    task_id: str,
    data: AdjudicationSubmissionInput,
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    service: ExpertProgramService = Depends(expert_service),
) -> CalibrationSubmissionView:
    return service.submit_calibration(task_id, data, principal.actor_id)


@router.post("/v1/intakes", response_model=CaseIntakeView, status_code=201)
def create_case_intake(
    data: CaseIntakeInput,
    principal: PrincipalContext = Depends(
        require_roles(
            PrincipalRole.ADMIN,
            PrincipalRole.CASE_MANAGER,
            PrincipalRole.CONTRIBUTOR,
        )
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> CaseIntakeView:
    return service.create_intake(data, principal.actor_id, principal.role)


@router.get("/v1/intakes/{intake_id}", response_model=CaseIntakeView)
def get_case_intake(
    intake_id: str,
    principal: PrincipalContext = Depends(current_principal),
    service: ExpertProgramService = Depends(expert_service),
) -> CaseIntakeView:
    return service.intake(intake_id, principal.actor_id, principal.role)


@router.post("/v1/intakes/{intake_id}/review", response_model=CaseIntakeView)
def review_case_intake(
    intake_id: str,
    data: CaseIntakeReviewInput,
    principal: PrincipalContext = Depends(
        require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> CaseIntakeView:
    return service.review_intake(intake_id, data, principal.actor_id)


@router.post(
    "/v1/intakes/{intake_id}/claim-tasks/seed",
    response_model=list[ClaimTaskView],
    status_code=201,
)
def seed_claim_tasks(
    intake_id: str,
    data: ClaimTaskSeedInput,
    principal: PrincipalContext = Depends(
        require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> list[ClaimTaskView]:
    return service.seed_claim_tasks(intake_id, data, principal.actor_id)


@router.post("/v1/claim-tasks/claim", response_model=ClaimTaskView)
def claim_reconstruction_task(
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    service: ExpertProgramService = Depends(expert_service),
) -> ClaimTaskView:
    return service.claim_claim_task(principal.actor_id)


@router.get("/v1/claim-tasks/{task_id}", response_model=ClaimTaskPayload)
def claim_reconstruction_payload(
    task_id: str,
    principal: PrincipalContext = Depends(
        require_roles(
            PrincipalRole.ADJUDICATOR,
            PrincipalRole.ADMIN,
            PrincipalRole.CASE_MANAGER,
            PrincipalRole.AUDITOR,
        )
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> ClaimTaskPayload:
    return service.claim_task_payload(task_id, principal.actor_id, principal.role)


@router.post(
    "/v1/claim-tasks/{task_id}/submit",
    response_model=ClaimSubmissionView,
    status_code=201,
)
def submit_claim_reconstruction(
    task_id: str,
    data: ClaimReconstructionInput,
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    service: ExpertProgramService = Depends(expert_service),
) -> ClaimSubmissionView:
    return service.submit_claim_reconstruction(task_id, data, principal.actor_id)


@router.post(
    "/v1/intakes/{intake_id}/claim-determinations",
    response_model=ClaimDeterminationView,
    status_code=201,
)
def determine_claim_reconstruction(
    intake_id: str,
    data: ClaimDeterminationInput,
    principal: PrincipalContext = Depends(
        require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> ClaimDeterminationView:
    return service.determine_claim(intake_id, data, principal.actor_id)


@router.get("/v1/my-tasks", response_model=list[TaskView])
def my_adjudication_tasks(
    status: TaskStatus | None = Query(default=None),
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADJUDICATOR)),
    session: Session = Depends(get_session),
) -> list[TaskView]:
    query = select(AdjudicationTaskORM).where(
        AdjudicationTaskORM.assigned_to == principal.actor_id
    )
    if status is not None:
        query = query.where(AdjudicationTaskORM.status == status.value)
    rows = session.scalars(query.order_by(AdjudicationTaskORM.created_at.desc())).all()
    return [_task_view(row) for row in rows]


@router.get(
    "/v1/experts/{actor_id}/credits", response_model=list[ContributionCreditView]
)
def expert_credits(
    actor_id: str,
    principal: PrincipalContext = Depends(current_principal),
    service: ExpertProgramService = Depends(expert_service),
) -> list[ContributionCreditView]:
    if principal.actor_id != actor_id and principal.role not in {
        PrincipalRole.ADMIN,
        PrincipalRole.CASE_MANAGER,
        PrincipalRole.AUDITOR,
    }:
        raise HTTPException(status_code=403, detail="credit access denied")
    return service.credits(actor_id)


@router.get(
    "/v1/public/contributors/{actor_id}/credits",
    response_model=list[ContributionCreditView],
)
def public_contributor_credits(
    actor_id: str,
    service: ExpertProgramService = Depends(expert_service),
) -> list[ContributionCreditView]:
    return service.credits(actor_id, public_only=True)


@router.post("/v1/compensation", response_model=CompensationView, status_code=201)
def create_compensation(
    data: CompensationInput,
    principal: PrincipalContext = Depends(
        require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER)
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> CompensationView:
    return service.create_compensation(data, principal.actor_id)


@router.post("/v1/compensation/{compensation_id}/status", response_model=CompensationView)
def update_compensation(
    compensation_id: str,
    data: CompensationStatusInput,
    principal: PrincipalContext = Depends(require_roles(PrincipalRole.ADMIN)),
    service: ExpertProgramService = Depends(expert_service),
) -> CompensationView:
    return service.update_compensation(compensation_id, data, principal.actor_id)


@router.get("/v1/experts/{actor_id}/compensation", response_model=list[CompensationView])
def expert_compensation(
    actor_id: str,
    principal: PrincipalContext = Depends(current_principal),
    service: ExpertProgramService = Depends(expert_service),
) -> list[CompensationView]:
    if principal.actor_id != actor_id and principal.role not in {
        PrincipalRole.ADMIN,
        PrincipalRole.CASE_MANAGER,
        PrincipalRole.AUDITOR,
    }:
        raise HTTPException(status_code=403, detail="compensation access denied")
    return service.compensation(actor_id)


@router.get("/v1/analytics/community", response_model=CommunityMetrics)
def community_metrics(
    _principal: PrincipalContext = Depends(
        require_roles(PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER, PrincipalRole.AUDITOR)
    ),
    service: ExpertProgramService = Depends(expert_service),
) -> CommunityMetrics:
    return service.metrics()
