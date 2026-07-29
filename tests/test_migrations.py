"""Alembic migration path tests (empty DB and previous-release → head)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "c9d2e4f6a8b0"
PREVIOUS_REVISION = "e47498e63a9d"


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    return cfg


def _migrate(tmp_path: Path, monkeypatch: object, db_name: str, revision: str = "head") -> str:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    url = f"sqlite:///{db_name}"
    monkeypatch.setenv("OPENCRITIQUE_DATABASE_URL", url)  # type: ignore[attr-defined]
    command.upgrade(_alembic_config(), revision)
    return url


def test_migrate_empty_database(tmp_path: Path, monkeypatch: object) -> None:
    url = _migrate(tmp_path, monkeypatch, "empty.db")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert "alembic_version" in tables
    assert "cases" in tables
    assert "determinations" in tables
    assert "appeal_records" in tables
    assert "novel_candidates" in tables
    assert "novel_determinations" in tables
    assert "scorecard_records" in tables
    assert "benchmark_versions" in tables
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == HEAD_REVISION


def test_migrate_from_previous_release(tmp_path: Path, monkeypatch: object) -> None:
    """Upgrade previous-release revision to current head."""
    url = _migrate(tmp_path, monkeypatch, "previous.db", revision=PREVIOUS_REVISION)
    with create_engine(url).connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == PREVIOUS_REVISION
    tables = set(inspect(create_engine(url)).get_table_names())
    assert "principals" in tables
    assert "novel_adjudication_tasks" in tables
    command.upgrade(_alembic_config(), "head")
    with create_engine(url).connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == HEAD_REVISION


def test_metadata_matches_migrated_schema(tmp_path: Path, monkeypatch: object) -> None:
    import opencritique_registry.db_models  # noqa: F401
    from opencritique_registry.db import Base

    url = _migrate(tmp_path, monkeypatch, "compare.db")
    migrated = set(inspect(create_engine(url)).get_table_names()) - {"alembic_version"}
    expected = set(Base.metadata.tables)
    assert migrated == expected
