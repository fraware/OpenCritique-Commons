"""OpenReviewer import / live export surface.

OpenReviewer is Llama-OpenReviewer-8B (Hugging Face), not OpenAI Chat Completions.
An OpenAI / BYOK key does **not** run this path. Local HF generation lives in
``hf_local`` (optional ``[live-openreviewer]`` extra). Import mode needs no GPU.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from opencritique_adapters.openreviewer import OpenReviewerFinding, OpenReviewerReview

from .paths import assert_not_production_fixtures_path
from .protocol import LiveRunnerPlugin, RunnerRunResult

OPENREVIEWER_UPSTREAM_SLUG = "maxidl/openreviewer"
OPENREVIEWER_UPSTREAM_REPOSITORY = "https://github.com/maxidl/openreviewer"
OPENREVIEWER_HF_MODEL_ID = "maxidl/Llama-OpenReviewer-8B"
OPENREVIEWER_HF_SPACE = "https://huggingface.co/spaces/maxidl/openreviewer"
DEFAULT_VENUE_TEMPLATE = "ICLR2025"

_RATING_INLINE_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:#{1,3}\s*)?rating\s*\n+([0-9]+(?:\.[0-9]+)?)"
)
_WEAKNESS_HEADER = re.compile(
    r"(?im)^(?:#{1,3}\s*)?(?:weak(?:ness(?:es)?)?|weak points?)\s*$"
)
_BULLET = re.compile(r"(?m)^\s*[-*]\s+(.+)$")


class OpenReviewerProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upstream: str = OPENREVIEWER_UPSTREAM_SLUG
    upstream_repository: str = OPENREVIEWER_UPSTREAM_REPOSITORY
    model_id: str | None = None
    execution_mode: Literal["import", "hf_local"] = "import"
    evidence_class: Literal["private_live"] = "private_live"
    performance_claims_authorized: bool = False
    imported_at: str
    notes: list[str] = Field(default_factory=list)

    @field_validator("performance_claims_authorized")
    @classmethod
    def _claims_locked(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return False


class OpenReviewerLiveExport(OpenReviewerReview):
    """OpenReviewer-shaped export with live/import provenance stamped."""

    opencritique_provenance: OpenReviewerProvenance


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_recommendation_score(markdown: str) -> float | None:
    match = _RATING_INLINE_RE.search(markdown)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    for line in markdown.splitlines():
        lowered = line.strip().lower()
        if lowered.startswith("rating"):
            digits = re.search(r"([0-9]+(?:\.[0-9]+)?)", line)
            if digits:
                try:
                    return float(digits.group(1))
                except ValueError:
                    return None
    return None


def _findings_from_markdown(markdown: str) -> list[OpenReviewerFinding]:
    lines = markdown.splitlines()
    in_weak = False
    bodies: list[str] = []
    for line in lines:
        if _WEAKNESS_HEADER.match(line.strip()):
            in_weak = True
            continue
        if in_weak and re.match(r"(?im)^(?:#{1,3}\s+)\S", line):
            in_weak = False
            continue
        if in_weak:
            bullet = _BULLET.match(line)
            if bullet:
                bodies.append(bullet.group(1).strip())
    findings: list[OpenReviewerFinding] = []
    for index, body in enumerate(bodies, start=1):
        title = body if len(body) >= 3 else f"Finding {index}"
        padded = body if len(body) >= 10 else f"{body} (imported)"
        findings.append(
            OpenReviewerFinding(
                finding_id=f"f{index}",
                title=title[:120],
                body=padded,
                section="weaknesses",
            )
        )
    return findings


def live_export_from_generated_markdown(
    markdown: str,
    *,
    venue_template: str = DEFAULT_VENUE_TEMPLATE,
    model_id: str = OPENREVIEWER_HF_MODEL_ID,
    title: str | None = None,
    notes: str | list[str] | None = None,
) -> OpenReviewerLiveExport:
    note_list = (
        [notes]
        if isinstance(notes, str)
        else list(notes or [])
    )
    provenance = OpenReviewerProvenance(
        model_id=model_id,
        execution_mode="hf_local",
        imported_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        notes=note_list
        or [
            "HF local OpenReviewer generation. Not powered by OpenAI/BYOK credentials.",
        ],
    )
    return OpenReviewerLiveExport(
        title=title or "OpenReviewer HF local review",
        venue_template=venue_template,
        markdown=markdown,
        recommendation_score=_parse_recommendation_score(markdown),
        findings=_findings_from_markdown(markdown),
        model_identifiers=[model_id],
        original_sha256=_sha256_text(markdown),
        opencritique_provenance=provenance,
    )


def import_openreviewer_export(
    export_path: Path | None = None,
    *,
    source: Path | None = None,
    venue_template: str | None = None,
    title: str | None = None,
) -> OpenReviewerLiveExport:
    """Normalize a Space / local export into an OpenReviewer-shaped live export."""
    path_arg = export_path if export_path is not None else source
    if path_arg is None:
        raise ValueError("provide export_path or source for OpenReviewer import")
    path = path_arg.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"export not found: {path}")
    raw = path.read_text(encoding="utf-8")
    payload: dict[str, Any]
    if path.suffix.lower() in {".md", ".markdown", ".txt"}:
        payload = {"markdown": raw}
    else:
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"markdown": raw}
        else:
            if isinstance(loaded, str):
                payload = {"markdown": loaded}
            elif isinstance(loaded, dict):
                payload = loaded
            else:
                raise ValueError("OpenReviewer export JSON must be an object or string")
        if "review" in payload and "markdown" not in payload:
            payload = {**payload, "markdown": str(payload["review"])}
        for alt in ("generated_review", "review_markdown", "text", "content"):
            if alt in payload and "markdown" not in payload:
                payload = {**payload, "markdown": str(payload[alt])}
                break

    markdown = str(payload.get("markdown") or "").strip()
    findings_raw = payload.get("findings") or []
    findings = [
        OpenReviewerFinding.model_validate(item) for item in findings_raw
    ]
    if not findings and markdown:
        findings = _findings_from_markdown(markdown)
    if not markdown and not findings:
        raise ValueError("OpenReviewer export requires markdown and/or findings")

    score = payload.get("recommendation_score")
    if score is None and markdown:
        score = _parse_recommendation_score(markdown)

    models = [str(item) for item in payload.get("model_identifiers") or []]
    if not models:
        models = [OPENREVIEWER_HF_MODEL_ID]
    provenance = OpenReviewerProvenance(
        model_id=models[0],
        execution_mode="import",
        imported_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        notes=[
            "Imported OpenReviewer export (Space or local). "
            f"HF Space reference: {OPENREVIEWER_HF_SPACE}. "
            "OpenAI/BYOK keys are not used for this path.",
            "performance_claims_authorized remains false.",
        ],
    )
    return OpenReviewerLiveExport(
        title=title or str(payload.get("title") or path.stem),
        venue_template=venue_template
        or str(payload.get("venue_template") or DEFAULT_VENUE_TEMPLATE),
        markdown=markdown or "# Review\n\n(imported structured findings only)\n",
        recommendation_score=float(score) if score is not None else None,
        findings=findings,
        model_identifiers=models,
        original_sha256=str(payload.get("original_sha256") or _sha256_text(raw)),
        opencritique_provenance=provenance,
    )


def write_openreviewer_live_export(export: OpenReviewerLiveExport, output: Path) -> Path:
    """Serialize a live/import export; refuse production fixture paths."""
    assert_not_production_fixtures_path(output)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = export.model_dump(mode="json")
    payload["performance_claims_authorized"] = False
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def run_openreviewer_review(*, manuscript: Path, **kwargs: object) -> OpenReviewerLiveExport:
    """Dispatch to HF local runner when available."""
    from .hf_local import run_openreviewer_hf_local

    return run_openreviewer_hf_local(manuscript, **kwargs)  # type: ignore[arg-type]


class OpenReviewerRunnerPlugin:
    """Thin ``LiveRunnerPlugin`` adapter over OpenReviewer import / HF local paths.

    ``run`` requires HF local (``[live-openreviewer]``). Import-only operators
    should call ``import_openreviewer_export`` + ``write_export`` instead of
    ``run`` — OpenAI/BYOK keys do not power this plugin.
    """

    @property
    def name(self) -> str:
        return "openreviewer"

    @property
    def live_extra(self) -> str | None:
        return "live-openreviewer"

    def run(self, manuscript: Path, **kwargs: Any) -> RunnerRunResult:
        export = run_openreviewer_review(manuscript=manuscript, **kwargs)
        return RunnerRunResult(
            review=export,
            provenance=export.opencritique_provenance,
            markdown=export.markdown,
        )

    def write_export(
        self,
        result: RunnerRunResult,
        output: Path,
        *,
        markdown_output: Path | None = None,
    ) -> Path:
        review = result.review
        if isinstance(review, OpenReviewerLiveExport):
            path = write_openreviewer_live_export(review, output)
        else:
            # Allow writing a pre-built live export passed as review.
            path = write_openreviewer_live_export(
                OpenReviewerLiveExport.model_validate(review),
                output,
            )
        if markdown_output is not None:
            assert_not_production_fixtures_path(markdown_output)
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            text = result.markdown
            if not text and isinstance(review, OpenReviewerLiveExport):
                text = review.markdown
            markdown_output.write_text(text, encoding="utf-8")
        return path


def openreviewer_runner_plugin() -> LiveRunnerPlugin:
    """Return the OpenReviewer plugin (typed as the shared protocol)."""
    return OpenReviewerRunnerPlugin()
