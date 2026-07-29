"""Production adapter fixture intake status (issues #3 / #5).

Production trees under ``fixtures/*/production/`` hold rights-cleared authentic
upstream exports when available. Until genuine exports land, the trees remain
empty of review payloads and status is ``pending`` / ``blocked``.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionIntakeStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"


class ProductionManifest(StrictModel):
    """Schema for ``fixtures/*/production/MANIFEST.json``."""

    manifest_version: str = "0.1"
    adapter: str
    source: str = Field(pattern=r"^production$")
    status: ProductionIntakeStatus
    upstream_repository: str
    upstream_commit_or_config: str | None = None
    retrieval_date: str | None = None
    rights_record_ids: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    blocked_reason: str | None = None
    performance_claims_authorized: bool = False

    @field_validator("performance_claims_authorized")
    @classmethod
    def claims_remain_false(cls, value: bool) -> bool:
        if value:
            raise ValueError("performance_claims_authorized must remain false")
        return value


class ProductionSection(StrictModel):
    """Report section shape for ``source=production`` (distinct from sample)."""

    source: str = "production"
    adapter: str
    status: ProductionIntakeStatus
    fixture_root: str
    export_count: int = 0
    blocked_reason: str | None = None
    notes: str = (
        "Production conversion fidelity only when status=ready; never reviewer-quality claims."
    )


ROOT = Path(__file__).resolve().parents[2]
COARSE_PRODUCTION = ROOT / "fixtures" / "coarse" / "production"
OPENREVIEWER_PRODUCTION = ROOT / "fixtures" / "openreviewer" / "production"

_REVIEW_SUFFIXES = (".json",)


def _count_review_artifacts(directory: Path) -> int:
    reviews = directory / "reviews"
    if not reviews.is_dir():
        return 0
    return sum(
        1
        for path in reviews.iterdir()
        if path.suffix in _REVIEW_SUFFIXES and path.is_file()
    )


def load_production_manifest(path: Path) -> ProductionManifest:
    return ProductionManifest.model_validate_json(path.read_text(encoding="utf-8"))


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
        raise ValueError(f"manifest adapter {manifest.adapter!r} != {adapter!r}")
    export_count = _count_review_artifacts(fixture_root)
    if manifest.status == ProductionIntakeStatus.READY and export_count < 1:
        raise ValueError(
            f"production manifest for {adapter} claims ready but reviews/ is empty"
        )
    if manifest.status == ProductionIntakeStatus.READY and export_count < 10:
        # Hard DoD for #3/#5 targets ≥10; fail closed rather than silently pass.
        raise ValueError(
            f"production manifest for {adapter} claims ready with only {export_count} exports"
        )
    return ProductionSection(
        adapter=adapter,
        status=manifest.status,
        fixture_root=str(fixture_root.as_posix()),
        export_count=export_count,
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
    ]
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
