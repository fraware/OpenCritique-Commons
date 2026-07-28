"""Registry workflows for append-only novel-concern determinations."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from opencritique_evaluation.models import (
    BenchmarkManifest,
    NovelConcernCandidate,
    NovelConcernDetermination,
    NovelConcernQueue,
    NovelDeterminationOutcome,
    NovelPrimaryDecision,
    PublicScorecard,
)
from opencritique_evaluation.novel_determination import (
    NOVEL_POLICY_VERSION,
    PRIMARY_BLINDED_FIELDS,
    SCORING_POLICY_VERSION,
    TIE_BREAK_BLINDED_FIELDS,
    apply_candidate_state,
    build_determination,
    bump_benchmark_version,
    candidate_snapshot_hash,
    determine_novel,
    requires_two_primaries,
    scorecard_hash,
)
from opencritique_schema.canonical import content_hash
from opencritique_schema.models import Severity

from .audit import record_event
from .db_models import (
    BenchmarkVersionORM,
    NovelAdjudicationSubmissionORM,
    NovelAdjudicationTaskORM,
    NovelCandidateORM,
    NovelDeterminationORM,
    ScorecardRecordORM,
    utcnow,
)
from .ids import new_id
from .schemas import TaskSlot, TaskStatus


class NovelDeterminationService:
    """Persist novel candidates, blinded tasks, and append-only determinations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register_scorecard(self, scorecard: PublicScorecard) -> ScorecardRecordORM:
        if scorecard.scorecard_id is None:
            raise HTTPException(status_code=422, detail="scorecard_id is required")
        existing = self.session.get(ScorecardRecordORM, scorecard.scorecard_id)
        if existing is not None:
            if existing.scorecard_hash != scorecard_hash(scorecard):
                raise HTTPException(
                    status_code=409,
                    detail="historical scorecard is immutable and content differs",
                )
            return existing
        row = ScorecardRecordORM(
            scorecard_id=scorecard.scorecard_id,
            scorecard_hash=scorecard_hash(scorecard),
            scorecard_json=scorecard.model_dump(mode="json"),
            result_id=scorecard.result.result_id,
            benchmark_id=scorecard.result.benchmark.benchmark_id,
            benchmark_version=scorecard.result.benchmark.version,
            reference_set_hash=scorecard.reference_set_hash
            or scorecard.result.benchmark.case_set_hash,
            scoring_policy_version=scorecard.scoring_policy_version or SCORING_POLICY_VERSION,
            predecessor_scorecard_id=scorecard.predecessor_scorecard_id,
            predecessor_scorecard_hash=scorecard.predecessor_scorecard_hash,
        )
        self.session.add(row)
        record_event(
            self.session,
            actor_id="system:scorecard",
            action="scorecard.registered",
            target_type="scorecard",
            target_id=scorecard.scorecard_id,
            event_data={"immutable": True},
        )
        self.session.flush()
        return row

    def register_benchmark(
        self,
        manifest: BenchmarkManifest,
        *,
        predecessor_version: str | None = None,
        determination_id: str | None = None,
    ) -> BenchmarkVersionORM:
        existing = self.session.scalar(
            select(BenchmarkVersionORM).where(
                BenchmarkVersionORM.benchmark_id == manifest.benchmark_id,
                BenchmarkVersionORM.version == manifest.version,
            )
        )
        if existing is not None:
            if existing.case_set_hash != manifest.case_set_hash:
                raise HTTPException(
                    status_code=409,
                    detail="benchmark version is immutable and case_set_hash differs",
                )
            return existing
        row = BenchmarkVersionORM(
            benchmark_id=manifest.benchmark_id,
            version=manifest.version,
            case_set_hash=manifest.case_set_hash,
            manifest_json=manifest.model_dump(mode="json"),
            predecessor_version=predecessor_version,
            created_from_determination_id=determination_id,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def ingest_queue(
        self,
        queue: NovelConcernQueue,
        *,
        matcher_version: str,
        matcher_config_id: str,
        benchmark: BenchmarkManifest,
        seed_tasks: bool = True,
    ) -> list[NovelCandidateORM]:
        rows: list[NovelCandidateORM] = []
        for candidate in queue.candidates:
            existing = self.session.get(NovelCandidateORM, candidate.candidate_id)
            if existing is not None:
                if existing.candidate_hash != candidate_snapshot_hash(candidate):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"candidate {candidate.candidate_id} is immutable "
                            "and content differs"
                        ),
                    )
                rows.append(existing)
                continue
            row = NovelCandidateORM(
                candidate_id=candidate.candidate_id,
                result_id=candidate.result_id,
                submission_id=candidate.submission_id,
                case_id=candidate.case_id,
                case_version=candidate.case_version,
                state=candidate.state.value,
                candidate_json=candidate.model_dump(mode="json"),
                candidate_hash=candidate_snapshot_hash(candidate),
                source_result_hash=queue.source_result_hash,
                source_submission_hash=queue.source_submission_hash,
                matcher_version=matcher_version,
                matcher_config_id=matcher_config_id,
                benchmark_id=benchmark.benchmark_id,
                benchmark_version=benchmark.version,
            )
            self.session.add(row)
            if seed_tasks and requires_two_primaries(candidate.concern.severity):
                for slot in (TaskSlot.PRIMARY, TaskSlot.SECONDARY):
                    self.session.add(
                        NovelAdjudicationTaskORM(
                            task_id=new_id("ocntask"),
                            candidate_id=candidate.candidate_id,
                            slot=slot.value,
                            status=TaskStatus.PENDING.value,
                        )
                    )
            elif seed_tasks:
                self.session.add(
                    NovelAdjudicationTaskORM(
                        task_id=new_id("ocntask"),
                        candidate_id=candidate.candidate_id,
                        slot=TaskSlot.PRIMARY.value,
                        status=TaskStatus.PENDING.value,
                    )
                )
            record_event(
                self.session,
                actor_id="system:novel-queue",
                action="novel_candidate.ingested",
                target_type="novel_candidate",
                target_id=candidate.candidate_id,
                event_data={"severity": candidate.concern.severity.value},
            )
            rows.append(row)
        self.session.flush()
        return rows

    def claim_task(self, *, task_id: str, actor_id: str) -> NovelAdjudicationTaskORM:
        task = self.session.get(NovelAdjudicationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="novel task not found")
        if task.status != TaskStatus.PENDING.value:
            raise HTTPException(status_code=409, detail="novel task is not pending")
        primaries = self.session.scalars(
            select(NovelAdjudicationSubmissionORM).where(
                NovelAdjudicationSubmissionORM.candidate_id == task.candidate_id,
                NovelAdjudicationSubmissionORM.slot.in_(
                    [TaskSlot.PRIMARY.value, TaskSlot.SECONDARY.value]
                ),
            )
        ).all()
        if any(row.adjudicator_id == actor_id for row in primaries):
            raise HTTPException(
                status_code=409,
                detail="expert already adjudicated this candidate in the primary round",
            )
        task.status = TaskStatus.CLAIMED.value
        task.assigned_to = actor_id
        task.claimed_at = utcnow()
        self.session.flush()
        return task

    def blinded_payload(self, task_id: str) -> dict:
        task = self.session.get(NovelAdjudicationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="novel task not found")
        candidate_row = self.session.get(NovelCandidateORM, task.candidate_id)
        if candidate_row is None:
            raise HTTPException(status_code=404, detail="novel candidate not found")
        candidate = NovelConcernCandidate.model_validate(candidate_row.candidate_json)
        concern = candidate.concern.model_dump(mode="json")
        # Blinding invariants: strip severity/confidence and system/model identity.
        concern.pop("severity", None)
        concern.pop("confidence", None)
        if task.slot == TaskSlot.TIE_BREAK.value:
            blinded = TIE_BREAK_BLINDED_FIELDS
        else:
            blinded = PRIMARY_BLINDED_FIELDS
        return {
            "task_id": task.task_id,
            "candidate_id": candidate.candidate_id,
            "case_id": candidate.case_id,
            "case_version": candidate.case_version,
            "slot": task.slot,
            "blinded_fields": blinded,
            "concern": {
                "local_id": concern["local_id"],
                "title": concern["title"],
                "summary": concern["summary"],
                "concern_type": concern["concern_type"],
                "anchors": concern["anchors"],
                "evidence_summary": concern.get("evidence_summary", ""),
            },
            "anchor_resolutions": [
                item.model_dump(mode="json") for item in candidate.anchor_resolutions
            ],
        }

    def submit_decision(
        self,
        *,
        task_id: str,
        actor_id: str,
        validity: NovelDeterminationOutcome,
        severity: Severity,
        confidence: float,
        reasoning: str,
        original_scorecard: PublicScorecard | None = None,
        recompute_result_factory=None,
    ) -> NovelConcernDetermination:
        task = self.session.get(NovelAdjudicationTaskORM, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="novel task not found")
        if task.assigned_to != actor_id:
            raise HTTPException(status_code=403, detail="task assigned to another adjudicator")
        if task.status != TaskStatus.CLAIMED.value:
            raise HTTPException(status_code=409, detail="task is not claimable for submission")
        candidate_row = self.session.get(NovelCandidateORM, task.candidate_id)
        if candidate_row is None:
            raise HTTPException(status_code=404, detail="novel candidate not found")
        if self._has_finalized_determination(task.candidate_id):
            raise HTTPException(
                status_code=409,
                detail="candidate already has a finalized determination",
            )

        blinded = (
            TIE_BREAK_BLINDED_FIELDS
            if task.slot == TaskSlot.TIE_BREAK.value
            else PRIMARY_BLINDED_FIELDS
        )
        provisional = {
            "adjudicator_id": actor_id,
            "slot": task.slot,
            "validity": validity.value,
            "severity": severity.value,
            "confidence": confidence,
            "reasoning": reasoning,
            "blinded_fields": blinded,
            "content_hash": "0" * 64,
        }
        digest = content_hash({k: v for k, v in provisional.items() if k != "content_hash"})
        decision = NovelPrimaryDecision.model_validate({**provisional, "content_hash": digest})
        decision_id = new_id("ocndec")
        self.session.add(
            NovelAdjudicationSubmissionORM(
                decision_id=decision_id,
                task_id=task.task_id,
                candidate_id=task.candidate_id,
                adjudicator_id=actor_id,
                slot=task.slot,
                decision_json=decision.model_dump(mode="json"),
                content_hash=decision.content_hash,
            )
        )
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = utcnow()
        self.session.flush()
        return self._recompute(
            candidate_row=candidate_row,
            original_scorecard=original_scorecard,
            recompute_result_factory=recompute_result_factory,
        )

    def _has_finalized_determination(self, candidate_id: str) -> bool:
        row = self.session.scalar(
            select(NovelDeterminationORM)
            .where(
                NovelDeterminationORM.candidate_id == candidate_id,
                NovelDeterminationORM.finalized.is_(True),
            )
            .order_by(NovelDeterminationORM.created_at.desc())
        )
        return row is not None

    def _recompute(
        self,
        *,
        candidate_row: NovelCandidateORM,
        original_scorecard: PublicScorecard | None,
        recompute_result_factory,
    ) -> NovelConcernDetermination:
        submissions = self.session.scalars(
            select(NovelAdjudicationSubmissionORM)
            .where(NovelAdjudicationSubmissionORM.candidate_id == candidate_row.candidate_id)
            .order_by(NovelAdjudicationSubmissionORM.created_at)
        ).all()
        decisions = [
            NovelPrimaryDecision.model_validate(row.decision_json) for row in submissions
        ]
        candidate = NovelConcernCandidate.model_validate(candidate_row.candidate_json)
        policy_outcome = determine_novel(
            decisions,
            require_two_primaries=requires_two_primaries(candidate.concern.severity),
        )
        queue = NovelConcernQueue(
            result_id=candidate.result_id,
            submission_id=candidate.submission_id,
            candidates=[candidate],
            source_result_hash=candidate_row.source_result_hash,
            source_submission_hash=candidate_row.source_submission_hash,
        )
        benchmark = BenchmarkManifest.model_validate(
            {
                "benchmark_id": candidate_row.benchmark_id,
                "version": candidate_row.benchmark_version,
                "title": "registered",
                "description": "registered benchmark stub for determination metadata",
                "evidence_class": "synthetic_scientific",
                "reference_completeness": "partial_natural",
                "domain_profiles": ["general"],
                "cases": [
                    {
                        "case_id": candidate.case_id,
                        "case_version": candidate.case_version,
                        "path": "case.json",
                    }
                ],
                "license": "Apache-2.0",
                "case_set_hash": "0" * 64,
                "created_at": candidate.created_at,
            }
        )
        # Prefer registered benchmark if present.
        registered = self.session.scalar(
            select(BenchmarkVersionORM).where(
                BenchmarkVersionORM.benchmark_id == candidate_row.benchmark_id,
                BenchmarkVersionORM.version == candidate_row.benchmark_version,
            )
        )
        if registered is not None:
            benchmark = BenchmarkManifest.model_validate(registered.manifest_json)

        successor = None
        recompute_scorecard = None
        determination_id = new_id("ocndet")
        if (
            policy_outcome.finalized
            and policy_outcome.outcome == NovelDeterminationOutcome.CONFIRMED
            and original_scorecard is not None
        ):
            successor = bump_benchmark_version(
                benchmark,
                new_version=f"{benchmark.version}+novel-{candidate.candidate_id[-8:]}",
            )
            self.register_benchmark(
                successor,
                predecessor_version=benchmark.version,
                determination_id=determination_id,
            )
            if recompute_result_factory is not None:
                updated_result = recompute_result_factory(successor)
                from opencritique_evaluation.novel_determination import (
                    recompute_scorecard_with_successor,
                )

                recompute_scorecard = recompute_scorecard_with_successor(
                    original_scorecard=original_scorecard,
                    successor_benchmark=successor,
                    updated_result=updated_result,
                )
                self.register_scorecard(recompute_scorecard)

        if policy_outcome.requires_tie_break:
            existing_tie = self.session.scalar(
                select(NovelAdjudicationTaskORM).where(
                    NovelAdjudicationTaskORM.candidate_id == candidate.candidate_id,
                    NovelAdjudicationTaskORM.slot == TaskSlot.TIE_BREAK.value,
                )
            )
            if existing_tie is None:
                self.session.add(
                    NovelAdjudicationTaskORM(
                        task_id=new_id("ocntask"),
                        candidate_id=candidate.candidate_id,
                        slot=TaskSlot.TIE_BREAK.value,
                        status=TaskStatus.PENDING.value,
                    )
                )

        determination = build_determination(
            determination_id=determination_id,
            queue=queue,
            candidate=candidate,
            decisions=decisions,
            policy=policy_outcome,
            matcher_version=candidate_row.matcher_version,
            matcher_config_id=candidate_row.matcher_config_id,
            benchmark=benchmark,
            decision_ids=[row.decision_id for row in submissions],
            original_scorecard=original_scorecard,
            successor_benchmark=successor,
            recompute_scorecard=recompute_scorecard,
        )
        # Never update prior determination rows; append only.
        self.session.add(
            NovelDeterminationORM(
                determination_id=determination.determination_id,
                candidate_id=determination.candidate_id,
                determination_json=determination.model_dump(mode="json"),
                determination_hash=content_hash(determination),
                outcome=determination.outcome.value,
                finalized=determination.finalized,
                requires_tie_break=determination.requires_tie_break,
                policy_version=determination.policy_version,
            )
        )
        if policy_outcome.finalized:
            updated = apply_candidate_state(
                candidate, policy_outcome.outcome, finalized=True
            )
            # Candidate JSON is immutable after ingest; state transitions are recorded via
            # append-only determinations. Keep ORM state column as a denormalized index only
            # when the snapshot hash still matches the ingested candidate body.
            candidate_row.state = updated.state.value
        record_event(
            self.session,
            actor_id="system:novel-determination",
            action="novel_determination.computed",
            target_type="novel_candidate",
            target_id=candidate.candidate_id,
            event_data={
                "determination_id": determination.determination_id,
                "outcome": determination.outcome.value,
                "finalized": determination.finalized,
                "requires_tie_break": determination.requires_tie_break,
                "policy_version": NOVEL_POLICY_VERSION,
            },
        )
        self.session.flush()
        return determination

    def latest_determination(self, candidate_id: str) -> NovelConcernDetermination:
        row = self.session.scalar(
            select(NovelDeterminationORM)
            .where(NovelDeterminationORM.candidate_id == candidate_id)
            .order_by(NovelDeterminationORM.created_at.desc())
        )
        if row is None:
            raise HTTPException(status_code=404, detail="novel determination not found")
        return NovelConcernDetermination.model_validate(row.determination_json)
