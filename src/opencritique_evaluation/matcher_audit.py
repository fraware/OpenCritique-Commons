"""Matcher-audit pilot: stratified sampling, blinding, agreement categories."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ConcernMatch, MatcherConfig


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AuditStratum(str, Enum):
    NEAR_THRESHOLD_ACCEPT = "near_threshold_accept"
    FAR_THRESHOLD_ACCEPT = "far_threshold_accept"
    UNMATCHED_SUBMITTED = "unmatched_submitted"
    UNMATCHED_REFERENCE = "unmatched_reference"
    AMBIGUOUS_ANCHOR = "ambiguous_anchor"
    TYPE_DISAGREEMENT = "type_disagreement"
    SEVERITY_DISAGREEMENT = "severity_disagreement"
    DOMAIN = "domain"


class AuditDecision(str, Enum):
    CORRECT_MATCH = "correct_match"
    PARTIAL_OVERBROAD = "partial_overbroad_match"
    INCORRECT_MATCH = "incorrect_match"
    UNRESOLVED = "unresolved"


class DisagreementCategory(str, Enum):
    NONE = "none"
    BOUNDARY = "boundary"
    TYPE = "type"
    SEVERITY = "severity"
    ANCHOR = "anchor"
    NOVELTY = "novelty"
    OTHER = "other"


class AuditCandidate(StrictModel):
    candidate_id: str
    stratum: AuditStratum
    case_id: str
    case_version: str
    submitted_local_id: str | None = None
    reference_concern_id: str | None = None
    match_score: float | None = None
    domain_profile: str | None = None
    blinded_payload: dict[str, Any]
    system_identity_hidden: bool = True


class AuditJudgment(StrictModel):
    candidate_id: str
    auditor_id: str
    decision: AuditDecision
    disagreement_category: DisagreementCategory = DisagreementCategory.NONE
    notes: str = ""
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MatcherAuditProtocol(StrictModel):
    protocol_version: str = "0.1"
    protocol_id: str = "matcher-audit-pilot-v0.1"
    population: str
    strata: list[AuditStratum]
    target_sample_size: int = Field(ge=1)
    random_seed: int
    blinding: str
    adjudication: str
    analysis: str
    human_audit_may_invalidate_policy: bool = True
    model_judgments_not_gold: bool = True


class MatcherAuditSample(StrictModel):
    sample_version: str = "0.1"
    protocol_id: str
    random_seed: int
    matcher_config: MatcherConfig
    candidates: list[AuditCandidate]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def unique_candidates(self) -> MatcherAuditSample:
        ids = [c.candidate_id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("audit candidate ids must be unique")
        return self


class AuditAgreementReport(StrictModel):
    report_version: str = "0.1"
    sample_id_hash: str
    judgments: list[AuditJudgment]
    raw_agreement: float | None
    chance_corrected_agreement: float | None
    decision_counts: dict[str, int]
    disagreement_counts: dict[str, int]
    estimated_false_match_rate: float | None
    estimated_missed_match_rate: float | None
    uncertainty_note: str
    matcher_config_gate_passed: bool | None = None
    policy_invalidated: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


DEFAULT_PROTOCOL = MatcherAuditProtocol(
    population=(
        "All matcher decisions from a frozen evaluation result over the active "
        "benchmark case set (synthetic pilot until natural cases exist)."
    ),
    strata=list(AuditStratum),
    target_sample_size=100,
    random_seed=20260728,
    blinding=(
        "Auditors see concern text and anchors only. System identity, leaderboard "
        "rank, and aggregate metrics are withheld in blinded_payload."
    ),
    adjudication=(
        "Two primary auditors; disagreements route to a tie-break auditor. "
        "Partial/overbroad matches must not be collapsed into correct matches."
    ),
    analysis=(
        "Report raw agreement, chance-corrected agreement, disagreement categories, "
        "and estimated false-match / missed-match rates with uncertainty intervals "
        "when sample size permits. Human audits may invalidate a matcher configuration."
    ),
)


def _candidate_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:20]
    return f"ocaud_{digest}"


def stratify_match_decisions(
    *,
    matches: list[tuple[str, str, str, ConcernMatch]],
    unmatched_submitted: list[tuple[str, str, str]],
    unmatched_reference: list[tuple[str, str, str]],
    ambiguous_anchors: list[tuple[str, str, str]],
    type_disagreements: list[tuple[str, str, ConcernMatch]],
    severity_disagreements: list[tuple[str, str, ConcernMatch]],
    domain_by_case: dict[tuple[str, str], str],
    config: MatcherConfig,
    seed: int,
    target_size: int = 100,
) -> MatcherAuditSample:
    """Build a stratified, blinded audit sample (versioned seed)."""
    rng = random.Random(seed)
    pool: list[AuditCandidate] = []

    def blind(case_id: str, case_version: str, **fields: Any) -> dict[str, Any]:
        payload = {
            "case_id": case_id,
            "case_version": case_version,
            "domain_profile": domain_by_case.get((case_id, case_version)),
            **fields,
        }
        # Explicitly omit system identity / leaderboard fields.
        payload.pop("system_id", None)
        payload.pop("leaderboard_rank", None)
        return payload

    near = []
    far = []
    for case_id, case_version, _domain, match in matches:
        distance = abs(match.score - config.threshold)
        stratum = (
            AuditStratum.NEAR_THRESHOLD_ACCEPT
            if distance <= 0.1
            else AuditStratum.FAR_THRESHOLD_ACCEPT
        )
        cand = AuditCandidate(
            candidate_id=_candidate_id(
                case_id, match.submitted_local_id, match.reference_concern_id
            ),
            stratum=stratum,
            case_id=case_id,
            case_version=case_version,
            submitted_local_id=match.submitted_local_id,
            reference_concern_id=match.reference_concern_id,
            match_score=match.score,
            domain_profile=domain_by_case.get((case_id, case_version)),
            blinded_payload=blind(
                case_id,
                case_version,
                submitted_local_id=match.submitted_local_id,
                reference_concern_id=match.reference_concern_id,
                score=match.score,
            ),
        )
        (near if stratum == AuditStratum.NEAR_THRESHOLD_ACCEPT else far).append(cand)

    def add_simple(
        rows: list[tuple[str, str, str]],
        stratum: AuditStratum,
        field_name: str,
    ) -> None:
        for case_id, case_version, value in rows:
            pool.append(
                AuditCandidate(
                    candidate_id=_candidate_id(stratum.value, case_id, value),
                    stratum=stratum,
                    case_id=case_id,
                    case_version=case_version,
                    submitted_local_id=value if "submitted" in stratum.value else None,
                    reference_concern_id=value if "reference" in stratum.value else None,
                    domain_profile=domain_by_case.get((case_id, case_version)),
                    blinded_payload=blind(case_id, case_version, **{field_name: value}),
                )
            )

    add_simple(unmatched_submitted, AuditStratum.UNMATCHED_SUBMITTED, "submitted_local_id")
    add_simple(unmatched_reference, AuditStratum.UNMATCHED_REFERENCE, "reference_concern_id")
    add_simple(ambiguous_anchors, AuditStratum.AMBIGUOUS_ANCHOR, "anchor_note")

    for case_id, case_version, match in type_disagreements:
        pool.append(
            AuditCandidate(
                candidate_id=_candidate_id("type", case_id, match.submitted_local_id),
                stratum=AuditStratum.TYPE_DISAGREEMENT,
                case_id=case_id,
                case_version=case_version,
                submitted_local_id=match.submitted_local_id,
                reference_concern_id=match.reference_concern_id,
                match_score=match.score,
                domain_profile=domain_by_case.get((case_id, case_version)),
                blinded_payload=blind(
                    case_id,
                    case_version,
                    submitted_local_id=match.submitted_local_id,
                    reference_concern_id=match.reference_concern_id,
                    type_score=match.type_score,
                ),
            )
        )
    for case_id, case_version, match in severity_disagreements:
        pool.append(
            AuditCandidate(
                candidate_id=_candidate_id("sev", case_id, match.submitted_local_id),
                stratum=AuditStratum.SEVERITY_DISAGREEMENT,
                case_id=case_id,
                case_version=case_version,
                submitted_local_id=match.submitted_local_id,
                reference_concern_id=match.reference_concern_id,
                match_score=match.score,
                domain_profile=domain_by_case.get((case_id, case_version)),
                blinded_payload=blind(
                    case_id,
                    case_version,
                    submitted_local_id=match.submitted_local_id,
                    reference_concern_id=match.reference_concern_id,
                ),
            )
        )

    # Domain stratum: one representative per domain when available.
    seen_domains: set[str] = set()
    for (case_id, case_version), domain in domain_by_case.items():
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        pool.append(
            AuditCandidate(
                candidate_id=_candidate_id("domain", case_id, domain),
                stratum=AuditStratum.DOMAIN,
                case_id=case_id,
                case_version=case_version,
                domain_profile=domain,
                blinded_payload=blind(case_id, case_version, domain_profile=domain),
            )
        )

    stratified_groups = {
        AuditStratum.NEAR_THRESHOLD_ACCEPT: near,
        AuditStratum.FAR_THRESHOLD_ACCEPT: far,
    }
    selected: list[AuditCandidate] = []
    # Take up to equal shares from each non-empty stratum group + pool.
    all_groups = [g for g in stratified_groups.values() if g] + (
        [pool] if pool else []
    )
    if not all_groups:
        all_groups = [[]]
    per = max(1, target_size // max(1, len(all_groups)))
    for group in all_groups:
        rng.shuffle(group)
        selected.extend(group[:per])
    rng.shuffle(selected)
    selected = selected[:target_size]
    # Deduplicate by candidate_id preserving order.
    dedup: list[AuditCandidate] = []
    seen: set[str] = set()
    for item in selected:
        if item.candidate_id in seen:
            continue
        seen.add(item.candidate_id)
        dedup.append(item)

    return MatcherAuditSample(
        protocol_id=DEFAULT_PROTOCOL.protocol_id,
        random_seed=seed,
        matcher_config=config,
        candidates=dedup,
    )


def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> float | None:
    if not labels_a or len(labels_a) != len(labels_b):
        return None
    n = len(labels_a)
    categories = sorted(set(labels_a) | set(labels_b))
    agree = sum(1 for a, b in zip(labels_a, labels_b, strict=True) if a == b) / n
    pe = 0.0
    for cat in categories:
        pa = sum(1 for x in labels_a if x == cat) / n
        pb = sum(1 for x in labels_b if x == cat) / n
        pe += pa * pb
    if abs(1.0 - pe) < 1e-12:
        return 1.0 if agree == 1.0 else 0.0
    return (agree - pe) / (1.0 - pe)


def analyze_audit_judgments(
    sample: MatcherAuditSample,
    judgments: list[AuditJudgment],
    *,
    invalidate_on_incorrect_rate: float = 0.25,
) -> AuditAgreementReport:
    by_candidate: dict[str, list[AuditJudgment]] = {}
    for item in judgments:
        by_candidate.setdefault(item.candidate_id, []).append(item)

    paired_a: list[str] = []
    paired_b: list[str] = []
    for items in by_candidate.values():
        if len(items) >= 2:
            paired_a.append(items[0].decision.value)
            paired_b.append(items[1].decision.value)

    raw = None
    if paired_a:
        raw = sum(1 for a, b in zip(paired_a, paired_b, strict=True) if a == b) / len(paired_a)
    kappa = cohen_kappa(paired_a, paired_b)

    decision_counts: dict[str, int] = {}
    disagreement_counts: dict[str, int] = {}
    for item in judgments:
        decision_counts[item.decision.value] = decision_counts.get(item.decision.value, 0) + 1
        disagreement_counts[item.disagreement_category.value] = (
            disagreement_counts.get(item.disagreement_category.value, 0) + 1
        )

    incorrect = decision_counts.get(AuditDecision.INCORRECT_MATCH.value, 0)
    correct = decision_counts.get(AuditDecision.CORRECT_MATCH.value, 0)
    total_matchish = incorrect + correct + decision_counts.get(
        AuditDecision.PARTIAL_OVERBROAD.value, 0
    )
    false_rate = (incorrect / total_matchish) if total_matchish else None
    unresolved = decision_counts.get(AuditDecision.UNRESOLVED.value, 0)
    missed_rate = (unresolved / len(judgments)) if judgments else None

    invalidated = false_rate is not None and false_rate >= invalidate_on_incorrect_rate
    sample_hash = hashlib.sha256(
        json.dumps(
            [c.candidate_id for c in sample.candidates],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    return AuditAgreementReport(
        sample_id_hash=sample_hash,
        judgments=judgments,
        raw_agreement=raw,
        chance_corrected_agreement=kappa,
        decision_counts=decision_counts,
        disagreement_counts=disagreement_counts,
        estimated_false_match_rate=false_rate,
        estimated_missed_match_rate=missed_rate,
        uncertainty_note=(
            "Rates are descriptive for the pilot sample; wide uncertainty is expected "
            "until natural adjudicated volume reaches protocol targets."
        ),
        matcher_config_gate_passed=not invalidated,
        policy_invalidated=invalidated,
    )


ConfigurationGate = Literal["passed", "failed", "pending_audit"]


def configuration_gate(
    report: AuditAgreementReport | None,
    *,
    require_audit: bool = True,
) -> ConfigurationGate:
    if report is None:
        return "pending_audit" if require_audit else "passed"
    if report.policy_invalidated or report.matcher_config_gate_passed is False:
        return "failed"
    return "passed"
