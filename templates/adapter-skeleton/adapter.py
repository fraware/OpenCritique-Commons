"""Skeleton adapter: upstream-shaped reviews -> EvaluationSubmission.

Copy into ``src/opencritique_adapters/<slug>.py`` and replace Example* names.
Wire ``convert_example_benchmark`` from the adapters CLI when ready.

This stub intentionally raises until you implement mapping against real sample
fixtures. Do not fabricate production authenticity.
"""

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
from opencritique_schema.models import Severity

from .contract import (
    EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED,
    EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID,
    EXAMPLE_UPSTREAM_CONTRACT_VERSION,
    EXAMPLE_UPSTREAM_REPOSITORY,
)

_HTTP_URL = TypeAdapter(HttpUrl)
_REPO = _HTTP_URL.validate_python(EXAMPLE_UPSTREAM_REPOSITORY)

assert EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED is False


class ExampleCompatibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ExampleFinding(ExampleCompatibleModel):
    finding_id: str
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    quote: str | None = None
    severity: Literal["critical", "major", "minor"] | None = None


class ExampleReview(ExampleCompatibleModel):
    title: str
    findings: list[ExampleFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_findings(self) -> ExampleReview:
        if not self.findings:
            raise ValueError("ExampleReview requires at least one finding")
        return self


class ExampleCaseMap(ExampleCompatibleModel):
    case_id: str
    case_version: str
    review_path: str
    abstained: bool = False
    failure: str | None = None


class ExampleBenchmarkMap(ExampleCompatibleModel):
    system_version: str
    example_commit: str | None = None
    contract_version: str = EXAMPLE_UPSTREAM_CONTRACT_VERSION
    model_identifiers: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    cases: list[ExampleCaseMap]


def _config_hash(payload: ExampleBenchmarkMap) -> str:
    material = json.dumps(
        {
            "example_commit": payload.example_commit,
            "contract_version": payload.contract_version,
            "model_identifiers": payload.model_identifiers,
            "configuration": payload.configuration,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _local_id(case_id: str, finding: ExampleFinding) -> str:
    material = f"{case_id}\x1f{finding.finding_id}\x1f{finding.title}".encode()
    return f"example_{hashlib.sha256(material).hexdigest()[:20]}"


def convert_example_benchmark(
    *,
    benchmark_manifest_path: Path,
    benchmark_root: Path,
    map_path: Path,
) -> EvaluationSubmission:
    """Convert mapped Example reviews into an EvaluationSubmission.

    Expand the body once ``fixtures/<slug>/`` sample reviews exist. Until then
    this function documents the required control flow.
    """
    benchmark = load_manifest(benchmark_manifest_path)
    mapping = ExampleBenchmarkMap.model_validate_json(map_path.read_text(encoding="utf-8"))
    benchmark_keys = {(item.case_id, item.case_version) for item in benchmark.cases}
    map_keys = {(item.case_id, item.case_version) for item in mapping.cases}
    extras = map_keys - benchmark_keys
    if extras:
        raise ValueError(f"Example map contains cases outside benchmark: {sorted(extras)}")

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
        review = ExampleReview.model_validate_json(review_path.read_text(encoding="utf-8"))
        bundle = load_case(benchmark_root, ref.path)
        if not bundle.manuscript_versions:
            raise ValueError(f"benchmark case {ref.case_id} has no manuscript version")
        concerns = [
            SubmittedConcern(
                local_id=_local_id(ref.case_id, finding),
                title=finding.title,
                summary=finding.body,
                concern_type="adapter.example.unclassified",
                severity=(
                    Severity.MAJOR
                    if finding.severity is None
                    else Severity(finding.severity)
                ),
                confidence=0.5,
                anchors=(
                    [SubmittedAnchor(source_text=finding.quote)] if finding.quote else []
                ),
                evidence_summary=(
                    "Converted from an Example finding. Claim reconstruction and "
                    "concern taxonomy remain unverified. Sample adapter only."
                ),
            )
            for finding in review.findings
        ]
        cases.append(
            CaseSubmission(
                case_id=entry.case_id,
                case_version=entry.case_version,
                concerns=concerns,
            )
        )

    system = SystemManifest(
        system_id="example",
        version=mapping.system_version,
        display_name="Example adapter",
        description=(
            "Skeleton submission from the adapter-authoring template. "
            "Not a production upstream; performance claims unauthorized."
        ),
        repository_url=_REPO,
        license="Apache-2.0",
        code_commit=mapping.example_commit or EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID,
        model_identifiers=mapping.model_identifiers,
        configuration_hash=_config_hash(mapping),
        execution_mode="external",
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
