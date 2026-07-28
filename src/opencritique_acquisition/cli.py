from __future__ import annotations

from pathlib import Path

import typer

from .models import AcquisitionLedger

app = typer.Typer(no_args_is_help=True)


@app.command("validate")
def validate(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    ledger = AcquisitionLedger.model_validate_json(path.read_text(encoding="utf-8"))
    typer.echo(
        f"PASS {len(ledger.sources)} source(s); "
        f"{ledger.total_imported_cases} imported case(s)"
    )
