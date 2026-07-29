from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from opencritique_schema.models import Anchor, Concern

from .models import (
    AnchorResolution,
    AnchorResolutionStatus,
    ConcernMatch,
    MatcherConfig,
    SubmittedAnchor,
    SubmittedConcern,
)

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u00ad", "")
    value = re.sub(r"-\s*\n\s*", "", value)
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value


def tokens(value: str) -> set[str]:
    return {item for item in _TOKEN_RE.findall(normalize_text(value)) if len(item) > 1}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def resolve_anchor(submitted: SubmittedAnchor, reference: list[Anchor]) -> AnchorResolution:
    exact: list[str] = []
    normalized: list[str] = []
    labels: list[str] = []
    pages: list[str] = []
    for anchor in reference:
        if submitted.source_text and anchor.source_text:
            if submitted.source_text == anchor.source_text:
                exact.append(anchor.anchor_id)
            elif normalize_text(submitted.source_text) == normalize_text(anchor.source_text):
                normalized.append(anchor.anchor_id)
        if submitted.object_label and anchor.object_label:
            if normalize_text(submitted.object_label) == normalize_text(anchor.object_label):
                labels.append(anchor.anchor_id)
        if (
            submitted.page is not None
            and anchor.page_start is not None
            and anchor.page_end is not None
        ):
            if anchor.page_start <= submitted.page <= anchor.page_end:
                pages.append(anchor.anchor_id)

    for status, values in (
        (AnchorResolutionStatus.EXACT, exact),
        (AnchorResolutionStatus.NORMALIZED, normalized),
        (AnchorResolutionStatus.OBJECT_LABEL, labels),
        (AnchorResolutionStatus.PAGE_ONLY, pages),
    ):
        unique = sorted(set(values))
        if len(unique) == 1:
            return AnchorResolution(
                submitted_index=0, status=status, reference_anchor_ids=unique
            )
        if len(unique) > 1:
            return AnchorResolution(
                submitted_index=0,
                status=AnchorResolutionStatus.AMBIGUOUS,
                reference_anchor_ids=unique,
            )
    return AnchorResolution(
        submitted_index=0,
        status=AnchorResolutionStatus.UNRESOLVED,
        reference_anchor_ids=[],
    )


def type_similarity(submitted: str, reference: str) -> float:
    left = submitted.casefold()
    right = reference.casefold()
    if left == right:
        return 1.0
    left_root = left.split(".", 1)[0]
    right_root = right.split(".", 1)[0]
    if left_root == right_root:
        return 0.75
    return 0.0


@dataclass(frozen=True)
class MatchCandidate:
    submitted: SubmittedConcern
    reference: Concern
    match: ConcernMatch


def score_candidate(
    submitted: SubmittedConcern,
    reference: Concern,
    resolved_anchor_ids: set[str],
    config: MatcherConfig | None = None,
) -> ConcernMatch:
    config = config or MatcherConfig()
    reference_anchors = set(reference.anchor_ids)
    if resolved_anchor_ids or reference_anchors:
        anchor_score = len(resolved_anchor_ids & reference_anchors) / max(
            len(resolved_anchor_ids | reference_anchors), 1
        )
    else:
        anchor_score = 0.0
    t_score = type_similarity(submitted.concern_type, reference.concern_type)
    lexical_score = jaccard(
        tokens(f"{submitted.title} {submitted.summary}"),
        tokens(f"{reference.title} {reference.summary}"),
    )
    total = (
        config.anchor_weight * anchor_score
        + config.type_weight * t_score
        + config.lexical_weight * lexical_score
    )
    return ConcernMatch(
        submitted_local_id=submitted.local_id,
        reference_concern_id=reference.concern_id,
        score=round(total, 6),
        anchor_score=round(anchor_score, 6),
        type_score=round(t_score, 6),
        lexical_score=round(lexical_score, 6),
    )


def greedy_match(
    submitted: list[SubmittedConcern],
    references: list[Concern],
    resolutions: dict[str, list[AnchorResolution]],
    config: MatcherConfig | None = None,
) -> list[ConcernMatch]:
    config = config or MatcherConfig()
    candidates: list[ConcernMatch] = []
    for concern in submitted:
        resolved_ids = {
            anchor_id
            for item in resolutions.get(concern.local_id, [])
            for anchor_id in item.reference_anchor_ids
        }
        for reference in references:
            match = score_candidate(concern, reference, resolved_ids, config)
            if match.score >= config.threshold:
                candidates.append(match)
    candidates.sort(key=lambda item: item.score, reverse=True)
    used_submitted: set[str] = set()
    used_reference: set[str] = set()
    selected: list[ConcernMatch] = []
    for candidate in candidates:
        if candidate.submitted_local_id in used_submitted:
            continue
        if candidate.reference_concern_id in used_reference:
            continue
        selected.append(candidate)
        used_submitted.add(candidate.submitted_local_id)
        used_reference.add(candidate.reference_concern_id)
    return selected
