"""Blinded matcher-audit API (issue #6)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from opencritique_evaluation.matcher_audit import (
    DEFAULT_PROTOCOL,
    AuditAgreementReport,
    AuditDecision,
    AuditJudgment,
    DisagreementCategory,
    MatcherAuditProtocol,
    MatcherAuditSample,
    analyze_audit_judgments,
    configuration_gate,
)

router = APIRouter(prefix="/v1/matcher-audit", tags=["matcher-audit"])


class AuditJudgmentBatch(BaseModel):
    judgments: list[AuditJudgment] = Field(min_length=1)


class AuditAnalyzeRequest(BaseModel):
    sample: MatcherAuditSample
    judgments: list[AuditJudgment] = Field(min_length=1)


@router.get("/protocol", response_model=MatcherAuditProtocol)
def get_protocol() -> MatcherAuditProtocol:
    return DEFAULT_PROTOCOL


@router.get("/blinding-rules")
def blinding_rules() -> dict[str, str | bool]:
    return {
        "system_identity_hidden": True,
        "leaderboard_hidden": True,
        "model_judgments_not_gold": True,
        "human_audit_may_invalidate_policy": True,
        "rule": DEFAULT_PROTOCOL.blinding,
    }


@router.post("/analyze", response_model=AuditAgreementReport)
def analyze(payload: AuditAnalyzeRequest) -> AuditAgreementReport:
    # Ensure submitted judgments only reference blinded candidate ids.
    known = {c.candidate_id for c in payload.sample.candidates}
    for item in payload.judgments:
        if item.candidate_id not in known:
            raise HTTPException(status_code=400, detail=f"unknown candidate_id {item.candidate_id}")
        partial = item.decision == AuditDecision.PARTIAL_OVERBROAD
        uncategorized = item.disagreement_category == DisagreementCategory.NONE
        if partial and uncategorized:
            # Partial matches must be categorized, not silently treated as exact.
            raise HTTPException(
                status_code=400,
                detail="partial/overbroad matches require a disagreement_category",
            )
    return analyze_audit_judgments(payload.sample, payload.judgments)


@router.post("/configuration-gate")
def gate(payload: AuditAnalyzeRequest) -> dict[str, str | bool | None]:
    report = analyze_audit_judgments(payload.sample, payload.judgments)
    status = configuration_gate(report)
    return {
        "gate": status,
        "policy_invalidated": report.policy_invalidated,
        "matcher_config_gate_passed": report.matcher_config_gate_passed,
        "disclosure": (
            "Scorecards must disclose matcher version and whether the manual audit gate passed. "
            "Human audits may invalidate a matching policy."
        ),
    }
