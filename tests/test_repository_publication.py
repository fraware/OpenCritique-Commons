from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_SOURCE_FILES = (
    "src/opencritique_schema/models.py",
    "src/opencritique_schema/registry.py",
    "src/opencritique_registry/api.py",
    "src/opencritique_evaluation/engine.py",
    "src/opencritique_evaluation/novel_determination.py",
    "src/opencritique_adapters/coarse.py",
    "src/opencritique_acquisition/models.py",
    "docs/canonicalization.md",
    "governance/decisions/ADR-0002-naming-deltas.md",
    "schemas/GOLDEN_HASHES.json",
    "migrations/env.py",
    "alembic.ini",
)

PROHIBITED_REPAIR_PATHS = (
    ".bootstrap",
    ".github/workflows/bootstrap-source.yml",
    ".github/workflows/publish-main.yml",
    ".github/workflows/publish-blobs.yml",
    ".github/workflows/repair-publish.yml",
)


def test_required_public_source_is_committed() -> None:
    missing = [path for path in REQUIRED_SOURCE_FILES if not (ROOT / path).is_file()]
    assert not missing, f"Required public source files are missing: {missing}"


def test_repair_transport_is_absent() -> None:
    present = [path for path in PROHIBITED_REPAIR_PATHS if (ROOT / path).exists()]
    assert not present, f"Temporary repair artifacts must not be committed: {present}"


def test_studio_assets_include_app_js() -> None:
    assert (ROOT / "src/opencritique_registry/studio_assets/app.js").is_file()


def test_evaluation_cli_exports_typer_app() -> None:
    from opencritique_evaluation.cli import app

    assert app is not None
