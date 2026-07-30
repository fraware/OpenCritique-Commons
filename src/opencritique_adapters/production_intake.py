"""Validate and stage production adapter export packages (issues #3 / #5).

Does not fabricate exports. Callers supply genuine rights-cleared packages; this
module refuse-closes incomplete, unauthorized, or sample-contaminated packages.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .production_errors import (
    ProductionIntakeError,
    ProductionManifestError,
    ProductionPackageUnauthorizedError,
    ProductionReadyIncompleteError,
)
from .production_fixtures import (
    ADAPTER_READY_MINIMA,
    ProductionArtifact,
    ProductionIntakeStatus,
    ProductionManifest,
    ProductionSection,
    check_manifest_invariants,
    file_sha256,
    load_production_manifest,
    production_section_for,
    verify_artifact_hashes,
)


@dataclass(frozen=True, slots=True)
class ProductionIntakeResult:
    adapter: str
    status: ProductionIntakeStatus
    export_count: int
    fixture_root: Path
    section: ProductionSection
    message: str


def discover_review_files(package_dir: Path) -> list[Path]:
    reviews = package_dir / "reviews"
    if not reviews.is_dir():
        return []
    return sorted(
        path
        for path in reviews.iterdir()
        if path.is_file() and path.suffix == ".json" and path.name != "MANIFEST.json"
    )


def build_artifacts_from_reviews(
    package_dir: Path,
    *,
    rights_record_id: str,
) -> list[ProductionArtifact]:
    artifacts: list[ProductionArtifact] = []
    for path in discover_review_files(package_dir):
        relative = path.relative_to(package_dir).as_posix()
        artifacts.append(
            ProductionArtifact(
                relative_path=relative,
                content_sha256=file_sha256(path),
                byte_size=path.stat().st_size,
                rights_record_id=rights_record_id,
            )
        )
    return artifacts


def validate_production_package(
    package_dir: Path,
    *,
    expected_adapter: str | None = None,
    require_ready: bool = False,
) -> ProductionManifest:
    """Validate a production package directory against the intake contract.

    Expects ``MANIFEST.json`` and optional ``reviews/*.json``. Refuses packages
    that claim ready without complete rights binding, upstream pin, and hashes.
    """
    if not package_dir.is_dir():
        raise ProductionPackageUnauthorizedError(
            f"production package directory not found: {package_dir}"
        )
    manifest_path = package_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        raise ProductionManifestError(f"MANIFEST.json missing under {package_dir}")
    manifest = load_production_manifest(manifest_path)
    if expected_adapter is not None and manifest.adapter != expected_adapter:
        raise ProductionManifestError(
            f"expected adapter {expected_adapter!r}, got {manifest.adapter!r}"
        )
    check_manifest_invariants(manifest)
    on_disk = discover_review_files(package_dir)
    if manifest.status == ProductionIntakeStatus.READY:
        if not on_disk:
            raise ProductionReadyIncompleteError(
                "ready package has empty reviews/; refusing incomplete package"
            )
        min_count = ADAPTER_READY_MINIMA.get(manifest.adapter, 10)
        if len(on_disk) < min_count:
            raise ProductionReadyIncompleteError(
                f"ready package for {manifest.adapter} has {len(on_disk)} reviews; "
                f"minimum is {min_count}"
            )
        verify_artifact_hashes(manifest, package_dir)
        declared = {item.relative_path for item in manifest.artifacts}
        actual = {path.relative_to(package_dir).as_posix() for path in on_disk}
        if declared != actual:
            raise ProductionReadyIncompleteError(
                "MANIFEST artifacts do not match reviews/ contents: "
                f"only_in_manifest={sorted(declared - actual)} "
                f"only_on_disk={sorted(actual - declared)}"
            )
    elif on_disk:
        raise ProductionPackageUnauthorizedError(
            f"status={manifest.status.value} package must not contain review JSON "
            "until rights clearance and ready promotion"
        )
    if require_ready and manifest.status != ProductionIntakeStatus.READY:
        raise ProductionPackageUnauthorizedError(
            f"package status is {manifest.status.value}; ready required"
        )
    return manifest


def validate_fixture_tree(adapter: str, fixture_root: Path) -> ProductionIntakeResult:
    """Validate an in-repo production fixture tree (sample-vs-production safe)."""
    section = production_section_for(adapter, fixture_root)
    manifest = load_production_manifest(fixture_root / "MANIFEST.json")
    if manifest.status == ProductionIntakeStatus.READY:
        validate_production_package(fixture_root, expected_adapter=adapter, require_ready=True)
    return ProductionIntakeResult(
        adapter=adapter,
        status=section.status,
        export_count=section.export_count,
        fixture_root=fixture_root,
        section=section,
        message=(
            f"{adapter}: status={section.status.value} exports={section.export_count}"
        ),
    )


def stage_validated_package(
    package_dir: Path,
    destination: Path,
    *,
    expected_adapter: str,
    dry_run: bool = False,
) -> ProductionIntakeResult:
    """Copy a validated ready package into the destination fixture tree.

    Refuses non-ready packages. Never invents review payloads.
    Refuses auto-promotion from private ``runs/`` (or other live) trees —
    operators must stage an explicit rights-cleared package outside those paths.
    """
    # Local import keeps adapters usable if runners are mid-merge with Coarse L1.
    from opencritique_runners.paths import assert_package_not_private_runs

    assert_package_not_private_runs(package_dir)
    manifest = validate_production_package(
        package_dir,
        expected_adapter=expected_adapter,
        require_ready=True,
    )
    if dry_run:
        section = ProductionSection(
            adapter=manifest.adapter,
            status=manifest.status,
            fixture_root=str(destination.as_posix()),
            export_count=len(manifest.artifacts),
            upstream_commit_or_config=manifest.upstream_commit_or_config,
            rights_record_count=len(manifest.rights_record_ids),
            blocked_reason=None,
        )
        return ProductionIntakeResult(
            adapter=manifest.adapter,
            status=manifest.status,
            export_count=len(manifest.artifacts),
            fixture_root=destination,
            section=section,
            message=f"dry-run OK: would stage {len(manifest.artifacts)} exports to {destination}",
        )

    destination.mkdir(parents=True, exist_ok=True)
    (destination / "reviews").mkdir(parents=True, exist_ok=True)
    # Clear prior review payloads only after validation succeeded.
    for stale in (destination / "reviews").glob("*.json"):
        stale.unlink()
    for artifact in manifest.artifacts:
        src = package_dir / artifact.relative_path
        dst = destination / artifact.relative_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    stamped = manifest.model_copy(
        update={
            "retrieval_date": manifest.retrieval_date
            or datetime.now(UTC).date().isoformat(),
        }
    )
    (destination / "MANIFEST.json").write_text(
        json.dumps(stamped.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = validate_fixture_tree(expected_adapter, destination)
    return result


def format_intake_error(exc: ProductionIntakeError) -> str:
    return f"{exc.code}: {exc}"
