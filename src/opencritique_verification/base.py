"""Shared verifier result types and evidence-hash binding."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VerifierArtifact(StrictModel):
    label: str
    media_type: str = "application/json"
    payload: dict[str, Any]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VerifierManifest(StrictModel):
    manifest_version: str = "0.1"
    verifier_id: str
    status: Literal["pass", "fail", "error"]
    summary: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VerifierResult(StrictModel):
    verifier_id: str
    status: Literal["pass", "fail", "error"]
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    error_kind: str | None = None
    manifest: VerifierManifest
    artifacts: list[VerifierArtifact] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def build_verifier_result(
    *,
    verifier_id: str,
    status: Literal["pass", "fail", "error"],
    summary: str,
    payload: dict[str, Any],
    details: dict[str, Any] | None = None,
    error_kind: str | None = None,
    artifact_label: str = "verifier_payload",
) -> VerifierResult:
    digest = bind_evidence_hash(payload)
    artifact = VerifierArtifact(
        label=artifact_label,
        payload=payload,
        sha256=digest,
    )
    manifest = VerifierManifest(
        verifier_id=verifier_id,
        status=status,
        summary=summary,
        artifact_sha256=digest,
    )
    return VerifierResult(
        verifier_id=verifier_id,
        status=status,
        summary=summary,
        details=details or payload,
        artifact_sha256=digest,
        error_kind=error_kind,
        manifest=manifest,
        artifacts=[artifact],
    )


def bind_evidence_hash(payload: dict[str, Any]) -> str:
    """Canonical SHA-256 over verifier artifact payload (sorted keys)."""
    material = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
