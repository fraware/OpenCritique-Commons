"""Production adapter fixture intake status (issues #3 / #5).

Production trees under ``fixtures/*/production/`` hold rights-cleared authentic
upstream exports when available. Until genuine exports land, the trees remain
empty of review payloads and status is ``pending`` / ``blocked``.

Sample fixtures live under ``fixtures/*/reviews/`` and use the sample adapter
contract id. Production intake must never treat sample contract pins as
authentic upstream pins.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .contract import COARSE_SAMPLE_ADAPTER_CONTRACT_ID
from .production_errors import (
    ProductionClaimsUnauthorizedError,
    ProductionHashMismatchError,
    ProductionManifestError,
    ProductionReadyIncompleteError,
    ProductionRightsBindingError,
    ProductionSampleContaminationError,
    ProductionUpstreamPinError,
)

# Keep in sync with openreviewer sample contract id without importing openreviewer
# (avoids circular import during package init).
_SAMPLE_ADAPTER_CONTRACT_IDS: Final[frozenset[str]] = frozenset(
    {
        COARSE_SAMPLE_ADAPTER_CONTRACT_ID,
        "opencritique-sample-adapter-contract-v1",
    }
)

ADAPTER_READY_MINIMA: Final[dict[str, int]] = {
    "coarse": 10,
    "openreviewer": 5,
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionIntakeStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"


class ProductionArtifact(StrictModel):
    """One rights-cleared production export recorded in the MANIFEST."""

    relative_path: str = Field(
        min_length=1,
        description="Path relative to the production fixture root (e.g. reviews/export-01.json).",
    )
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1)
    rights_record_id: str = Field(min_length=1)


class ProductionManifest(StrictModel):
    """Schema for ``fixtures/*/production/MANIFEST.json``."""

    manifest_version: str = "0.1"
    adapter: str = Field(pattern=r"^(coarse|openreviewer)$")
    source: str = Field(pattern=r"^production$")
    status: ProductionIntakeStatus
    upstream_repository: str = Field(min_length=1)
    upstream_commit_or_config: str | None = None
    retrieval_date: str | None = None
    rights_record_ids: list[str] = Field(default_factory=list)
    artifacts: list[ProductionArtifact] = Field(default_factory=list)
    blocked_reason: str | None = None
    performance_claims_authorized: bool = False
    # Explicit separation from sample adapter contract trees.
    sample_contract_forbidden: bool = True

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_remain_false(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value


ROOT = Path(__file__).resolve().parents[2]
COARSE_PRODUCTION = ROOT / "fixtures" / "coarse" / "production"
OPENREVIEWER_PRODUCTION = ROOT / "fixtures" / "openreviewer" / "production"

_REVIEW_SUFFIXES = (".json",)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_review_artifacts(directory: Path) -> int:
    reviews = directory / "reviews"
    if not reviews.is_dir():
        return 0
    return sum(
        1
        for path in reviews.iterdir()
        if path.suffix in _REVIEW_SUFFIXES and path.is_file()
    )


def check_manifest_invariants(manifest: ProductionManifest) -> None:
    """Raise typed intake errors when MANIFEST status contract is violated."""
    if manifest.performance_claims_authorized:
        raise ProductionClaimsUnauthorizedError(
            "performance_claims_authorized must remain false"
        )
    if len(manifest.rights_record_ids) != len(set(manifest.rights_record_ids)):
        raise ProductionRightsBindingError("rights_record_ids must be unique")
    paths = [item.relative_path for item in manifest.artifacts]
    if len(paths) != len(set(paths)):
        raise ProductionManifestError("artifact relative_path values must be unique")

    if manifest.status == ProductionIntakeStatus.READY:
        if not (manifest.upstream_commit_or_config or "").strip():
            raise ProductionUpstreamPinError(
                "ready production manifest requires upstream_commit_or_config"
            )
        pin = (manifest.upstream_commit_or_config or "").strip()
        if pin in _SAMPLE_ADAPTER_CONTRACT_IDS:
            raise ProductionSampleContaminationError(
                "production upstream pin must not be a sample adapter contract id"
            )
        if not (manifest.retrieval_date or "").strip():
            raise ProductionReadyIncompleteError(
                "ready production manifest requires retrieval_date"
            )
        if manifest.blocked_reason:
            raise ProductionReadyIncompleteError(
                "ready production manifest must not set blocked_reason"
            )
        if not manifest.rights_record_ids:
            raise ProductionRightsBindingError(
                "ready production manifest requires rights_record_ids"
            )
        if not manifest.artifacts:
            raise ProductionReadyIncompleteError(
                "ready production manifest requires artifact records"
            )
        min_count = ADAPTER_READY_MINIMA.get(manifest.adapter, 10)
        if len(manifest.artifacts) < min_count:
            raise ProductionReadyIncompleteError(
                f"ready production manifest for {manifest.adapter} requires "
                f"at least {min_count} artifacts; got {len(manifest.artifacts)}"
            )
        rights = set(manifest.rights_record_ids)
        for artifact in manifest.artifacts:
            if artifact.rights_record_id not in rights:
                raise ProductionRightsBindingError(
                    f"artifact {artifact.relative_path} rights_record_id "
                    f"{artifact.rights_record_id!r} not listed in rights_record_ids"
                )
        return

    if manifest.status in {ProductionIntakeStatus.PENDING, ProductionIntakeStatus.BLOCKED}:
        if manifest.artifacts:
            raise ProductionManifestError(
                f"{manifest.status.value} production manifest must not list artifacts "
                "until status=ready"
            )
        if manifest.status == ProductionIntakeStatus.BLOCKED and not (
            manifest.blocked_reason or ""
        ).strip():
            raise ProductionManifestError(
                "blocked production manifest requires blocked_reason"
            )


def load_production_manifest(path: Path) -> ProductionManifest:
    try:
        manifest = ProductionManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        message = str(exc)
        if "performance_claims_authorized" in message:
            raise ProductionClaimsUnauthorizedError(
                "performance_claims_authorized must remain false"
            ) from exc
        raise ProductionManifestError(f"invalid production MANIFEST at {path}: {exc}") from exc
    check_manifest_invariants(manifest)
    return manifest


class ProductionSection(StrictModel):
    """Report section shape for ``source=production`` (distinct from sample)."""

    source: str = "production"
    adapter: str
    status: ProductionIntakeStatus
    fixture_root: str
    export_count: int = 0
    upstream_commit_or_config: str | None = None
    rights_record_count: int = 0
    blocked_reason: str | None = None
    notes: str = (
        "Production conversion fidelity only when status=ready; never reviewer-quality claims."
    )


def verify_artifact_hashes(manifest: ProductionManifest, fixture_root: Path) -> None:
    """Fail closed when declared hashes do not match on-disk bytes."""
    for artifact in manifest.artifacts:
        path = (fixture_root / artifact.relative_path).resolve()
        root = fixture_root.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ProductionHashMismatchError(
                f"artifact path escapes fixture root: {artifact.relative_path}"
            ) from exc
        if not path.is_file():
            raise ProductionHashMismatchError(
                f"missing production artifact file: {artifact.relative_path}"
            )
        actual_size = path.stat().st_size
        if actual_size != artifact.byte_size:
            raise ProductionHashMismatchError(
                f"byte_size mismatch for {artifact.relative_path}: "
                f"declared {artifact.byte_size}, actual {actual_size}"
            )
        actual_hash = file_sha256(path)
        if actual_hash != artifact.content_sha256:
            raise ProductionHashMismatchError(
                f"content_sha256 mismatch for {artifact.relative_path}: "
                f"declared {artifact.content_sha256}, actual {actual_hash}"
            )


def production_section_for(adapter: str, fixture_root: Path) -> ProductionSection:
    manifest_path = fixture_root / "MANIFEST.json"
    if not manifest_path.is_file():
        return ProductionSection(
            adapter=adapter,
            status=ProductionIntakeStatus.BLOCKED,
            fixture_root=str(fixture_root.as_posix()),
            export_count=0,
            blocked_reason="MANIFEST.json missing",
        )
    manifest = load_production_manifest(manifest_path)
    if manifest.adapter != adapter:
        raise ProductionManifestError(
            f"manifest adapter {manifest.adapter!r} != {adapter!r}"
        )
    export_count = _count_review_artifacts(fixture_root)
    min_count = ADAPTER_READY_MINIMA.get(adapter, 10)
    if manifest.status == ProductionIntakeStatus.READY:
        if export_count < 1:
            raise ProductionReadyIncompleteError(
                f"production manifest for {adapter} claims ready but reviews/ is empty"
            )
        if export_count < min_count:
            raise ProductionReadyIncompleteError(
                f"production manifest for {adapter} claims ready with only "
                f"{export_count} exports (minimum {min_count})"
            )
        if len(manifest.artifacts) != export_count:
            raise ProductionReadyIncompleteError(
                f"production manifest for {adapter} artifact count "
                f"{len(manifest.artifacts)} != on-disk review count {export_count}"
            )
        verify_artifact_hashes(manifest, fixture_root)
    return ProductionSection(
        adapter=adapter,
        status=manifest.status,
        fixture_root=str(fixture_root.as_posix()),
        export_count=export_count,
        upstream_commit_or_config=manifest.upstream_commit_or_config,
        rights_record_count=len(manifest.rights_record_ids),
        blocked_reason=manifest.blocked_reason,
    )


def assert_production_tree_fail_closed(adapter: str, fixture_root: Path) -> ProductionSection:
    """Return the production section; raise if READY with insufficient exports."""
    return production_section_for(adapter, fixture_root)


def production_section_markdown(section: ProductionSection) -> str:
    lines = [
        f"## source=production (`{section.adapter}`)",
        "",
        f"- Status: `{section.status.value}`",
        f"- Fixture root: `{section.fixture_root}`",
        f"- Export count: {section.export_count}",
        f"- Rights record count: {section.rights_record_count}",
    ]
    if section.upstream_commit_or_config:
        lines.append(f"- Upstream pin: `{section.upstream_commit_or_config}`")
    if section.blocked_reason:
        lines.append(f"- Blocked reason: {section.blocked_reason}")
    lines.extend(["", section.notes, ""])
    return "\n".join(lines)


def dump_manifest_schema() -> dict[str, Any]:
    return ProductionManifest.model_json_schema()


def write_manifest_schema(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dump_manifest_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
