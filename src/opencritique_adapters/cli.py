from __future__ import annotations

import json
from pathlib import Path

import typer

from .coarse import convert_coarse_benchmark
from .coarse_loss import build_conversion_loss_report, write_report_artifacts
from .contract import COARSE_UPSTREAM_CONTRACT_VERSION
from .openreviewer import convert_openreviewer_benchmark
from .openreviewer_loss import write_cross_adapter_report

app = typer.Typer(no_args_is_help=True)


@app.command("coarse")
def convert_coarse(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    benchmark_root: Path = typer.Option(..., exists=True, file_okay=False),
    mapping: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("coarse-submission.json")),
) -> None:
    submission = convert_coarse_benchmark(
        benchmark_manifest_path=manifest,
        benchmark_root=benchmark_root,
        map_path=mapping,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(submission.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    typer.echo(str(output))


@app.command("coarse-loss-report")
def coarse_loss_report(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    benchmark_root: Path = typer.Option(..., exists=True, file_okay=False),
    mapping: Path = typer.Option(..., exists=True, dir_okay=False),
    extracted_texts: Path | None = typer.Option(None, exists=True, dir_okay=False),
    docs_dir: Path = typer.Option(Path("docs")),
) -> None:
    texts = None
    if extracted_texts is not None:
        texts = json.loads(extracted_texts.read_text(encoding="utf-8"))
    report = build_conversion_loss_report(
        benchmark_manifest_path=manifest,
        benchmark_root=benchmark_root,
        map_path=mapping,
        extracted_texts=texts,
    )
    paths = write_report_artifacts(report, docs_dir)
    typer.echo(
        f"{COARSE_UPSTREAM_CONTRACT_VERSION}: wrote {paths['markdown']} and {paths['json']}"
    )


@app.command("openreviewer")
def convert_openreviewer(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    benchmark_root: Path = typer.Option(..., exists=True, file_okay=False),
    mapping: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("openreviewer-submission.json")),
) -> None:
    submission = convert_openreviewer_benchmark(
        benchmark_manifest_path=manifest,
        benchmark_root=benchmark_root,
        map_path=mapping,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(submission.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    typer.echo(str(output))


@app.command("cross-adapter-report")
def cross_adapter_report(docs_dir: Path = typer.Option(Path("docs"))) -> None:
    paths = write_cross_adapter_report(docs_dir)
    typer.echo(f"wrote {paths['markdown']} and {paths['json']}")
