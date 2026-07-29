"""Import-reference CLI works on maintainer-owned sample REF cases."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from opencritique_registry.cli import app

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "cases" / "reference"


def test_import_reference_sample_paths(tmp_path: Path) -> None:
    db = tmp_path / "ref.db"
    artifacts = tmp_path / "artifacts"
    runner = CliRunner()
    boot = runner.invoke(
        app,
        [
            "bootstrap-admin",
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--actor-id",
            "opencritique-admin",
        ],
    )
    assert boot.exit_code == 0, boot.stdout + boot.stderr
    result = runner.invoke(
        app,
        [
            "import-reference",
            str(REF),
            "--project-root",
            str(ROOT),
            "--database-url",
            f"sqlite:///{db.as_posix()}",
            "--artifact-root",
            str(artifacts),
            "--actor-id",
            "opencritique-admin",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Imported" in result.stdout
    assert (REF / "REF-01" / "case.json").is_file()
