"""Map upstream Coarse Review objects into OpenCritique CoarseReview JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from opencritique_adapters.coarse import (
    CoarseDetailedComment,
    CoarseOverviewFeedback,
    CoarseOverviewIssue,
    CoarseReview,
)

from .provenance import LiveProvenance


def _as_dict(value: Any) -> dict[str, Any]:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        payload = dump(mode="json")
        if isinstance(payload, dict):
            return payload
        raise TypeError(
            f"model_dump(mode='json') returned {type(payload)!r}, expected dict"
        )
    if isinstance(value, dict):
        return value
    raise TypeError(f"cannot map Coarse review payload of type {type(value)!r}")


def map_coarse_review(
    upstream_review: Any,
    *,
    provenance: LiveProvenance,
    loss_notes: list[str] | None = None,
) -> CoarseReview:
    """Convert a Coarse ``Review`` (or compatible mapping) to ``CoarseReview``.

    Field shapes match the public Coarse Review/DetailedComment contract used by
    the sample adapter. Extra upstream keys are preserved via ``extra="allow"``.
    """
    payload = _as_dict(upstream_review)
    notes = list(loss_notes or [])
    language = payload.get("language")
    if language is not None and not isinstance(language, dict):
        language = _as_dict(language)
        notes.append(
            "Mapped LanguageContext object to a plain dict for CoarseReview.language."
        )

    overall_raw = payload.get("overall_feedback") or {}
    if not isinstance(overall_raw, dict):
        overall_raw = _as_dict(overall_raw)
    issues = [
        CoarseOverviewIssue.model_validate(item if isinstance(item, dict) else _as_dict(item))
        for item in overall_raw.get("issues") or []
    ]
    overall = CoarseOverviewFeedback(
        summary=str(overall_raw.get("summary") or ""),
        assessment=str(overall_raw.get("assessment") or ""),
        issues=issues,
        recommendation=str(overall_raw.get("recommendation") or ""),
        revision_targets=[str(item) for item in overall_raw.get("revision_targets") or []],
    )

    comments: list[CoarseDetailedComment] = []
    for item in payload.get("detailed_comments") or []:
        raw = item if isinstance(item, dict) else _as_dict(item)
        comments.append(CoarseDetailedComment.model_validate(raw))

    if not comments:
        notes.append("Upstream review contained no detailed_comments.")

    date_value = str(payload.get("date") or datetime.now(UTC).strftime("%m/%d/%Y"))
    review = CoarseReview(
        title=str(payload.get("title") or "Untitled"),
        domain=str(payload.get("domain") or "unknown"),
        taxonomy=str(payload.get("taxonomy") or "unknown"),
        date=date_value,
        overall_feedback=overall,
        detailed_comments=comments,
        language=language,
    )
    # Stamp provenance without unlocking claims (extra="allow" on CoarseReview).
    stamped = review.model_dump(mode="json")
    stamped["opencritique_provenance"] = provenance.as_export_block()
    if notes:
        stamped["opencritique_conversion_notes"] = notes
    stamped["performance_claims_authorized"] = False
    return CoarseReview.model_validate(stamped)
