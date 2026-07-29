from __future__ import annotations

import hashlib
import json

from .models import (
    EvaluationResult,
    EvaluationSubmission,
    NovelConcernCandidate,
    NovelConcernQueue,
    ReferenceCompleteness,
)


def _hash_model(model) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_novel_queue(
    result: EvaluationResult, submission: EvaluationSubmission
) -> NovelConcernQueue:
    if result.benchmark.reference_completeness == ReferenceCompleteness.COMPLETE_SEEDED:
        raise ValueError("complete seeded benchmarks do not produce novel-concern queues")
    if result.submission_id != submission.submission_id:
        raise ValueError("result and submission identities do not match")
    by_case = {(item.case_id, item.case_version): item for item in submission.cases}
    candidates: list[NovelConcernCandidate] = []
    for case_result in result.case_evaluations:
        case_submission = by_case.get((case_result.case_id, case_result.case_version))
        if case_submission is None:
            continue
        by_id = {item.local_id: item for item in case_submission.concerns}
        for local_id in case_result.unmatched_submitted_ids:
            concern = by_id[local_id]
            material = (
                f"{result.result_id}\x1f{case_result.case_id}\x1f"
                f"{case_result.case_version}\x1f{local_id}"
            ).encode()
            candidate_id = f"ocnovel_{hashlib.sha256(material).hexdigest()[:24]}"
            candidates.append(
                NovelConcernCandidate(
                    candidate_id=candidate_id,
                    result_id=result.result_id,
                    submission_id=submission.submission_id,
                    case_id=case_result.case_id,
                    case_version=case_result.case_version,
                    concern=concern,
                    anchor_resolutions=case_result.anchor_resolutions.get(local_id, []),
                )
            )
    return NovelConcernQueue(
        result_id=result.result_id,
        submission_id=submission.submission_id,
        candidates=candidates,
        source_result_hash=_hash_model(result),
        source_submission_hash=_hash_model(submission),
    )
