"""PR9 / issue #6: matcher-audit pilot protocol and blinding."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from opencritique_evaluation.matcher_audit import (
    DEFAULT_PROTOCOL,
    AuditDecision,
    AuditJudgment,
    DisagreementCategory,
    MatcherConfig,
    analyze_audit_judgments,
    configuration_gate,
    stratify_match_decisions,
)
from opencritique_evaluation.models import ConcernMatch
from opencritique_registry.api import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_protocol_document_exists() -> None:
    path = ROOT / "docs" / "matcher-audit-protocol.md"
    text = path.read_text(encoding="utf-8")
    assert "stratified" in text.lower() or "Strata" in text
    assert "invalidate" in text.lower()
    assert DEFAULT_PROTOCOL.human_audit_may_invalidate_policy is True
    assert DEFAULT_PROTOCOL.model_judgments_not_gold is True
    assert DEFAULT_PROTOCOL.target_sample_size >= 100


def test_stratified_blinded_sample() -> None:
    match = ConcernMatch(
        submitted_local_id="s1",
        reference_concern_id="occon_ref_1",
        score=0.56,
        anchor_score=0.5,
        type_score=0.5,
        lexical_score=0.5,
    )
    sample = stratify_match_decisions(
        matches=[("occase_a", "1.0.0", "ml", match)],
        unmatched_submitted=[("occase_a", "1.0.0", "s2")],
        unmatched_reference=[("occase_a", "1.0.0", "occon_ref_2")],
        ambiguous_anchors=[("occase_a", "1.0.0", "ambiguous-quote")],
        type_disagreements=[("occase_a", "1.0.0", match)],
        severity_disagreements=[],
        domain_by_case={("occase_a", "1.0.0"): "empirical_ml"},
        config=MatcherConfig(threshold=0.55),
        seed=DEFAULT_PROTOCOL.random_seed,
        target_size=20,
    )
    assert sample.candidates
    assert all(c.system_identity_hidden for c in sample.candidates)
    assert all("system_id" not in c.blinded_payload for c in sample.candidates)
    assert all("leaderboard_rank" not in c.blinded_payload for c in sample.candidates)


def test_agreement_and_policy_invalidation() -> None:
    match = ConcernMatch(
        submitted_local_id="s1",
        reference_concern_id="occon_ref_1",
        score=0.9,
        anchor_score=0.9,
        type_score=0.9,
        lexical_score=0.9,
    )
    sample = stratify_match_decisions(
        matches=[("occase_a", "1.0.0", "ml", match)],
        unmatched_submitted=[],
        unmatched_reference=[],
        ambiguous_anchors=[],
        type_disagreements=[],
        severity_disagreements=[],
        domain_by_case={("occase_a", "1.0.0"): "empirical_ml"},
        config=MatcherConfig(),
        seed=1,
        target_size=5,
    )
    cand = sample.candidates[0].candidate_id
    judgments = [
        AuditJudgment(
            candidate_id=cand,
            auditor_id="auditor-a",
            decision=AuditDecision.INCORRECT_MATCH,
            disagreement_category=DisagreementCategory.TYPE,
        ),
        AuditJudgment(
            candidate_id=cand,
            auditor_id="auditor-b",
            decision=AuditDecision.INCORRECT_MATCH,
            disagreement_category=DisagreementCategory.TYPE,
        ),
    ]
    report = analyze_audit_judgments(sample, judgments, invalidate_on_incorrect_rate=0.1)
    assert report.raw_agreement == 1.0
    assert report.policy_invalidated is True
    assert configuration_gate(report) == "failed"


def test_partial_not_collapsed_and_api() -> None:
    app = create_app(initialize=False)
    client = TestClient(app)
    proto = client.get("/v1/matcher-audit/protocol")
    assert proto.status_code == 200
    assert proto.json()["protocol_id"] == DEFAULT_PROTOCOL.protocol_id
    rules = client.get("/v1/matcher-audit/blinding-rules")
    assert rules.json()["system_identity_hidden"] is True

    match = ConcernMatch(
        submitted_local_id="s1",
        reference_concern_id="occon_ref_1",
        score=0.8,
        anchor_score=0.8,
        type_score=0.8,
        lexical_score=0.8,
    )
    sample = stratify_match_decisions(
        matches=[("occase_a", "1.0.0", "ml", match)],
        unmatched_submitted=[],
        unmatched_reference=[],
        ambiguous_anchors=[],
        type_disagreements=[],
        severity_disagreements=[],
        domain_by_case={("occase_a", "1.0.0"): "empirical_ml"},
        config=MatcherConfig(),
        seed=2,
        target_size=3,
    )
    cand = sample.candidates[0].candidate_id
    bad = client.post(
        "/v1/matcher-audit/analyze",
        json={
            "sample": sample.model_dump(mode="json"),
            "judgments": [
                {
                    "candidate_id": cand,
                    "auditor_id": "a1",
                    "decision": "partial_overbroad_match",
                    "disagreement_category": "none",
                    "notes": "",
                    "decided_at": "2026-07-28T00:00:00Z",
                }
            ],
        },
    )
    assert bad.status_code == 400

    studio = (ROOT / "src/opencritique_registry/studio_assets/index.html").read_text(
        encoding="utf-8"
    )
    assert "Matcher audit" in studio or "matcher audit" in studio.lower()
