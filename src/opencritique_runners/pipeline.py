"""Orchestrate live Coarse → convert → eval/scorecard or registry handoff."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opencritique_adapters.coarse import (
    CoarseBenchmarkMap,
    CoarseCaseMap,
    CoarseReview,
    convert_coarse_benchmark,
)
from opencritique_evaluation.engine import evaluate, load_manifest
from opencritique_evaluation.scorecard import build_scorecard, write_html, write_json

from .coarse import DEFAULT_COARSE_MODEL, ReviewPaperFn, run_coarse_review, write_coarse_export
from .env import load_operator_env
from .paths import assert_not_production_fixtures_path
from .provenance import COARSE_LIVE_COMMIT_PIN, LiveProvenance

CLAIMS_BANNER = (
    "NOT AUTHORIZED - private live / sample gold != production authenticity "
    "!= scientific performance claims (performance_claims_authorized=false)."
)

# Maintainer sample manuscripts that already have gold concerns in synth benches.
_SAMPLE_GOLD: dict[str, dict[str, str]] = {
    "corpus/samples/sample-econ-01/manuscript.md": {
        "case_id": "occase_synth_econ_01",
        "case_version": "1.0.0",
        "benchmark_root": "benchmarks/coarse-synth-v0.1",
    },
}


@dataclass(frozen=True)
class GoldBinding:
    case_id: str
    case_version: str
    benchmark_root: Path
    manifest_path: Path


@dataclass(frozen=True)
class CoarsePipelineResult:
    review_path: Path
    provenance: LiveProvenance
    submission_path: Path | None
    evaluation_path: Path | None
    scorecard_json: Path | None
    scorecard_html: Path | None
    handoff: str | None
    claims_authorized: bool = False


def _repo_root() -> Path:
    # src/opencritique_runners/pipeline.py → parents[2] = repo root
    return Path(__file__).resolve().parents[2]


def _normalize_repo_relative(path: Path, *, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def resolve_gold_binding(
    manuscript: Path,
    *,
    benchmark_root: Path | None = None,
    case_id: str | None = None,
    case_version: str | None = None,
    repo_root: Path | None = None,
) -> GoldBinding | None:
    """Resolve gold concerns for a manuscript when a synth bench binding exists."""
    root = repo_root or _repo_root()
    rel = _normalize_repo_relative(manuscript, root=root)
    preset = _SAMPLE_GOLD.get(rel)
    if preset is None and case_id is None:
        return None
    bench = (
        benchmark_root
        if benchmark_root is not None
        else root / (preset["benchmark_root"] if preset else "")
    )
    if benchmark_root is None and preset is None:
        return None
    if not bench.is_dir():
        return None
    binding_case = case_id or (preset["case_id"] if preset else None)
    binding_version = case_version or (preset["case_version"] if preset else "1.0.0")
    if not binding_case:
        return None
    manifest = bench / "manifest.json"
    if not manifest.is_file():
        return None
    return GoldBinding(
        case_id=binding_case,
        case_version=binding_version,
        benchmark_root=bench.resolve(),
        manifest_path=manifest.resolve(),
    )


def _write_json(path: Path, payload: object) -> Path:
    assert_not_production_fixtures_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump = getattr(payload, "model_dump", None)
    if callable(dump):
        text = json.dumps(dump(mode="json"), indent=2, sort_keys=True)
    else:
        text = json.dumps(payload, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def build_live_coarse_map(
    *,
    review_path: Path,
    map_path: Path,
    gold: GoldBinding,
    model_id: str,
    system_version: str = "live-byok-0.1",
) -> Path:
    """Write a one-case CoarseBenchmarkMap pointing at a live export."""
    assert_not_production_fixtures_path(map_path)
    relative_review = _relpath(review_path, map_path.parent)
    mapping = CoarseBenchmarkMap(
        system_version=system_version,
        coarse_commit=COARSE_LIVE_COMMIT_PIN,
        model_identifiers=[model_id],
        configuration={
            "execution_mode": "byok",
            "evidence_class": "private_live",
            "performance_claims_authorized": False,
        },
        cases=[
            CoarseCaseMap(
                case_id=gold.case_id,
                case_version=gold.case_version,
                review_path=relative_review,
                run_id=f"ocrun_live_{gold.case_id}",
            )
        ],
    )
    return _write_json(map_path, mapping)


def _relpath(target: Path, start: Path) -> str:
    return Path(target).resolve().relative_to(Path(start).resolve()).as_posix()


def run_coarse_pipeline(
    *,
    manuscript: Path,
    out_dir: Path,
    model: str = DEFAULT_COARSE_MODEL,
    benchmark_root: Path | None = None,
    case_id: str | None = None,
    case_version: str | None = None,
    review_paper: ReviewPaperFn | None = None,
    load_env: bool = True,
    write_scorecard_html: bool = True,
) -> CoarsePipelineResult:
    """Live review → export → convert/eval when gold exists; else registry handoff."""
    if load_env:
        load_operator_env()
    assert_not_production_fixtures_path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    review, provenance, markdown = run_coarse_review(
        manuscript=manuscript,
        model=model,
        review_paper=review_paper,
        load_env=False,
    )
    review_path = write_coarse_export(
        review,
        out_dir / "coarse-review.json",
        markdown=markdown,
        markdown_output=out_dir / "coarse-review.md",
    )
    _write_json(out_dir / "provenance.json", provenance)

    gold = resolve_gold_binding(
        manuscript,
        benchmark_root=benchmark_root,
        case_id=case_id,
        case_version=case_version,
    )
    if gold is None:
        handoff = (
            "No gold concerns bound to this manuscript. Export written; "
            "convert/eval skipped. Next: register for Studio with "
            f"`opencritique-registry import-live-run --from {review_path}` "
            "(or re-run pipeline with --register), or seed samples via "
            "bootstrap-sample-workspace. "
            + CLAIMS_BANNER
        )
        _write_json(
            out_dir / "handoff.json",
            {
                "status": "registry_handoff",
                "review_path": str(review_path),
                "message": handoff,
                "evidence_class": "private_live",
                "next": (
                    "opencritique-registry import-live-run "
                    f"--from {review_path}"
                ),
                "performance_claims_authorized": False,
            },
        )
        return CoarsePipelineResult(
            review_path=review_path,
            provenance=provenance,
            submission_path=None,
            evaluation_path=None,
            scorecard_json=None,
            scorecard_html=None,
            handoff=handoff,
            claims_authorized=False,
        )

    map_path = build_live_coarse_map(
        review_path=review_path,
        map_path=out_dir / "live-map.json",
        gold=gold,
        model_id=model,
    )
    submission = convert_coarse_benchmark(
        benchmark_manifest_path=gold.manifest_path,
        benchmark_root=gold.benchmark_root,
        map_path=map_path,
    )
    # Force claims locked on the converted system manifest path via evaluation.
    submission_path = _write_json(out_dir / "coarse-submission.json", submission)
    benchmark = load_manifest(gold.manifest_path)
    result = evaluate(
        benchmark=benchmark,
        benchmark_root=gold.benchmark_root,
        submission=submission,
    )
    if result.performance_claim_authorized:
        raise RuntimeError("invariant violated: live pipeline must keep claims locked")
    evaluation_path = _write_json(out_dir / "evaluation-result.json", result)
    scorecard = build_scorecard(result)
    scorecard_json = out_dir / "scorecard.json"
    write_json(scorecard, scorecard_json)
    scorecard_html: Path | None = None
    if write_scorecard_html:
        scorecard_html = out_dir / "scorecard.html"
        write_html(scorecard, scorecard_html)
    summary = {
        "status": "evaluated",
        "review_path": str(review_path),
        "submission_path": str(submission_path),
        "evaluation_path": str(evaluation_path),
        "scorecard_json": str(scorecard_json),
        "scorecard_html": str(scorecard_html) if scorecard_html else None,
        "performance_claims_authorized": False,
        "banner": CLAIMS_BANNER,
    }
    _write_json(out_dir / "pipeline-summary.json", summary)
    return CoarsePipelineResult(
        review_path=review_path,
        provenance=provenance,
        submission_path=submission_path,
        evaluation_path=evaluation_path,
        scorecard_json=scorecard_json,
        scorecard_html=scorecard_html,
        handoff=None,
        claims_authorized=False,
    )


def mock_review_from_fixture(fixture_path: Path) -> Callable[..., tuple[Any, str, Any]]:
    """Build a ``review_paper`` double that returns a fixture CoarseReview shape."""

    def _review_paper(
        pdf_path: str | Path,
        model: str | None = None,
        **_kwargs: object,
    ) -> tuple[Any, str, Any]:
        review = CoarseReview.model_validate_json(fixture_path.read_text(encoding="utf-8"))
        payload = review.model_dump(mode="json")
        # Strip sample-only fixture metadata so mapping stamps live provenance.
        payload.pop("opencritique_fixture", None)
        return payload, f"# mocked review for {pdf_path}\nmodel={model}\n", object()

    return _review_paper
