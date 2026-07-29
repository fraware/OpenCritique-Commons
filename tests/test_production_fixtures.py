"""Production fixture tree intake (issues #3 / #5)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from opencritique_adapters.coarse_loss import build_conversion_loss_report
from opencritique_adapters.openreviewer_loss import build_cross_adapter_report
from opencritique_adapters.production_errors import (
    ProductionClaimsUnauthorizedError,
    ProductionHashMismatchError,
    ProductionPackageUnauthorizedError,
    ProductionReadyIncompleteError,
    ProductionRightsBindingError,
    ProductionSampleContaminationError,
    ProductionUpstreamPinError,
)
from opencritique_adapters.production_fixtures import (
    ADAPTER_READY_MINIMA,
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
    ProductionArtifact,
    ProductionIntakeStatus,
    ProductionManifest,
    assert_production_tree_fail_closed,
    dump_manifest_schema,
    load_production_manifest,
    write_manifest_schema,
)
from opencritique_adapters.production_intake import (
    stage_validated_package,
    validate_fixture_tree,
    validate_production_package,
)

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "coarse-synth-v0.1"
MANIFEST = BENCH / "manifest.json"
MAP = ROOT / "fixtures" / "coarse" / "maps" / "synth-map.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ready_manifest(
    *,
    adapter: str,
    artifacts: list[ProductionArtifact],
    rights: list[str],
    pin: str = "abc123deadbeef",
) -> dict:
    return {
        "manifest_version": "0.1",
        "adapter": adapter,
        "source": "production",
        "status": "ready",
        "upstream_repository": "https://example.invalid/upstream",
        "upstream_commit_or_config": pin,
        "retrieval_date": "2026-07-29",
        "rights_record_ids": rights,
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "blocked_reason": None,
        "performance_claims_authorized": False,
        "sample_contract_forbidden": True,
    }


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
    result = validate_fixture_tree(adapter, root)
    assert result.status != ProductionIntakeStatus.READY


def test_ready_manifest_without_exports_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "production"
    (root / "reviews").mkdir(parents=True)
    manifest = {
        "manifest_version": "0.1",
        "adapter": "coarse",
        "source": "production",
        "status": "ready",
        "upstream_repository": "https://example.invalid/coarse",
        "upstream_commit_or_config": "deadbeef",
        "retrieval_date": "2026-07-29",
        "rights_record_ids": ["rr-1"],
        "artifacts": [],
        "performance_claims_authorized": False,
        "blocked_reason": None,
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProductionReadyIncompleteError, match="artifact"):
        assert_production_tree_fail_closed("coarse", root)


@pytest.mark.parametrize(
    "adapter,min_count",
    [
        ("coarse", ADAPTER_READY_MINIMA["coarse"]),
        ("openreviewer", ADAPTER_READY_MINIMA["openreviewer"]),
    ],
)
def test_ready_below_required_export_count_fails_closed(
    tmp_path: Path, adapter: str, min_count: int
) -> None:
    """READY without ≥10 / ≥5 exports must fail closed."""
    root = tmp_path / "production"
    (root / "reviews").mkdir(parents=True)
    short = min_count - 1
    assert short >= 1
    artifacts = []
    for idx in range(short):
        name = f"reviews/e{idx}.json"
        data = b'{"ok":true}' + f"{idx}".encode()
        (root / name).write_bytes(data)
        artifacts.append(
            ProductionArtifact(
                relative_path=name,
                content_sha256=_sha(data),
                byte_size=len(data),
                rights_record_id="rr-1",
            )
        )
    (root / "MANIFEST.json").write_text(
        json.dumps(
            _ready_manifest(adapter=adapter, artifacts=artifacts, rights=["rr-1"])
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionReadyIncompleteError, match="at least"):
        assert_production_tree_fail_closed(adapter, root)


def test_ready_with_empty_reviews_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "production"
    (root / "reviews").mkdir(parents=True)
    payload = b'{"title":"cleared"}'
    artifact = ProductionArtifact(
        relative_path="reviews/missing.json",
        content_sha256=_sha(payload),
        byte_size=len(payload),
        rights_record_id="rr-1",
    )
    # Pad to coarse minimum with declared-but-missing files by writing only one
    # and expecting hash/ready failure after enough artifacts declared.
    artifacts = [
        ProductionArtifact(
            relative_path=f"reviews/export-{idx:02d}.json",
            content_sha256=_sha(payload + bytes([idx])),
            byte_size=len(payload) + 1,
            rights_record_id="rr-1",
        )
        for idx in range(ADAPTER_READY_MINIMA["coarse"])
    ]
    # Fix first artifact to match written file; leave others missing.
    artifacts[0] = artifact
    (root / "reviews" / "missing.json").write_bytes(payload)
    (root / "MANIFEST.json").write_text(
        json.dumps(_ready_manifest(adapter="coarse", artifacts=artifacts, rights=["rr-1"])),
        encoding="utf-8",
    )
    with pytest.raises((ProductionReadyIncompleteError, ProductionHashMismatchError)):
        assert_production_tree_fail_closed("coarse", root)


def test_reject_sample_contract_pin_as_production(tmp_path: Path) -> None:
    root = tmp_path / "production"
    (root / "reviews").mkdir(parents=True)
    payload = b'{"ok":true}'
    artifacts = []
    for idx in range(ADAPTER_READY_MINIMA["coarse"]):
        name = f"reviews/e{idx}.json"
        data = payload + f"{idx}".encode()
        (root / name).write_bytes(data)
        artifacts.append(
            ProductionArtifact(
                relative_path=name,
                content_sha256=_sha(data),
                byte_size=len(data),
                rights_record_id="rr-1",
            )
        )
    (root / "MANIFEST.json").write_text(
        json.dumps(
            _ready_manifest(
                adapter="coarse",
                artifacts=artifacts,
                rights=["rr-1"],
                pin="opencritique-sample-adapter-contract-v1",
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionSampleContaminationError):
        load_production_manifest(root / "MANIFEST.json")


def test_reject_claims_authorized(tmp_path: Path) -> None:
    path = tmp_path / "MANIFEST.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "0.1",
                "adapter": "coarse",
                "source": "production",
                "status": "blocked",
                "upstream_repository": "https://example.invalid/coarse",
                "blocked_reason": "blocked",
                "performance_claims_authorized": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionClaimsUnauthorizedError):
        load_production_manifest(path)


def test_reject_ready_without_upstream_pin(tmp_path: Path) -> None:
    path = tmp_path / "MANIFEST.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "0.1",
                "adapter": "coarse",
                "source": "production",
                "status": "ready",
                "upstream_repository": "https://example.invalid/coarse",
                "upstream_commit_or_config": None,
                "retrieval_date": "2026-07-29",
                "rights_record_ids": ["rr-1"],
                "artifacts": [
                    {
                        "relative_path": f"reviews/a{i}.json",
                        "content_sha256": f"{i:064x}",
                        "byte_size": 1,
                        "rights_record_id": "rr-1",
                    }
                    for i in range(10)
                ],
                "performance_claims_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionUpstreamPinError):
        load_production_manifest(path)


def test_reject_rights_binding_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "MANIFEST.json"
    artifacts = [
        {
            "relative_path": f"reviews/a{i}.json",
            "content_sha256": f"{i:064x}",
            "byte_size": 1,
            "rights_record_id": "missing-rr",
        }
        for i in range(10)
    ]
    path.write_text(
        json.dumps(
            {
                "manifest_version": "0.1",
                "adapter": "coarse",
                "source": "production",
                "status": "ready",
                "upstream_repository": "https://example.invalid/coarse",
                "upstream_commit_or_config": "deadbeef",
                "retrieval_date": "2026-07-29",
                "rights_record_ids": ["rr-1"],
                "artifacts": artifacts,
                "performance_claims_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionRightsBindingError):
        load_production_manifest(path)


def test_blocked_package_with_reviews_rejected(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    (package / "reviews").mkdir(parents=True)
    (package / "reviews" / "sneaky.json").write_text("{}", encoding="utf-8")
    (package / "MANIFEST.json").write_text(
        json.dumps(
            {
                "manifest_version": "0.1",
                "adapter": "openreviewer",
                "source": "production",
                "status": "blocked",
                "upstream_repository": "https://example.invalid/or",
                "blocked_reason": "not cleared",
                "performance_claims_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionPackageUnauthorizedError):
        validate_production_package(package, expected_adapter="openreviewer")


def test_hash_mismatch_rejected(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    (package / "reviews").mkdir(parents=True)
    artifacts = []
    for idx in range(ADAPTER_READY_MINIMA["openreviewer"]):
        name = f"reviews/r{idx}.json"
        data = b'{"x":1}' + bytes([idx])
        (package / name).write_bytes(data)
        artifacts.append(
            ProductionArtifact(
                relative_path=name,
                content_sha256=_sha(data if idx else b"wrong"),
                byte_size=len(data),
                rights_record_id="rr-1",
            )
        )
    (package / "MANIFEST.json").write_text(
        json.dumps(
            _ready_manifest(
                adapter="openreviewer",
                artifacts=artifacts,
                rights=["rr-1"],
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProductionHashMismatchError):
        validate_production_package(package, expected_adapter="openreviewer", require_ready=True)


def test_stage_dry_run_ready_package(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    dest = tmp_path / "dest"
    (package / "reviews").mkdir(parents=True)
    artifacts = []
    for idx in range(ADAPTER_READY_MINIMA["openreviewer"]):
        name = f"reviews/r{idx}.json"
        data = json.dumps({"id": idx}).encode()
        (package / name).write_bytes(data)
        artifacts.append(
            ProductionArtifact(
                relative_path=name,
                content_sha256=_sha(data),
                byte_size=len(data),
                rights_record_id="rr-1",
            )
        )
    (package / "MANIFEST.json").write_text(
        json.dumps(
            _ready_manifest(adapter="openreviewer", artifacts=artifacts, rights=["rr-1"])
        ),
        encoding="utf-8",
    )
    result = stage_validated_package(
        package, dest, expected_adapter="openreviewer", dry_run=True
    )
    assert result.export_count == ADAPTER_READY_MINIMA["openreviewer"]
    assert not (dest / "reviews").exists()


def test_ingest_cli_validate_tree() -> None:
    import importlib.util
    import sys

    name = "ingest_production_adapter_exports"
    spec = importlib.util.spec_from_file_location(
        name,
        ROOT / "scripts" / "ingest_production_adapter_exports.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    runner = CliRunner()
    result = runner.invoke(module.app, ["validate-tree", "--adapter", "coarse"])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_manifest_schema_roundtrip(tmp_path: Path) -> None:
    schema_path = tmp_path / "MANIFEST.schema.json"
    write_manifest_schema(schema_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema == dump_manifest_schema()
    # Refresh shipped schemas beside fixtures.
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
    from opencritique_adapters.coarse_loss import report_to_markdown as coarse_md
    from opencritique_adapters.openreviewer_loss import report_to_markdown as cross_md
    from opencritique_adapters.production_fixtures import production_section_markdown

    section_md = production_section_markdown(report.production)
    assert "NOT READY" in section_md
    assert "refuse" in section_md.lower()
    coarse_text = coarse_md(report)
    assert "NOT READY" in coarse_text
    cross = build_cross_adapter_report()
    assert len(cross.production_sections) == 2
    assert all(s.source == "production" for s in cross.production_sections)
    assert all(s.status != ProductionIntakeStatus.READY for s in cross.production_sections)
    cross_text = cross_md(cross)
    assert cross_text.count("NOT READY") >= 2
