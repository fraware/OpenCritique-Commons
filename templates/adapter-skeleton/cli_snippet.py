"""CLI snippet for a third adapter.

Paste into ``opencritique_adapters.cli`` (and import ``convert_example_benchmark``)
after renaming Example -> your slug. Do not register until convert is tested.
"""

from __future__ import annotations

from pathlib import Path

import typer

# from .adapter import convert_example_benchmark


def register_example_command(app: typer.Typer) -> None:
    @app.command("example")
    def convert_example(
        manifest: Path = typer.Option(..., exists=True, dir_okay=False),
        benchmark_root: Path = typer.Option(..., exists=True, file_okay=False),
        mapping: Path = typer.Option(..., exists=True, dir_okay=False),
        output: Path = typer.Option(Path("example-submission.json")),
    ) -> None:
        _ = (manifest, benchmark_root, mapping, output)
        raise NotImplementedError(
            "Wire convert_example_benchmark after copying the skeleton into "
            "src/opencritique_adapters/ and adding sample fixtures."
        )
        # import json
        # submission = convert_example_benchmark(
        #     benchmark_manifest_path=manifest,
        #     benchmark_root=benchmark_root,
        #     map_path=mapping,
        # )
        # output.parent.mkdir(parents=True, exist_ok=True)
        # output.write_text(
        #     json.dumps(submission.model_dump(mode="json"), indent=2, sort_keys=True),
        #     encoding="utf-8",
        # )
        # typer.echo(str(output))
