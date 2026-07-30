"""PR E: only adjudicated gold enters performance denominators."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from opencritique_evaluation.engine import evaluate
from opencritique_evaluation.models import (
    BenchmarkCaseRef,
    BenchmarkEvidenceClass,
    BenchmarkManifest,
    CaseSubmission,
    EvaluationSubmission,
    ReferenceCompleteness,
    SubmittedAnchor,
    SubmittedConcern,
    SystemManifest,
)
from opencritique_evaluation.novel_determination import (
    NovelDeterminationOutcome,
    outcome_affects_precision_recall,
)
from opencritique_evaluation.reference_policy import (
    DEFAULT_GOLD_STATUS_WEIGHTS,
    EMPTY_GOLD_WITHHOLD_REASON,
    eligible_references,
    gold_weight,
    is_eligible_gold_reference,
)
from opencritique_schema.canonical import content_hash
from opencritique_schema.models import (
    ActorReference,
    ActorType,
    Anchor,
    AnchorResolutionStatus,
    AnchorType,
    ArtifactReference,
    CaseBundle,
    Claim,
    ClaimType,
    Concern,
    ConcernOrigin,
    ConcernOriginType,
    ConcernStatus,
    Explicitness,
    IngestionMetadata,
    Manuscript,
    ManuscriptVersion,
    ResolutionDisposition,
    RightsClassification,
    Severity,
    SourceFormat,
    VerificationGrade,
)

ACTOR = ActorReference(
    actor_id="opencritique-test",
    actor_type=ActorType.SYSTEM,
    display_name="test",
)
NOW = datetime(2026, 1, 1, tzinfo=UTC)
QUOTE = "Identification fails under clustered sampling without robust variance."


def _hashed(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def _concern(
    *,
    suffix: str,
    status: ConcernStatus,
    disposition: ResolutionDisposition | None = None,
    version_id: str,
    claim_id: str,
    anchor_id: str,
) -> Concern:
    payload: dict = {
        "id": f"occon_gold_pol_{suffix}",
        "concern_id": f"occon_gold_pol_{suffix}",
        "created_at": NOW,
        "created_by": ACTOR,
        "manuscript_version_id": version_id,
        "title": f"Gold policy concern {suffix}",
        "summary": f"Summary for gold policy concern {suffix}.",
        "concern_type": "methodological.selection",
        "claim_ids": [claim_id],
        "anchor_ids": [anchor_id],
        "severity": Severity.MODERATE,
        "confidence": 0.85,
        "verification_grade": VerificationGrade.V1,
        "status": status,
        "potential_consequence": "Inference may be overconfident.",
        "required_resolution": "Clarify reporting.",
        "origin": ConcernOrigin(
            origin_type=ConcernOriginType.HUMAN,
            origin_id="unit-test-curation",
        ),
    }
    if disposition is not None:
        payload["resolution_disposition"] = disposition
    return _hashed(Concern, payload)


def _write_bench(
    root: Path,
    *,
    concerns: list[Concern],
    matched_local_ids: list[str] | None = None,
) -> tuple[BenchmarkManifest, EvaluationSubmission]:
    case_id = "occase_gold_pol_01"
    case_version = "1.0.0"
    version_id = "ocver_gold_pol_01_v1"
    manuscript_id = "ocms_gold_pol_01"
    anchor_id = "ocanc_gold_pol_01_q1"
    claim_id = "occlm_gold_pol_01_c1"

    artifact = ArtifactReference(
        uri="memory://gold-policy.md",
        sha256=hashlib.sha256(QUOTE.encode()).hexdigest(),
        media_type="text/markdown",
        byte_size=len(QUOTE.encode()),
    )
    manuscript = _hashed(
        Manuscript,
        {
            "id": manuscript_id,
            "manuscript_id": manuscript_id,
            "created_at": NOW,
            "created_by": ACTOR,
            "title": "[TEST] Gold policy fixture",
            "rights_classification": RightsClassification.PUBLIC,
            "consent_policy_id": "test-policy-v1",
            "current_version_id": version_id,
        },
    )
    version = _hashed(
        ManuscriptVersion,
        {
            "id": version_id,
            "version_id": version_id,
            "created_at": NOW,
            "created_by": ACTOR,
            "manuscript_id": manuscript_id,
            "source_format": SourceFormat.MARKDOWN,
            "source_artifact": artifact,
            "language": "en",
            "domain_profile": "economics_statistics",
            "page_count": 1,
            "ingestion_metadata": IngestionMetadata(
                method="unit_test",
                tool="tests/test_reference_eligibility.py",
                tool_version="0.5.0a1",
            ),
        },
    )
    anchor = _hashed(
        Anchor,
        {
            "id": anchor_id,
            "anchor_id": anchor_id,
            "created_at": NOW,
            "created_by": ACTOR,
            "manuscript_version_id": version_id,
            "anchor_type": AnchorType.TEXT_SPAN,
            "page_start": 1,
            "page_end": 1,
            "source_text": QUOTE,
            "normalized_text": QUOTE.casefold(),
            "resolution_status": AnchorResolutionStatus.EXACT,
            "extraction_confidence": 1.0,
        },
    )
    claim = _hashed(
        Claim,
        {
            "id": claim_id,
            "claim_id": claim_id,
            "created_at": NOW,
            "created_by": ACTOR,
            "manuscript_version_id": version_id,
            "statement": "Clustered sampling identification claim",
            "claim_type": ClaimType.METHODOLOGICAL,
            "explicitness": Explicitness.EXPLICIT,
            "scope": "unit test manuscript",
            "anchor_ids": [anchor_id],
            "reconstruction_notes": "Direct quote fixture.",
            "approval_status": "candidate",
        },
    )
    # Re-bind concern claim/anchor ids to this fixture's shared graph.
    rebound: list[Concern] = []
    for index, concern in enumerate(concerns):
        rebound.append(
            _concern(
                suffix=f"{index}_{concern.status.value}",
                status=concern.status,
                disposition=concern.resolution_disposition,
                version_id=version_id,
                claim_id=claim_id,
                anchor_id=anchor_id,
            )
        )

    bundle = CaseBundle(
        case_id=case_id,
        case_version=case_version,
        policy_version="case-policy-v0.1",
        case_type="microcase",
        manuscript=manuscript,
        manuscript_versions=[version],
        anchors=[anchor],
        claims=[claim],
        concerns=rebound,
        evidence=[],
        counterpositions=[],
        adjudications=[],
        known_ambiguities=["Unit-test gold eligibility fixture."],
    )
    case_dir = root / "cases" / "GOLD-01"
    case_dir.mkdir(parents=True)
    case_path = case_dir / "case.json"
    case_path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    case_set_hash = hashlib.sha256(case_path.read_bytes()).hexdigest()
    manifest = BenchmarkManifest(
        benchmark_id="ocbench_gold_policy_unit",
        version="0.1.0",
        title="Gold policy unit fixture",
        description="Minimal complete_seeded benchmark for gold eligibility",
        evidence_class=BenchmarkEvidenceClass.SYNTHETIC_SCIENTIFIC,
        reference_completeness=ReferenceCompleteness.COMPLETE_SEEDED,
        domain_profiles=["economics_statistics"],
        cases=[
            BenchmarkCaseRef(
                case_id=case_id,
                case_version=case_version,
                path="cases/GOLD-01/case.json",
            )
        ],
        license="Apache-2.0",
        case_set_hash=case_set_hash,
        created_at=NOW,
        limitations=["Unit test fixture only."],
    )
    (root / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    submitted: list[SubmittedConcern] = []
    for local_id, concern in zip(
        matched_local_ids or [f"s{i}" for i in range(len(rebound))],
        rebound,
        strict=False,
    ):
        submitted.append(
            SubmittedConcern(
                local_id=local_id,
                title=concern.title,
                summary=concern.summary,
                concern_type=concern.concern_type,
                severity=Severity.MODERATE,
                confidence=0.9,
                anchors=[SubmittedAnchor(page=1, source_text=QUOTE)],
            )
        )
    if not submitted:
        submitted.append(
            SubmittedConcern(
                local_id="s_orphan",
                title="Orphan submitted concern",
                summary="Submitted against an empty or non-gold reference set.",
                concern_type="reporting.typo",
                severity=Severity.MINOR,
                confidence=0.5,
                anchors=[SubmittedAnchor(page=1, source_text="no matching quote")],
            )
        )

    submission = EvaluationSubmission(
        submission_id="ocsub_gold_policy",
        system=SystemManifest(
            system_id="sys_gold_policy",
            version="0.0.1",
            display_name="Gold Policy System",
            configuration_hash="b" * 64,
        ),
        benchmark_id=manifest.benchmark_id,
        benchmark_version=manifest.version,
        cases=[
            CaseSubmission(
                case_id=case_id,
                case_version=case_version,
                concerns=submitted,
            )
        ],
        created_at=NOW,
    )
    return manifest, submission


def _stub_concern(
    status: ConcernStatus,
    disposition: ResolutionDisposition | None = None,
) -> Concern:
    """Lightweight concern for policy-unit tests (ids are rebound in _write_bench)."""
    return _concern(
        suffix="stub",
        status=status,
        disposition=disposition,
        version_id="ocver_gold_pol_01_v1",
        claim_id="occlm_gold_pol_01_c1",
        anchor_id="ocanc_gold_pol_01_q1",
    )


def test_policy_confirmed_and_qualified_are_gold() -> None:
    confirmed = _stub_concern(ConcernStatus.CONFIRMED)
    qualified = _stub_concern(ConcernStatus.QUALIFIED)
    assert is_eligible_gold_reference(confirmed)
    assert is_eligible_gold_reference(qualified)
    assert gold_weight(confirmed) == DEFAULT_GOLD_STATUS_WEIGHTS[ConcernStatus.CONFIRMED] == 1.0
    assert gold_weight(qualified) == DEFAULT_GOLD_STATUS_WEIGHTS[ConcernStatus.QUALIFIED] == 1.0
    assert eligible_references([confirmed, qualified]) == [confirmed, qualified]


def test_policy_proposed_unresolved_rejected_outside_denominators() -> None:
    pool = [
        _stub_concern(ConcernStatus.PROPOSED),
        _stub_concern(ConcernStatus.UNDER_REVIEW),
        _stub_concern(ConcernStatus.UNRESOLVED),
        _stub_concern(ConcernStatus.REJECTED),
        _stub_concern(ConcernStatus.SUPERSEDED),
    ]
    assert eligible_references(pool) == []
    for item in pool:
        assert not is_eligible_gold_reference(item)


def test_policy_resolved_disposition_split() -> None:
    correction = _stub_concern(
        ConcernStatus.RESOLVED,
        ResolutionDisposition.MANUSCRIPT_CORRECTION,
    )
    withdrawn = _stub_concern(
        ConcernStatus.RESOLVED,
        ResolutionDisposition.WITHDRAWN,
    )
    rejected = _stub_concern(
        ConcernStatus.RESOLVED,
        ResolutionDisposition.REJECTED,
    )
    bare = _stub_concern(ConcernStatus.RESOLVED)
    assert is_eligible_gold_reference(correction)
    assert gold_weight(correction) == 1.0
    assert not is_eligible_gold_reference(withdrawn)
    assert not is_eligible_gold_reference(rejected)
    assert not is_eligible_gold_reference(bare)
    assert bare.resolution_disposition is None


def test_resolution_disposition_forbidden_unless_resolved() -> None:
    with pytest.raises(ValidationError, match="resolution_disposition"):
        _concern(
            suffix="bad",
            status=ConcernStatus.CONFIRMED,
            disposition=ResolutionDisposition.MANUSCRIPT_CORRECTION,
            version_id="ocver_gold_pol_01_v1",
            claim_id="occlm_gold_pol_01_c1",
            anchor_id="ocanc_gold_pol_01_q1",
        )


def test_novel_determination_orientation_aligns_with_gold_policy() -> None:
    assert outcome_affects_precision_recall(NovelDeterminationOutcome.CONFIRMED)
    assert outcome_affects_precision_recall(NovelDeterminationOutcome.QUALIFIED)
    assert not outcome_affects_precision_recall(NovelDeterminationOutcome.REJECTED)
    assert not outcome_affects_precision_recall(NovelDeterminationOutcome.UNRESOLVED)
    assert set(DEFAULT_GOLD_STATUS_WEIGHTS) == {
        ConcernStatus.CONFIRMED,
        ConcernStatus.QUALIFIED,
    }


def test_proposed_and_unresolved_do_not_inflate_denominators(tmp_path: Path) -> None:
    root = tmp_path / "bench"
    root.mkdir()
    manifest, submission = _write_bench(
        root,
        concerns=[
            _stub_concern(ConcernStatus.PROPOSED),
            _stub_concern(ConcernStatus.UNRESOLVED),
        ],
    )
    result = evaluate(benchmark=manifest, benchmark_root=root, submission=submission)
    m = result.metrics
    assert m.eligible_reference_concerns == 0
    assert m.precision.value is None
    assert m.recall.value is None
    assert EMPTY_GOLD_WITHHOLD_REASON.split(";")[0] in (m.precision.withheld_reason or "")
    assert "no eligible gold" in (m.recall.withheld_reason or "")
    assert "fall back" in (m.recall.withheld_reason or "")


def test_confirmed_and_qualified_enter_denominators(tmp_path: Path) -> None:
    root = tmp_path / "bench"
    root.mkdir()
    manifest, submission = _write_bench(
        root,
        concerns=[
            _stub_concern(ConcernStatus.CONFIRMED),
            _stub_concern(ConcernStatus.QUALIFIED),
        ],
        matched_local_ids=["s1", "s2"],
    )
    result = evaluate(benchmark=manifest, benchmark_root=root, submission=submission)
    m = result.metrics
    assert m.eligible_reference_concerns == 2
    assert m.matched_concerns == 2
    assert m.recall.value == 1.0
    assert m.precision.value == 1.0
    assert m.recall.withheld_reason is None
    assert m.precision.withheld_reason is None


def test_resolved_manuscript_correction_in_withdrawn_out(tmp_path: Path) -> None:
    root = tmp_path / "bench"
    root.mkdir()
    manifest, submission = _write_bench(
        root,
        concerns=[
            _stub_concern(
                ConcernStatus.RESOLVED,
                ResolutionDisposition.MANUSCRIPT_CORRECTION,
            ),
            _stub_concern(
                ConcernStatus.RESOLVED,
                ResolutionDisposition.WITHDRAWN,
            ),
        ],
        matched_local_ids=["s1", "s2"],
    )
    result = evaluate(benchmark=manifest, benchmark_root=root, submission=submission)
    m = result.metrics
    assert m.eligible_reference_concerns == 1
    assert m.matched_concerns == 1
    assert m.missed_reference == 0
    assert m.recall.value == 1.0
    # One submitted concern targets the non-gold withdrawn reference and is unmatched.
    assert m.unmatched_submitted == 1
    assert m.precision.value == 0.5


def test_empty_eligible_withholds_without_rejected_pool_fallback(tmp_path: Path) -> None:
    root = tmp_path / "bench"
    root.mkdir()
    manifest, submission = _write_bench(
        root,
        concerns=[
            _stub_concern(ConcernStatus.REJECTED),
            _stub_concern(ConcernStatus.SUPERSEDED),
            _stub_concern(ConcernStatus.RESOLVED),  # bare resolved → fail-closed
        ],
    )
    result = evaluate(benchmark=manifest, benchmark_root=root, submission=submission)
    m = result.metrics
    assert m.eligible_reference_concerns == 0
    assert m.matched_concerns == 0
    assert m.precision.value is None
    assert m.recall.value is None
    assert m.severity_weighted_precision.value is None
    assert m.severity_weighted_recall.value is None
    assert m.false_critical_per_manuscript.value is None
    assert m.reference_match_brier_score.value is None
    for metric in (
        m.precision,
        m.recall,
        m.severity_weighted_precision,
        m.severity_weighted_recall,
        m.false_critical_per_manuscript,
        m.reference_match_brier_score,
    ):
        assert metric.withheld_reason is not None
        assert "no eligible gold" in metric.withheld_reason
        assert "fall back" in metric.withheld_reason
