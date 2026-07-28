from __future__ import annotations

import json
from pathlib import Path

import typer

from opencritique_acquisition.cli import app as acquisition_app
from opencritique_adapters.cli import app as adapters_app
from opencritique_evaluation.cli import app as evaluation_app
from opencritique_registry.cli import app as registry_app

from .models import CaseBundle
from .registry import export_json_schemas, list_schemas, load_extended_registry

app = typer.Typer(no_args_is_help=True)
conformance_app = typer.Typer(no_args_is_help=True)
schema_app = typer.Typer(no_args_is_help=True)
app.add_typer(conformance_app, name="conformance")
app.add_typer(schema_app, name="schema")
app.add_typer(registry_app, name="registry")
app.add_typer(evaluation_app, name="evaluation")
app.add_typer(adapters_app, name="adapters")
app.add_typer(acquisition_app, name="acquisition")


def load_case(path: Path) -> CaseBundle:
    return CaseBundle.model_validate_json(path.read_text(encoding="utf-8"))


@conformance_app.command("case")
def validate_case(path: Path) -> None:
    case = load_case(path)
    typer.echo(f"PASS {case.case_id} ({len(case.concerns)} concern(s))")


@conformance_app.command("run")
def run_directory(path: Path) -> None:
    files = sorted(path.glob("REF-*/case.json")) if path.is_dir() else [path]
    if not files:
        raise typer.BadParameter(f"No case files found under {path}")
    failures = 0
    for file in files:
        try:
            case = load_case(file)
            typer.echo(f"PASS {case.case_id}: {file}")
        except Exception as exc:  # CLI should report all failures in one run.
            failures += 1
            typer.echo(f"FAIL {file}: {exc}", err=True)
    typer.echo(f"\n{len(files) - failures}/{len(files)} cases passed")
    if failures:
        raise typer.Exit(code=1)


@schema_app.command("export")
def export_schemas(path: Path = typer.Argument(Path("schemas"))) -> None:
    load_extended_registry()
    path.mkdir(parents=True, exist_ok=True)
    inventory = {
        "freeze_release": "0.5.0a1",
        "schemas": [
            {
                "schema_id": entry.schema_id,
                "schema_version": entry.schema_version,
                "model": entry.model.__name__,
                "persistent": entry.persistent,
                "description": entry.description,
            }
            for entry in list_schemas()
        ],
    }
    inventory_path = path / "inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    typer.echo(str(inventory_path))
    for name, schema in export_json_schemas().items():
        target = path / f"{name}.schema.json"
        target.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        typer.echo(str(target))


@schema_app.command("list")
def list_registered_schemas() -> None:
    load_extended_registry()
    for entry in list_schemas():
        typer.echo(f"{entry.schema_id}@{entry.schema_version}\t{entry.model.__name__}")


if __name__ == "__main__":
    app()
