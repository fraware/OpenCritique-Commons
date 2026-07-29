#!/usr/bin/env python3
"""Validate (and optionally stage) production adapter export packages.

Refuses incomplete or unauthorized packages with typed exit codes. Does not
fabricate Coarse / OpenReviewer production exports.

Examples:
  python scripts/ingest_production_adapter_exports.py validate \\
      --adapter coarse --package /path/to/cleared-exports

  python scripts/ingest_production_adapter_exports.py validate-tree --adapter coarse

  python scripts/ingest_production_adapter_exports.py stage \\
      --adapter openreviewer --package /path/to/cleared-exports --dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opencritique_adapters.production_errors import (  # noqa: E402
    ProductionIntakeError,
)
from opencritique_adapters.production_fixtures import (  # noqa: E402
    COARSE_PRODUCTION,
    OPENREVIEWER_PRODUCTION,
)
from opencritique_adapters.production_intake import (  # noqa: E402
    format_intake_error,
    stage_validated_package,
    validate_fixture_tree,
    validate_production_package,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)

_TREE = {
    "coarse": COARSE_PRODUCTION,
    "openreviewer": OPENREVIEWER_PRODUCTION,
}


def _fail(exc: ProductionIntakeError) -> None:
    typer.secho(format_intake_error(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=2)


@app.command("validate")
def validate_cmd(
    package: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    adapter: str = typer.Option(..., help="coarse | openreviewer"),
    require_ready: bool = typer.Option(False, help="Fail unless status=ready"),
) -> None:
    """Validate a directory of real exports against the production intake contract."""
    try:
        manifest = validate_production_package(
            package,
            expected_adapter=adapter,
            require_ready=require_ready,
        )
    except ProductionIntakeError as exc:
        _fail(exc)
    typer.echo(
        f"PASS adapter={manifest.adapter} status={manifest.status.value} "
        f"artifacts={len(manifest.artifacts)} claims_authorized="
        f"{manifest.performance_claims_authorized}"
    )


@app.command("validate-tree")
def validate_tree_cmd(
    adapter: str = typer.Option(..., help="coarse | openreviewer"),
) -> None:
    """Validate the in-repo production fixture tree for an adapter."""
    root = _TREE.get(adapter)
    if root is None:
        typer.secho(f"unknown adapter: {adapter}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    try:
        result = validate_fixture_tree(adapter, root)
    except ProductionIntakeError as exc:
        _fail(exc)
    typer.echo(f"PASS {result.message}")


@app.command("stage")
def stage_cmd(
    package: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    adapter: str = typer.Option(..., help="coarse | openreviewer"),
    destination: Path | None = typer.Option(
        None,
        help="Defaults to fixtures/<adapter>/production/",
    ),
    dry_run: bool = typer.Option(True, help="Default dry-run; pass --no-dry-run to copy"),
) -> None:
    """Stage a validated ready package into the production fixture tree."""
    dest = destination or _TREE[adapter]
    try:
        result = stage_validated_package(
            package,
            dest,
            expected_adapter=adapter,
            dry_run=dry_run,
        )
    except ProductionIntakeError as exc:
        _fail(exc)
    typer.echo(result.message)


if __name__ == "__main__":
    app()
