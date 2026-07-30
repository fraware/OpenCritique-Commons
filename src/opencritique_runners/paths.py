"""Output path guardrails for live runners."""

from __future__ import annotations

from pathlib import Path

from opencritique_adapters.production_errors import ProductionPackageUnauthorizedError

# Directory names that mark private operator-local evidence (not production intake).
_PRIVATE_RUN_MARKERS = frozenset({"runs", ".runtime-live", ".demo-e2e"})


def is_production_fixtures_path(path: Path) -> bool:
    """True when ``path`` resolves under ``fixtures/<adapter>/production/``."""
    resolved = path.resolve()
    parts = [part.lower() for part in resolved.parts]
    for index, part in enumerate(parts):
        if part != "fixtures":
            continue
        if index + 2 >= len(parts):
            continue
        if parts[index + 2] == "production":
            return True
    return False


def is_under_private_runs(path: Path) -> bool:
    """True when *path* resolves under a private live/runs tree."""
    parts = tuple(part.lower() for part in path.resolve().parts)
    return any(marker in parts for marker in _PRIVATE_RUN_MARKERS)


def assert_not_production_fixtures_path(path: Path, *, action: str = "write") -> None:
    """Refuse live-runner writes into production fixture trees."""
    if is_production_fixtures_path(path):
        raise ProductionPackageUnauthorizedError(
            f"Refusing to {action} under fixtures/*/production/: {path}. "
            "Private live runs stay under runs/ (or another non-production path). "
            "Promotion requires rights clearance + volume gates via the staging "
            "ingest path — never auto-promote from the live runner."
        )


def assert_output_not_production_fixture(path: Path) -> None:
    """Alias used by the OpenReviewer runner surface."""
    assert_not_production_fixtures_path(path)


def assert_package_not_private_runs(package_dir: Path) -> None:
    """Refuse auto-promoting private ``runs/`` trees into production fixtures."""
    if is_under_private_runs(package_dir):
        raise ProductionPackageUnauthorizedError(
            "refusing to stage from runs/ (or other private live trees); "
            "build an explicit rights-cleared production package outside runs/, "
            "then call ingest_production_adapter_exports.py stage. "
            "Private live ≠ production authenticity."
        )
