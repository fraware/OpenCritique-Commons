from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .models import PublicScorecard, ScorecardSignature, SignedScorecardEnvelope
from .trust import (
    KeyRole,
    TrustPolicyMode,
    TrustStore,
    VerificationFailureReason,
    VerificationResult,
    evaluate_key_policy,
    key_id_from_raw_public,
)

_MARKED_KEY_ID_PREFIXES = (
    "ed25519:TEST-",
    "ed25519:DEV-ROOT-",
    "ed25519:DEV-RELEASE-",
    "ed25519:PROD-ROOT-",
    "ed25519:PROD-RELEASE-",
)


def _key_id_matches_embedded_public(key_id: str, expected_key_id: str) -> bool:
    if key_id == expected_key_id:
        return True
    raw_suffix = expected_key_id.removeprefix("ed25519:")
    for prefix in _MARKED_KEY_ID_PREFIXES:
        if key_id.startswith(prefix) and key_id.removeprefix(prefix) == raw_suffix:
            return True
    return False


def canonical_scorecard_bytes(scorecard: PublicScorecard) -> bytes:
    return json.dumps(
        scorecard.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def generate_keypair(private_path: Path, public_path: Path) -> str:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(private_bytes)
    try:
        private_path.chmod(0o600)
    except OSError:
        # Windows and some CI filesystems may not support POSIX mode bits.
        pass
    public_path.write_bytes(public_bytes)
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return key_id_from_raw_public(raw_public)


def sign_scorecard(
    scorecard: PublicScorecard,
    private_key_path: Path,
    *,
    key_role: KeyRole | None = None,
    key_id_override: str | None = None,
    not_before: datetime | None = None,
    not_after: datetime | None = None,
) -> SignedScorecardEnvelope:
    private_key = serialization.load_pem_private_key(
        private_key_path.read_bytes(), password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("private key is not Ed25519")
    public_key = private_key.public_key()
    payload = canonical_scorecard_bytes(scorecard)
    signature = private_key.sign(payload)
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = key_id_override or key_id_from_raw_public(raw_public)
    return SignedScorecardEnvelope(
        scorecard=scorecard,
        signature=ScorecardSignature(
            key_id=key_id,
            public_key_base64=base64.b64encode(raw_public).decode("ascii"),
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            signature_base64=base64.b64encode(signature).decode("ascii"),
            signed_at=datetime.now(UTC),
            key_role=key_role.value if key_role is not None else None,
            not_before=not_before,
            not_after=not_after,
        ),
    )


def verify_envelope(
    envelope: SignedScorecardEnvelope,
    trusted_public_key_path: Path | None = None,
    *,
    trust_store: TrustStore | None = None,
    trust_store_path: Path | None = None,
    allow_untrusted_test: bool = False,
    policy_mode: TrustPolicyMode | None = None,
) -> bool:
    """Boolean verification wrapper. Requires trust material or explicit test opt-in.

    Prefer ``verify_envelope_detailed`` with an explicit trust store for production.
    Calling without a trust store, trust-store path, or trusted PEM raises
    ``ValueError`` unless ``allow_untrusted_test=True`` is set deliberately.
    """
    from .trust import load_trust_store

    loaded_store = trust_store
    if loaded_store is None and trust_store_path is not None:
        loaded_store = load_trust_store(trust_store_path)

    has_trust_material = loaded_store is not None or trusted_public_key_path is not None
    if not has_trust_material and not allow_untrusted_test:
        raise ValueError(
            "verify_envelope requires trust_store, trust_store_path, or "
            "trusted_public_key_path; pass allow_untrusted_test=True only for "
            "explicit ephemeral tests"
        )

    if policy_mode is None:
        if allow_untrusted_test and not has_trust_material:
            mode = TrustPolicyMode.TEST
        else:
            mode = TrustPolicyMode.PRODUCTION
    else:
        mode = policy_mode

    result = verify_envelope_detailed(
        envelope,
        trust_store=loaded_store,
        trusted_public_key_path=trusted_public_key_path,
        policy_mode=mode,
    )
    return result.ok


def verify_envelope_detailed(
    envelope: SignedScorecardEnvelope,
    *,
    trust_store: TrustStore | None = None,
    trusted_public_key_path: Path | None = None,
    policy_mode: TrustPolicyMode = TrustPolicyMode.PRODUCTION,
    at: datetime | None = None,
) -> VerificationResult:
    """Verify scorecard integrity relative to a trust policy.

    A valid signature establishes artifact integrity relative to a trusted key; it does
    **not** establish scientific correctness. Production and development policies
    fail closed without trust material; only ``TEST`` may verify against the
    embedded public key alone.
    """
    now = at or datetime.now(UTC)
    payload = canonical_scorecard_bytes(envelope.scorecard)
    if hashlib.sha256(payload).hexdigest() != envelope.signature.payload_sha256:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.PAYLOAD_TAMPER,
            detail="canonical payload digest does not match signature.payload_sha256",
            key_id=envelope.signature.key_id,
            policy_mode=policy_mode,
        )
    try:
        raw_public = base64.b64decode(envelope.signature.public_key_base64, validate=True)
    except ValueError:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.PUBLIC_KEY_MISMATCH,
            detail="public_key_base64 is not valid base64",
            key_id=envelope.signature.key_id,
            policy_mode=policy_mode,
        )
    expected_key_id = key_id_from_raw_public(raw_public)
    # Allow unmistakable TEST-/DEV- prefixed ids that still hash-match the suffix.
    key_id = envelope.signature.key_id
    if not _key_id_matches_embedded_public(key_id, expected_key_id):
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.KEY_ID_MISMATCH,
            detail="key_id does not match embedded public key",
            key_id=key_id,
            policy_mode=policy_mode,
        )

    if trust_store is not None:
        record = trust_store.get(key_id)
        policy = evaluate_key_policy(
            record,
            key_id=key_id,
            policy_mode=policy_mode,
            at=envelope.signature.signed_at if policy_mode == TrustPolicyMode.HISTORICAL else now,
            store=trust_store,
        )
        if not policy.ok:
            return policy
        assert record is not None
        if record.public_key_base64 != envelope.signature.public_key_base64:
            return VerificationResult(
                ok=False,
                reason=VerificationFailureReason.PUBLIC_KEY_MISMATCH,
                detail="envelope public key does not match trust store record",
                key_id=key_id,
                key_role=record.role,
                policy_mode=policy_mode,
            )
    elif trusted_public_key_path is not None:
        trusted = serialization.load_pem_public_key(trusted_public_key_path.read_bytes())
        if not isinstance(trusted, Ed25519PublicKey):
            return VerificationResult(
                ok=False,
                reason=VerificationFailureReason.PUBLIC_KEY_MISMATCH,
                detail="trusted public key is not Ed25519",
                key_id=key_id,
                policy_mode=policy_mode,
            )
        trusted_raw = trusted.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if trusted_raw != raw_public:
            return VerificationResult(
                ok=False,
                reason=VerificationFailureReason.PUBLIC_KEY_MISMATCH,
                detail="envelope public key does not match trusted PEM",
                key_id=key_id,
                policy_mode=policy_mode,
            )
    elif policy_mode in {
        TrustPolicyMode.PRODUCTION,
        TrustPolicyMode.DEVELOPMENT,
        TrustPolicyMode.HISTORICAL,
    }:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.UNKNOWN_KEY,
            detail=(
                f"{policy_mode.value} verification requires an explicit trust "
                "store or trusted PEM"
            ),
            key_id=key_id,
            policy_mode=policy_mode,
        )

    # Envelope-local validity interval, when present.
    if envelope.signature.not_before and now < envelope.signature.not_before:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.NOT_YET_VALID,
            detail="envelope not_before is in the future",
            key_id=key_id,
            policy_mode=policy_mode,
        )
    if envelope.signature.not_after and now > envelope.signature.not_after:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.EXPIRED_KEY,
            detail="envelope not_after has passed",
            key_id=key_id,
            policy_mode=policy_mode,
        )

    public_key = Ed25519PublicKey.from_public_bytes(raw_public)
    try:
        public_key.verify(
            base64.b64decode(envelope.signature.signature_base64, validate=True), payload
        )
    except (InvalidSignature, ValueError):
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.SIGNATURE_TAMPER,
            detail="Ed25519 signature verification failed",
            key_id=key_id,
            policy_mode=policy_mode,
        )
    role = None
    if trust_store is not None:
        record = trust_store.get(key_id)
        role = record.role if record else None
    return VerificationResult(
        ok=True,
        key_id=key_id,
        key_role=role,
        policy_mode=policy_mode,
    )
