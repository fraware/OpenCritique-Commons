"""End-to-end novel-concern determination tests (issue #2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from opencritique_evaluation.models import (
    AnchorResolution,
    AnchorResolutionStatus,
    BenchmarkCaseRef,
    BenchmarkEvidenceClass,
    BenchmarkManifest,
    CaseEvaluation,
    EvaluationMetrics,
    EvaluationResult,
    MetricValue,
    NovelConcernCandidate,
    NovelConcernQueue,
    NovelDeterminationOutcome,
    NovelPrimaryDecision,
    PublicScorecard,
    ReferenceCompleteness,
    SubmittedAnchor,
    SubmittedConcern,
    SystemManifest,
)
from opencritique_evaluation.novel_determination import (
    determine_novel,
    outcome_affects_precision_recall,
    recompute_scorecard_with_successor,
    scorecard_hash,
)
from opencritique_evaluation.scorecard import build_scorecard
from opencritique_registry.artifacts import LocalArtifactStore
from opencritique_registry.conformance import audit_registry
from opencritique_registry.db import make_engine, make_session_factory
from opencritique_registry.db_models import (
    NovelAdjudicationTaskORM,
    NovelCandidateORM,
    NovelDeterminationORM,
    PrincipalORM,
)
from opencritique_registry.novel_service import NovelDeterminationService
from opencritique_schema.canonical import content_hash
from opencritique_schema.models import Severity


def _metric(value: float | None = None) -> MetricValue:
    return MetricValue(value=value, numerator=None, denominator=None, withheld_reason=None)


def _system() -> SystemManifest:
    return SystemManifest(
        system_id="sys-test",
        version="0.0.1",
        display_name="Test System",
        configuration_hash="a" * 64,
    )


def _benchmark(version: str = "0.1.0") -> BenchmarkManifest:
    return BenchmarkManifest(
        benchmark_id="bench-novel",
        version=version,
        title="Novel test bench",
        description="Partial natural reference set for novel determination tests",
        evidence_class=BenchmarkEvidenceClass.SYNTHETIC_SCIENTIFIC,
        reference_completeness=ReferenceCompleteness.PARTIAL_NATURAL,
        domain_profiles=["physics"],
        cases=[BenchmarkCaseRef(case_id="case-1", case_version="1", path="case.json")],
        license="Apache-2.0",
        case_set_hash="b" * 64,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        limitations=["Incomplete natural reference set"],
    )


def _result(benchmark: BenchmarkManifest) -> EvaluationResult:
    return EvaluationResult(
        result_id="result-1",
        benchmark=benchmark,
        system=_system(),
        submission_id="sub-1",
        matcher_version="opencritique-matcher-v0.2",
        case_evaluations=[
            CaseEvaluation(
                case_id="case-1",
                case_version="1",
                submitted_count=1,
                eligible_reference_count=0,
                matches=[],
                unmatched_submitted_ids=["local-1"],
                missed_reference_ids=[],
                anchor_resolutions={
                    "local-1": [
                        AnchorResolution(
                            submitted_index=0,
                            status=AnchorResolutionStatus.UNRESOLVED,
                            reference_anchor_ids=[],
                        )
                    ]
                },
                abstained=False,
                failure=None,
            )
        ],
        metrics=EvaluationMetrics(
            cases_total=1,
            cases_completed=1,
            cases_abstained=0,
            cases_failed=0,
            submitted_concerns=1,
            eligible_reference_concerns=0,
            matched_concerns=0,
            unmatched_submitted=1,
            missed_reference=0,
            anchor_resolution_rate=_metric(0.0),
            precision=_metric(None),
            recall=_metric(None),
            severity_weighted_precision=_metric(None),
            severity_weighted_recall=_metric(None),
            false_critical_per_manuscript=_metric(None),
            brier_score=_metric(None),
            novel_candidates_pending_adjudication=1,
        ),
        performance_claim_authorized=False,
        claim_boundary="Synthetic fixture; no performance claims.",
    )


def _candidate(*, severity: Severity = Severity.MAJOR) -> NovelConcernCandidate:
    return NovelConcernCandidate(
        candidate_id="ocnovel_testdetermination0001",
        result_id="result-1",
        submission_id="sub-1",
        case_id="case-1",
        case_version="1",
        concern=SubmittedConcern(
            local_id="local-1",
            title="Possible missing derivation step",
            summary="Submitted concern that did not match the incomplete reference set.",
            concern_type="derivation",
            severity=severity,
            confidence=0.7,
            anchors=[SubmittedAnchor(page=3, source_text="equation (4)")],
        ),
        anchor_resolutions=[
            AnchorResolution(
                submitted_index=0,
                status=AnchorResolutionStatus.PAGE_ONLY,
                reference_anchor_ids=[],
            )
        ],
    )


def _queue(candidate: NovelConcernCandidate) -> NovelConcernQueue:
    return NovelConcernQueue(
        result_id=candidate.result_id,
        submission_id=candidate.submission_id,
        candidates=[candidate],
        source_result_hash="c" * 64,
        source_submission_hash="d" * 64,
    )


def _decision(
    *,
    adjudicator_id: str,
    slot: str,
    validity: NovelDeterminationOutcome,
    severity: Severity = Severity.MAJOR,
) -> NovelPrimaryDecision:
    payload = {
        "adjudicator_id": adjudicator_id,
        "slot": slot,
        "validity": validity.value,
        "severity": severity.value,
        "confidence": 0.8,
        "reasoning": f"{validity.value} with rationale for testing.",
        "blinded_fields": ["submitted.severity"],
    }
    return NovelPrimaryDecision.model_validate(
        {**payload, "content_hash": content_hash(payload)}
    )


@pytest.fixture()
def session(tmp_path: Path):
    from opencritique_registry.migrate import upgrade_head

    url = f"sqlite:///{(tmp_path / 'novel.db').as_posix()}"
    upgrade_head(url)
    engine = make_engine(url)
    factory = make_session_factory(engine)
    with factory() as sess:
        for actor_id in ("expert-a", "expert-b", "expert-c"):
            sess.add(
                PrincipalORM(
                    actor_id=actor_id,
                    role="adjudicator",
                    display_name=actor_id,
                    active=True,
                )
            )
        sess.commit()
        yield sess


def _service(session: Session) -> NovelDeterminationService:
    return NovelDeterminationService(session)


def test_policy_outcomes_confirmed_qualified_rejected_unresolved() -> None:
    confirmed = determine_novel(
        [
            _decision(
                adjudicator_id="a",
                slot="primary",
                validity=NovelDeterminationOutcome.CONFIRMED,
            ),
            _decision(
                adjudicator_id="b",
                slot="secondary",
                validity=NovelDeterminationOutcome.CONFIRMED,
            ),
        ]
    )
    assert confirmed.outcome == NovelDeterminationOutcome.CONFIRMED
    assert confirmed.finalized

    qualified = determine_novel(
        [
            _decision(
                adjudicator_id="a",
                slot="primary",
                validity=NovelDeterminationOutcome.CONFIRMED,
            ),
            _decision(
                adjudicator_id="b",
                slot="secondary",
                validity=NovelDeterminationOutcome.QUALIFIED,
            ),
        ]
    )
    assert qualified.outcome == NovelDeterminationOutcome.QUALIFIED

    rejected = determine_novel(
        [
            _decision(
                adjudicator_id="a",
                slot="primary",
                validity=NovelDeterminationOutcome.REJECTED,
            ),
            _decision(
                adjudicator_id="b",
                slot="secondary",
                validity=NovelDeterminationOutcome.REJECTED,
            ),
        ]
    )
    assert rejected.outcome == NovelDeterminationOutcome.REJECTED

    unresolved = determine_novel(
        [
            _decision(
                adjudicator_id="a",
                slot="primary",
                validity=NovelDeterminationOutcome.CONFIRMED,
            ),
            _decision(
                adjudicator_id="b",
                slot="secondary",
                validity=NovelDeterminationOutcome.REJECTED,
            ),
        ]
    )
    assert unresolved.requires_tie_break
    assert unresolved.outcome == NovelDeterminationOutcome.UNRESOLVED
    assert not unresolved.finalized
    assert not outcome_affects_precision_recall(NovelDeterminationOutcome.UNRESOLVED)
    assert not outcome_affects_precision_recall(NovelDeterminationOutcome.REJECTED)


def test_conflicting_primaries_create_exactly_one_tie_break(session: Session) -> None:
    service = _service(session)
    candidate = _candidate(severity=Severity.CRITICAL)
    queue = _queue(candidate)
    benchmark = _benchmark()
    service.register_benchmark(benchmark)
    service.ingest_queue(
        queue,
        matcher_version="opencritique-matcher-v0.2",
        matcher_config_id="default-v0.2",
        benchmark=benchmark,
    )
    tasks = session.query(NovelAdjudicationTaskORM).all()
    assert len(tasks) == 2
    primary = next(item for item in tasks if item.slot == "primary")
    secondary = next(item for item in tasks if item.slot == "secondary")
    service.claim_task(task_id=primary.task_id, actor_id="expert-a")
    service.submit_decision(
        task_id=primary.task_id,
        actor_id="expert-a",
        validity=NovelDeterminationOutcome.CONFIRMED,
        severity=Severity.CRITICAL,
        confidence=0.9,
        reasoning="Looks like a real gap in the derivation.",
    )
    service.claim_task(task_id=secondary.task_id, actor_id="expert-b")
    determination = service.submit_decision(
        task_id=secondary.task_id,
        actor_id="expert-b",
        validity=NovelDeterminationOutcome.REJECTED,
        severity=Severity.MINOR,
        confidence=0.6,
        reasoning="Not a valid concern under the manuscript claims.",
    )
    assert determination.requires_tie_break
    assert not determination.finalized
    tie_tasks = (
        session.query(NovelAdjudicationTaskORM)
        .filter_by(candidate_id=candidate.candidate_id, slot="tie_break")
        .all()
    )
    assert len(tie_tasks) == 1
    # Recompute again must not create a second tie-break task.
    candidate_row = session.get(NovelCandidateORM, candidate.candidate_id)
    assert candidate_row is not None
    service._recompute(
        candidate_row=candidate_row,
        original_scorecard=None,
        recompute_result_factory=None,
    )
    assert (
        session.query(NovelAdjudicationTaskORM)
        .filter_by(candidate_id=candidate.candidate_id, slot="tie_break")
        .count()
        == 1
    )


@pytest.mark.parametrize(
    "outcome",
    [
        NovelDeterminationOutcome.CONFIRMED,
        NovelDeterminationOutcome.QUALIFIED,
        NovelDeterminationOutcome.REJECTED,
        NovelDeterminationOutcome.UNRESOLVED,
    ],
)
def test_end_to_end_final_outcomes(
    session: Session, outcome: NovelDeterminationOutcome, tmp_path
) -> None:
    service = _service(session)
    candidate = _candidate(severity=Severity.MAJOR)
    queue = _queue(candidate)
    benchmark = _benchmark()
    original = build_scorecard(_result(benchmark))
    service.register_benchmark(benchmark)
    service.register_scorecard(original)
    service.ingest_queue(
        queue,
        matcher_version="opencritique-matcher-v0.2",
        matcher_config_id="default-v0.2",
        benchmark=benchmark,
    )
    tasks = session.query(NovelAdjudicationTaskORM).order_by(NovelAdjudicationTaskORM.slot).all()
    primary = next(item for item in tasks if item.slot == "primary")
    secondary = next(item for item in tasks if item.slot == "secondary")

    def _submit(task, actor, validity):
        service.claim_task(task_id=task.task_id, actor_id=actor)
        return service.submit_decision(
            task_id=task.task_id,
            actor_id=actor,
            validity=validity,
            severity=Severity.MAJOR,
            confidence=0.85,
            reasoning=f"Decision {validity.value} with inspectable reasoning.",
            original_scorecard=original,
            recompute_result_factory=(
                (lambda successor: _result(successor).model_copy(update={"result_id": "result-2"}))
                if outcome == NovelDeterminationOutcome.CONFIRMED
                else None
            ),
        )

    if outcome == NovelDeterminationOutcome.UNRESOLVED:
        _submit(primary, "expert-a", NovelDeterminationOutcome.CONFIRMED)
        determination = _submit(secondary, "expert-b", NovelDeterminationOutcome.REJECTED)
        assert determination.requires_tie_break
        tie = (
            session.query(NovelAdjudicationTaskORM)
            .filter_by(slot="tie_break")
            .one()
        )
        determination = _submit(tie, "expert-c", NovelDeterminationOutcome.UNRESOLVED)
    elif outcome == NovelDeterminationOutcome.QUALIFIED:
        _submit(primary, "expert-a", NovelDeterminationOutcome.CONFIRMED)
        determination = _submit(secondary, "expert-b", NovelDeterminationOutcome.QUALIFIED)
    else:
        _submit(primary, "expert-a", outcome)
        determination = _submit(secondary, "expert-b", outcome)

    assert determination.finalized
    assert determination.outcome == outcome
    if outcome == NovelDeterminationOutcome.CONFIRMED:
        assert determination.successor_benchmark_version is not None
        assert determination.successor_case_set_hash is not None
        assert determination.predecessor_scorecard_id == original.scorecard_id
        assert determination.recompute_scorecard_id is not None
        # Historical scorecard unchanged.
        scorecard_row = session.get(
            __import__(
                "opencritique_registry.db_models", fromlist=["ScorecardRecordORM"]
            ).ScorecardRecordORM,
            original.scorecard_id,
        )
        assert scorecard_row is not None
        assert scorecard_hash(original) == scorecard_hash(
            PublicScorecard.model_validate(scorecard_row.scorecard_json)
        )
    if outcome == NovelDeterminationOutcome.REJECTED:
        assert "inspectable reasoning" in determination.rationale.lower() or determination.rationale
    store = LocalArtifactStore(tmp_path / "artifacts", max_bytes=1024 * 1024)
    report = audit_registry(session, store)
    assert report.passed, report.failures


def test_same_expert_cannot_adjudicate_twice(session: Session) -> None:
    service = _service(session)
    candidate = _candidate()
    queue = _queue(candidate)
    benchmark = _benchmark()
    service.register_benchmark(benchmark)
    service.ingest_queue(
        queue,
        matcher_version="opencritique-matcher-v0.2",
        matcher_config_id="default-v0.2",
        benchmark=benchmark,
    )
    primary = session.query(NovelAdjudicationTaskORM).filter_by(slot="primary").one()
    secondary = session.query(NovelAdjudicationTaskORM).filter_by(slot="secondary").one()
    service.claim_task(task_id=primary.task_id, actor_id="expert-a")
    service.submit_decision(
        task_id=primary.task_id,
        actor_id="expert-a",
        validity=NovelDeterminationOutcome.CONFIRMED,
        severity=Severity.MAJOR,
        confidence=0.8,
        reasoning="Primary decision.",
    )
    with pytest.raises(HTTPException):
        service.claim_task(task_id=secondary.task_id, actor_id="expert-a")


def test_blinding_strips_severity_confidence_and_system_identity(session: Session) -> None:
    service = _service(session)
    candidate = _candidate()
    queue = _queue(candidate)
    benchmark = _benchmark()
    service.register_benchmark(benchmark)
    service.ingest_queue(
        queue,
        matcher_version="opencritique-matcher-v0.2",
        matcher_config_id="default-v0.2",
        benchmark=benchmark,
    )
    task = session.query(NovelAdjudicationTaskORM).filter_by(slot="primary").one()
    payload = service.blinded_payload(task.task_id)
    assert "severity" not in payload["concern"]
    assert "confidence" not in payload["concern"]
    assert "system_identity" in payload["blinded_fields"]
    assert "model_identity" in payload["blinded_fields"]


def test_candidate_cannot_be_edited_in_place(session: Session) -> None:
    service = _service(session)
    candidate = _candidate()
    queue = _queue(candidate)
    benchmark = _benchmark()
    service.register_benchmark(benchmark)
    service.ingest_queue(
        queue,
        matcher_version="opencritique-matcher-v0.2",
        matcher_config_id="default-v0.2",
        benchmark=benchmark,
    )
    altered = candidate.model_copy(
        update={
            "concern": candidate.concern.model_copy(update={"title": "Tampered title here"})
        }
    )
    with pytest.raises(HTTPException):
        service.ingest_queue(
            _queue(altered),
            matcher_version="opencritique-matcher-v0.2",
            matcher_config_id="default-v0.2",
            benchmark=benchmark,
        )


def test_audit_detects_altered_determination(session: Session, tmp_path) -> None:
    service = _service(session)
    candidate = _candidate(severity=Severity.MINOR)
    queue = _queue(candidate)
    benchmark = _benchmark()
    service.register_benchmark(benchmark)
    service.ingest_queue(
        queue,
        matcher_version="opencritique-matcher-v0.2",
        matcher_config_id="default-v0.2",
        benchmark=benchmark,
    )
    task = session.query(NovelAdjudicationTaskORM).one()
    service.claim_task(task_id=task.task_id, actor_id="expert-a")
    service.submit_decision(
        task_id=task.task_id,
        actor_id="expert-a",
        validity=NovelDeterminationOutcome.REJECTED,
        severity=Severity.MINOR,
        confidence=0.5,
        reasoning="Rejected with reasoning retained for inspection.",
    )
    row = session.query(NovelDeterminationORM).one()
    payload = dict(row.determination_json)
    payload["rationale"] = "silently altered"
    row.determination_json = payload
    session.flush()
    store = LocalArtifactStore(tmp_path / "artifacts", max_bytes=1024 * 1024)
    report = audit_registry(session, store)
    assert any("altered determination hash" in item for item in report.failures)


def test_recompute_links_predecessor_without_mutating_original() -> None:
    benchmark = _benchmark()
    original = build_scorecard(_result(benchmark))
    from opencritique_evaluation.novel_determination import bump_benchmark_version

    successor = bump_benchmark_version(benchmark, new_version="0.1.1")
    assert successor.version != benchmark.version
    assert successor.case_set_hash != benchmark.case_set_hash
    recomputed = recompute_scorecard_with_successor(
        original_scorecard=original,
        successor_benchmark=successor,
        updated_result=_result(successor).model_copy(update={"result_id": "result-2"}),
    )
    assert recomputed.predecessor_scorecard_id == original.scorecard_id
    assert recomputed.predecessor_scorecard_hash == scorecard_hash(original)
    assert recomputed.scorecard_id != original.scorecard_id
    assert original.immutable
