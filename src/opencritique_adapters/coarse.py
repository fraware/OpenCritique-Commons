from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, model_validator

from opencritique_evaluation.engine import load_case, load_manifest
from opencritique_evaluation.models import (
    CaseSubmission,
    EvaluationSubmission,
    SubmittedAnchor,
    SubmittedConcern,
    SystemManifest,
)
from opencritique_schema.coarse_adapter import CONFIDENCE_MAP, SEVERITY_MAP

_HTTP_URL = TypeAdapter(HttpUrl)


class CoarseCompatibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CoarseOverviewIssue(CoarseCompatibleModel):
    title: str
    body: str


class CoarseOverviewFeedback(CoarseCompatibleModel):
    summary: str = ""
    assessment: str = ""
    issues: list[CoarseOverviewIssue] = Field(default_factory=list)
    recommendation: str = ""
    revision_targets: list[str] = Field(default_factory=list)


class CoarseDetailedComment(CoarseCompatibleModel):
    number: int
    title: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    feedback: str = Field(min_length=1)
    status: str = "Pending"
    severity: Literal["critical", "major", "minor"] = "major"
    confidence: Literal["high", "medium", "low"] = "medium"


class CoarseReview(CoarseCompatibleModel):
    title: str
    domain: str
    taxonomy: str
    date: str
    overall_feedback: CoarseOverviewFeedback
    detailed_comments: list[CoarseDetailedComment]
    language: dict[str, Any] | None = None

    @model_validator(mode="after")
    def unique_comment_numbers(self) -> CoarseReview:
        numbers = [item.number for item in self.detailed_comments]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Coarse detailed comment numbers must be unique")
        return self


class CoarseCaseMap(CoarseCompatibleModel):
    case_id: str
    case_version: str
    review_path: str
    run_id: str | None = None
    failure: str | None = None
    abstained: bool = False

    @model_validator(mode="after")
    def state_consistency(self) -> CoarseCaseMap:
        if self.failure and self.abstained:
            raise ValueError("case cannot be both failed and abstained")
        return self


class CoarseBenchmarkMap(CoarseCompatibleModel):
    system_version: str
    coarse_commit: str | None = None
    model_identifiers: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    cases: list[CoarseCaseMap]
    declared_cost_currency: str | None = None
    declared_cost_minor: int | None = None
    declared_latency_seconds: float | None = None

    @model_validator(mode="after")
    def unique_cases(self) -> CoarseBenchmarkMap:
        keys = [(item.case_id, item.case_version) for item in self.cases]
        if len(keys) != len(set(keys)):
            raise ValueError("Coarse benchmark map cases must be unique")
        return self


def _config_hash(payload: CoarseBenchmarkMap) -> str:
    material = json.dumps(
        {
            "coarse_commit": payload.coarse_commit,
            "model_identifiers": payload.model_identifiers,
            "configuration": payload.configuration,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _local_id(case_id: str, comment: CoarseDetailedComment) -> str:
    material = (
        f"{case_id}\x1f{comment.number}\x1f{comment.title}\x1f{comment.quote}"
    ).encode()
    return f"coarse_{hashlib.sha256(material).hexdigest()[:20]}"


def convert_coarse_benchmark(
    *,
    benchmark_manifest_path: Path,
    benchmark_root: Path,
    map_path: Path,
) -> EvaluationSubmission:
    benchmark = load_manifest(benchmark_manifest_path)
    mapping = CoarseBenchmarkMap.model_validate_json(map_path.read_text(encoding="utf-8"))
    benchmark_keys = {(item.case_id, item.case_version) for item in benchmark.cases}
    map_keys = {(item.case_id, item.case_version) for item in mapping.cases}
    extras = map_keys - benchmark_keys
    if extras:
        raise ValueError(f"Coarse map contains cases outside benchmark: {sorted(extras)}")

    mapped = {(item.case_id, item.case_version): item for item in mapping.cases}
    cases: list[CaseSubmission] = []
    for ref in benchmark.cases:
        entry = mapped.get((ref.case_id, ref.case_version))
        if entry is None:
            cases.append(
                CaseSubmission(
                    case_id=ref.case_id,
                    case_version=ref.case_version,
                    abstained=True,
                )
            )
            continue
        if entry.failure:
            cases.append(
                CaseSubmission(
                    case_id=entry.case_id,
                    case_version=entry.case_version,
                    failure=entry.failure,
                )
            )
            continue
        if entry.abstained:
            cases.append(
                CaseSubmission(
                    case_id=entry.case_id,
                    case_version=entry.case_version,
                    abstained=True,
                )
            )
            continue
        review_path = (map_path.parent / entry.review_path).resolve()
        review = CoarseReview.model_validate_json(review_path.read_text(encoding="utf-8"))
        bundle = load_case(benchmark_root, ref.path)
        concerns = [
            SubmittedConcern(
                local_id=_local_id(ref.case_id, comment),
                title=comment.title,
                summary=comment.feedback,
                concern_type="adapter.coarse.unclassified",
                severity=SEVERITY_MAP[comment.severity],
                confidence=CONFIDENCE_MAP[comment.confidence],
                anchors=[SubmittedAnchor(source_text=comment.quote)],
                evidence_summary=(
                    "Converted from a Coarse DetailedComment. The quote is preserved verbatim; "
                    "claim reconstruction and concern taxonomy remain unverified."
                ),
            )
            for comment in review.detailed_comments
        ]
        # Validate that the benchmark artifact is a real OpenCritique case before accepting output.
        if not bundle.manuscript_versions:
            raise ValueError(f"benchmark case {ref.case_id} has no manuscript version")
        cases.append(
            CaseSubmission(
                case_id=entry.case_id,
                case_version=entry.case_version,
                concerns=concerns,
            )
        )

    system = SystemManifest(
        system_id="coarse",
        version=mapping.system_version,
        display_name="Coarse",
        description=(
            "Submission converted from Coarse's public Review/DetailedComment contract. "
            "OpenCritique does not infer claim validity from this conversion."
        ),
        repository_url=_HTTP_URL.validate_python("https://github.com/Davidvandijcke/coarse"),
        license="MIT",
        code_commit=mapping.coarse_commit,
        model_identifiers=mapping.model_identifiers,
        configuration_hash=_config_hash(mapping),
        execution_mode="external",
        declared_cost_currency=mapping.declared_cost_currency,
        declared_cost_minor=mapping.declared_cost_minor,
        declared_latency_seconds=mapping.declared_latency_seconds,
    )
    submission_material = json.dumps(
        {
            "system": system.model_dump(mode="json"),
            "benchmark": [benchmark.benchmark_id, benchmark.version],
            "cases": [item.model_dump(mode="json") for item in cases],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return EvaluationSubmission(
        submission_id=f"ocsub_{hashlib.sha256(submission_material).hexdigest()[:24]}",
        system=system,
        benchmark_id=benchmark.benchmark_id,
        benchmark_version=benchmark.version,
        cases=cases,
        created_at=datetime.now(UTC),
    )
