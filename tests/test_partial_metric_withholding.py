"""PR D: withhold precision-family metrics on incomplete reference sets."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from opencritique_adapters.coarse import convert_coarse_benchmark
from opencritique_adapters.openreviewer import convert_openreviewer_benchmark
from opencritique_evaluation.engine import evaluate, load_manifest
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
from opencritique_evaluation.scorecard import build_scorecard, write_html
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
    RightsClassification,
    Severity,
    SourceFormat,
    VerificationGrade,
)

ROOT = Path(__file__).resolve().parents[1]
ACTOR = ActorReference(
    actor_id="opencritique-test",
    actor_type=ActorType.SYSTEM,
    display_name="test",
)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _hashed(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def _assert_withheld(metric, *, substring: str) -> None:
    assert metric.value is None
    assert metric.withheld_reason is not None
    assert substring in metric.withheld_reason


def _assert_reference_recall(metric) -> None:
    assert metric.withheld_reason is not None
    assert "reference recall only" in metric.withheld_reason
    assert "not true scientific recall" in metric.withheld_reason


def test_unknown_synth_fixtures_withhold_precision_family() -> None:
    bench = ROOT / "benchmarks" / "coarse-synth-v0.1"
    mapping = ROOT / "fixtures" / "coarse" / "maps" / "synth-map.json"
    submission = EvaluationSubmission.model_validate(
        convert_coarse_benchmark(
            benchmark_manifest_path=bench / "manifest.json",
            benchmark_root=bench,
            map_path=mapping,
        ).model_dump(mode="json")
    )
    benchmark = load_manifest(bench / "manifest.json")
    assert benchmark.reference_completeness == ReferenceCompleteness.UNKNOWN
    result = evaluate(
        benchmark=benchmark, benchmark_root=bench, submission=submission
    )
    m = result.metrics
    _assert_withheld(m.precision, substring="incomplete")
    _assert_withheld(m.severity_weighted_precision, substring="incomplete")
    _assert_withheld(m.false_critical_per_manuscript, substring="incomplete")
    _assert_withheld(m.reference_match_brier_score, substring="incomplete")
    assert "adjudication candidates" in (m.precision.withheld_reason or "")
    assert m.novel_candidates_pending_adjudication == m.unmatched_submitted
    assert m.unmatched_submitted >= 1
    _assert_reference_recall(m.recall)
    _assert_reference_recall(m.severity_weighted_recall)

    scorecard = build_scorecard(result)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "scorecard.html"
        write_html(scorecard, path)
        html = path.read_text(encoding="utf-8")
    assert "Withheld" in html
    assert "Reference-match Brier score" in html
    assert "Reference recall" in html
    assert "Adjudication candidates" in html


def test_openreviewer_unknown_withholds_brier_and_precision() -> None:
    bench = ROOT / "benchmarks" / "openreviewer-synth-v0.1"
    mapping = ROOT / "fixtures" / "openreviewer" / "maps" / "synth-map.json"
    submission = EvaluationSubmission.model_validate(
        convert_openreviewer_benchmark(
            benchmark_manifest_path=bench / "manifest.json",
            benchmark_root=bench,
            map_path=mapping,
        ).model_dump(mode="json")
    )
    benchmark = load_manifest(bench / "manifest.json")
    assert benchmark.reference_completeness == ReferenceCompleteness.UNKNOWN
    result = evaluate(
        benchmark=benchmark, benchmark_root=bench, submission=submission
    )
    _assert_withheld(result.metrics.precision, substring="incomplete")
    _assert_withheld(result.metrics.reference_match_brier_score, substring="incomplete")
    assert (
        result.metrics.novel_candidates_pending_adjudication
        == result.metrics.unmatched_submitted
    )


def _write_complete_seeded_fixture(root: Path) -> tuple[BenchmarkManifest, EvaluationSubmission]:
    case_id = "occase_complete_seeded_01"
    case_version = "1.0.0"
    version_id = "ocver_complete_seeded_01_v1"
    manuscript_id = "ocms_complete_seeded_01"
    anchor_id = "ocanc_complete_seeded_01_q1"
    claim_id = "occlm_complete_seeded_01_c1"
    concern_id = "occon_complete_seeded_01_k1"
    quote = "Identification fails under clustered sampling without robust variance."

    artifact = ArtifactReference(
        uri="memory://complete-seeded.md",
        sha256=hashlib.sha256(quote.encode()).hexdigest(),
        media_type="text/markdown",
        byte_size=len(quote.encode()),
    )
    manuscript = _hashed(
        Manuscript,
        {
            "id": manuscript_id,
            "manuscript_id": manuscript_id,
            "created_at": NOW,
            "created_by": ACTOR,
            "title": "[TEST] Complete seeded fixture",
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
                tool="tests/test_partial_metric_withholding.py",
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
            "source_text": quote,
            "normalized_text": quote.casefold(),
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
    concern = _hashed(
        Concern,
        {
            "id": concern_id,
            "concern_id": concern_id,
            "created_at": NOW,
            "created_by": ACTOR,
            "manuscript_version_id": version_id,
            "title": "Missing robust variance under clustering",
            "summary": "The manuscript does not report cluster-robust standard errors.",
            "concern_type": "methodological.selection",
            "claim_ids": [claim_id],
            "anchor_ids": [anchor_id],
            "severity": Severity.MODERATE,
            "confidence": 0.85,
            "verification_grade": VerificationGrade.V1,
            "status": ConcernStatus.CONFIRMED,
            "potential_consequence": "Inference may be overconfident.",
            "required_resolution": "Report cluster-robust standard errors.",
            "origin": ConcernOrigin(
                origin_type=ConcernOriginType.HUMAN,
                origin_id="unit-test-curation",
            ),
        },
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
        concerns=[concern],
        evidence=[],
        counterpositions=[],
        adjudications=[],
        known_ambiguities=["Unit-test complete seeded fixture."],
    )
    case_dir = root / "cases" / "COMPLETE-01"
    case_dir.mkdir(parents=True)
    case_path = case_dir / "case.json"
    case_path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    case_set_hash = hashlib.sha256(case_path.read_bytes()).hexdigest()
    manifest = BenchmarkManifest(
        benchmark_id="ocbench_complete_seeded_unit",
        version="0.1.0",
        title="Complete seeded unit fixture",
        description="Minimal complete_seeded benchmark for metric withholding tests",
        evidence_class=BenchmarkEvidenceClass.SYNTHETIC_SCIENTIFIC,
        reference_completeness=ReferenceCompleteness.COMPLETE_SEEDED,
        domain_profiles=["economics_statistics"],
        cases=[
            BenchmarkCaseRef(
                case_id=case_id,
                case_version=case_version,
                path="cases/COMPLETE-01/case.json",
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
    system = SystemManifest(
        system_id="sys_complete_seeded",
        version="0.0.1",
        display_name="Complete Seeded System",
        configuration_hash="a" * 64,
    )
    matched = SubmittedConcern(
        local_id="s1",
        title=concern.title,
        summary=concern.summary,
        concern_type=concern.concern_type,
        severity=Severity.MODERATE,
        confidence=0.9,
        anchors=[SubmittedAnchor(page=1, source_text=quote)],
    )
    unmatched_fp = SubmittedConcern(
        local_id="s2",
        title="Unrelated fabricated concern about typography",
        summary="This concern is intentionally unmatched for FP scoring.",
        concern_type="reporting.typo",
        severity=Severity.CRITICAL,
        confidence=0.4,
        anchors=[SubmittedAnchor(page=1, source_text="no such quote anywhere")],
    )
    submission = EvaluationSubmission(
        submission_id="ocsub_complete_seeded",
        system=system,
        benchmark_id=manifest.benchmark_id,
        benchmark_version=manifest.version,
        cases=[
            CaseSubmission(
                case_id=case_id,
                case_version=case_version,
                concerns=[matched, unmatched_fp],
            )
        ],
        created_at=NOW,
    )
    return manifest, submission


def test_complete_seeded_still_computes_precision_family(tmp_path: Path) -> None:
    root = tmp_path / "bench"
    root.mkdir()
    manifest, submission = _write_complete_seeded_fixture(root)
    result = evaluate(
        benchmark=manifest, benchmark_root=root, submission=submission
    )
    m = result.metrics
    assert m.precision.value is not None
    assert m.severity_weighted_precision.value is not None
    assert m.false_critical_per_manuscript.value is not None
    assert m.reference_match_brier_score.value is not None
    assert m.recall.value is not None
    assert m.recall.withheld_reason is None
    assert m.matched_concerns == 1
    assert m.unmatched_submitted == 1
    assert m.false_critical_per_manuscript.numerator == 1.0
    assert m.precision.value == 0.5

    scorecard = build_scorecard(result)
    html_path = tmp_path / "scorecard.html"
    write_html(scorecard, html_path)
    html = html_path.read_text(encoding="utf-8")
    assert "Reference-match Brier score" in html
    assert ">Recall</th>" in html
    assert "Reference recall" not in html
    assert m.precision.value is not None
    assert "Withheld" not in html.split("False critical")[0]  # precision/recall rows present


def test_partial_natural_withholds_like_unknown(tmp_path: Path) -> None:
    root = tmp_path / "bench"
    root.mkdir()
    manifest, submission = _write_complete_seeded_fixture(root)
    partial = manifest.model_copy(
        update={"reference_completeness": ReferenceCompleteness.PARTIAL_NATURAL}
    )
    result = evaluate(
        benchmark=partial, benchmark_root=root, submission=submission
    )
    m = result.metrics
    _assert_withheld(m.precision, substring="partial_natural")
    _assert_withheld(m.severity_weighted_precision, substring="partial_natural")
    _assert_withheld(m.false_critical_per_manuscript, substring="partial_natural")
    _assert_withheld(m.reference_match_brier_score, substring="partial_natural")
    assert m.novel_candidates_pending_adjudication == m.unmatched_submitted == 1
    # Unmatched critical must not inflate false-critical when incomplete.
    assert m.false_critical_per_manuscript.value is None
    _assert_reference_recall(m.recall)
    if m.recall.value is not None:
        assert m.recall.value == 1.0
