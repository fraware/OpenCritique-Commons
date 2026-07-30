from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime
from pathlib import Path

from opencritique_schema.canonical import canonical_json_bytes

from .claim_auth_verify import verify_claim_authorization
from .models import (
    ClaimAuthorization,
    ClaimScope,
    EvaluationResult,
    PublicScorecard,
    ReferenceCompleteness,
)
from .trust import TrustPolicyMode, TrustStore

_PUBLIC_SCOPES = frozenset(
    {
        ClaimScope.PUBLIC_DOMAIN_BOUNDED,
        ClaimScope.PUBLIC_COMPARATIVE,
    }
)

_INCOMPLETE_REFERENCE = frozenset(
    {
        ReferenceCompleteness.PARTIAL_NATURAL,
        ReferenceCompleteness.UNKNOWN,
    }
)


def _coerce_unauthorized(result: EvaluationResult) -> EvaluationResult:
    auth = result.claim_authorization
    return result.model_copy(
        update={
            "claim_authorization": ClaimAuthorization(
                claim_scope=ClaimScope.NONE,
                expert_natural_evidence=auth.expert_natural_evidence,
                rights_cleared_cases=auth.rights_cleared_cases,
                protected_holdout=auth.protected_holdout,
                independent_evaluation=auth.independent_evaluation,
                matcher_audit_complete=auth.matcher_audit_complete,
                frozen_scoring_policy=auth.frozen_scoring_policy,
                signed_authorization_manifest_digest=(
                    auth.signed_authorization_manifest_digest
                ),
                signed_authorization_manifest_path=(
                    auth.signed_authorization_manifest_path
                ),
                domain_scope=auth.domain_scope,
                use_scope=auth.use_scope,
                authorization_verified=False,
                verification_report_digest=auth.verification_report_digest,
            ),
            "performance_claim_authorized": False,
        }
    )


def build_scorecard(
    result: EvaluationResult,
    *,
    predecessor_scorecard_id: str | None = None,
    predecessor_scorecard_hash: str | None = None,
    trust_store: TrustStore | None = None,
    trust_store_path: Path | None = None,
    policy_mode: TrustPolicyMode | None = None,
    at: datetime | None = None,
) -> PublicScorecard:
    """Build a public scorecard.

    Scientific performance headlines require a successfully verified claim-
    authorization envelope. Unsigned, missing, or failed verification yields a
    non-performance record. Integrity of a later scorecard signature is distinct
    from claim authorization and is enforced separately by ``signing.verify_*``.
    """
    scope = result.claim_authorization.claim_scope
    authorized_public = False

    if scope in _PUBLIC_SCOPES:
        report = verify_claim_authorization(
            result.claim_authorization_envelope,
            benchmark=result.benchmark,
            matcher_version=result.matcher_version,
            matcher_config=result.matcher_config,
            scoring_policy_version=result.scoring_policy_version,
            trust_store=trust_store,
            trust_store_path=trust_store_path,
            policy_mode=policy_mode or TrustPolicyMode.PRODUCTION,
            at=at,
            expected_digest=result.benchmark.signed_authorization_manifest_digest,
        )
        if report.ok:
            authorized_public = True
        else:
            result = _coerce_unauthorized(result)
            scope = ClaimScope.NONE

    if authorized_public and scope in _PUBLIC_SCOPES:
        headline = (
            f"{result.system.display_name} — independently evaluated scientific scorecard"
        )
        disclosure = result.claim_boundary
    elif scope == ClaimScope.PRIVATE_METHOD_REPORT:
        headline = f"{result.system.display_name} — private method report"
        disclosure = (
            "This scorecard is a private method report only and does not authorize "
            "public scientific performance claims. "
            + result.claim_boundary
        )
    else:
        headline = f"{result.system.display_name} — non-performance evaluation record"
        disclosure = (
            "This scorecard does not establish reviewer quality or scientific reliability. "
            + result.claim_boundary
        )
    provisional = PublicScorecard(
        result=result,
        headline=headline,
        disclosure=disclosure,
        predecessor_scorecard_id=predecessor_scorecard_id,
        predecessor_scorecard_hash=predecessor_scorecard_hash,
        reference_set_hash=result.benchmark.case_set_hash,
        scoring_policy_version=result.scoring_policy_version,
        immutable=True,
    )
    digest = hashlib.sha256(canonical_json_bytes(provisional)).hexdigest()
    scorecard_id = f"ocscore_{digest[:24]}"
    return provisional.model_copy(update={"scorecard_id": scorecard_id})


def write_json(scorecard: PublicScorecard, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(scorecard.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _metric(name: str, metric) -> str:
    if metric.value is None:
        value = "Withheld"
        note = metric.withheld_reason or "Unavailable"
    else:
        value = f"{metric.value:.4f}" if isinstance(metric.value, float) else str(metric.value)
        note = metric.withheld_reason or ""
    return (
        f"<tr><th>{html.escape(name)}</th><td>{html.escape(value)}</td>"
        f"<td>{html.escape(note)}</td></tr>"
    )


def write_html(scorecard: PublicScorecard, path: Path) -> None:
    result = scorecard.result
    metrics = result.metrics
    completeness = result.benchmark.reference_completeness
    incomplete = completeness in _INCOMPLETE_REFERENCE
    recall_label = "Reference recall" if incomplete else "Recall"
    sw_recall_label = (
        "Severity-weighted reference recall" if incomplete else "Severity-weighted recall"
    )
    rows = "".join(
        [
            _metric("Anchor resolution rate", metrics.anchor_resolution_rate),
            _metric("Precision", metrics.precision),
            _metric(recall_label, metrics.recall),
            _metric("Severity-weighted precision", metrics.severity_weighted_precision),
            _metric(sw_recall_label, metrics.severity_weighted_recall),
            _metric("False critical / manuscript", metrics.false_critical_per_manuscript),
            _metric(
                "Reference-match Brier score", metrics.reference_match_brier_score
            ),
        ]
    )
    scope = result.claim_authorization.claim_scope.value
    if result.performance_claim_authorized:
        authorization = f"AUTHORIZED ({scope})"
    else:
        authorization = f"NOT AUTHORIZED ({scope})"
    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in result.benchmark.limitations
    )
    if incomplete:
        unmatched_line = (
            "<li>Adjudication candidates (unmatched submitted): "
            f"{metrics.novel_candidates_pending_adjudication}</li>"
        )
    else:
        unmatched_line = (
            f"<li>Unmatched submitted concerns: {metrics.unmatched_submitted}</li>"
            "<li>Novel candidates pending adjudication: "
            f"{metrics.novel_candidates_pending_adjudication}</li>"
        )
    counts = (
        f"<li>Submitted concerns: {metrics.submitted_concerns}</li>"
        f"<li>Eligible reference concerns: {metrics.eligible_reference_concerns}</li>"
        f"<li>Matched concerns: {metrics.matched_concerns}</li>"
        f"{unmatched_line}"
        f"<li>Missed reference concerns: {metrics.missed_reference}</li>"
    )
    style = (
        "body{font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;"
        "padding:0 20px;line-height:1.5}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #bbb;padding:8px;text-align:left}"
        ".boundary{border:2px solid #333;padding:16px;background:#f5f5f5}"
        "code{word-break:break-all}"
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>{html.escape(scorecard.headline)}</title>
<style>{style}</style>
</head>
<body>
<h1>{html.escape(scorecard.headline)}</h1>
<div class="boundary">
<strong>Performance-claim status: {authorization}</strong>
<p>{html.escape(scorecard.disclosure)}</p>
</div>
<h2>Frozen configuration</h2>
<p>System: {html.escape(result.system.system_id)} @ {html.escape(result.system.version)}<br>
Benchmark: {html.escape(result.benchmark.benchmark_id)} @
{html.escape(result.benchmark.version)}<br>
Matcher: {html.escape(result.matcher_version)} / {html.escape(result.matcher_config.config_id)}<br>
Threshold: {result.matcher_config.threshold:.3f}; weights (anchor/type/lexical):<br>
{result.matcher_config.anchor_weight:.2f}/{result.matcher_config.type_weight:.2f}/
{result.matcher_config.lexical_weight:.2f}<br>
Result: <code>{html.escape(result.result_id)}</code></p>
<h2>Coverage</h2>
<p>{metrics.cases_completed}/{metrics.cases_total} cases completed;
{metrics.cases_abstained} abstained; {metrics.cases_failed} failed.</p>
<h2>Metrics</h2>
<table><thead><tr><th>Metric</th><th>Value</th><th>Qualification</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Counts</h2><ul>{counts}</ul>
<h2>Limitations</h2><ul>{limitations}</ul>
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
