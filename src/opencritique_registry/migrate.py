"""Alembic upgrade helpers for registry initialization."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[2], Path.cwd()]
    for candidate in candidates:
        if (candidate / "alembic.ini").is_file() and (candidate / "migrations").is_dir():
            return candidate
    raise RuntimeError(
        "cannot locate alembic.ini and migrations/; run from the repository root "
        "or install an editable checkout"
    )


def alembic_config(*, database_url: str | None = None) -> Config:
    """Build an Alembic Config rooted at the repository package layout."""
    root = _repo_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("path_separator", "os")
    if database_url is not None:
        cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def upgrade_head(database_url: str) -> None:
    """Apply all migrations to ``head`` for ``database_url``."""
    previous = os.environ.get("OPENCRITIQUE_DATABASE_URL")
    os.environ["OPENCRITIQUE_DATABASE_URL"] = database_url
    try:
        command.upgrade(alembic_config(database_url=database_url), "head")
    finally:
        if previous is None:
            os.environ.pop("OPENCRITIQUE_DATABASE_URL", None)
        else:
            os.environ["OPENCRITIQUE_DATABASE_URL"] = previous
