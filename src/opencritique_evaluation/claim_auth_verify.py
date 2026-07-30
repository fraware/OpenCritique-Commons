"""Cryptographic verification of claim-authorization envelopes (PR 41).

Mirrors ``verify_envelope_detailed`` for scorecards. A valid signature establishes
integrity relative to a trusted claim-authority key; it does **not** establish
scientific correctness of the underlying evaluation metrics.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from opencritique_schema.canonical import canonical_json_bytes, content_hash

from .models import (
    BenchmarkManifest,
    ClaimAuthorization,
    ClaimAuthorizationDecision,
    ClaimScope,
    MatcherConfig,
    SignedClaimAuthorizationEnvelope,
    StrictModel,
)
from .trust import (
    CLAIM_AUTHORITY_SIGNING_ROLES,
    KeyRole,
    TrustPolicyMode,
    TrustStore,
    VerificationFailureReason,
    evaluate_key_policy,
    key_id_from_raw_public,
    load_trust_store,
)

DEFAULT_MATCHER_VERSION = "opencritique-matcher-v0.2"
DEFAULT_SCORING_POLICY_VERSION = "scoring-policy-v0.1"

_PUBLIC_SCOPES = frozenset(
    {
        ClaimScope.PUBLIC_DOMAIN_BOUNDED,
        ClaimScope.PUBLIC_COMPARATIVE,
    }
)

# Development / test verification may accept TEST keys in addition to claim roles.
_CLAIM_DEV_ROLES: frozenset[KeyRole] = CLAIM_AUTHORITY_SIGNING_ROLES | {
    KeyRole.TEST,
}


class ClaimAuthVerificationReport(StrictModel):
    """Structured result of claim-authorization envelope verification."""

    ok: bool
    reason: VerificationFailureReason | None = None
    detail: str = ""
    key_id: str | None = None
    key_role: KeyRole | None = None
    policy_mode: TrustPolicyMode
    claim_scope: ClaimScope | None = None
    decision_digest: str | None = None
    report_digest: str | None = None


def canonical_decision_bytes(decision: ClaimAuthorizationDecision) -> bytes:
    return json.dumps(
        decision.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def matcher_config_hash(config: MatcherConfig) -> str:
    return content_hash(config)


def scoring_policy_hash(version: str) -> str:
    return hashlib.sha256(
        canonical_json_bytes({"scoring_policy_version": version})
    ).hexdigest()


def benchmark_manifest_content_hash(manifest: BenchmarkManifest) -> str:
    """Hash binding fields excluding envelope locator/digest (avoids circularity)."""
    data = manifest.model_dump(mode="json")
    data.pop("signed_authorization_manifest_digest", None)
    data.pop("signed_authorization_manifest_path", None)
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def envelope_content_digest(envelope: SignedClaimAuthorizationEnvelope) -> str:
    """Digest of the full envelope artifact (for manifest digest binding)."""
    return content_hash(envelope)


def load_claim_authorization_envelope(
    path: Path,
) -> SignedClaimAuthorizationEnvelope:
    return SignedClaimAuthorizationEnvelope.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def sign_claim_authorization_decision(
    decision: ClaimAuthorizationDecision,
    private_key_path: Path,
    *,
    key_id_override: str | None = None,
    signed_at: datetime | None = None,
) -> SignedClaimAuthorizationEnvelope:
    private_key = serialization.load_pem_private_key(
        private_key_path.read_bytes(), password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    public_key = private_key.public_key()
    payload = canonical_decision_bytes(decision)
    signature = private_key.sign(payload)
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = key_id_override or key_id_from_raw_public(raw_public)
    return SignedClaimAuthorizationEnvelope(
        decision=decision,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        signature=base64.b64encode(signature).decode("ascii"),
        key_id=key_id,
        signed_at=signed_at or datetime.now(UTC),
    )


def build_claim_authorization_decision(
    *,
    claim_scope: ClaimScope,
    benchmark: BenchmarkManifest,
    matcher_version: str,
    matcher_config: MatcherConfig,
    scoring_policy_version: str = DEFAULT_SCORING_POLICY_VERSION,
    authority_id: str,
    issued_at: datetime,
    not_after: datetime,
    authorized_metrics: list[str] | None = None,
    predecessor_id: str | None = None,
    domain_scope: str | None = None,
    use_scope: str | None = None,
) -> ClaimAuthorizationDecision:
    domain = (domain_scope or benchmark.domain_scope or "").strip()
    use = (use_scope or benchmark.use_scope or "").strip()
    if not domain or not use:
        raise ValueError("domain_scope and use_scope are required for a decision")
    return ClaimAuthorizationDecision(
        claim_scope=claim_scope,
        authorized_metrics=list(authorized_metrics or []),
        benchmark_id=benchmark.benchmark_id,
        benchmark_version=benchmark.version,
        case_set_hash=benchmark.case_set_hash,
        benchmark_manifest_hash=benchmark_manifest_content_hash(benchmark),
        scoring_policy_hash=scoring_policy_hash(scoring_policy_version),
        matcher_version=matcher_version,
        matcher_config_hash=matcher_config_hash(matcher_config),
        domain_scope=domain,
        use_scope=use,
        issued_at=issued_at,
        not_after=not_after,
        authority_id=authority_id,
        predecessor_id=predecessor_id,
    )


def _fail(
    *,
    reason: VerificationFailureReason,
    detail: str,
    policy_mode: TrustPolicyMode,
    key_id: str | None = None,
    key_role: KeyRole | None = None,
    claim_scope: ClaimScope | None = None,
    decision_digest: str | None = None,
) -> ClaimAuthVerificationReport:
    report = ClaimAuthVerificationReport(
        ok=False,
        reason=reason,
        detail=detail,
        key_id=key_id,
        key_role=key_role,
        policy_mode=policy_mode,
        claim_scope=claim_scope,
        decision_digest=decision_digest,
    )
    return report.model_copy(
        update={"report_digest": content_hash(report.model_dump(mode="json"))}
    )


def _ok(
    *,
    policy_mode: TrustPolicyMode,
    key_id: str,
    key_role: KeyRole | None,
    claim_scope: ClaimScope,
    decision_digest: str,
) -> ClaimAuthVerificationReport:
    report = ClaimAuthVerificationReport(
        ok=True,
        key_id=key_id,
        key_role=key_role,
        policy_mode=policy_mode,
        claim_scope=claim_scope,
        decision_digest=decision_digest,
    )
    return report.model_copy(
        update={"report_digest": content_hash(report.model_dump(mode="json"))}
    )


def verify_claim_authorization(
    envelope: SignedClaimAuthorizationEnvelope | None,
    *,
    benchmark: BenchmarkManifest,
    matcher_version: str,
    matcher_config: MatcherConfig,
    scoring_policy_version: str = DEFAULT_SCORING_POLICY_VERSION,
    trust_store: TrustStore | None = None,
    trust_store_path: Path | None = None,
    policy_mode: TrustPolicyMode | None = None,
    at: datetime | None = None,
    expected_digest: str | None = None,
) -> ClaimAuthVerificationReport:
    """Verify a claim-authorization envelope and bind it to a live benchmark.

    Fail closed: missing envelope, unknown keys, role mismatches, binding drift,
    expiry, and revocation all return ``ok=False``.
    """
    mode = policy_mode or TrustPolicyMode.PRODUCTION
    now = at or datetime.now(UTC)

    if envelope is None:
        return _fail(
            reason=VerificationFailureReason.ENVELOPE_MISSING,
            detail="no signed claim-authorization envelope provided",
            policy_mode=mode,
        )

    payload = canonical_decision_bytes(envelope.decision)
    decision_digest = hashlib.sha256(payload).hexdigest()
    if decision_digest != envelope.payload_sha256:
        return _fail(
            reason=VerificationFailureReason.PAYLOAD_TAMPER,
            detail="canonical decision digest does not match envelope.payload_sha256",
            policy_mode=mode,
            key_id=envelope.key_id,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )

    if expected_digest is not None:
        artifact_digest = envelope_content_digest(envelope)
        if expected_digest not in {artifact_digest, envelope.payload_sha256}:
            return _fail(
                reason=VerificationFailureReason.DIGEST_MISMATCH,
                detail=(
                    "manifest signed_authorization_manifest_digest does not match "
                    "envelope content digest or payload_sha256"
                ),
                policy_mode=mode,
                key_id=envelope.key_id,
                claim_scope=envelope.decision.claim_scope,
                decision_digest=decision_digest,
            )

    loaded_store = trust_store
    if loaded_store is None and trust_store_path is not None:
        loaded_store = load_trust_store(trust_store_path)

    if loaded_store is None:
        if mode in {
            TrustPolicyMode.PRODUCTION,
            TrustPolicyMode.DEVELOPMENT,
            TrustPolicyMode.HISTORICAL,
        }:
            return _fail(
                reason=VerificationFailureReason.UNKNOWN_KEY,
                detail=(
                    f"{mode.value} claim-authorization verification requires an "
                    "explicit trust store"
                ),
                policy_mode=mode,
                key_id=envelope.key_id,
                claim_scope=envelope.decision.claim_scope,
                decision_digest=decision_digest,
            )
        return _fail(
            reason=VerificationFailureReason.UNKNOWN_KEY,
            detail="claim-authorization verification requires a trust store",
            policy_mode=mode,
            key_id=envelope.key_id,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )

    key_id = envelope.key_id
    record = loaded_store.get(key_id)
    permitted = (
        _CLAIM_DEV_ROLES
        if mode in {TrustPolicyMode.DEVELOPMENT, TrustPolicyMode.TEST}
        else CLAIM_AUTHORITY_SIGNING_ROLES
    )
    policy = evaluate_key_policy(
        record,
        key_id=key_id,
        policy_mode=mode,
        at=envelope.signed_at if mode == TrustPolicyMode.HISTORICAL else now,
        store=loaded_store,
        permitted_roles=permitted,
    )
    if not policy.ok:
        assert policy.reason is not None
        return _fail(
            reason=policy.reason,
            detail=policy.detail,
            policy_mode=mode,
            key_id=key_id,
            key_role=policy.key_role,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )
    assert record is not None

    try:
        raw_public = base64.b64decode(record.public_key_base64, validate=True)
    except ValueError:
        return _fail(
            reason=VerificationFailureReason.PUBLIC_KEY_MISMATCH,
            detail="trust store public_key_base64 is not valid base64",
            policy_mode=mode,
            key_id=key_id,
            key_role=record.role,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )

    if now < envelope.decision.issued_at:
        return _fail(
            reason=VerificationFailureReason.DECISION_NOT_YET_VALID,
            detail="decision issued_at is in the future",
            policy_mode=mode,
            key_id=key_id,
            key_role=record.role,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )
    if now > envelope.decision.not_after:
        return _fail(
            reason=VerificationFailureReason.DECISION_EXPIRED,
            detail="decision not_after has passed",
            policy_mode=mode,
            key_id=key_id,
            key_role=record.role,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )

    public_key = Ed25519PublicKey.from_public_bytes(raw_public)
    try:
        public_key.verify(base64.b64decode(envelope.signature, validate=True), payload)
    except (InvalidSignature, ValueError):
        return _fail(
            reason=VerificationFailureReason.SIGNATURE_TAMPER,
            detail="Ed25519 signature verification failed",
            policy_mode=mode,
            key_id=key_id,
            key_role=record.role,
            claim_scope=envelope.decision.claim_scope,
            decision_digest=decision_digest,
        )

    decision = envelope.decision
    binding_errors: list[str] = []
    if decision.benchmark_id != benchmark.benchmark_id:
        binding_errors.append("benchmark_id")
    if decision.benchmark_version != benchmark.version:
        binding_errors.append("benchmark_version")
    if decision.case_set_hash != benchmark.case_set_hash:
        binding_errors.append("case_set_hash")
    expected_manifest_hash = benchmark_manifest_content_hash(benchmark)
    if decision.benchmark_manifest_hash != expected_manifest_hash:
        binding_errors.append("benchmark_manifest_hash")
    expected_policy_hash = scoring_policy_hash(scoring_policy_version)
    if decision.scoring_policy_hash != expected_policy_hash:
        binding_errors.append("scoring_policy_hash")
    if decision.matcher_version != matcher_version:
        binding_errors.append("matcher_version")
    expected_matcher_hash = matcher_config_hash(matcher_config)
    if decision.matcher_config_hash != expected_matcher_hash:
        binding_errors.append("matcher_config_hash")
    if decision.domain_scope != (benchmark.domain_scope or ""):
        binding_errors.append("domain_scope")
    if decision.use_scope != (benchmark.use_scope or ""):
        binding_errors.append("use_scope")
    if binding_errors:
        return _fail(
            reason=VerificationFailureReason.BINDING_MISMATCH,
            detail="decision binding mismatch: " + ", ".join(binding_errors),
            policy_mode=mode,
            key_id=key_id,
            key_role=record.role,
            claim_scope=decision.claim_scope,
            decision_digest=decision_digest,
        )

    if decision.claim_scope not in _PUBLIC_SCOPES:
        return _fail(
            reason=VerificationFailureReason.SCOPE_NOT_PUBLIC,
            detail=(
                f"verified decision claim_scope={decision.claim_scope.value} is not "
                "a public scientific scope"
            ),
            policy_mode=mode,
            key_id=key_id,
            key_role=record.role,
            claim_scope=decision.claim_scope,
            decision_digest=decision_digest,
        )

    return _ok(
        policy_mode=mode,
        key_id=key_id,
        key_role=record.role,
        claim_scope=decision.claim_scope,
        decision_digest=decision_digest,
    )


def derived_claim_authorization(
    benchmark: BenchmarkManifest,
    *,
    envelope: SignedClaimAuthorizationEnvelope,
    report: ClaimAuthVerificationReport,
    comparative_authorized: bool = False,
) -> ClaimAuthorization:
    """Build the transitional ClaimAuthorization view from a verification report."""
    from .models import BenchmarkEvidenceClass

    expert_natural = benchmark.evidence_class == BenchmarkEvidenceClass.EXPERT_NATURAL
    base_kwargs = {
        "expert_natural_evidence": expert_natural,
        "rights_cleared_cases": benchmark.rights_cleared_cases,
        "protected_holdout": benchmark.protected_holdout,
        "independent_evaluation": benchmark.independent_evaluation,
        "matcher_audit_complete": benchmark.matcher_audit_complete,
        "frozen_scoring_policy": benchmark.frozen_scoring_policy,
        "signed_authorization_manifest_digest": (
            benchmark.signed_authorization_manifest_digest
        ),
        "signed_authorization_manifest_path": (
            benchmark.signed_authorization_manifest_path
        ),
        "domain_scope": benchmark.domain_scope,
        "use_scope": benchmark.use_scope,
        "verification_report_digest": report.report_digest,
    }
    if not report.ok:
        return ClaimAuthorization(
            claim_scope=ClaimScope.NONE,
            authorization_verified=False,
            **base_kwargs,
        )

    scope = envelope.decision.claim_scope
    if scope == ClaimScope.PUBLIC_COMPARATIVE and not (
        comparative_authorized or benchmark.comparative_authorization
    ):
        return ClaimAuthorization(
            claim_scope=ClaimScope.NONE,
            authorization_verified=False,
            **base_kwargs,
        )
    return ClaimAuthorization(
        claim_scope=scope,
        authorization_verified=True,
        **base_kwargs,
    )
