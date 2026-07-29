"""End-to-end synthetic adapter convert → evaluate → scorecard (claims locked)."""

from __future__ import annotations

from pathlib import Path

from opencritique_adapters.coarse import convert_coarse_benchmark
from opencritique_adapters.openreviewer import convert_openreviewer_benchmark
from opencritique_evaluation.engine import evaluate, load_manifest
from opencritique_evaluation.models import EvaluationResult, EvaluationSubmission
from opencritique_evaluation.scorecard import build_scorecard

ROOT = Path(__file__).resolve().parents[1]


def _assert_claims_locked(scorecard_disclosure: str, *, authorized: bool) -> None:
    assert authorized is False
    assert "NOT AUTHORIZED" in scorecard_disclosure.upper()


def _round_trip_submission(submission) -> EvaluationSubmission:
    """Match CLI path: convert → JSON → evaluate → scorecard."""
    return EvaluationSubmission.model_validate(submission.model_dump(mode="json"))


def _round_trip_result(result: EvaluationResult) -> EvaluationResult:
    return EvaluationResult.model_validate(result.model_dump(mode="json"))


def test_coarse_synth_convert_evaluate_scorecard_claims_locked() -> None:
    bench = ROOT / "benchmarks" / "coarse-synth-v0.1"
    manifest_path = bench / "manifest.json"
    mapping = ROOT / "fixtures" / "coarse" / "maps" / "synth-map.json"
    submission = _round_trip_submission(
        convert_coarse_benchmark(
            benchmark_manifest_path=manifest_path,
            benchmark_root=bench,
            map_path=mapping,
        )
    )
    benchmark = load_manifest(manifest_path)
    result = _round_trip_result(
        evaluate(
            benchmark=benchmark,
            benchmark_root=bench,
            submission=submission,
        )
    )
    scorecard = build_scorecard(result)
    _assert_claims_locked(
        scorecard.disclosure,
        authorized=result.performance_claim_authorized,
    )
    assert result.performance_claim_authorized is False
    assert scorecard.result.performance_claim_authorized is False
    assert result.metrics.submitted_concerns >= 1


def test_openreviewer_synth_convert_evaluate_scorecard_claims_locked() -> None:
    bench = ROOT / "benchmarks" / "openreviewer-synth-v0.1"
    manifest_path = bench / "manifest.json"
    mapping = ROOT / "fixtures" / "openreviewer" / "maps" / "synth-map.json"
    submission = _round_trip_submission(
        convert_openreviewer_benchmark(
            benchmark_manifest_path=manifest_path,
            benchmark_root=bench,
            map_path=mapping,
        )
    )
    benchmark = load_manifest(manifest_path)
    result = _round_trip_result(
        evaluate(
            benchmark=benchmark,
            benchmark_root=bench,
            submission=submission,
        )
    )
    scorecard = build_scorecard(result)
    _assert_claims_locked(
        scorecard.disclosure,
        authorized=result.performance_claim_authorized,
    )
    assert result.metrics.submitted_concerns >= 1
