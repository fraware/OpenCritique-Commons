from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from opencritique_schema.canonical import content_hash
from opencritique_schema.models import (
    ActorReference,
    ActorType,
    Adjudication,
    CaseBundle,
    RightsClassification,
    Severity,
)

from .artifacts import LocalArtifactStore
from .assignment_guards import AssignmentRecord, blocks_duplicate_primary
from .audit import record_event
from .db_models import (
    AdjudicationSubmissionORM,
    AdjudicationTaskORM,
    AppealRecordORM,
    ArtifactCaseLinkORM,
    ArtifactORM,
    CalibrationAttemptORM,
    CalibrationSetORM,
    CalibrationTaskORM,
    CaseIntakeORM,
    CaseORM,
    ClaimReconstructionTaskORM,
    ConcernIndexORM,
    ContributionCreditORM,
    DeterminationORM,
    ExpertProfileORM,
    ExpertQualificationORM,
    PrincipalORM,
    UseGrantORM,
    utcnow,
)
from .determination import determine
from .expert_policy import is_qualification_expired
from .ids import new_id
from .rights import active_grant, require_use_grant
from .schemas import (
    AdjudicationSubmissionInput,
    AppealRecordInput,
    AppealRecordView,
    ArtifactView,
    BlindedAnchor,
    BlindedClaim,
    BlindedCounterposition,
    BlindedEvidence,
    BlindedTaskPayload,
    CaseRegistration,
    CaseView,
    ClaimableTaskView,
    DataUse,
    DeterminationView,
    GrantBasis,
    GrantStatus,
    PrincipalCreate,
    PrincipalRole,
    PrincipalView,
    PriorAdjudicationView,
    RightsGrantInput,
    RightsGrantView,
    TaskSlot,
    TaskStatus,
    TaskView,
)
from .timeutils import as_utc, optional_utc

POLICY_VERSION = "adjudication-v0.2"
PRIMARY_BLINDED_FIELDS = [
    "concern.severity",
    "concern.confidence",
    "concern.verification_grade",
    "concern.status",
    "concern.origin",
    "evidence.producer",
    "evidence.tool_manifest",
    "counterposition.source",
    "reviewer_system_identity",
    "model_identity",
    "other_adjudications",
]
TIE_BREAK_BLINDED_FIELDS = [
    "concern.severity",
    "concern.confidence",
    "concern.verification_grade",
    "concern.status",
    "concern.origin",
    "evidence.producer",
    "evidence.tool_manifest",
    "counterposition.source",
    "reviewer_system_identity",
    "model_identity",
    "adjudicator_identity",
]


def _hashed_model(model_type: type[Adjudication], values: dict[str, Any]) -> Adjudication:
    provisional = model_type.model_validate({**values, "content_hash": "0" * 64})
    return provisional.model_copy(update={"content_hash": provisional.expected_content_hash()})


def _case_row(session: Session, case_id: str, case_version: str) -> CaseORM:
    row = session.scalar(
        select(CaseORM).where(CaseORM.case_id == case_id, CaseORM.case_version == case_version)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="case version not found")
    return row


def _bundle(row: CaseORM) -> CaseBundle:
    return CaseBundle.model_validate(row.bundle_json)


def _task_view(row: AdjudicationTaskORM) -> TaskView:
    return TaskView(
        task_id=row.task_id,
        case_id=row.case_id,
        case_version=row.case_version,
        concern_id=row.concern_id,
        slot=TaskSlot(row.slot),
        status=TaskStatus(row.status),
        assigned_to=row.assigned_to,
        claimed_at=optional_utc(row.claimed_at),
        completed_at=optional_utc(row.completed_at),
    )


def _grant_view(row: UseGrantORM) -> RightsGrantView:
    return RightsGrantView(
        grant_id=row.grant_id,
        case_id=row.case_id,
        case_version=row.case_version,
        use=DataUse(row.use_type),
        basis=GrantBasis(row.basis),
        authority=row.authority,
        scope=row.scope,
        status=GrantStatus(row.status),
        granted_by=row.granted_by,
        created_at=as_utc(row.created_at),
        revoked_at=optional_utc(row.revoked_at),
        expires_at=optional_utc(row.expires_at),
    )


class RegistryService:
    def __init__(self, session: Session, store: LocalArtifactStore) -> None:
        self.session = session
        self.store = store

    def create_principal(self, data: PrincipalCreate, actor_id: str) -> PrincipalView:
        if self.session.get(PrincipalORM, data.actor_id) is not None:
            raise HTTPException(status_code=409, detail="principal already exists")
        row = PrincipalORM(
            actor_id=data.actor_id,
            role=data.role.value,
            display_name=data.display_name,
            active=True,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="principal.created",
            target_type="principal",
            target_id=data.actor_id,
            event_data={"role": data.role.value},
        )
        self.session.flush()
        return PrincipalView(
            actor_id=row.actor_id,
            role=PrincipalRole(row.role),
            display_name=row.display_name,
            active=row.active,
        )

    def put_artifact(
        self,
        *,
        data: bytes,
        media_type: str,
        rights_classification: RightsClassification,
        actor_id: str,
    ) -> ArtifactView:
        digest, path = self.store.put(data)
        row = self.session.get(ArtifactORM, digest)
        if row is None:
            row = ArtifactORM(
                sha256=digest,
                storage_uri=path.as_uri(),
                media_type=media_type,
                byte_size=len(data),
                rights_classification=rights_classification.value,
                created_by=actor_id,
            )
            self.session.add(row)
            record_event(
                self.session,
                actor_id=actor_id,
                action="artifact.created",
                target_type="artifact",
                target_id=digest,
                event_data={"media_type": media_type, "byte_size": len(data)},
            )
            self.session.flush()
        elif row.media_type != media_type or row.byte_size != len(data):
            raise HTTPException(
                status_code=409,
                detail="artifact metadata conflicts with stored object",
            )
        return ArtifactView(
            sha256=row.sha256,
            media_type=row.media_type,
            byte_size=row.byte_size,
            rights_classification=RightsClassification(row.rights_classification),
            download_path=f"/v1/artifacts/{row.sha256}",
        )

    def register_case(self, registration: CaseRegistration, actor_id: str) -> CaseView:
        bundle = registration.bundle
        bundle_digest = content_hash(bundle)
        existing = self.session.scalar(
            select(CaseORM).where(
                CaseORM.case_id == bundle.case_id,
                CaseORM.case_version == bundle.case_version,
            )
        )
        if existing is not None:
            if existing.bundle_hash != bundle_digest:
                raise HTTPException(
                    status_code=409,
                    detail="case identifier/version already exists with different content",
                )
            return self.case_view(existing)

        referenced = self._collect_artifacts(bundle)
        missing = [sha for sha in referenced if self.session.get(ArtifactORM, sha) is None]
        if missing:
            raise HTTPException(
                status_code=422,
                detail={"message": "case references unregistered artifacts", "sha256": missing},
            )

        row = CaseORM(
            case_id=bundle.case_id,
            case_version=bundle.case_version,
            case_type=bundle.case_type,
            rights_classification=bundle.manuscript.rights_classification.value,
            bundle_hash=bundle_digest,
            bundle_json=bundle.model_dump(mode="json"),
            imported_by=actor_id,
        )
        self.session.add(row)
        for concern in bundle.concerns:
            self.session.add(
                ConcernIndexORM(
                    concern_id=concern.concern_id,
                    case_id=bundle.case_id,
                    case_version=bundle.case_version,
                    submitted_severity=concern.severity.value,
                    submitted_confidence=concern.confidence,
                    concern_type=concern.concern_type,
                )
            )
        for sha, purpose in referenced.items():
            self.session.add(
                ArtifactCaseLinkORM(
                    case_id=bundle.case_id,
                    case_version=bundle.case_version,
                    sha256=sha,
                    purpose=purpose,
                )
            )
        self.session.flush()
        for grant in registration.grants:
            self.add_grant(
                case_id=bundle.case_id,
                case_version=bundle.case_version,
                data=grant,
                actor_id=actor_id,
            )
        record_event(
            self.session,
            actor_id=actor_id,
            action="case.registered",
            target_type="case",
            target_id=f"{bundle.case_id}@{bundle.case_version}",
            event_data={"bundle_hash": bundle_digest},
        )
        self.session.flush()
        return self.case_view(row)

    def add_grant(
        self,
        *,
        case_id: str,
        case_version: str,
        data: RightsGrantInput,
        actor_id: str,
    ) -> RightsGrantView:
        _case_row(self.session, case_id, case_version)
        row = UseGrantORM(
            grant_id=new_id("ocgrant"),
            case_id=case_id,
            case_version=case_version,
            use_type=data.use.value,
            basis=data.basis.value,
            authority=data.authority,
            scope=data.scope,
            status=GrantStatus.ACTIVE.value,
            granted_by=actor_id,
            expires_at=data.expires_at,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action="rights.granted",
            target_type="case",
            target_id=f"{case_id}@{case_version}",
            event_data={"grant_id": row.grant_id, "use": data.use.value, "basis": data.basis.value},
        )
        self.session.flush()
        return _grant_view(row)

    def revoke_grant(self, grant_id: str, actor_id: str) -> RightsGrantView:
        row = self.session.get(UseGrantORM, grant_id)
        if row is None:
            raise HTTPException(status_code=404, detail="grant not found")
        if row.status != GrantStatus.ACTIVE.value:
            return _grant_view(row)
        row.status = GrantStatus.REVOKED.value
        row.revoked_at = utcnow()
        self.session.flush()
        if (
            row.use_type == DataUse.EXPERT_ADJUDICATION.value
            and active_grant(
                self.session,
                case_id=row.case_id,
                case_version=row.case_version,
                use=DataUse.EXPERT_ADJUDICATION,
            )
            is None
        ):
            pending = self.session.scalars(
                select(AdjudicationTaskORM).where(
                    AdjudicationTaskORM.case_id == row.case_id,
                    AdjudicationTaskORM.case_version == row.case_version,
                    AdjudicationTaskORM.status.in_(
                        [TaskStatus.PENDING.value, TaskStatus.CLAIMED.value]
                    ),
                )
            ).all()
            for task in pending:
                task.status = TaskStatus.CANCELLED.value
        record_event(
            self.session,
            actor_id=actor_id,
            action="rights.revoked",
            target_type="grant",
            target_id=grant_id,
            event_data={"use": row.use_type},
        )
        self.session.flush()
        return _grant_view(row)

    def list_grants(self, *, case_id: str, case_version: str) -> list[RightsGrantView]:
        _case_row(self.session, case_id, case_version)
        rows = self.session.scalars(
            select(UseGrantORM)
            .where(
                UseGrantORM.case_id == case_id,
                UseGrantORM.case_version == case_version,
            )
            .order_by(UseGrantORM.created_at)
        ).all()
        return [_grant_view(row) for row in rows]

    def list_tasks(self, *, case_id: str, case_version: str) -> list[TaskView]:
        _case_row(self.session, case_id, case_version)
        rows = self.session.scalars(
            select(AdjudicationTaskORM)
            .where(
                AdjudicationTaskORM.case_id == case_id,
                AdjudicationTaskORM.case_version == case_version,
            )
            .order_by(AdjudicationTaskORM.created_at, AdjudicationTaskORM.slot)
        ).all()
        return [_task_view(row) for row in rows]

    def list_claimable_tasks(self, *, limit: int = 50) -> list[ClaimableTaskView]:
        """Return pending adjudication slots with concern titles for Studio UX."""
        rows = self.session.scalars(
            select(AdjudicationTaskORM)
            .where(AdjudicationTaskORM.status == TaskStatus.PENDING.value)
            .order_by(AdjudicationTaskORM.created_at, AdjudicationTaskORM.slot)
            .limit(max(1, min(limit, 200)))
        ).all()
        views: list[ClaimableTaskView] = []
        for row in rows:
            try:
                require_use_grant(
                    self.session,
                    case_id=row.case_id,
                    case_version=row.case_version,
                    use=DataUse.EXPERT_ADJUDICATION,
                )
            except HTTPException:
                continue
            case_row = _case_row(self.session, row.case_id, row.case_version)
            bundle = _bundle(case_row)
            concern = next(
                (item for item in bundle.concerns if item.concern_id == row.concern_id),
                None,
            )
            evidence_class = None
            for note in bundle.known_ambiguities:
                if note.startswith("evidence_class="):
                    evidence_class = note.split("=", 1)[1].strip()
                    break
            views.append(
                ClaimableTaskView(
                    task_id=row.task_id,
                    case_id=row.case_id,
                    case_version=row.case_version,
                    concern_id=row.concern_id,
                    concern_title=concern.title if concern else row.concern_id,
                    slot=TaskSlot(row.slot),
                    status=TaskStatus(row.status),
                    evidence_class=evidence_class,
                )
            )
        return views

    def seed_tasks(
        self,
        *,
        case_id: str,
        case_version: str,
        concern_ids: list[str] | None,
        actor_id: str,
    ) -> list[TaskView]:
        require_use_grant(
            self.session,
            case_id=case_id,
            case_version=case_version,
            use=DataUse.EXPERT_ADJUDICATION,
        )
        row = _case_row(self.session, case_id, case_version)
        bundle = _bundle(row)
        available = {concern.concern_id for concern in bundle.concerns}
        selected = available if concern_ids is None else set(concern_ids)
        unknown = selected - available
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_concern_ids": sorted(unknown)})
        created: list[TaskView] = []
        for concern_id in sorted(selected):
            for slot in (TaskSlot.PRIMARY, TaskSlot.SECONDARY):
                existing = self.session.scalar(
                    select(AdjudicationTaskORM).where(
                        AdjudicationTaskORM.case_id == case_id,
                        AdjudicationTaskORM.case_version == case_version,
                        AdjudicationTaskORM.concern_id == concern_id,
                        AdjudicationTaskORM.slot == slot.value,
                    )
                )
                if existing is not None:
                    created.append(_task_view(existing))
                    continue
                task = AdjudicationTaskORM(
                    task_id=new_id("octask"),
                    case_id=case_id,
                    case_version=case_version,
                    concern_id=concern_id,
                    slot=slot.value,
                    status=TaskStatus.PENDING.value,
                )
                self.session.add(task)
                self.session.flush()
                created.append(_task_view(task))
        record_event(
            self.session,
            actor_id=actor_id,
            action="adjudication.tasks_seeded",
            target_type="case",
            target_id=f"{case_id}@{case_version}",
            event_data={"concern_ids": sorted(selected)},
        )
        return created

    def _adjudicator_is_qualified(self, adjudicator_id: str, domain_profile: str) -> bool:
        active_set = self.session.scalar(
            select(CalibrationSetORM).where(
                CalibrationSetORM.domain_profile == domain_profile,
                CalibrationSetORM.active.is_(True),
            )
        )
        if active_set is None:
            return True
        now = datetime.now(UTC)
        qualifications = self.session.scalars(
            select(ExpertQualificationORM).where(
                ExpertQualificationORM.actor_id == adjudicator_id,
                ExpertQualificationORM.domain_profile == domain_profile,
                ExpertQualificationORM.status == "active",
            )
        ).all()
        active = []
        for item in qualifications:
            if is_qualification_expired(expires_at=optional_utc(item.expires_at), now=now):
                if item.status == "active":
                    item.status = "expired"
                continue
            active.append(item)
        return bool(active)

    def _case_domain_profile(self, case_id: str, case_version: str, concern_id: str) -> str:
        row = _case_row(self.session, case_id, case_version)
        bundle = _bundle(row)
        concern = next(item for item in bundle.concerns if item.concern_id == concern_id)
        version = next(
            item for item in bundle.manuscript_versions
            if item.version_id == concern.manuscript_version_id
        )
        return version.domain_profile

    def claim_task(self, adjudicator_id: str) -> TaskView:
        candidates = self.session.scalars(
            select(AdjudicationTaskORM)
            .where(AdjudicationTaskORM.status == TaskStatus.PENDING.value)
            .order_by(AdjudicationTaskORM.created_at, AdjudicationTaskORM.slot)
            .with_for_update(skip_locked=True)
        ).all()
        for task in candidates:
            try:
                require_use_grant(
                    self.session,
                    case_id=task.case_id,
                    case_version=task.case_version,
                    use=DataUse.EXPERT_ADJUDICATION,
                )
            except HTTPException:
                continue
            domain_profile = self._case_domain_profile(
                task.case_id, task.case_version, task.concern_id
            )
            if not self._adjudicator_is_qualified(adjudicator_id, domain_profile):
                continue
            sibling_rows = self.session.scalars(
                select(AdjudicationTaskORM).where(
                    AdjudicationTaskORM.concern_id == task.concern_id,
                )
            ).all()
            if blocks_duplicate_primary(
                candidate=AssignmentRecord(
                    task_id=task.task_id,
                    concern_id=task.concern_id,
                    slot=task.slot,
                    assigned_to=task.assigned_to,
                    status=task.status,
                ),
                existing=[
                    AssignmentRecord(
                        task_id=row.task_id,
                        concern_id=row.concern_id,
                        slot=row.slot,
                        assigned_to=row.assigned_to,
                        status=row.status,
                    )
                    for row in sibling_rows
                ],
                adjudicator_id=adjudicator_id,
            ):
                continue
            task.status = TaskStatus.CLAIMED.value
            task.assigned_to = adjudicator_id
            task.claimed_at = utcnow()
            record_event(
                self.session,
                actor_id=adjudicator_id,
                action="adjudication.task_claimed",
                target_type="task",
                target_id=task.task_id,
                event_data={"slot": task.slot},
            )
            self.session.flush()
            return _task_view(task)
        raise HTTPException(status_code=404, detail="no eligible adjudication task")

    def build_blinded_payload(
        self,
        *,
        task_id: str,
        slot: TaskSlot,
        case_id: str,
        case_version: str,
        concern_id: str,
        prior_adjudications: list[PriorAdjudicationView] | None = None,
    ) -> BlindedTaskPayload:
        row = _case_row(self.session, case_id, case_version)
        bundle = _bundle(row)
        concern = next(item for item in bundle.concerns if item.concern_id == concern_id)
        claim_ids = set(concern.claim_ids)
        anchor_ids = set(concern.anchor_ids)
        evidence = [item for item in bundle.evidence if item.concern_id == concern.concern_id]
        for item in evidence:
            anchor_ids.update(item.anchor_ids)
        counterpositions = [
            item for item in bundle.counterpositions if item.concern_id == concern.concern_id
        ]
        for item in counterpositions:
            anchor_ids.update(item.supporting_anchor_ids)
        version = next(
            item
            for item in bundle.manuscript_versions
            if item.version_id == concern.manuscript_version_id
        )
        return BlindedTaskPayload(
            task_id=task_id,
            slot=slot,
            case_id=bundle.case_id,
            case_version=bundle.case_version,
            case_type=bundle.case_type,
            manuscript_title=bundle.manuscript.title,
            domain_profile=version.domain_profile,
            language=version.language,
            manuscript_artifact_sha256=version.source_artifact.sha256,
            rendered_artifact_sha256=(
                version.rendered_artifact.sha256 if version.rendered_artifact else None
            ),
            concern_id=concern.concern_id,
            concern_title=concern.title,
            concern_summary=concern.summary,
            concern_type=concern.concern_type,
            proposed_consequence=concern.potential_consequence,
            proposed_resolution=concern.required_resolution,
            uncertainty_sources=concern.uncertainty_sources,
            claims=[
                BlindedClaim(
                    claim_id=item.claim_id,
                    statement=item.statement,
                    claim_type=item.claim_type.value,
                    explicitness=item.explicitness.value,
                    scope=item.scope,
                    anchor_ids=item.anchor_ids,
                    reconstruction_notes=item.reconstruction_notes,
                    approval_status=item.approval_status,
                )
                for item in bundle.claims
                if item.claim_id in claim_ids
            ],
            anchors=[
                BlindedAnchor(
                    anchor_id=item.anchor_id,
                    anchor_type=item.anchor_type,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    bounding_boxes=[box.model_dump(mode="json") for box in item.bounding_boxes],
                    section_path=item.section_path,
                    source_text=item.source_text,
                    normalized_text=item.normalized_text,
                    object_label=item.object_label,
                    object_coordinates=item.object_coordinates,
                    extraction_confidence=item.extraction_confidence,
                    rendered_artifact_sha256=(
                        item.rendered_reference.artifact.sha256
                        if item.rendered_reference is not None
                        else None
                    ),
                    resolution_status=item.resolution_status.value,
                )
                for item in bundle.anchors
                if item.anchor_id in anchor_ids
            ],
            evidence=[
                BlindedEvidence(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type.value,
                    supports=item.supports.value,
                    description=item.description,
                    anchor_ids=item.anchor_ids,
                    method=item.method,
                    reproducibility_status=item.reproducibility_status.value,
                    limitations=item.limitations,
                    independence_group=item.independence_group,
                    artifact_sha256=(
                        item.artifact_reference.sha256 if item.artifact_reference else None
                    ),
                )
                for item in evidence
            ],
            counterpositions=[
                BlindedCounterposition(
                    counterposition_id=item.counterposition_id,
                    statement=item.statement,
                    supporting_anchor_ids=item.supporting_anchor_ids,
                    supporting_evidence_ids=item.supporting_evidence_ids,
                    residual_disagreement=item.residual_disagreement,
                    adequacy_status=item.adequacy_status,
                )
                for item in counterpositions
            ],
            prior_adjudications=prior_adjudications or [],
            blinded_fields=(
                TIE_BREAK_BLINDED_FIELDS if slot == TaskSlot.TIE_BREAK else PRIMARY_BLINDED_FIELDS
            ),
        )

    def task_payload(self, task_id: str, actor_id: str, role: PrincipalRole) -> BlindedTaskPayload:
        task = self.session.get(AdjudicationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        if role == PrincipalRole.ADJUDICATOR and task.assigned_to != actor_id:
            raise HTTPException(status_code=403, detail="task is assigned to another adjudicator")
        prior_views: list[PriorAdjudicationView] = []
        if TaskSlot(task.slot) == TaskSlot.TIE_BREAK:
            submissions = self.session.scalars(
                select(AdjudicationSubmissionORM)
                .where(
                    AdjudicationSubmissionORM.concern_id == task.concern_id,
                    AdjudicationSubmissionORM.slot.in_(
                        [TaskSlot.PRIMARY.value, TaskSlot.SECONDARY.value]
                    ),
                )
                .order_by(AdjudicationSubmissionORM.created_at)
            ).all()
            for submission in submissions:
                adjudication = Adjudication.model_validate(submission.decision_json)
                prior_views.append(
                    PriorAdjudicationView(
                        slot=TaskSlot(submission.slot),
                        validity=adjudication.validity,
                        severity=adjudication.severity,
                        confidence=adjudication.confidence,
                        reasoning=adjudication.reasoning,
                        evidence_ids=adjudication.evidence_ids,
                        counterposition_assessment=adjudication.counterposition_assessment,
                        requested_followup=adjudication.requested_followup,
                    )
                )
        return self.build_blinded_payload(
            task_id=task.task_id,
            slot=TaskSlot(task.slot),
            case_id=task.case_id,
            case_version=task.case_version,
            concern_id=task.concern_id,
            prior_adjudications=prior_views,
        )

    def _record_contribution_credit(
        self,
        *,
        actor_id: str,
        contribution_type: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, Any] | None = None,
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
                public_name=(profile.attribution_name if profile else None),
                public=(profile.public_attribution if profile else False),
                credit_metadata=metadata or {},
            )
        )

    def submit_adjudication(
        self,
        *,
        task_id: str,
        data: AdjudicationSubmissionInput,
        actor_id: str,
    ) -> tuple[Adjudication, TaskView, DeterminationView]:
        task = self.session.get(AdjudicationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        if task.assigned_to != actor_id:
            raise HTTPException(status_code=403, detail="task is assigned to another adjudicator")
        if task.status != TaskStatus.CLAIMED.value:
            raise HTTPException(status_code=409, detail="task is not claimable for submission")
        require_use_grant(
            self.session,
            case_id=task.case_id,
            case_version=task.case_version,
            use=DataUse.EXPERT_ADJUDICATION,
        )
        if not data.evidence_ids and not data.requested_followup:
            raise HTTPException(
                status_code=422,
                detail="adjudication must cite evidence or request follow-up evidence",
            )
        row = _case_row(self.session, task.case_id, task.case_version)
        bundle = _bundle(row)
        concern = next(item for item in bundle.concerns if item.concern_id == task.concern_id)
        valid_evidence = {
            item.evidence_id for item in bundle.evidence if item.concern_id == concern.concern_id
        }
        unknown = set(data.evidence_ids) - valid_evidence
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_evidence_ids": sorted(unknown)})
        if (
            concern.severity.value in {"major", "critical"}
            and not data.counterposition_assessment.strip()
        ):
            raise HTTPException(status_code=422, detail="counterposition assessment is required")
        if (
            data.conflict_declaration.status == "disclosed"
            and not data.conflict_declaration.description.strip()
        ):
            raise HTTPException(
                status_code=422,
                detail="disclosed conflicts require a non-empty description",
            )
        if data.conflict_declaration.status == "disqualifying":
            raise HTTPException(
                status_code=409,
                detail="disqualifying conflict requires reassignment",
            )
        adjudication_id = new_id("ocj")
        adjudication = _hashed_model(
            Adjudication,
            {
                "id": adjudication_id,
                "adjudication_id": adjudication_id,
                "schema_version": "0.1.0",
                "created_at": datetime.now(UTC),
                "created_by": ActorReference(
                    actor_id=actor_id,
                    actor_type=ActorType.HUMAN,
                    display_name=None,
                ),
                "concern_id": task.concern_id,
                "adjudicator_id": actor_id,
                "adjudication_round": 2 if task.slot == TaskSlot.TIE_BREAK.value else 1,
                "blinded_fields": (
                    TIE_BREAK_BLINDED_FIELDS
                    if task.slot == TaskSlot.TIE_BREAK.value
                    else PRIMARY_BLINDED_FIELDS
                ),
                "conflict_declaration": data.conflict_declaration,
                "validity": data.validity,
                "severity": data.severity,
                "confidence": data.confidence,
                "reasoning": data.reasoning,
                "evidence_ids": data.evidence_ids,
                "counterposition_assessment": data.counterposition_assessment,
                "requested_followup": data.requested_followup,
                "anchors_reviewed": data.anchors_reviewed,
            },
        )
        self.session.add(
            AdjudicationSubmissionORM(
                adjudication_id=adjudication.adjudication_id,
                task_id=task.task_id,
                case_id=task.case_id,
                case_version=task.case_version,
                concern_id=task.concern_id,
                adjudicator_id=actor_id,
                slot=task.slot,
                decision_json=adjudication.model_dump(mode="json"),
                content_hash=adjudication.content_hash,
            )
        )
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = utcnow()
        self._record_contribution_credit(
            actor_id=actor_id,
            contribution_type="scientific_adjudication",
            target_type="adjudication",
            target_id=adjudication.adjudication_id,
            metadata={"case_id": task.case_id, "concern_id": task.concern_id, "slot": task.slot},
        )
        record_event(
            self.session,
            actor_id=actor_id,
            action="adjudication.submitted",
            target_type="adjudication",
            target_id=adjudication.adjudication_id,
            event_data={"task_id": task.task_id, "slot": task.slot},
        )
        self.session.flush()
        determination = self._recompute_determination(
            task.concern_id, task.case_id, task.case_version
        )
        return adjudication, _task_view(task), determination

    def latest_determination(self, concern_id: str) -> DeterminationView:
        row = self.session.scalar(
            select(DeterminationORM)
            .where(DeterminationORM.concern_id == concern_id)
            .order_by(DeterminationORM.created_at.desc())
        )
        if row is None:
            raise HTTPException(status_code=404, detail="determination not found")
        return self._determination_view(row)

    def create_appeal_record(self, data: AppealRecordInput, actor_id: str) -> AppealRecordView:
        determination = self.session.get(DeterminationORM, data.determination_id)
        if determination is None:
            raise HTTPException(status_code=404, detail="determination not found")
        if determination.concern_id != data.concern_id:
            raise HTTPException(status_code=422, detail="determination does not match concern_id")
        if data.predecessor_record_id is not None:
            predecessor = self.session.get(AppealRecordORM, data.predecessor_record_id)
            if predecessor is None:
                raise HTTPException(status_code=404, detail="predecessor appeal record not found")
            if predecessor.concern_id != data.concern_id:
                raise HTTPException(
                    status_code=422, detail="predecessor record does not match concern"
                )
        row = AppealRecordORM(
            record_id=new_id("ocapp"),
            case_id=determination.case_id,
            case_version=determination.case_version,
            concern_id=data.concern_id,
            determination_id=data.determination_id,
            record_type=data.record_type,
            predecessor_record_id=data.predecessor_record_id,
            requested_by=data.requested_by,
            rationale=data.rationale,
            payload_json=data.payload,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id=actor_id,
            action=f"{data.record_type}.recorded",
            target_type=data.record_type,
            target_id=row.record_id,
            event_data={
                "concern_id": data.concern_id,
                "determination_id": data.determination_id,
                "predecessor_record_id": data.predecessor_record_id,
            },
        )
        self.session.flush()
        return self._appeal_view(row)

    def list_appeal_records(self, concern_id: str) -> list[AppealRecordView]:
        rows = self.session.scalars(
            select(AppealRecordORM)
            .where(AppealRecordORM.concern_id == concern_id)
            .order_by(AppealRecordORM.created_at)
        ).all()
        return [self._appeal_view(row) for row in rows]

    def can_read_case(
        self,
        *,
        case_id: str,
        case_version: str,
        actor_id: str,
        role: PrincipalRole,
        concern_id: str | None = None,
    ) -> bool:
        if role in {PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER, PrincipalRole.AUDITOR}:
            return True
        if role in {PrincipalRole.PUBLIC, PrincipalRole.DEVELOPER}:
            try:
                require_use_grant(
                    self.session,
                    case_id=case_id,
                    case_version=case_version,
                    use=DataUse.PUBLIC_RELEASE,
                )
                return True
            except HTTPException:
                return False
        if role == PrincipalRole.ADJUDICATOR:
            query = select(AdjudicationTaskORM).where(
                AdjudicationTaskORM.case_id == case_id,
                AdjudicationTaskORM.case_version == case_version,
                AdjudicationTaskORM.assigned_to == actor_id,
                AdjudicationTaskORM.status.in_(
                    [TaskStatus.CLAIMED.value, TaskStatus.COMPLETED.value]
                ),
            )
            if concern_id is not None:
                query = query.where(AdjudicationTaskORM.concern_id == concern_id)
            return self.session.scalar(query) is not None
        return False

    def can_read_artifact(self, sha256: str, actor_id: str, role: PrincipalRole) -> bool:
        artifact = self.session.get(ArtifactORM, sha256)
        if artifact is None:
            return False
        if role in {PrincipalRole.ADMIN, PrincipalRole.CASE_MANAGER, PrincipalRole.AUDITOR}:
            return True
        links = self.session.scalars(
            select(ArtifactCaseLinkORM).where(ArtifactCaseLinkORM.sha256 == sha256)
        ).all()
        if role in {PrincipalRole.PUBLIC, PrincipalRole.DEVELOPER}:
            for link in links:
                try:
                    require_use_grant(
                        self.session,
                        case_id=link.case_id,
                        case_version=link.case_version,
                        use=DataUse.PUBLIC_RELEASE,
                    )
                    return True
                except HTTPException:
                    continue
            return False
        if role == PrincipalRole.ADJUDICATOR:
            for link in links:
                task = self.session.scalar(
                    select(AdjudicationTaskORM).where(
                        AdjudicationTaskORM.case_id == link.case_id,
                        AdjudicationTaskORM.case_version == link.case_version,
                        AdjudicationTaskORM.assigned_to == actor_id,
                        AdjudicationTaskORM.status.in_(
                            [TaskStatus.CLAIMED.value, TaskStatus.COMPLETED.value]
                        ),
                    )
                )
                if task is not None:
                    return True
                calibration = self.session.scalar(
                    select(CalibrationTaskORM)
                    .join(
                        CalibrationAttemptORM,
                        CalibrationAttemptORM.attempt_id == CalibrationTaskORM.attempt_id,
                    )
                    .where(
                        CalibrationTaskORM.case_id == link.case_id,
                        CalibrationTaskORM.case_version == link.case_version,
                        CalibrationAttemptORM.adjudicator_id == actor_id,
                        CalibrationTaskORM.status.in_(
                            [TaskStatus.PENDING.value, TaskStatus.COMPLETED.value]
                        ),
                    )
                )
                if calibration is not None:
                    return True
            intake_task = self.session.scalar(
                select(ClaimReconstructionTaskORM)
                .join(
                    CaseIntakeORM,
                    CaseIntakeORM.intake_id == ClaimReconstructionTaskORM.intake_id,
                )
                .where(
                    CaseIntakeORM.source_artifact_sha256 == sha256,
                    ClaimReconstructionTaskORM.assigned_to == actor_id,
                    ClaimReconstructionTaskORM.status.in_(
                        [TaskStatus.CLAIMED.value, TaskStatus.COMPLETED.value]
                    ),
                )
            )
            if intake_task is not None:
                return True
        if role == PrincipalRole.CONTRIBUTOR:
            intake = self.session.scalar(
                select(CaseIntakeORM).where(
                    CaseIntakeORM.source_artifact_sha256 == sha256,
                    CaseIntakeORM.submitted_by == actor_id,
                )
            )
            return intake is not None or artifact.created_by == actor_id
        return False

    def case_view(self, row: CaseORM) -> CaseView:
        return CaseView(
            case_id=row.case_id,
            case_version=row.case_version,
            case_type=row.case_type,
            rights_classification=RightsClassification(row.rights_classification),
            bundle_hash=row.bundle_hash,
            imported_at=as_utc(row.imported_at),
            imported_by=row.imported_by,
        )

    def _recompute_determination(
        self, concern_id: str, case_id: str, case_version: str
    ) -> DeterminationView:
        rows = self.session.scalars(
            select(AdjudicationSubmissionORM)
            .where(AdjudicationSubmissionORM.concern_id == concern_id)
            .order_by(AdjudicationSubmissionORM.created_at)
        ).all()
        submissions = [
            (TaskSlot(row.slot), Adjudication.model_validate(row.decision_json)) for row in rows
        ]
        result = determine(submissions)
        determination = DeterminationORM(
            determination_id=new_id("ocdet"),
            case_id=case_id,
            case_version=case_version,
            concern_id=concern_id,
            policy_version=POLICY_VERSION,
            status=result.status.value,
            severity=result.severity.value if result.severity else None,
            requires_tie_break=result.requires_tie_break,
            rationale=result.rationale,
            submission_ids=[row.adjudication_id for row in rows],
        )
        self.session.add(determination)
        if result.requires_tie_break:
            existing = self.session.scalar(
                select(AdjudicationTaskORM).where(
                    AdjudicationTaskORM.case_id == case_id,
                    AdjudicationTaskORM.case_version == case_version,
                    AdjudicationTaskORM.concern_id == concern_id,
                    AdjudicationTaskORM.slot == TaskSlot.TIE_BREAK.value,
                )
            )
            if existing is None:
                self.session.add(
                    AdjudicationTaskORM(
                        task_id=new_id("octask"),
                        case_id=case_id,
                        case_version=case_version,
                        concern_id=concern_id,
                        slot=TaskSlot.TIE_BREAK.value,
                        status=TaskStatus.PENDING.value,
                    )
                )
        record_event(
            self.session,
            actor_id="system:determination-policy",
            action="determination.computed",
            target_type="concern",
            target_id=concern_id,
            event_data={
                "status": result.status.value,
                "severity": result.severity.value if result.severity else None,
                "requires_tie_break": result.requires_tie_break,
                "policy_version": POLICY_VERSION,
            },
        )
        self.session.flush()
        return self._determination_view(determination)

    @staticmethod
    def _determination_view(row: DeterminationORM) -> DeterminationView:
        return DeterminationView(
            determination_id=row.determination_id,
            case_id=row.case_id,
            case_version=row.case_version,
            concern_id=row.concern_id,
            policy_version=row.policy_version,
            status=row.status,
            severity=Severity(row.severity) if row.severity is not None else None,
            requires_tie_break=row.requires_tie_break,
            rationale=row.rationale,
            submission_ids=row.submission_ids,
            created_at=as_utc(row.created_at),
        )

    @staticmethod
    def _appeal_view(row: AppealRecordORM) -> AppealRecordView:
        return AppealRecordView(
            record_id=row.record_id,
            case_id=row.case_id,
            case_version=row.case_version,
            concern_id=row.concern_id,
            determination_id=row.determination_id,
            record_type=cast(Literal["appeal", "correction"], row.record_type),
            predecessor_record_id=row.predecessor_record_id,
            requested_by=row.requested_by,
            rationale=row.rationale,
            payload=row.payload_json,
            created_at=as_utc(row.created_at),
        )

    @staticmethod
    def _collect_artifacts(bundle: CaseBundle) -> dict[str, str]:
        artifacts: dict[str, str] = {}
        for version in bundle.manuscript_versions:
            artifacts[version.source_artifact.sha256] = "manuscript_source"
            if version.rendered_artifact:
                artifacts[version.rendered_artifact.sha256] = "manuscript_render"
            if version.extracted_artifact:
                artifacts[version.extracted_artifact.sha256] = "manuscript_extraction"
        for anchor in bundle.anchors:
            if anchor.rendered_reference:
                artifacts[anchor.rendered_reference.artifact.sha256] = "anchor_render"
        for evidence in bundle.evidence:
            if evidence.artifact_reference:
                artifacts[evidence.artifact_reference.sha256] = "evidence"
        return artifacts
