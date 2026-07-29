"""Matcher-audit denominators and session manifests (issue #6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencritique_evaluation.matcher_audit import (
    DEFAULT_PROTOCOL,
    AuditDecision,
    AuditEvidenceClass,
    AuditJudgment,
    DisagreementCategory,
    MatcherConfig,
    analyze_audit_judgments,
    build_session_manifest,
    load_session_manifest,
    measure_current_denominators,
    persist_session_manifest,
    stratify_match_decisions,
)
from opencritique_evaluation.models import ConcernMatch

ROOT = Path(__file__).resolve().parents[1]


def _sample() -> object:
    match = ConcernMatch(
        submitted_local_id="s1",
        reference_concern_id="occon_ref_1",
        score=0.56,
        anchor_score=0.5,
        type_score=0.5,
        lexical_score=0.5,
    )
    return stratify_match_decisions(
        matches=[("occase_a", "1.0.0", "ml", match)],
        unmatched_submitted=[("occase_a", "1.0.0", "s2")],
        unmatched_reference=[],
        ambiguous_anchors=[],
        type_disagreements=[],
        severity_disagreements=[],
        domain_by_case={("occase_a", "1.0.0"): "empirical_ml"},
        config=MatcherConfig(threshold=0.55),
        seed=DEFAULT_PROTOCOL.random_seed,
        target_size=10,
        evidence_class=AuditEvidenceClass.SAMPLE,
    )


def test_current_denominators_honest() -> None:
    account = measure_current_denominators(natural_decision_count=0, repo_root=ROOT)
    assert account.natural_decisions_available == 0
    assert account.natural_dod_met is False
    assert account.performance_claims_authorized is False
    assert account.sample_decisions_available >= 17  # 12 coarse + 5 openreviewer


def test_natural_empty_population_yields_empty_sample() -> None:
    sample = stratify_match_decisions(
        matches=[],
        unmatched_submitted=[],
        unmatched_reference=[],
        ambiguous_anchors=[],
        type_disagreements=[],
        severity_disagreements=[],
        domain_by_case={},
        config=MatcherConfig(),
        seed=1,
        evidence_class=AuditEvidenceClass.NATURAL,
        population_denominator=0,
    )
    assert sample.candidates == []
    assert sample.population_denominator == 0
    manifest = build_session_manifest(sample)
    assert manifest.natural_dod_met is False
    assert manifest.evidence_class == AuditEvidenceClass.NATURAL


def test_sample_session_cannot_claim_natural_dod() -> None:
    sample = _sample()
    manifest = build_session_manifest(sample)
    assert manifest.evidence_class == AuditEvidenceClass.SAMPLE
    assert manifest.natural_dod_met is False
    assert len(manifest.configuration_hash) == 64
    payload = manifest.model_dump(mode="json")
    payload["natural_dod_met"] = True
    with pytest.raises(ValueError, match="sample sessions"):
        type(manifest).model_validate(payload)


def test_persist_and_load_session_manifest(tmp_path: Path) -> None:
    sample = _sample()
    manifest = build_session_manifest(sample, session_id="ocmas_test")
    path = persist_session_manifest(manifest, tmp_path / "session.json")
    loaded = load_session_manifest(path)
    assert loaded.session_id == "ocmas_test"
    assert loaded.sampled_count == len(sample.candidates)
    assert loaded.performance_claims_authorized is False


def test_agreement_report_carries_evidence_class() -> None:
    sample = _sample()
    cand = sample.candidates[0].candidate_id
    report = analyze_audit_judgments(
        sample,
        [
            AuditJudgment(
                candidate_id=cand,
                auditor_id="a",
                decision=AuditDecision.CORRECT_MATCH,
                disagreement_category=DisagreementCategory.NONE,
            ),
            AuditJudgment(
                candidate_id=cand,
                auditor_id="b",
                decision=AuditDecision.CORRECT_MATCH,
                disagreement_category=DisagreementCategory.NONE,
            ),
        ],
    )
    assert report.evidence_class == AuditEvidenceClass.SAMPLE
    assert report.natural_dod_met is False
    assert "evidence_class=sample" in report.uncertainty_note


def test_denominator_doc_states_natural_zero() -> None:
    text = (ROOT / "docs" / "matcher-audit-denominators.md").read_text(encoding="utf-8")
    assert "**0**" in text or "natural | **0**" in text.lower() or "natural" in text.lower()
    assert "natural_dod_met" in text
