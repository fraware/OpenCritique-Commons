"""Signing-key trust store, roles, rotation, and revocation (issue #4)."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class KeyRole(str, Enum):
    OFFLINE_ROOT = "offline_root"
    ONLINE_RELEASE = "online_release"
    CLAIM_AUTHORITY = "claim_authority"
    EVIDENCE_AUTHORITY = "evidence_authority"
    TEST = "test"


# Default roles permitted to sign public scorecard envelopes.
SCORECARD_SIGNING_ROLES: frozenset[KeyRole] = frozenset(
    {KeyRole.OFFLINE_ROOT, KeyRole.ONLINE_RELEASE}
)

# Roles permitted to sign claim-authorization envelopes under production policy.
CLAIM_AUTHORITY_SIGNING_ROLES: frozenset[KeyRole] = frozenset(
    {KeyRole.CLAIM_AUTHORITY, KeyRole.OFFLINE_ROOT}
)


class KeyStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TrustPolicyMode(str, Enum):
    PRODUCTION = "production"
    HISTORICAL = "historical"
    TEST = "test"
    DEVELOPMENT = "development"


class VerificationFailureReason(str, Enum):
    PAYLOAD_TAMPER = "payload_tamper"
    SIGNATURE_TAMPER = "signature_tamper"
    KEY_ID_MISMATCH = "key_id_mismatch"
    UNKNOWN_KEY = "unknown_key"
    REVOKED_KEY = "revoked_key"
    EXPIRED_KEY = "expired_key"
    TEST_KEY_IN_PRODUCTION = "test_key_in_production"
    DEVELOPMENT_KEY_IN_PRODUCTION = "development_key_in_production"
    ROLE_NOT_PERMITTED = "role_not_permitted"
    PUBLIC_KEY_MISMATCH = "public_key_mismatch"
    NOT_YET_VALID = "not_yet_valid"
    SUPERSEDED_WITHOUT_HISTORICAL = "superseded_without_historical"
    ENVELOPE_MISSING = "envelope_missing"
    BINDING_MISMATCH = "binding_mismatch"
    DECISION_NOT_YET_VALID = "decision_not_yet_valid"
    DECISION_EXPIRED = "decision_expired"
    DIGEST_MISMATCH = "digest_mismatch"
    SCOPE_NOT_PUBLIC = "scope_not_public"


class TrustedKeyRecord(StrictModel):
    key_id: str
    role: KeyRole
    status: KeyStatus
    public_key_pem: str
    public_key_base64: str
    fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    not_before: datetime
    not_after: datetime | None = None
    superseded_by: str | None = None
    channels: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def interval_order(self) -> TrustedKeyRecord:
        if self.not_after is not None and self.not_after <= self.not_before:
            raise ValueError("not_after must be after not_before")
        if self.role == KeyRole.TEST and "TEST" not in self.key_id.upper():
            # Soft marker; production policy still rejects KeyRole.TEST.
            pass
        return self


class RevocationRecord(StrictModel):
    revocation_id: str
    key_id: str
    revoked_at: datetime
    reason: str
    signed_statement_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    incident_reference: str | None = None


class RotationStatement(StrictModel):
    statement_id: str
    statement_version: str = "0.1"
    issued_at: datetime
    retiring_key_id: str
    successor_key_id: str
    effective_at: datetime
    historical_verification_retained: bool = True
    notes: str = ""


class TrustStore(StrictModel):
    store_version: str = "0.1"
    store_id: str
    policy_mode_default: TrustPolicyMode = TrustPolicyMode.PRODUCTION
    keys: list[TrustedKeyRecord]
    revocations: list[RevocationRecord] = Field(default_factory=list)
    rotations: list[RotationStatement] = Field(default_factory=list)
    published_channels: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""

    @model_validator(mode="after")
    def unique_keys(self) -> TrustStore:
        ids = [item.key_id for item in self.keys]
        if len(ids) != len(set(ids)):
            raise ValueError("trust store key_id values must be unique")
        return self

    def get(self, key_id: str) -> TrustedKeyRecord | None:
        for item in self.keys:
            if item.key_id == key_id:
                return item
        return None

    def is_revoked(self, key_id: str) -> RevocationRecord | None:
        matches = [item for item in self.revocations if item.key_id == key_id]
        return matches[-1] if matches else None


class VerificationResult(StrictModel):
    ok: bool
    reason: VerificationFailureReason | None = None
    detail: str = ""
    key_id: str | None = None
    key_role: KeyRole | None = None
    policy_mode: TrustPolicyMode


def key_id_from_raw_public(raw_public: bytes) -> str:
    return f"ed25519:{hashlib.sha256(raw_public).hexdigest()[:16]}"


def fingerprint_pem(public_pem: bytes) -> tuple[str, str, str]:
    """Return (key_id, public_key_base64, fingerprint_sha256)."""
    public_key = serialization.load_pem_public_key(public_pem)
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("only Ed25519 public keys are supported")
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        key_id_from_raw_public(raw),
        base64.b64encode(raw).decode("ascii"),
        hashlib.sha256(raw).hexdigest(),
    )


def load_trust_store(path: Path) -> TrustStore:
    return TrustStore.model_validate_json(path.read_text(encoding="utf-8"))


def write_trust_store(store: TrustStore, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        store.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def build_trusted_key_record(
    *,
    public_key_path: Path,
    role: KeyRole,
    status: KeyStatus,
    not_before: datetime,
    not_after: datetime | None = None,
    channels: list[str] | None = None,
    notes: str = "",
    key_id_override: str | None = None,
    superseded_by: str | None = None,
) -> TrustedKeyRecord:
    pem = public_key_path.read_bytes()
    key_id, b64, fingerprint = fingerprint_pem(pem)
    if key_id_override:
        key_id = key_id_override
    if role == KeyRole.TEST and not key_id.startswith("ed25519:TEST-"):
        # Unmistakable test marker for production rejection.
        key_id = f"ed25519:TEST-{key_id.removeprefix('ed25519:')}"
    return TrustedKeyRecord(
        key_id=key_id,
        role=role,
        status=status,
        public_key_pem=pem.decode("ascii"),
        public_key_base64=b64,
        fingerprint_sha256=fingerprint,
        not_before=not_before,
        not_after=not_after,
        superseded_by=superseded_by,
        channels=channels or [],
        notes=notes,
    )


def evaluate_key_policy(
    record: TrustedKeyRecord | None,
    *,
    key_id: str,
    policy_mode: TrustPolicyMode,
    at: datetime,
    store: TrustStore,
    permitted_roles: frozenset[KeyRole] | None = None,
) -> VerificationResult:
    allowed = permitted_roles if permitted_roles is not None else SCORECARD_SIGNING_ROLES
    if record is None:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.UNKNOWN_KEY,
            detail=f"key_id {key_id} is not present in the trust store",
            key_id=key_id,
            policy_mode=policy_mode,
        )
    if policy_mode == TrustPolicyMode.PRODUCTION and record.role == KeyRole.TEST:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.TEST_KEY_IN_PRODUCTION,
            detail="test keys are rejected by production verification policy",
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    channels = {item.lower() for item in record.channels}
    is_dev_only = "development" in channels and "production" not in channels
    if policy_mode == TrustPolicyMode.PRODUCTION and is_dev_only:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.DEVELOPMENT_KEY_IN_PRODUCTION,
            detail="development-channel keys are rejected by production verification policy",
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    if policy_mode == TrustPolicyMode.DEVELOPMENT and "development" not in channels:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.ROLE_NOT_PERMITTED,
            detail="development policy requires a development-channel key",
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    revocation = store.is_revoked(key_id)
    if revocation is not None or record.status == KeyStatus.REVOKED:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.REVOKED_KEY,
            detail=(
                "key revoked"
                + (f" at {revocation.revoked_at.isoformat()}" if revocation else "")
                + (f": {revocation.reason}" if revocation else "")
            ),
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    if at < record.not_before:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.NOT_YET_VALID,
            detail=f"key not valid before {record.not_before.isoformat()}",
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    if record.not_after is not None and at > record.not_after:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.EXPIRED_KEY,
            detail=f"key expired at {record.not_after.isoformat()}",
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    if record.status == KeyStatus.EXPIRED:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.EXPIRED_KEY,
            detail="key status is expired",
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    if record.status == KeyStatus.SUPERSEDED:
        if policy_mode != TrustPolicyMode.HISTORICAL:
            return VerificationResult(
                ok=False,
                reason=VerificationFailureReason.SUPERSEDED_WITHOUT_HISTORICAL,
                detail="superseded keys require historical verification policy",
                key_id=key_id,
                key_role=record.role,
                policy_mode=policy_mode,
            )
    if policy_mode in {
        TrustPolicyMode.PRODUCTION,
        TrustPolicyMode.DEVELOPMENT,
    } and record.role not in allowed:
        return VerificationResult(
            ok=False,
            reason=VerificationFailureReason.ROLE_NOT_PERMITTED,
            detail=(
                f"role {record.role.value} cannot sign under "
                f"{policy_mode.value} policy for this artifact class"
            ),
            key_id=key_id,
            key_role=record.role,
            policy_mode=policy_mode,
        )
    return VerificationResult(
        ok=True,
        key_id=key_id,
        key_role=record.role,
        policy_mode=policy_mode,
    )


ThreatModelCoverage = Literal[
    "substitution",
    "rollback",
    "compromise",
    "unauthorized_signing",
    "stale_key_acceptance",
]

THREAT_MODEL: tuple[ThreatModelCoverage, ...] = (
    "substitution",
    "rollback",
    "compromise",
    "unauthorized_signing",
    "stale_key_acceptance",
)
