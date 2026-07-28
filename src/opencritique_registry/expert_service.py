from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from opencritique_schema.canonical import content_hash
from opencritique_schema.models import (
    CaseBundle,
    Severity,
)

from .artifacts import LocalArtifactStore
from .audit import record_event
from .db_models import (
    AdjudicationSubmissionORM,
    AdjudicationTaskORM,
    ArtifactORM,
    CalibrationAttemptORM,
    CalibrationSetORM,
    CalibrationSubmissionORM,
    CalibrationTaskORM,
    CaseIntakeORM,
    CaseORM,
    ClaimReconstructionDeterminationORM,
    ClaimReconstructionSubmissionORM,
    ClaimReconstructionTaskORM,
    CompensationRecordORM,
    ContributionCreditORM,
    ExpertProfileORM,
    ExpertQualificationORM,
    PrincipalORM,
    utcnow,
)
from .expert_schemas import (
    AgreementMetrics,
    CalibrationAttemptStatus,
    CalibrationAttemptView,
    CalibrationMetrics,
    CalibrationScore,
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
    CompensationStatus,
    CompensationStatusInput,
    CompensationView,
    ContributionCreditView,
    ExpertProfileInput,
    ExpertProfileView,
    ExpertStatus,
    IntakeStatus,
    QualificationStatus,
    QualificationView,
)
from .ids import new_id
from .schemas import (
    AdjudicationSubmissionInput,
    BlindedTaskPayload,
    PrincipalRole,
    TaskSlot,
    TaskStatus,
)
from .service import PRIMARY_BLINDED_FIELDS, RegistryService
from .timeutils import as_utc, optional_utc

SEVERITY_ORDER = {
    Severity.INFORMATIONAL.value: 0,
    Severity.MINOR.value: 1,
    Severity.MODERATE.value: 2,
    Severity.MAJOR.value: 3,
    Severity.CRITICAL.value: 4,
}


def _case_row(session: Session, case_id: str, case_version: str) -> CaseORM:
    row = session.scalar(
        select(CaseORM).where(CaseORM.case_id == case_id, CaseORM.case_version == case_version)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="case version not found")
    return row


def _bundle(row: CaseORM) -> CaseBundle:
    return CaseBundle.model_validate(row.bundle_json)


def _profile_view(row: ExpertProfileORM) -> ExpertProfileView:
    return ExpertProfileView(
        actor_id=row.actor_id,
        domains=row.domains,
        methodologies=row.methodologies,
        affiliation=row.affiliation,
        biography=row.biography,
        orcid=row.orcid,
        public_attribution=row.public_attribution,
        attribution_name=row.attribution_name,
        compensation_currency=row.compensation_currency,
        status=ExpertStatus(row.status),
        created_at=as_utc(row.created_at),
        updated_at=as_utc(row.updated_at),
    )


def _calibration_set_view(row: CalibrationSetORM) -> CalibrationSetView:
    return CalibrationSetView(
        set_id=row.set_id,
        name=row.name,
        domain_profile=row.domain_profile,
        case_refs=row.case_refs,
        min_cases=row.min_cases,
        pass_threshold=row.pass_threshold,
        max_false_critical=row.max_false_critical,
        active=row.active,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


def _calibration_score(data: dict[str, Any] | None) -> CalibrationScore | None:
    return CalibrationScore.model_validate(data) if data is not None else None


def _attempt_view(row: CalibrationAttemptORM) -> CalibrationAttemptView:
    return CalibrationAttemptView(
        attempt_id=row.attempt_id,
        set_id=row.set_id,
        adjudicator_id=row.adjudicator_id,
        status=CalibrationAttemptStatus(row.status),
        score=_calibration_score(row.score_json),
        passed=row.passed,
        created_at=as_utc(row.created_at),
        completed_at=optional_utc(row.completed_at),
    )


def _calibration_task_view(row: CalibrationTaskORM) -> CalibrationTaskView:
    return CalibrationTaskView(
        task_id=row.task_id,
        attempt_id=row.attempt_id,
        case_id=row.case_id,
        case_version=row.case_version,
        concern_id=row.concern_id,
        sequence=row.sequence,
        status=TaskStatus(row.status),
        completed_at=optional_utc(row.completed_at),
    )


def _intake_view(row: CaseIntakeORM) -> CaseIntakeView:
    return CaseIntakeView(
        intake_id=row.intake_id,
        submitted_by=row.submitted_by,
        title=row.title,
        source_artifact_sha256=row.source_artifact_sha256,
        domain_profile=row.domain_profile,
        language=row.language,
        rights_classification=row.rights_classification,
        requested_uses=row.requested_uses,
        rights_attestation=row.rights_attestation,
        contains_sensitive_data=row.contains_sensitive_data,
        contains_personal_data=row.contains_personal_data,
        redistribution_allowed=row.redistribution_allowed,
        notes=row.notes,
        status=IntakeStatus(row.status),
        reviewed_by=row.reviewed_by,
        review_reason=row.review_reason,
        created_at=as_utc(row.created_at),
        reviewed_at=optional_utc(row.reviewed_at),
    )


def _claim_task_view(row: ClaimReconstructionTaskORM) -> ClaimTaskView:
    return ClaimTaskView(
        task_id=row.task_id,
        intake_id=row.intake_id,
        slot=TaskSlot(row.slot),
        status=TaskStatus(row.status),
        assigned_to=row.assigned_to,
        anchor_context=row.anchor_context,
        claimed_at=optional_utc(row.claimed_at),
        completed_at=optional_utc(row.completed_at),
    )


def _qualification_view(row: ExpertQualificationORM) -> QualificationView:
    return QualificationView(
        qualification_id=row.qualification_id,
        actor_id=row.actor_id,
        domain_profile=row.domain_profile,
        status=QualificationStatus(row.status),
        source_attempt_id=row.source_attempt_id,
        valid_from=as_utc(row.valid_from),
        expires_at=optional_utc(row.expires_at),
        revoked_at=optional_utc(row.revoked_at),
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


def _compensation_view(row: CompensationRecordORM) -> CompensationView:
    return CompensationView(
        compensation_id=row.compensation_id,
        actor_id=row.actor_id,
        task_type=row.task_type,
        task_id=row.task_id,
        amount_minor=row.amount_minor,
        currency=row.currency,
        basis=row.basis,
        status=CompensationStatus(row.status),
        approved_by=row.approved_by,
        external_reference=row.external_reference,
        created_at=as_utc(row.created_at),
        paid_at=optional_utc(row.paid_at),
    )


def _credit_view(row: ContributionCreditORM) -> ContributionCreditView:
    return ContributionCreditView(
        credit_id=row.credit_id,
        actor_id=row.actor_id,
        contribution_type=row.contribution_type,
        target_type=row.target_type,
        target_id=row.target_id,
        public_name=row.public_name,
        public=row.public,
        metadata=row.credit_metadata,
        created_at=as_utc(row.created_at),
    )


def _kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    observed = sum(left == right for left, right in pairs) / len(pairs)
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    labels = set(left_counts) | set(right_counts)
    expected = sum(
        (left_counts[label] / len(pairs)) * (right_counts[label] / len(pairs))
        for label in labels
    )
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else None
    return (observed - expected) / (1.0 - expected)


class ExpertProgramService:
    def __init__(self, session: Session, store: LocalArtifactStore) -> None:
        self.session = session
        self.store = store
        self.registry = RegistryService(session, store)

    # Expert profiles and qualification -------------------------------------------------
    def upsert_profile(
        self, actor_id: str, data: ExpertProfileInput, acting_actor_id: str
    ) -> ExpertProfileView:
        principal = self.session.get(PrincipalORM, actor_id)
        if principal is None or principal.role != PrincipalRole.ADJUDICATOR.value:
            raise HTTPException(status_code=422, detail="expert profile requires adjudicator role")
        row = self.session.get(ExpertProfileORM, actor_id)
        if row is None:
            row = ExpertProfileORM(
                actor_id=actor_id,
                domains=data.domains,
                methodologies=data.methodologies,
                affiliation=data.affiliation,
                biography=data.biography,
                orcid=data.orcid,
                public_attribution=data.public_attribution,
                attribution_name=data.attribution_name,
                compensation_currency=data.compensation_currency,
                status=ExpertStatus.CALIBRATION.value,
            )
            self.session.add(row)
            action = "expert.profile_created"
        else:
            row.domains = data.domains
            row.methodologies = data.methodologies
            row.affiliation = data.affiliation
            row.biography = data.biography
            row.orcid = data.orcid
            row.public_attribution = data.public_attribution
            row.attribution_name = data.attribution_name
            row.compensation_currency = data.compensation_currency
            row.updated_at = utcnow()
            action = "expert.profile_updated"
        record_event(
            self.session,
            actor_id=acting_actor_id,
            action=action,
            target_type="expert_profile",
            target_id=actor_id,
            event_data={"domains": data.domains, "public_attribution": data.public_attribution},
        )
        self.session.flush()
        return _profile_view(row)

    def profile(self, actor_id: str) -> ExpertProfileView:
        row = self.session.get(ExpertProfileORM, actor_id)
        if row is None:
            raise HTTPException(status_code=404, detail="expert profile not found")
        return _profile_view(row)

    def qualifications(self, actor_id: str) -> list[QualificationView]:
        rows = self.session.scalars(
            select(ExpertQualificationORM)
            .where(ExpertQualificationORM.actor_id == actor_id)
            .order_by(ExpertQualificationORM.created_at.desc())
        ).all()
        return [_qualification_view(row) for row in rows]

    # Calibration ----------------------------------------------------------------------
    def create_calibration_set(
        self, data: CalibrationSetInput, actor_id: str
    ) -> CalibrationSetView:
        for ref in data.case_refs:
            row = _case_row(self.session, ref.case_id, ref.case_version)
            bundle = _bundle(row)
            if not any(item.concern_id == ref.concern_id for item in bundle.concerns):
                raise HTTPException(
                    status_code=422,
                    detail=f"calibration concern {ref.concern_id} not found",
                )
            concern = next(item for item in bundle.concerns if item.concern_id == ref.concern_id)
            version = next(
                item
                for item in bundle.manuscript_versions
                if item.version_id == concern.manuscript_version_id
            )
            if version.domain_profile != data.domain_profile:
                raise HTTPException(
                    status_code=422,
                    detail="all calibration cases must match domain_profile",
                )
            references = [
                item for item in bundle.adjudications if item.concern_id == ref.concern_id
            ]
            if len(references) < 2:
                raise HTTPException(
                    status_code=422,
                    detail="calibration case requires two reference adjudications",
                )
            reference_validities = {item.validity.value for item in references}
            reference_severities = {item.severity.value for item in references}
            if len(reference_validities) != 1 or len(reference_severities) != 1:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "calibration references require stable consensus on both "
                        "validity and severity"
                    ),
                )
        row = CalibrationSetORM(
            set_id=new_id("occalset"),
            name=data.name,
            domain_profile=data.domain_profile,
            case_refs=[item.model_dump(mode="json") for item in data.case_refs],
            min_cases=data.min_cases,
            pass_threshold=data.pass_threshold,
            max_false_critical=data.max_false_critical,
            active=data.active,
            created_by=actor_id,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="calibration.set_created",
            target_type="calibration_set",
            target_id=row.set_id,
            event_data={"domain_profile": row.domain_profile, "case_count": len(row.case_refs)},
        )
        self.session.flush()
        return _calibration_set_view(row)

    def start_calibration(self, set_id: str, adjudicator_id: str) -> CalibrationAttemptView:
        profile = self.session.get(ExpertProfileORM, adjudicator_id)
        if profile is None:
            raise HTTPException(status_code=409, detail="create expert profile before calibration")
        calibration_set = self.session.get(CalibrationSetORM, set_id)
        if calibration_set is None or not calibration_set.active:
            raise HTTPException(status_code=404, detail="active calibration set not found")
        existing = self.session.scalar(
            select(CalibrationAttemptORM).where(
                CalibrationAttemptORM.set_id == set_id,
                CalibrationAttemptORM.adjudicator_id == adjudicator_id,
                CalibrationAttemptORM.status == CalibrationAttemptStatus.IN_PROGRESS.value,
            )
        )
        if existing is not None:
            return _attempt_view(existing)
        attempt = CalibrationAttemptORM(
            attempt_id=new_id("occal"),
            set_id=set_id,
            adjudicator_id=adjudicator_id,
            status=CalibrationAttemptStatus.IN_PROGRESS.value,
        )
        self.session.add(attempt)
        self.session.flush()
        for sequence, ref in enumerate(calibration_set.case_refs, start=1):
            self.session.add(
                CalibrationTaskORM(
                    task_id=new_id("occaltask"),
                    attempt_id=attempt.attempt_id,
                    case_id=ref["case_id"],
                    case_version=ref["case_version"],
                    concern_id=ref["concern_id"],
                    sequence=sequence,
                    status=TaskStatus.PENDING.value,
                )
            )
        record_event(
            self.session,
            actor_id=adjudicator_id,
            action="calibration.attempt_started",
            target_type="calibration_attempt",
            target_id=attempt.attempt_id,
            event_data={"set_id": set_id},
        )
        self.session.flush()
        return _attempt_view(attempt)

    def calibration_tasks(self, attempt_id: str, actor_id: str) -> list[CalibrationTaskView]:
        attempt = self.session.get(CalibrationAttemptORM, attempt_id)
        if attempt is None:
            raise HTTPException(status_code=404, detail="calibration attempt not found")
        if attempt.adjudicator_id != actor_id:
            raise HTTPException(
                status_code=403,
                detail="calibration attempt belongs to another expert",
            )
        rows = self.session.scalars(
            select(CalibrationTaskORM)
            .where(CalibrationTaskORM.attempt_id == attempt_id)
            .order_by(CalibrationTaskORM.sequence)
        ).all()
        return [_calibration_task_view(row) for row in rows]

    def calibration_payload(
        self, task_id: str, actor_id: str
    ) -> BlindedTaskPayload:
        task = self.session.get(CalibrationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="calibration task not found")
        attempt = self.session.get(CalibrationAttemptORM, task.attempt_id)
        if attempt is None or attempt.adjudicator_id != actor_id:
            raise HTTPException(
                status_code=403,
                detail="calibration task belongs to another expert",
            )
        if task.status == TaskStatus.COMPLETED.value:
            raise HTTPException(
                status_code=409,
                detail="calibration task is already completed",
            )
        return self.registry.build_blinded_payload(
            task_id=task.task_id,
            slot=TaskSlot.PRIMARY,
            case_id=task.case_id,
            case_version=task.case_version,
            concern_id=task.concern_id,
            prior_adjudications=[],
        ).model_copy(update={"blinded_fields": PRIMARY_BLINDED_FIELDS + ["reference_decision"]})

    def submit_calibration(
        self, task_id: str, data: AdjudicationSubmissionInput, actor_id: str
    ) -> CalibrationSubmissionView:
        task = self.session.get(CalibrationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="calibration task not found")
        attempt = self.session.get(CalibrationAttemptORM, task.attempt_id)
        if attempt is None or attempt.adjudicator_id != actor_id:
            raise HTTPException(
                status_code=403,
                detail="calibration task belongs to another expert",
            )
        if task.status != TaskStatus.PENDING.value:
            raise HTTPException(status_code=409, detail="calibration task is not pending")
        if not data.anchors_reviewed:
            raise HTTPException(status_code=422, detail="anchors must be reviewed")
        if not data.evidence_ids and not data.requested_followup:
            raise HTTPException(
                status_code=422,
                detail="calibration must cite evidence or request follow-up evidence",
            )
        bundle = _bundle(_case_row(self.session, task.case_id, task.case_version))
        valid_evidence = {
            item.evidence_id
            for item in bundle.evidence
            if item.concern_id == task.concern_id
        }
        unknown = set(data.evidence_ids) - valid_evidence
        if unknown:
            raise HTTPException(
                status_code=422,
                detail={"unknown_evidence_ids": sorted(unknown)},
            )
        if data.conflict_declaration.status == "disqualifying":
            raise HTTPException(
                status_code=409,
                detail="disqualifying conflict requires reassignment",
            )
        decision = {
            **data.model_dump(mode="json"),
            "task_id": task.task_id,
            "concern_id": task.concern_id,
            "adjudicator_id": actor_id,
        }
        submission = CalibrationSubmissionORM(
            submission_id=new_id("occalsub"),
            task_id=task.task_id,
            adjudicator_id=actor_id,
            decision_json=decision,
            content_hash=content_hash(decision),
        )
        self.session.add(submission)
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = utcnow()
        self.session.flush()
        self._complete_calibration_if_ready(attempt)
        self._record_credit(
            actor_id=actor_id,
            contribution_type="calibration_case_completed",
            target_type="calibration_task",
            target_id=task.task_id,
            metadata={"attempt_id": attempt.attempt_id},
        )
        record_event(
            self.session,
            actor_id=actor_id,
            action="calibration.submitted",
            target_type="calibration_task",
            target_id=task.task_id,
            event_data={"attempt_id": attempt.attempt_id},
        )
        self.session.flush()
        return CalibrationSubmissionView(
            submission_id=submission.submission_id,
            task=_calibration_task_view(task),
            attempt=_attempt_view(attempt),
        )

    def _reference_decision(self, task: CalibrationTaskORM) -> tuple[str, str]:
        bundle = _bundle(_case_row(self.session, task.case_id, task.case_version))
        refs = [item for item in bundle.adjudications if item.concern_id == task.concern_id]
        validity = Counter(item.validity.value for item in refs)
        severity = Counter(item.severity.value for item in refs)
        if not validity or not severity:
            raise HTTPException(status_code=500, detail="calibration reference decision missing")
        return validity.most_common(1)[0][0], severity.most_common(1)[0][0]

    def _complete_calibration_if_ready(self, attempt: CalibrationAttemptORM) -> None:
        tasks = self.session.scalars(
            select(CalibrationTaskORM).where(CalibrationTaskORM.attempt_id == attempt.attempt_id)
        ).all()
        if not tasks or any(task.status != TaskStatus.COMPLETED.value for task in tasks):
            return
        calibration_set = self.session.get(CalibrationSetORM, attempt.set_id)
        if calibration_set is None:
            raise HTTPException(status_code=500, detail="calibration set missing")
        submissions = {
            row.task_id: row
            for row in self.session.scalars(
                select(CalibrationSubmissionORM).where(
                    CalibrationSubmissionORM.task_id.in_([task.task_id for task in tasks])
                )
            ).all()
        }
        validity_correct = 0
        severity_correct = 0
        severity_distance = 0
        false_critical = 0
        for task in tasks:
            submitted = submissions[task.task_id].decision_json
            reference_validity, reference_severity = self._reference_decision(task)
            validity_correct += int(submitted["validity"] == reference_validity)
            severity_correct += int(submitted["severity"] == reference_severity)
            severity_distance += abs(
                SEVERITY_ORDER[submitted["severity"]] - SEVERITY_ORDER[reference_severity]
            )
            false_critical += int(
                submitted["severity"] == Severity.CRITICAL.value
                and reference_severity != Severity.CRITICAL.value
            )
        count = len(tasks)
        validity_accuracy = validity_correct / count
        severity_accuracy = severity_correct / count
        mean_distance = severity_distance / count
        aggregate = 0.75 * validity_accuracy + 0.25 * (1.0 - mean_distance / 4.0)
        passed = (
            count >= calibration_set.min_cases
            and aggregate >= calibration_set.pass_threshold
            and false_critical <= calibration_set.max_false_critical
        )
        score = CalibrationScore(
            completed_cases=count,
            validity_accuracy=validity_accuracy,
            severity_exact_accuracy=severity_accuracy,
            severity_mean_absolute_distance=mean_distance,
            false_critical_count=false_critical,
            aggregate_score=aggregate,
            passed=passed,
        )
        attempt.score_json = score.model_dump(mode="json")
        attempt.passed = passed
        attempt.status = CalibrationAttemptStatus.COMPLETED.value
        attempt.completed_at = utcnow()
        profile = self.session.get(ExpertProfileORM, attempt.adjudicator_id)
        if passed:
            existing = self.session.scalar(
                select(ExpertQualificationORM).where(
                    ExpertQualificationORM.actor_id == attempt.adjudicator_id,
                    ExpertQualificationORM.domain_profile == calibration_set.domain_profile,
                    ExpertQualificationORM.status == QualificationStatus.ACTIVE.value,
                )
            )
            if existing is None:
                self.session.add(
                    ExpertQualificationORM(
                        qualification_id=new_id("ocqual"),
                        actor_id=attempt.adjudicator_id,
                        domain_profile=calibration_set.domain_profile,
                        status=QualificationStatus.ACTIVE.value,
                        source_attempt_id=attempt.attempt_id,
                        created_by=calibration_set.created_by,
                    )
                )
            if profile is not None:
                profile.status = ExpertStatus.ELIGIBLE.value
        elif profile is not None:
            profile.status = ExpertStatus.CALIBRATION.value

    # Rights-cleared intake -------------------------------------------------------------
    def create_intake(
        self,
        data: CaseIntakeInput,
        actor_id: str,
        role: PrincipalRole,
    ) -> CaseIntakeView:
        artifact = self.session.get(ArtifactORM, data.source_artifact_sha256)
        if artifact is None:
            raise HTTPException(status_code=422, detail="source artifact is not registered")
        if (
            role not in {PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER}
            and artifact.created_by != actor_id
        ):
            raise HTTPException(
                status_code=403,
                detail="contributors may submit only their artifacts",
            )
        if artifact.rights_classification != data.rights_classification.value:
            raise HTTPException(status_code=422, detail="artifact rights classification mismatch")
        row = CaseIntakeORM(
            intake_id=new_id("ocintake"),
            submitted_by=actor_id,
            title=data.title,
            source_artifact_sha256=data.source_artifact_sha256,
            domain_profile=data.domain_profile,
            language=data.language,
            rights_classification=data.rights_classification.value,
            requested_uses=[item.value for item in data.requested_uses],
            rights_attestation=data.rights_attestation.model_dump(mode="json"),
            contains_sensitive_data=data.contains_sensitive_data,
            contains_personal_data=data.contains_personal_data,
            redistribution_allowed=data.redistribution_allowed,
            notes=data.notes,
            status=IntakeStatus.SUBMITTED.value,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="intake.submitted",
            target_type="case_intake",
            target_id=row.intake_id,
            event_data={"requested_uses": row.requested_uses},
        )
        self.session.flush()
        return _intake_view(row)

    def review_intake(
        self, intake_id: str, data: CaseIntakeReviewInput, actor_id: str
    ) -> CaseIntakeView:
        row = self.session.get(CaseIntakeORM, intake_id)
        if row is None:
            raise HTTPException(status_code=404, detail="intake not found")
        if row.status in {IntakeStatus.REJECTED.value, IntakeStatus.WITHDRAWN.value}:
            raise HTTPException(status_code=409, detail="closed intake cannot be reviewed")
        row.status = data.status
        row.review_reason = data.reason
        row.reviewed_by = actor_id
        row.reviewed_at = utcnow()
        record_event(
            self.session,
            actor_id=actor_id,
            action=f"intake.{data.status}",
            target_type="case_intake",
            target_id=intake_id,
            event_data={"reason": data.reason},
        )
        self.session.flush()
        return _intake_view(row)

    def intake(self, intake_id: str, actor_id: str, role: PrincipalRole) -> CaseIntakeView:
        row = self.session.get(CaseIntakeORM, intake_id)
        if row is None:
            raise HTTPException(status_code=404, detail="intake not found")
        if (
            role
            not in {PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER, PrincipalRole.AUDITOR}
            and row.submitted_by != actor_id
        ):
            raise HTTPException(status_code=403, detail="intake access denied")
        return _intake_view(row)

    # Claim reconstruction -------------------------------------------------------------
    def seed_claim_tasks(
        self, intake_id: str, data: ClaimTaskSeedInput, actor_id: str
    ) -> list[ClaimTaskView]:
        intake = self.session.get(CaseIntakeORM, intake_id)
        if intake is None:
            raise HTTPException(status_code=404, detail="intake not found")
        if intake.status != IntakeStatus.ACCEPTED.value:
            raise HTTPException(status_code=409, detail="intake must be accepted")
        if "expert_adjudication" not in intake.requested_uses:
            raise HTTPException(
                status_code=403,
                detail="intake lacks expert-adjudication authorization",
            )
        existing = self.session.scalars(
            select(ClaimReconstructionTaskORM).where(
                ClaimReconstructionTaskORM.intake_id == intake_id
            )
        ).all()
        if existing:
            return [_claim_task_view(row) for row in existing]
        rows = []
        context = [item.model_dump(mode="json") for item in data.anchor_context]
        for slot in (TaskSlot.PRIMARY, TaskSlot.SECONDARY):
            row = ClaimReconstructionTaskORM(
                task_id=new_id("occlaimtask"),
                intake_id=intake_id,
                slot=slot.value,
                status=TaskStatus.PENDING.value,
                anchor_context=context,
            )
            self.session.add(row)
            rows.append(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="claim_reconstruction.tasks_seeded",
            target_type="case_intake",
            target_id=intake_id,
            event_data={"anchor_count": len(context)},
        )
        self.session.flush()
        return [_claim_task_view(row) for row in rows]

    def claim_claim_task(self, adjudicator_id: str) -> ClaimTaskView:
        candidates = self.session.scalars(
            select(ClaimReconstructionTaskORM)
            .where(ClaimReconstructionTaskORM.status == TaskStatus.PENDING.value)
            .order_by(ClaimReconstructionTaskORM.created_at, ClaimReconstructionTaskORM.slot)
            .with_for_update(skip_locked=True)
        ).all()
        for task in candidates:
            intake = self.session.get(CaseIntakeORM, task.intake_id)
            if intake is None or intake.status != IntakeStatus.ACCEPTED.value:
                continue
            if not self.registry._adjudicator_is_qualified(adjudicator_id, intake.domain_profile):
                continue
            prior = self.session.scalar(
                select(ClaimReconstructionTaskORM).where(
                    ClaimReconstructionTaskORM.intake_id == task.intake_id,
                    ClaimReconstructionTaskORM.assigned_to == adjudicator_id,
                    ClaimReconstructionTaskORM.task_id != task.task_id,
                    ClaimReconstructionTaskORM.status.in_(
                        [TaskStatus.CLAIMED.value, TaskStatus.COMPLETED.value]
                    ),
                )
            )
            if prior is not None:
                continue
            task.status = TaskStatus.CLAIMED.value
            task.assigned_to = adjudicator_id
            task.claimed_at = utcnow()
            record_event(
                self.session,
                actor_id=adjudicator_id,
                action="claim_reconstruction.task_claimed",
                target_type="claim_task",
                target_id=task.task_id,
            )
            self.session.flush()
            return _claim_task_view(task)
        raise HTTPException(status_code=404, detail="no eligible claim-reconstruction task")

    def claim_task_payload(
        self, task_id: str, actor_id: str, role: PrincipalRole
    ) -> ClaimTaskPayload:
        task = self.session.get(ClaimReconstructionTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="claim task not found")
        if role == PrincipalRole.ADJUDICATOR and task.assigned_to != actor_id:
            raise HTTPException(status_code=403, detail="claim task belongs to another expert")
        intake = self.session.get(CaseIntakeORM, task.intake_id)
        if intake is None:
            raise HTTPException(status_code=500, detail="claim-task intake missing")
        prior: list[dict[str, Any]] = []
        if task.slot == TaskSlot.TIE_BREAK.value:
            rows = self.session.scalars(
                select(ClaimReconstructionSubmissionORM).where(
                    ClaimReconstructionSubmissionORM.intake_id == intake.intake_id
                )
            ).all()
            prior = [row.claim_json for row in rows]
        return ClaimTaskPayload(
            task=_claim_task_view(task),
            title=intake.title,
            domain_profile=intake.domain_profile,
            language=intake.language,
            source_artifact_sha256=intake.source_artifact_sha256,
            prior_reconstructions=prior,
            blinded_fields=[
                "submitter_identity",
                "rights_authority",
                "requested_uses",
                (
                    "other_reconstructions"
                    if task.slot != TaskSlot.TIE_BREAK.value
                    else "expert_identity"
                ),
            ],
        )

    def submit_claim_reconstruction(
        self, task_id: str, data: ClaimReconstructionInput, actor_id: str
    ) -> ClaimSubmissionView:
        task = self.session.get(ClaimReconstructionTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="claim task not found")
        if task.assigned_to != actor_id:
            raise HTTPException(status_code=403, detail="claim task belongs to another expert")
        if task.status != TaskStatus.CLAIMED.value:
            raise HTTPException(status_code=409, detail="claim task is not open")
        allowed = {item["anchor_id"] for item in task.anchor_context}
        unknown = set(data.anchor_ids) - allowed
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_anchor_ids": sorted(unknown)})
        submission = ClaimReconstructionSubmissionORM(
            submission_id=new_id("occlaimsub"),
            task_id=task.task_id,
            intake_id=task.intake_id,
            adjudicator_id=actor_id,
            slot=task.slot,
            claim_json=data.model_dump(mode="json"),
            content_hash=content_hash(data),
        )
        self.session.add(submission)
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = utcnow()
        self._record_credit(
            actor_id=actor_id,
            contribution_type="claim_reconstruction",
            target_type="claim_submission",
            target_id=submission.submission_id,
            metadata={"intake_id": task.intake_id, "slot": task.slot},
        )
        record_event(
            self.session,
            actor_id=actor_id,
            action="claim_reconstruction.submitted",
            target_type="claim_submission",
            target_id=submission.submission_id,
            event_data={"intake_id": task.intake_id, "slot": task.slot},
        )
        self.session.flush()
        return ClaimSubmissionView(
            submission_id=submission.submission_id,
            task=_claim_task_view(task),
            claim=data,
        )

    def determine_claim(
        self, intake_id: str, data: ClaimDeterminationInput, actor_id: str
    ) -> ClaimDeterminationView:
        intake = self.session.get(CaseIntakeORM, intake_id)
        if intake is None:
            raise HTTPException(status_code=404, detail="intake not found")
        submissions = self.session.scalars(
            select(ClaimReconstructionSubmissionORM).where(
                ClaimReconstructionSubmissionORM.intake_id == intake_id
            )
        ).all()
        known = {row.submission_id for row in submissions}
        unknown = set(data.selected_submission_ids) - known
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_submission_ids": sorted(unknown)})
        if len(submissions) < 2 and data.status.value != "unresolved":
            raise HTTPException(status_code=409, detail="two reconstructions are required")
        row = ClaimReconstructionDeterminationORM(
            determination_id=new_id("occlaimdet"),
            intake_id=intake_id,
            status=data.status.value,
            canonical_claim_json=(
                data.canonical_claim.model_dump(mode="json") if data.canonical_claim else None
            ),
            submission_ids=data.selected_submission_ids,
            rationale=data.rationale,
            created_by=actor_id,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="claim_reconstruction.determined",
            target_type="claim_determination",
            target_id=row.determination_id,
            event_data={"intake_id": intake_id, "status": row.status},
        )
        self.session.flush()
        return ClaimDeterminationView(
            determination_id=row.determination_id,
            intake_id=row.intake_id,
            status=row.status,
            canonical_claim=row.canonical_claim_json,
            selected_submission_ids=row.submission_ids,
            rationale=row.rationale,
            created_by=row.created_by,
            created_at=as_utc(row.created_at),
        )

    # Credit and compensation -----------------------------------------------------------
    def _record_credit(
        self,
        *,
        actor_id: str,
        contribution_type: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, Any],
    ) -> None:
        existing = self.session.scalar(
            select(ContributionCreditORM).where(
                ContributionCreditORM.actor_id == actor_id,
                ContributionCreditORM.contribution_type == contribution_type,
                ContributionCreditORM.target_id == target_id,
            )
        )
        if existing is not None:
            return
        profile = self.session.get(ExpertProfileORM, actor_id)
        self.session.add(
            ContributionCreditORM(
                credit_id=new_id("occredit"),
                actor_id=actor_id,
                contribution_type=contribution_type,
                target_type=target_type,
                target_id=target_id,
                public_name=profile.attribution_name if profile else None,
                public=profile.public_attribution if profile else False,
                credit_metadata=metadata,
            )
        )

    def credits(self, actor_id: str, public_only: bool = False) -> list[ContributionCreditView]:
        query = select(ContributionCreditORM).where(ContributionCreditORM.actor_id == actor_id)
        if public_only:
            query = query.where(ContributionCreditORM.public.is_(True))
        rows = self.session.scalars(query.order_by(ContributionCreditORM.created_at)).all()
        return [_credit_view(row) for row in rows]

    def create_compensation(self, data: CompensationInput, actor_id: str) -> CompensationView:
        assigned_actor: str | None = None
        completed = False
        if data.task_type == "adjudication":
            task = self.session.get(AdjudicationTaskORM, data.task_id)
            assigned_actor = task.assigned_to if task else None
            completed = bool(task and task.status == TaskStatus.COMPLETED.value)
        elif data.task_type == "calibration":
            task = self.session.get(CalibrationTaskORM, data.task_id)
            attempt = self.session.get(CalibrationAttemptORM, task.attempt_id) if task else None
            assigned_actor = attempt.adjudicator_id if attempt else None
            completed = bool(task and task.status == TaskStatus.COMPLETED.value)
        else:
            task = self.session.get(ClaimReconstructionTaskORM, data.task_id)
            assigned_actor = task.assigned_to if task else None
            completed = bool(task and task.status == TaskStatus.COMPLETED.value)
        if assigned_actor is None:
            raise HTTPException(status_code=404, detail="compensated task not found")
        if assigned_actor != data.actor_id:
            raise HTTPException(status_code=422, detail="task was completed by another expert")
        if not completed:
            raise HTTPException(status_code=409, detail="only completed tasks may be compensated")
        existing = self.session.scalar(
            select(CompensationRecordORM).where(
                CompensationRecordORM.task_type == data.task_type,
                CompensationRecordORM.task_id == data.task_id,
            )
        )
        if existing is not None:
            return _compensation_view(existing)
        row = CompensationRecordORM(
            compensation_id=new_id("ocpay"),
            actor_id=data.actor_id,
            task_type=data.task_type,
            task_id=data.task_id,
            amount_minor=data.amount_minor,
            currency=data.currency,
            status=CompensationStatus.APPROVED.value,
            basis=data.basis,
            approved_by=actor_id,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="compensation.approved",
            target_type="compensation",
            target_id=row.compensation_id,
            event_data={"amount_minor": row.amount_minor, "currency": row.currency},
        )
        self.session.flush()
        return _compensation_view(row)

    def update_compensation(
        self, compensation_id: str, data: CompensationStatusInput, actor_id: str
    ) -> CompensationView:
        row = self.session.get(CompensationRecordORM, compensation_id)
        if row is None:
            raise HTTPException(status_code=404, detail="compensation record not found")
        if row.status != CompensationStatus.APPROVED.value:
            raise HTTPException(status_code=409, detail="compensation status is final")
        row.status = data.status
        row.external_reference = data.external_reference
        if data.status == CompensationStatus.PAID.value:
            row.paid_at = utcnow()
        record_event(
            self.session,
            actor_id=actor_id,
            action=f"compensation.{data.status}",
            target_type="compensation",
            target_id=compensation_id,
            event_data={"external_reference": data.external_reference},
        )
        self.session.flush()
        return _compensation_view(row)

    def compensation(self, actor_id: str) -> list[CompensationView]:
        rows = self.session.scalars(
            select(CompensationRecordORM)
            .where(CompensationRecordORM.actor_id == actor_id)
            .order_by(CompensationRecordORM.created_at)
        ).all()
        return [_compensation_view(row) for row in rows]

    # Analytics -------------------------------------------------------------------------
    def metrics(self) -> CommunityMetrics:
        rows = self.session.scalars(
            select(AdjudicationSubmissionORM)
            .where(
                AdjudicationSubmissionORM.slot.in_(
                    [TaskSlot.PRIMARY.value, TaskSlot.SECONDARY.value]
                )
            )
            .order_by(AdjudicationSubmissionORM.concern_id, AdjudicationSubmissionORM.slot)
        ).all()
        grouped: dict[str, dict[str, AdjudicationSubmissionORM]] = defaultdict(dict)
        for row in rows:
            grouped[row.concern_id][row.slot] = row
        pairs: list[tuple[AdjudicationSubmissionORM, AdjudicationSubmissionORM]] = []
        for slots in grouped.values():
            if TaskSlot.PRIMARY.value in slots and TaskSlot.SECONDARY.value in slots:
                pairs.append((slots[TaskSlot.PRIMARY.value], slots[TaskSlot.SECONDARY.value]))
        validity_pairs: list[tuple[str, str]] = []
        severity_pairs: list[tuple[str, str]] = []
        validity_distribution: Counter[str] = Counter()
        domain_pairs: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
        severity_distances = []
        contested_critical = 0
        tie_breaks = 0
        for left, right in pairs:
            lv = left.decision_json["validity"]
            rv = right.decision_json["validity"]
            ls = left.decision_json["severity"]
            rs = right.decision_json["severity"]
            validity_pairs.append((lv, rv))
            severity_pairs.append((ls, rs))
            validity_distribution[lv] += 1
            validity_distribution[rv] += 1
            severity_distances.append(abs(SEVERITY_ORDER[ls] - SEVERITY_ORDER[rs]))
            contested_critical += int((ls == "critical") != (rs == "critical"))
            tie = self.session.scalar(
                select(AdjudicationTaskORM).where(
                    AdjudicationTaskORM.concern_id == left.concern_id,
                    AdjudicationTaskORM.slot == TaskSlot.TIE_BREAK.value,
                )
            )
            tie_breaks += int(tie is not None)
            case = _case_row(self.session, left.case_id, left.case_version)
            bundle = _bundle(case)
            concern = next(item for item in bundle.concerns if item.concern_id == left.concern_id)
            version = next(
                item
                for item in bundle.manuscript_versions
                if item.version_id == concern.manuscript_version_id
            )
            domain_pairs[version.domain_profile].append((lv, rv, ls, rs))
        n = len(pairs)
        breakdown: dict[str, dict[str, float | int | None]] = {}
        for domain, items in domain_pairs.items():
            vpairs = [(lv, rv) for lv, rv, _, _ in items]
            spairs = [(ls, rs) for _, _, ls, rs in items]
            breakdown[domain] = {
                "paired_concerns": len(items),
                "validity_raw_agreement": sum(a == b for a, b in vpairs) / len(items),
                "validity_cohens_kappa": _kappa(vpairs),
                "severity_exact_agreement": sum(a == b for a, b in spairs) / len(items),
                "severity_cohens_kappa": _kappa(spairs),
            }
        agreement = AgreementMetrics(
            paired_concerns=n,
            validity_raw_agreement=(sum(a == b for a, b in validity_pairs) / n if n else None),
            validity_cohens_kappa=_kappa(validity_pairs),
            severity_exact_agreement=(sum(a == b for a, b in severity_pairs) / n if n else None),
            severity_cohens_kappa=_kappa(severity_pairs),
            severity_mean_absolute_distance=(sum(severity_distances) / n if n else None),
            contested_critical_rate=(contested_critical / n if n else None),
            tie_break_rate=(tie_breaks / n if n else None),
            validity_distribution=dict(validity_distribution),
            domain_breakdown=breakdown,
        )
        attempts = self.session.scalar(select(func.count()).select_from(CalibrationAttemptORM)) or 0
        completed = self.session.scalar(
            select(func.count()).select_from(CalibrationAttemptORM).where(
                CalibrationAttemptORM.status == CalibrationAttemptStatus.COMPLETED.value
            )
        ) or 0
        passed = self.session.scalar(
            select(func.count()).select_from(CalibrationAttemptORM).where(
                CalibrationAttemptORM.passed.is_(True)
            )
        ) or 0
        qualifications = self.session.scalar(
            select(func.count()).select_from(ExpertQualificationORM).where(
                ExpertQualificationORM.status == QualificationStatus.ACTIVE.value
            )
        ) or 0
        calibration = CalibrationMetrics(
            attempts=attempts,
            completed_attempts=completed,
            passed_attempts=passed,
            pass_rate=(passed / completed if completed else None),
            active_qualifications=qualifications,
        )
        credit_count = (
            self.session.scalar(select(func.count()).select_from(ContributionCreditORM))
            or 0
        )
        compensation_rows = self.session.scalars(
            select(CompensationRecordORM).where(
                CompensationRecordORM.status.in_(
                    [CompensationStatus.APPROVED.value, CompensationStatus.PAID.value]
                )
            )
        ).all()
        totals: dict[str, int] = defaultdict(int)
        for row in compensation_rows:
            totals[row.currency] += row.amount_minor
        return CommunityMetrics(
            agreement=agreement,
            calibration=calibration,
            contribution_credits=credit_count,
            approved_compensation_minor_by_currency=dict(totals),
        )
