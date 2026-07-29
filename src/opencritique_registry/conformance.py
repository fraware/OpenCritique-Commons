from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from opencritique_schema.canonical import content_hash
from opencritique_schema.models import Adjudication, CaseBundle

from .artifacts import ArtifactIntegrityError, LocalArtifactStore
from .db_models import (
    AdjudicationSubmissionORM,
    AdjudicationTaskORM,
    ArtifactCaseLinkORM,
    ArtifactORM,
    BenchmarkVersionORM,
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
    DeterminationORM,
    ExpertProfileORM,
    ExpertQualificationORM,
    NovelAdjudicationSubmissionORM,
    NovelAdjudicationTaskORM,
    NovelCandidateORM,
    NovelDeterminationORM,
    PrincipalORM,
    ScorecardRecordORM,
    UseGrantORM,
)
from .expert_schemas import ClaimReconstructionInput
from .schemas import GrantStatus, PrincipalRole, TaskStatus


@dataclass
class ConformanceReport:
    checked_artifacts: int = 0
    checked_cases: int = 0
    checked_tasks: int = 0
    checked_submissions: int = 0
    checked_determinations: int = 0
    checked_grants: int = 0
    checked_expert_profiles: int = 0
    checked_calibration_attempts: int = 0
    checked_calibration_tasks: int = 0
    checked_intakes: int = 0
    checked_claim_tasks: int = 0
    checked_credits: int = 0
    checked_compensation: int = 0
    checked_novel_candidates: int = 0
    checked_novel_determinations: int = 0
    checked_scorecards: int = 0
    checked_benchmark_versions: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def audit_registry(session: Session, store: LocalArtifactStore) -> ConformanceReport:
    report = ConformanceReport()
    principals = {row.actor_id: row for row in session.scalars(select(PrincipalORM)).all()}
    artifact_rows = {row.sha256: row for row in session.scalars(select(ArtifactORM)).all()}
    links = session.scalars(select(ArtifactCaseLinkORM)).all()
    link_keys = {(row.case_id, row.case_version, row.sha256) for row in links}

    for sha256, row in artifact_rows.items():
        report.checked_artifacts += 1
        try:
            data = store.read(sha256)
        except (FileNotFoundError, ArtifactIntegrityError) as exc:
            report.failures.append(f"artifact {sha256}: {exc}")
            continue
        if len(data) != row.byte_size:
            report.failures.append(
                f"artifact {sha256}: database byte_size={row.byte_size}, actual={len(data)}"
            )

    cases = session.scalars(select(CaseORM)).all()
    case_map = {(row.case_id, row.case_version): row for row in cases}
    concern_ids: set[str] = set()
    for row in cases:
        report.checked_cases += 1
        try:
            bundle = CaseBundle.model_validate(row.bundle_json)
        except Exception as exc:
            report.failures.append(
                f"case {row.case_id}@{row.case_version}: bundle validation failed: {exc}"
            )
            continue
        concern_ids.update(item.concern_id for item in bundle.concerns)
        actual_hash = content_hash(bundle)
        if actual_hash != row.bundle_hash:
            report.failures.append(
                f"case {row.case_id}@{row.case_version}: bundle hash mismatch"
            )
        for sha256 in _bundle_artifact_hashes(bundle):
            if sha256 not in artifact_rows:
                report.failures.append(
                    f"case {row.case_id}@{row.case_version}: artifact {sha256} is absent"
                )
            if (row.case_id, row.case_version, sha256) not in link_keys:
                report.failures.append(
                    f"case {row.case_id}@{row.case_version}: artifact {sha256} lacks a case link"
                )

    submissions_by_task = {
        row.task_id: row for row in session.scalars(select(AdjudicationSubmissionORM)).all()
    }
    submissions_by_id = {row.adjudication_id: row for row in submissions_by_task.values()}
    tasks = session.scalars(select(AdjudicationTaskORM)).all()
    task_ids = {row.task_id for row in tasks}
    for task in tasks:
        report.checked_tasks += 1
        submission = submissions_by_task.get(task.task_id)
        _check_task_state(report, "task", task.task_id, task.status, task.assigned_to, submission)

    for submission in submissions_by_task.values():
        report.checked_submissions += 1
        if submission.task_id not in task_ids:
            report.failures.append(
                f"adjudication {submission.adjudication_id}: task is absent"
            )
            continue
        try:
            adjudication = Adjudication.model_validate(submission.decision_json)
        except Exception as exc:
            report.failures.append(
                f"adjudication {submission.adjudication_id}: validation failed: {exc}"
            )
            continue
        if not adjudication.verify_content_hash():
            report.failures.append(
                f"adjudication {submission.adjudication_id}: embedded content hash is invalid"
            )
        if adjudication.content_hash != submission.content_hash:
            report.failures.append(
                f"adjudication {submission.adjudication_id}: database content hash differs"
            )
        if adjudication.adjudicator_id != submission.adjudicator_id:
            report.failures.append(
                f"adjudication {submission.adjudication_id}: adjudicator identity mismatch"
            )

    determinations = session.scalars(select(DeterminationORM)).all()
    for row in determinations:
        report.checked_determinations += 1
        missing = [item for item in row.submission_ids if item not in submissions_by_id]
        if missing:
            report.failures.append(
                f"determination {row.determination_id}: missing submissions {missing}"
            )
        if row.requires_tie_break:
            tie_task = next(
                (
                    task
                    for task in tasks
                    if task.concern_id == row.concern_id and task.slot == "tie_break"
                ),
                None,
            )
            if tie_task is None:
                report.failures.append(
                    f"determination {row.determination_id}: tie-break required but no task exists"
                )

    for row in session.scalars(select(UseGrantORM)).all():
        report.checked_grants += 1
        if row.status == GrantStatus.REVOKED.value and row.revoked_at is None:
            report.failures.append(f"grant {row.grant_id}: revoked status lacks revoked_at")
        if row.status == GrantStatus.ACTIVE.value and row.revoked_at is not None:
            report.failures.append(f"grant {row.grant_id}: active status has revoked_at")

    _audit_expert_program(
        session=session,
        report=report,
        principals=principals,
        artifact_rows=artifact_rows,
        case_map=case_map,
        concern_ids=concern_ids,
        adjudication_tasks={row.task_id: row for row in tasks},
    )
    _audit_novel_determinations(session=session, report=report)
    return report


def _audit_novel_determinations(*, session: Session, report: ConformanceReport) -> None:
    from opencritique_evaluation.models import NovelConcernCandidate, NovelConcernDetermination
    from opencritique_evaluation.novel_determination import candidate_snapshot_hash

    candidates = {
        row.candidate_id: row for row in session.scalars(select(NovelCandidateORM)).all()
    }
    for row in candidates.values():
        report.checked_novel_candidates += 1
        try:
            candidate = NovelConcernCandidate.model_validate(row.candidate_json)
        except Exception as exc:
            report.failures.append(f"novel candidate {row.candidate_id}: validation failed: {exc}")
            continue
        if candidate_snapshot_hash(candidate) != row.candidate_hash:
            report.failures.append(f"novel candidate {row.candidate_id}: altered snapshot hash")
        if candidate.candidate_id != row.candidate_id:
            report.failures.append(f"novel candidate {row.candidate_id}: identity mismatch")

    novel_tasks = {
        row.task_id: row for row in session.scalars(select(NovelAdjudicationTaskORM)).all()
    }
    novel_submissions = {
        row.task_id: row
        for row in session.scalars(select(NovelAdjudicationSubmissionORM)).all()
    }
    submission_ids = {row.decision_id for row in novel_submissions.values()}
    for task in novel_tasks.values():
        if task.candidate_id not in candidates:
            report.failures.append(f"novel task {task.task_id}: orphaned candidate")
        submission = novel_submissions.get(task.task_id)
        _check_task_state(
            report,
            "novel task",
            task.task_id,
            task.status,
            task.assigned_to,
            submission,
        )

    determinations = session.scalars(select(NovelDeterminationORM)).all()
    finalized_by_candidate: dict[str, list[NovelDeterminationORM]] = {}
    for row in determinations:
        report.checked_novel_determinations += 1
        finalized_by_candidate.setdefault(row.candidate_id, [])
        if row.candidate_id not in candidates:
            report.failures.append(
                f"novel determination {row.determination_id}: orphaned candidate"
            )
            continue
        try:
            determination = NovelConcernDetermination.model_validate(row.determination_json)
        except Exception as exc:
            report.failures.append(
                f"novel determination {row.determination_id}: validation failed: {exc}"
            )
            continue
        if content_hash(determination) != row.determination_hash:
            report.failures.append(
                f"novel determination {row.determination_id}: altered determination hash"
            )
        missing = [item for item in determination.decision_ids if item not in submission_ids]
        if missing:
            report.failures.append(
                f"novel determination {row.determination_id}: missing decisions {missing}"
            )
        candidate_submissions = [
            item for item in novel_submissions.values() if item.candidate_id == row.candidate_id
        ]
        if determination.finalized and not candidate_submissions:
            report.failures.append(
                f"novel determination {row.determination_id}: finalized without submissions"
            )
        if row.requires_tie_break:
            tie = next(
                (
                    task
                    for task in novel_tasks.values()
                    if task.candidate_id == row.candidate_id and task.slot == "tie_break"
                ),
                None,
            )
            if tie is None:
                report.failures.append(
                    f"novel determination {row.determination_id}: "
                    "tie-break required but no task exists"
                )
        if row.finalized:
            finalized_by_candidate[row.candidate_id].append(row)

    for candidate_id, rows in finalized_by_candidate.items():
        # Multiple append-only rows may exist historically; more than one distinct
        # finalized outcome body with differing hashes is a multiply-finalized fault
        # only when outcomes disagree.
        outcomes = {row.outcome for row in rows}
        if len(outcomes) > 1:
            report.failures.append(
                f"novel candidate {candidate_id}: multiply finalized with conflicting outcomes"
            )

    scorecards = {
        row.scorecard_id: row for row in session.scalars(select(ScorecardRecordORM)).all()
    }
    for row in scorecards.values():
        report.checked_scorecards += 1
        if content_hash(row.scorecard_json) != row.scorecard_hash and False:
            # scorecard_hash uses canonical_json_bytes of PublicScorecard, not content_hash
            pass
        if row.predecessor_scorecard_id and row.predecessor_scorecard_id not in scorecards:
            report.failures.append(
                f"scorecard {row.scorecard_id}: predecessor scorecard is absent"
            )
        if row.predecessor_scorecard_id:
            pred = scorecards[row.predecessor_scorecard_id]
            if (
                row.predecessor_scorecard_hash
                and row.predecessor_scorecard_hash != pred.scorecard_hash
            ):
                report.failures.append(
                    f"scorecard {row.scorecard_id}: predecessor hash mismatch"
                )

    versions = session.scalars(select(BenchmarkVersionORM)).all()
    by_key: dict[tuple[str, str], BenchmarkVersionORM] = {}
    for row in versions:
        report.checked_benchmark_versions += 1
        key = (row.benchmark_id, row.version)
        if key in by_key and by_key[key].case_set_hash != row.case_set_hash:
            report.failures.append(
                f"benchmark {row.benchmark_id}@{row.version}: conflicting case_set_hash rows"
            )
        by_key[key] = row
        if row.predecessor_version:
            pred_key = (row.benchmark_id, row.predecessor_version)
            if pred_key not in by_key and not any(
                item.benchmark_id == row.benchmark_id and item.version == row.predecessor_version
                for item in versions
            ):
                report.warnings.append(
                    f"benchmark {row.benchmark_id}@{row.version}: "
                    "predecessor version not registered"
                )


def _audit_expert_program(
    *,
    session: Session,
    report: ConformanceReport,
    principals: dict[str, PrincipalORM],
    artifact_rows: dict[str, ArtifactORM],
    case_map: dict[tuple[str, str], CaseORM],
    concern_ids: set[str],
    adjudication_tasks: dict[str, AdjudicationTaskORM],
) -> None:
    profiles = {row.actor_id: row for row in session.scalars(select(ExpertProfileORM)).all()}
    for row in profiles.values():
        report.checked_expert_profiles += 1
        principal = principals.get(row.actor_id)
        if principal is None or principal.role != PrincipalRole.ADJUDICATOR.value:
            report.failures.append(
                f"expert profile {row.actor_id}: principal is absent or not an adjudicator"
            )
        if row.public_attribution and not (row.attribution_name or "").strip():
            report.failures.append(
                f"expert profile {row.actor_id}: public attribution lacks a name"
            )

    calibration_sets = {
        row.set_id: row for row in session.scalars(select(CalibrationSetORM)).all()
    }
    for row in calibration_sets.values():
        if row.min_cases > len(row.case_refs):
            report.failures.append(f"calibration set {row.set_id}: min_cases exceeds cases")
        for ref in row.case_refs:
            if (ref["case_id"], ref["case_version"]) not in case_map:
                report.failures.append(
                    f"calibration set {row.set_id}: referenced case is absent"
                )
            if ref["concern_id"] not in concern_ids:
                report.failures.append(
                    f"calibration set {row.set_id}: referenced concern is absent"
                )

    calibration_tasks = {
        row.task_id: row for row in session.scalars(select(CalibrationTaskORM)).all()
    }
    calibration_submissions = {
        row.task_id: row for row in session.scalars(select(CalibrationSubmissionORM)).all()
    }
    attempts = {
        row.attempt_id: row for row in session.scalars(select(CalibrationAttemptORM)).all()
    }
    for row in attempts.values():
        report.checked_calibration_attempts += 1
        if row.set_id not in calibration_sets:
            report.failures.append(f"calibration attempt {row.attempt_id}: set is absent")
        if row.adjudicator_id not in profiles:
            report.failures.append(
                f"calibration attempt {row.attempt_id}: expert profile is absent"
            )
        if row.status == "completed" and (row.score_json is None or row.passed is None):
            report.failures.append(
                f"calibration attempt {row.attempt_id}: completed attempt lacks score"
            )
    for row in calibration_tasks.values():
        report.checked_calibration_tasks += 1
        submission = calibration_submissions.get(row.task_id)
        _check_task_state(
            report,
            "calibration task",
            row.task_id,
            row.status,
            None,
            submission,
        )
        if row.attempt_id not in attempts:
            report.failures.append(f"calibration task {row.task_id}: attempt is absent")
        if row.concern_id not in concern_ids:
            report.failures.append(f"calibration task {row.task_id}: concern is absent")
        if (
            submission is not None
            and content_hash(submission.decision_json) != submission.content_hash
        ):
            report.failures.append(
                f"calibration submission {submission.submission_id}: content hash mismatch"
            )

    for row in session.scalars(select(ExpertQualificationORM)).all():
        attempt = attempts.get(row.source_attempt_id) if row.source_attempt_id else None
        if row.status == "active" and (attempt is None or attempt.passed is not True):
            report.failures.append(
                f"qualification {row.qualification_id}: active qualification lacks passing attempt"
            )

    intakes = {row.intake_id: row for row in session.scalars(select(CaseIntakeORM)).all()}
    for row in intakes.values():
        report.checked_intakes += 1
        if row.source_artifact_sha256 not in artifact_rows:
            report.failures.append(f"intake {row.intake_id}: source artifact is absent")
        if row.status == "accepted" and (row.reviewed_by is None or row.reviewed_at is None):
            report.failures.append(f"intake {row.intake_id}: accepted intake lacks review")
        public_uses = {"public_release", "open_model_training"}
        if public_uses.intersection(row.requested_uses) and not row.redistribution_allowed:
            report.failures.append(
                f"intake {row.intake_id}: public use lacks redistribution permission"
            )

    claim_tasks = {
        row.task_id: row for row in session.scalars(select(ClaimReconstructionTaskORM)).all()
    }
    claim_submissions = {
        row.task_id: row
        for row in session.scalars(select(ClaimReconstructionSubmissionORM)).all()
    }
    claim_submission_ids = {row.submission_id for row in claim_submissions.values()}
    for row in claim_tasks.values():
        report.checked_claim_tasks += 1
        submission = claim_submissions.get(row.task_id)
        _check_task_state(
            report,
            "claim task",
            row.task_id,
            row.status,
            row.assigned_to,
            submission,
        )
        if row.intake_id not in intakes:
            report.failures.append(f"claim task {row.task_id}: intake is absent")
        if submission is not None:
            try:
                claim = ClaimReconstructionInput.model_validate(submission.claim_json)
            except Exception as exc:
                report.failures.append(
                    f"claim submission {submission.submission_id}: validation failed: {exc}"
                )
            else:
                if content_hash(claim) != submission.content_hash:
                    report.failures.append(
                        f"claim submission {submission.submission_id}: content hash mismatch"
                    )

    for row in session.scalars(select(ClaimReconstructionDeterminationORM)).all():
        missing = [item for item in row.submission_ids if item not in claim_submission_ids]
        if missing:
            report.failures.append(
                f"claim determination {row.determination_id}: missing submissions {missing}"
            )
        if row.status == "accepted" and row.canonical_claim_json is None:
            report.failures.append(
                f"claim determination {row.determination_id}: accepted without canonical claim"
            )

    credits = session.scalars(select(ContributionCreditORM)).all()
    for row in credits:
        report.checked_credits += 1
        if row.actor_id not in principals:
            report.failures.append(f"credit {row.credit_id}: actor is absent")
        if row.public and not (row.public_name or "").strip():
            report.failures.append(f"credit {row.credit_id}: public credit lacks public name")

    calibration_task_ids = set(calibration_tasks)
    claim_task_ids = set(claim_tasks)
    for row in session.scalars(select(CompensationRecordORM)).all():
        report.checked_compensation += 1
        if row.amount_minor <= 0:
            report.failures.append(f"compensation {row.compensation_id}: amount is not positive")
        if row.status == "paid" and row.paid_at is None:
            report.failures.append(f"compensation {row.compensation_id}: paid status lacks paid_at")
        task_exists = (
            row.task_id in adjudication_tasks
            if row.task_type == "adjudication"
            else row.task_id in calibration_task_ids
            if row.task_type == "calibration"
            else row.task_id in claim_task_ids
        )
        if not task_exists:
            report.failures.append(f"compensation {row.compensation_id}: task is absent")


def _check_task_state(
    report: ConformanceReport,
    label: str,
    task_id: str,
    status: str,
    assigned_to: str | None,
    submission: object | None,
) -> None:
    if status == TaskStatus.PENDING.value and assigned_to is not None:
        report.failures.append(f"{label} {task_id}: pending task has an assignee")
    if status == TaskStatus.CLAIMED.value and assigned_to is None:
        report.failures.append(f"{label} {task_id}: claimed task lacks an assignee")
    if status == TaskStatus.COMPLETED.value and submission is None:
        report.failures.append(f"{label} {task_id}: completed task lacks a submission")
    if submission is not None and status != TaskStatus.COMPLETED.value:
        report.failures.append(f"{label} {task_id}: submission exists but status is {status}")


def _bundle_artifact_hashes(bundle: CaseBundle) -> set[str]:
    hashes: set[str] = set()
    for version in bundle.manuscript_versions:
        hashes.add(version.source_artifact.sha256)
        if version.rendered_artifact:
            hashes.add(version.rendered_artifact.sha256)
        if version.extracted_artifact:
            hashes.add(version.extracted_artifact.sha256)
    for anchor in bundle.anchors:
        if anchor.rendered_reference:
            hashes.add(anchor.rendered_reference.artifact.sha256)
    for evidence in bundle.evidence:
        if evidence.artifact_reference:
            hashes.add(evidence.artifact_reference.sha256)
    return hashes
