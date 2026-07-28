"""OpenReviewer-style adapter: markdown/template reviews → EvaluationSubmission."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from opencritique_evaluation.engine import load_case, load_manifest
from opencritique_evaluation.models import (
    CaseSubmission,
    EvaluationSubmission,
    SubmittedAnchor,
    SubmittedConcern,
    SystemManifest,
)
from opencritique_schema.models import Severity

OPENREVIEWER_CONTRACT_VERSION = "openreviewer-markdown-template-v1"
OPENREVIEWER_REPOSITORY = "https://github.com/maxidl/openreviewer"
OPENREVIEWER_FIXTURE_KIND = "synthetic_rights_cleared_maintainer"
OPENREVIEWER_PERFORMANCE_CLAIMS_AUTHORIZED = False

_WEAKNESS_RE = re.compile(
    r"(?im)^(?:#{1,3}\s*)?(?:weak(?:ness(?:es)?)?|weak points?)\s*$"
)
_BULLET_RE = re.compile(r"(?m)^\s*[-*]\s+(.+)$")


class OpenReviewerCompatibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class OpenReviewerFinding(OpenReviewerCompatibleModel):
    finding_id: str
    title: str = Field(min_length=3)
    body: str = Field(min_length=10)
    section: str | None = None
    # Explicitly optional — must remain unavailable when absent.
    severity: Literal["critical", "major", "moderate", "minor"] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    quote: str | None = None
    page: int | None = Field(default=None, ge=1)


class OpenReviewerReview(OpenReviewerCompatibleModel):
    """Contract for OpenReviewer-style outputs (markdown and/or structured findings)."""

    title: str
    venue_template: str
    markdown: str
    recommendation_score: float | None = Field(default=None, ge=0, le=10)
    findings: list[OpenReviewerFinding] = Field(default_factory=list)
    model_identifiers: list[str] = Field(default_factory=list)
    original_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_content(self) -> OpenReviewerReview:
        if not self.markdown.strip() and not self.findings:
            raise ValueError("OpenReviewer review requires markdown and/or findings")
        return self


class OpenReviewerCaseMap(OpenReviewerCompatibleModel):
    case_id: str
    case_version: str
    review_path: str
    abstained: bool = False
    failure: str | None = None


class OpenReviewerBenchmarkMap(OpenReviewerCompatibleModel):
    system_version: str
    openreviewer_commit: str | None = None
    contract_version: str = OPENREVIEWER_CONTRACT_VERSION
    model_identifiers: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    cases: list[OpenReviewerCaseMap]


def provenance_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _config_hash(payload: OpenReviewerBenchmarkMap) -> str:
    material = json.dumps(
        {
            "openreviewer_commit": payload.openreviewer_commit,
            "contract_version": payload.contract_version,
            "model_identifiers": payload.model_identifiers,
            "configuration": payload.configuration,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def parse_weaknesses_from_markdown(markdown: str) -> list[OpenReviewerFinding]:
    """Extract weakness bullets when structured findings are absent.

    Does not invent severity, confidence, or anchors.
    """
    lines = markdown.splitlines()
    findings: list[OpenReviewerFinding] = []
    in_weak = False
    idx = 0
    for line in lines:
        if _WEAKNESS_RE.match(line.strip()):
            in_weak = True
            continue
        if in_weak and line.startswith("#"):
            break
        if in_weak:
            match = _BULLET_RE.match(line)
            if match:
                idx += 1
                body = match.group(1).strip()
                findings.append(
                    OpenReviewerFinding(
                        finding_id=f"md-weak-{idx}",
                        title=body[:80],
                        body=body if len(body) >= 10 else f"{body} (see review prose)",
                        section="weaknesses",
                        severity=None,
                        confidence=None,
                        quote=None,
                        page=None,
                    )
                )
    return findings


def _severity_or_unavailable(value: str | None) -> Severity:
    # When severity is absent, do not invent a scientific grade — use informational
    # and mark uncertainty in evidence_summary.
    mapping = {
        "critical": Severity.CRITICAL,
        "major": Severity.MAJOR,
        "moderate": Severity.MODERATE,
        "minor": Severity.MINOR,
    }
    if value is None:
        return Severity.INFORMATIONAL
    return mapping.get(value, Severity.INFORMATIONAL)


def findings_to_concerns(
    case_id: str, findings: list[OpenReviewerFinding]
) -> list[SubmittedConcern]:
    concerns: list[SubmittedConcern] = []
    for finding in findings:
        material = f"{case_id}\x1f{finding.finding_id}\x1f{finding.title}".encode()
        local_id = f"orv_{hashlib.sha256(material).hexdigest()[:20]}"
        missing: list[str] = []
        if finding.severity is None:
            missing.append("severity")
        if finding.confidence is None:
            missing.append("confidence")
        if not (finding.quote or finding.page):
            missing.append("anchors")
        label = None
        if not (finding.quote or finding.page):
            label = finding.section or "review_prose"
        anchor = SubmittedAnchor(
            page=finding.page,
            source_text=finding.quote,
            object_label=label,
        )
        evidence = (
            "Converted from an OpenReviewer-style finding. "
            "Claims and taxonomy remain provisional. "
            + (
                f"Unavailable upstream fields left unavailable: {', '.join(missing)}."
                if missing
                else "All mapped optional fields were present."
            )
        )
        concerns.append(
            SubmittedConcern(
                local_id=local_id,
                title=finding.title,
                summary=finding.body,
                concern_type="adapter.openreviewer.unclassified",
                severity=_severity_or_unavailable(finding.severity),
                confidence=0.0 if finding.confidence is None else finding.confidence,
                anchors=[anchor],
                evidence_summary=evidence,
            )
        )
    return concerns


def convert_openreviewer_benchmark(
    *,
    benchmark_manifest_path: Path,
    benchmark_root: Path,
    map_path: Path,
) -> EvaluationSubmission:
    benchmark = load_manifest(benchmark_manifest_path)
    mapping = OpenReviewerBenchmarkMap.model_validate_json(map_path.read_text(encoding="utf-8"))
    if mapping.contract_version != OPENREVIEWER_CONTRACT_VERSION:
        raise ValueError(
            f"unsupported OpenReviewer contract {mapping.contract_version}; "
            f"expected {OPENREVIEWER_CONTRACT_VERSION}"
        )
    mapped = {(item.case_id, item.case_version): item for item in mapping.cases}
    cases: list[CaseSubmission] = []
    for ref in benchmark.cases:
        entry = mapped.get((ref.case_id, ref.case_version))
        if entry is None:
            cases.append(
                CaseSubmission(case_id=ref.case_id, case_version=ref.case_version, abstained=True)
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
        raw = review_path.read_bytes()
        digest = provenance_hash(raw)
        review = OpenReviewerReview.model_validate_json(raw)
        if review.original_sha256 and review.original_sha256 != digest:
            raise ValueError(f"provenance hash mismatch for {review_path}")
        # Preserve original bytes by hash even when the field was omitted.
        review = review.model_copy(update={"original_sha256": digest})
        findings = list(review.findings) or parse_weaknesses_from_markdown(review.markdown)
        bundle = load_case(benchmark_root, ref.path)
        if not bundle.manuscript_versions:
            raise ValueError(f"benchmark case {ref.case_id} has no manuscript version")
        cases.append(
            CaseSubmission(
                case_id=entry.case_id,
                case_version=entry.case_version,
                concerns=findings_to_concerns(entry.case_id, findings),
            )
        )

    system = SystemManifest(
        system_id="openreviewer",
        version=mapping.system_version,
        display_name="OpenReviewer",
        description=(
            "Submission converted from an OpenReviewer-style markdown/template contract. "
            "Unavailable severity, confidence, or anchors remain unavailable. "
            "OpenCritique does not infer reviewer quality from this conversion."
        ),
        repository_url=OPENREVIEWER_REPOSITORY,
        license="research-open-weights",
        code_commit=mapping.openreviewer_commit,
        model_identifiers=mapping.model_identifiers,
        configuration_hash=_config_hash(mapping),
        execution_mode="external",
    )
    material = json.dumps(
        {
            "system": system.model_dump(mode="json"),
            "benchmark": [benchmark.benchmark_id, benchmark.version],
            "cases": [item.model_dump(mode="json") for item in cases],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return EvaluationSubmission(
        submission_id=f"ocsub_{hashlib.sha256(material).hexdigest()[:24]}",
        system=system,
        benchmark_id=benchmark.benchmark_id,
        benchmark_version=benchmark.version,
        cases=cases,
        created_at=datetime.now(UTC),
    )
