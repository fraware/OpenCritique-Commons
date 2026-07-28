"""Append-only novel-concern determination policy and scorecard recompute.

Implements issue #2 invariants without mutating historical scorecards or
benchmark manifests in place.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from opencritique_schema.canonical import canonical_json_bytes, content_hash
from opencritique_schema.models import Severity

from .models import (
    BenchmarkManifest,
    EvaluationResult,
    NovelCandidateState,
    NovelConcernCandidate,
    NovelConcernDetermination,
    NovelConcernQueue,
    NovelDeterminationOutcome,
    NovelPrimaryDecision,
    PublicScorecard,
)
from .scorecard import build_scorecard

NOVEL_POLICY_VERSION = "novel-determination-v0.1"
SCORING_POLICY_VERSION = "scoring-policy-v0.1"

PRIMARY_BLINDED_FIELDS = [
    "submitted.severity",
    "submitted.confidence",
    "system_identity",
    "model_identity",
    "other_adjudications",
]

TIE_BREAK_BLINDED_FIELDS = [
    *PRIMARY_BLINDED_FIELDS,
    "adjudicator_identity",
]

SEVERITY_ORDER = {
    Severity.INFORMATIONAL: 0,
    Severity.MINOR: 1,
    Severity.MODERATE: 2,
    Severity.MAJOR: 3,
    Severity.CRITICAL: 4,
}

_OUTCOME_TO_STATE = {
    NovelDeterminationOutcome.CONFIRMED: NovelCandidateState.ACCEPTED_NOVEL,
    NovelDeterminationOutcome.QUALIFIED: NovelCandidateState.QUALIFIED,
    NovelDeterminationOutcome.REJECTED: NovelCandidateState.REJECTED,
    NovelDeterminationOutcome.UNRESOLVED: NovelCandidateState.UNRESOLVED,
}


class NovelDeterminationError(Exception):
    """Typed failure for novel-concern determination workflows."""


@dataclass(frozen=True)
class NovelPolicyResult:
    outcome: NovelDeterminationOutcome
    severity: Severity | None
    requires_tie_break: bool
    finalized: bool
    rationale: str


def candidate_snapshot_hash(candidate: NovelConcernCandidate) -> str:
    return content_hash(candidate)


def decision_content_hash(decision: dict) -> str:
    return content_hash(decision)


def requires_two_primaries(severity: Severity) -> bool:
    return severity in {Severity.MAJOR, Severity.CRITICAL}


def _validity_from_two(
    left: NovelDeterminationOutcome, right: NovelDeterminationOutcome
) -> tuple[NovelDeterminationOutcome, bool, str]:
    if left == right:
        return left, False, "The two primary adjudicators agree on validity."
    pair = {left, right}
    if pair == {NovelDeterminationOutcome.CONFIRMED, NovelDeterminationOutcome.QUALIFIED}:
        return (
            NovelDeterminationOutcome.QUALIFIED,
            False,
            "Confirmed and qualified resolve conservatively to qualified.",
        )
    return (
        NovelDeterminationOutcome.UNRESOLVED,
        True,
        "The primary validity decisions require tie-break adjudication.",
    )


def _severity_from_two(left: Severity, right: Severity) -> tuple[Severity | None, bool, str]:
    if left == right:
        return left, False, "The two primary adjudicators agree on severity."
    gap = abs(SEVERITY_ORDER[left] - SEVERITY_ORDER[right])
    if Severity.CRITICAL in {left, right}:
        return None, True, "Any contested critical classification requires tie-break adjudication."
    if gap <= 1:
        lower = min((left, right), key=SEVERITY_ORDER.__getitem__)
        return lower, False, "Adjacent severity decisions resolve to the lower severity."
    return (
        None,
        True,
        "Severity decisions separated by two or more levels require tie-break adjudication.",
    )


def determine_novel(
    decisions: list[NovelPrimaryDecision],
    *,
    require_two_primaries: bool = True,
) -> NovelPolicyResult:
    """Apply two-primary + optional tie-break policy to novel-candidate decisions."""
    primaries = [item for item in decisions if item.slot in {"primary", "secondary"}]
    ties = [item for item in decisions if item.slot == "tie_break"]
    if not require_two_primaries and len(primaries) == 1 and not ties:
        only = primaries[0]
        return NovelPolicyResult(
            outcome=only.validity,
            severity=only.severity,
            requires_tie_break=False,
            finalized=True,
            rationale="Single primary adjudication accepted for non-major/critical candidate.",
        )
    if len(primaries) < 2:
        return NovelPolicyResult(
            outcome=NovelDeterminationOutcome.UNRESOLVED,
            severity=None,
            requires_tie_break=False,
            finalized=False,
            rationale="Two independent primary adjudications have not been completed.",
        )
    if len(primaries) > 2:
        raise NovelDeterminationError("more than two primary decisions are not allowed")
    if primaries[0].adjudicator_id == primaries[1].adjudicator_id:
        raise NovelDeterminationError("the same expert may not adjudicate both primary slots")

    validity, validity_tie, validity_reason = _validity_from_two(
        primaries[0].validity, primaries[1].validity
    )
    severity, severity_tie, severity_reason = _severity_from_two(
        primaries[0].severity, primaries[1].severity
    )
    tie_required = validity_tie or severity_tie
    if tie_required and not ties:
        return NovelPolicyResult(
            outcome=NovelDeterminationOutcome.UNRESOLVED,
            severity=None if severity_tie else severity,
            requires_tie_break=True,
            finalized=False,
            rationale=f"{validity_reason} {severity_reason}",
        )
    if tie_required and ties:
        if len(ties) > 1:
            raise NovelDeterminationError("only one tie-break decision is allowed")
        tie = ties[-1]
        if tie.adjudicator_id in {primaries[0].adjudicator_id, primaries[1].adjudicator_id}:
            raise NovelDeterminationError("tie-break adjudicator must differ from primaries")
        return NovelPolicyResult(
            outcome=tie.validity,
            severity=tie.severity,
            requires_tie_break=False,
            finalized=True,
            rationale=(
                "Tie-break adjudication controls the contested dimensions. "
                f"Primary validity: {validity_reason} Primary severity: {severity_reason}"
            ),
        )
    return NovelPolicyResult(
        outcome=validity,
        severity=severity,
        requires_tie_break=False,
        finalized=True,
        rationale=f"{validity_reason} {severity_reason}",
    )


def apply_candidate_state(
    candidate: NovelConcernCandidate, outcome: NovelDeterminationOutcome, *, finalized: bool
) -> NovelConcernCandidate:
    if not finalized:
        return candidate
    return candidate.model_copy(update={"state": _OUTCOME_TO_STATE[outcome]})


def bump_benchmark_version(manifest: BenchmarkManifest, *, new_version: str) -> BenchmarkManifest:
    """Return a successor benchmark manifest; never mutates the input."""
    if new_version == manifest.version:
        raise NovelDeterminationError("successor benchmark version must differ")
    successor_cases = list(manifest.cases)
    material = {
        "benchmark_id": manifest.benchmark_id,
        "version": new_version,
        "cases": [item.model_dump(mode="json") for item in successor_cases],
        "predecessor_version": manifest.version,
        "predecessor_case_set_hash": manifest.case_set_hash,
    }
    case_set_hash = hashlib.sha256(canonical_json_bytes(material)).hexdigest()
    return manifest.model_copy(
        update={
            "version": new_version,
            "case_set_hash": case_set_hash,
            "created_at": datetime.now(UTC),
            "limitations": [
                *manifest.limitations,
                (
                    "Successor version created after confirmed novel-concern determination; "
                    f"predecessor {manifest.version} remains immutable."
                ),
            ],
        }
    )


def scorecard_hash(scorecard: PublicScorecard) -> str:
    return hashlib.sha256(canonical_json_bytes(scorecard)).hexdigest()


def recompute_scorecard_with_successor(
    *,
    original_scorecard: PublicScorecard,
    successor_benchmark: BenchmarkManifest,
    updated_result: EvaluationResult,
) -> PublicScorecard:
    """Build a new scorecard linked to an immutable predecessor."""
    if not original_scorecard.immutable:
        raise NovelDeterminationError("original scorecard must be marked immutable")
    predecessor_id = original_scorecard.scorecard_id
    predecessor_digest = scorecard_hash(original_scorecard)
    if updated_result.benchmark.version != successor_benchmark.version:
        raise NovelDeterminationError("updated result must reference the successor benchmark")
    if updated_result.benchmark.case_set_hash != successor_benchmark.case_set_hash:
        raise NovelDeterminationError("updated result case_set_hash must match successor")
    recomputed = updated_result.model_copy(
        update={
            "predecessor_result_id": original_scorecard.result.result_id,
            "scoring_policy_version": SCORING_POLICY_VERSION,
            "benchmark": successor_benchmark,
        }
    )
    return build_scorecard(
        recomputed,
        predecessor_scorecard_id=predecessor_id,
        predecessor_scorecard_hash=predecessor_digest,
    )


def build_determination(
    *,
    determination_id: str,
    queue: NovelConcernQueue,
    candidate: NovelConcernCandidate,
    decisions: list[NovelPrimaryDecision],
    policy: NovelPolicyResult,
    matcher_version: str,
    matcher_config_id: str,
    benchmark: BenchmarkManifest,
    decision_ids: list[str] | None = None,
    original_scorecard: PublicScorecard | None = None,
    successor_benchmark: BenchmarkManifest | None = None,
    recompute_scorecard: PublicScorecard | None = None,
) -> NovelConcernDetermination:
    if candidate.candidate_id not in {item.candidate_id for item in queue.candidates}:
        raise NovelDeterminationError("candidate is not part of the provided queue")
    resolved_decision_ids = decision_ids or [
        f"ocndec_{hashlib.sha256(item.content_hash.encode()).hexdigest()[:24]}"
        for item in decisions
    ]
    return NovelConcernDetermination(
        determination_id=determination_id,
        candidate_id=candidate.candidate_id,
        result_id=candidate.result_id,
        submission_id=candidate.submission_id,
        case_id=candidate.case_id,
        case_version=candidate.case_version,
        outcome=policy.outcome,
        severity=policy.severity,
        requires_tie_break=policy.requires_tie_break,
        finalized=policy.finalized,
        policy_version=NOVEL_POLICY_VERSION,
        scoring_policy_version=SCORING_POLICY_VERSION if policy.finalized else None,
        rationale=policy.rationale,
        decision_ids=resolved_decision_ids,
        candidate_snapshot_hash=candidate_snapshot_hash(candidate),
        source_result_hash=queue.source_result_hash,
        source_submission_hash=queue.source_submission_hash,
        matcher_version=matcher_version,
        matcher_config_id=matcher_config_id,
        benchmark_id=benchmark.benchmark_id,
        benchmark_version=benchmark.version,
        successor_benchmark_version=(
            successor_benchmark.version if successor_benchmark is not None else None
        ),
        successor_case_set_hash=(
            successor_benchmark.case_set_hash if successor_benchmark is not None else None
        ),
        predecessor_scorecard_id=(
            original_scorecard.scorecard_id if original_scorecard is not None else None
        ),
        predecessor_scorecard_hash=(
            scorecard_hash(original_scorecard) if original_scorecard is not None else None
        ),
        recompute_scorecard_id=(
            recompute_scorecard.scorecard_id if recompute_scorecard is not None else None
        ),
        recompute_scorecard_hash=(
            scorecard_hash(recompute_scorecard) if recompute_scorecard is not None else None
        ),
    )


def outcome_affects_precision_recall(outcome: NovelDeterminationOutcome) -> bool:
    """Unresolved and rejected novel candidates do not enter the reference set."""
    return outcome in {
        NovelDeterminationOutcome.CONFIRMED,
        NovelDeterminationOutcome.QUALIFIED,
    }
