"""Production fixture tree intake (issues #3 / #5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opencritique_adapters.coarse_loss import build_conversion_loss_report
from opencritique_adapters.openreviewer_loss import build_cross_adapter_report
from opencritique_adapters.production_fixtures import (
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
    ProductionIntakeStatus,
    ProductionManifest,
    assert_production_tree_fail_closed,
    dump_manifest_schema,
    load_production_manifest,
    write_manifest_schema,
)

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "coarse-synth-v0.1"
MANIFEST = BENCH / "manifest.json"
MAP = ROOT / "fixtures" / "coarse" / "maps" / "synth-map.json"


@pytest.mark.parametrize(
    "root,adapter",
    [
        (COARSE_PRODUCTION, "coarse"),
        (OPENREVIEWER_PRODUCTION, "openreviewer"),
    ],
)
def test_production_trees_documented_and_blocked(root: Path, adapter: str) -> None:
    assert (root / "README.md").is_file()
    assert (root / "MANIFEST.json").is_file()
    assert (root / "reviews").is_dir()
    manifest = load_production_manifest(root / "MANIFEST.json")
    assert manifest.adapter == adapter
    assert manifest.source == "production"
    assert manifest.performance_claims_authorized is False
    assert manifest.status in {
        ProductionIntakeStatus.PENDING,
        ProductionIntakeStatus.BLOCKED,
    }
    assert manifest.blocked_reason
    # No fabricated production review payloads.
    reviews = [
        path
        for path in (root / "reviews").iterdir()
        if path.is_file() and path.suffix == ".json"
    ]
    assert reviews == []
    section = assert_production_tree_fail_closed(adapter, root)
    assert section.export_count == 0
    assert section.status != ProductionIntakeStatus.READY


def test_ready_manifest_without_exports_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "production"
    (root / "reviews").mkdir(parents=True)
    manifest = {
        "manifest_version": "0.1",
        "adapter": "coarse",
        "source": "production",
        "status": "ready",
        "upstream_repository": "https://example.invalid/coarse",
        "artifacts": [],
        "performance_claims_authorized": False,
        "blocked_reason": None,
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        assert_production_tree_fail_closed("coarse", root)


def test_manifest_schema_roundtrip(tmp_path: Path) -> None:
    schema_path = tmp_path / "MANIFEST.schema.json"
    write_manifest_schema(schema_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema == dump_manifest_schema()
    # Shipped schemas beside fixtures.
    for root in (COARSE_PRODUCTION, OPENREVIEWER_PRODUCTION):
        write_manifest_schema(root / "MANIFEST.schema.json")
        assert (root / "MANIFEST.schema.json").is_file()
    ProductionManifest.model_validate_json(
        (COARSE_PRODUCTION / "MANIFEST.json").read_text(encoding="utf-8")
    )


def test_loss_reports_include_production_section() -> None:
    extracted = json.loads(
        (ROOT / "fixtures" / "coarse" / "extracted_texts.json").read_text(encoding="utf-8")
    )
    report = build_conversion_loss_report(
        benchmark_manifest_path=MANIFEST,
        benchmark_root=BENCH,
        map_path=MAP,
        extracted_texts=extracted,
    )
    assert report.production is not None
    assert report.production.source == "production"
    assert report.production.status != ProductionIntakeStatus.READY
    cross = build_cross_adapter_report()
    assert len(cross.production_sections) == 2
    assert all(s.source == "production" for s in cross.production_sections)
    assert all(s.status != ProductionIntakeStatus.READY for s in cross.production_sections)
