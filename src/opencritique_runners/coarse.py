"""Live Coarse upstream runner (optional ``[live-coarse]`` extra)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from opencritique_adapters.coarse import CoarseReview

from .env import load_operator_env, prepare_coarse_provider_env
from .mapping import map_coarse_review
from .paths import assert_not_production_fixtures_path
from .protocol import LiveRunnerPlugin, RunnerRunResult
from .provenance import COARSE_LIVE_COMMIT_PIN, COARSE_LIVE_PACKAGE_PIN, LiveProvenance

DEFAULT_COARSE_MODEL = "openai/gpt-4o"

ReviewPaperFn = Callable[..., tuple[Any, str, Any]]


def _import_review_paper() -> ReviewPaperFn:
    try:
        from coarse import review_paper  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Coarse upstream is not installed. Install the live extra:\n"
            '  pip install -e ".[live-coarse]"\n'
            f"(pins {COARSE_LIVE_PACKAGE_PIN}, commit {COARSE_LIVE_COMMIT_PIN})"
        ) from exc
    return review_paper


def run_coarse_review(
    *,
    manuscript: Path,
    model: str = DEFAULT_COARSE_MODEL,
    skip_cost_gate: bool = True,
    review_paper: ReviewPaperFn | None = None,
    load_env: bool = True,
) -> tuple[CoarseReview, LiveProvenance, str]:
    """Invoke upstream ``review_paper`` and map to ``CoarseReview``.

    ``review_paper`` may be injected for tests. Default CI must not call paid APIs.
    """
    from .env import format_live_runner_error, redact_secrets

    if load_env:
        load_operator_env()
    prepare_coarse_provider_env()
    manuscript = manuscript.resolve()
    if not manuscript.is_file():
        raise FileNotFoundError(f"manuscript not found: {manuscript}")

    invoke = review_paper if review_paper is not None else _import_review_paper()
    try:
        upstream_review, markdown, _paper_text = invoke(
            pdf_path=manuscript,
            model=model,
            skip_cost_gate=skip_cost_gate,
        )
    except Exception as exc:  # noqa: BLE001 - surface actionable CLI errors
        if isinstance(exc, (FileNotFoundError, RuntimeError, ValueError)):
            # Preserve typed failures; still redact any accidental key material.
            message = redact_secrets(str(exc))
            if message != str(exc):
                raise type(exc)(message) from exc
            raise
        raise RuntimeError(format_live_runner_error(exc)) from exc
    provenance = LiveProvenance(
        model_id=model,
        manuscript_path=str(manuscript),
        notes=[
            "Private live Coarse run. Not production authenticity.",
            "performance_claims_authorized remains false.",
        ],
    )
    mapped = map_coarse_review(upstream_review, provenance=provenance)
    return mapped, provenance, markdown


def write_coarse_export(
    review: CoarseReview,
    output: Path,
    *,
    markdown: str | None = None,
    markdown_output: Path | None = None,
) -> Path:
    """Serialize a live Coarse export; refuse production fixture paths."""
    assert_not_production_fixtures_path(output)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = review.model_dump(mode="json")
    payload["performance_claims_authorized"] = False
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if markdown is not None and markdown_output is not None:
        assert_not_production_fixtures_path(markdown_output)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown, encoding="utf-8")
    return output


class CoarseRunnerPlugin:
    """Thin ``LiveRunnerPlugin`` adapter over ``run_coarse_review`` / ``write_coarse_export``."""

    @property
    def name(self) -> str:
        return "coarse"

    @property
    def live_extra(self) -> str | None:
        return "live-coarse"

    def run(self, manuscript: Path, **kwargs: Any) -> RunnerRunResult:
        review, provenance, markdown = run_coarse_review(manuscript=manuscript, **kwargs)
        return RunnerRunResult(review=review, provenance=provenance, markdown=markdown)

    def write_export(
        self,
        result: RunnerRunResult,
        output: Path,
        *,
        markdown_output: Path | None = None,
    ) -> Path:
        return write_coarse_export(
            result.review,
            output,
            markdown=result.markdown or None,
            markdown_output=markdown_output,
        )


def coarse_runner_plugin() -> LiveRunnerPlugin:
    """Return the Coarse plugin (typed as the shared protocol)."""
    return CoarseRunnerPlugin()
