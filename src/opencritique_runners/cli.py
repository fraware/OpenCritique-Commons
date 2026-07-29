"""CLI for optional live upstream runners."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from .coarse import DEFAULT_COARSE_MODEL, run_coarse_review, write_coarse_export
from .env import format_live_runner_error, load_operator_env, require_byok_api_key
from .openreviewer import (
    import_openreviewer_export,
    run_openreviewer_review,
    write_openreviewer_live_export,
)
from .pipeline import CLAIMS_BANNER, run_coarse_pipeline
from .provenance import COARSE_LIVE_COMMIT_PIN, COARSE_LIVE_PACKAGE_PIN

app = typer.Typer(
    no_args_is_help=True,
    help="Optional live upstream runners (Coarse / OpenReviewer). Claims stay locked.",
)
pipeline_app = typer.Typer(
    no_args_is_help=True, help="Live -> convert -> eval orchestrators."
)
app.add_typer(pipeline_app, name="pipeline")


def _fail(exc: BaseException) -> NoReturn:
    typer.secho(format_live_runner_error(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(code=2) from exc


@app.callback()
def _runners_callback() -> None:
    load_operator_env()


@app.command("coarse")
def coarse_cmd(
    manuscript: Path = typer.Option(
        ...,
        exists=True,
        dir_okay=False,
        help="Manuscript path (PDF/MD/TeX/… supported by Coarse).",
    ),
    output: Path = typer.Option(
        Path("runs/coarse/review.json"),
        help="Output CoarseReview JSON path (must not be under fixtures/*/production/).",
    ),
    model: str = typer.Option(DEFAULT_COARSE_MODEL, help="litellm-compatible model id."),
    markdown_output: Path | None = typer.Option(
        None,
        help="Optional path for rendered markdown review.",
    ),
    skip_cost_gate: bool = typer.Option(
        True,
        help="Skip Coarse interactive cost confirmation (default for non-interactive CLI).",
    ),
) -> None:
    """Run upstream Coarse ``review_paper`` and write a CoarseReview JSON export."""
    try:
        require_byok_api_key()
        review, provenance, markdown = run_coarse_review(
            manuscript=manuscript,
            model=model,
            skip_cost_gate=skip_cost_gate,
            load_env=False,
        )
        md_path = markdown_output
        if md_path is None and output.suffix.lower() == ".json":
            md_path = output.with_suffix(".md")
        path = write_coarse_export(
            review,
            output,
            markdown=markdown,
            markdown_output=md_path,
        )
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        _fail(exc)

    typer.echo(str(path))
    typer.echo(
        f"provenance: upstream={provenance.upstream} commit={COARSE_LIVE_COMMIT_PIN} "
        f"package={COARSE_LIVE_PACKAGE_PIN} model={provenance.model_id} "
        f"execution_mode=byok evidence_class=private_live"
    )
    typer.echo(CLAIMS_BANNER)
    typer.echo(
        "Next: opencritique-registry import-live-run --from "
        f"{path} --manuscript {manuscript}"
    )


@pipeline_app.command("coarse")
def pipeline_coarse_cmd(
    manuscript: Path = typer.Option(..., exists=True, dir_okay=False),
    out_dir: Path = typer.Option(Path("runs/pipeline/coarse")),
    model: str = typer.Option(DEFAULT_COARSE_MODEL),
    benchmark_root: Path | None = typer.Option(
        None,
        exists=True,
        file_okay=False,
        help="Benchmark root with gold concerns; auto-resolved for known samples.",
    ),
    case_id: str | None = typer.Option(None, help="Override gold case_id."),
    case_version: str | None = typer.Option(None, help="Override gold case_version."),
    register: bool = typer.Option(
        False,
        "--register",
        help="After export, register the live case and seed Studio tasks "
        "(evidence_class=private_live).",
    ),
    database_url: str | None = typer.Option(
        None, help="Registry database URL when using --register."
    ),
    artifact_root: Path | None = typer.Option(
        None, help="Artifact root when using --register."
    ),
) -> None:
    """Live Coarse -> convert -> evaluate/scorecard when gold exists; else registry handoff."""
    try:
        require_byok_api_key()
        result = run_coarse_pipeline(
            manuscript=manuscript,
            out_dir=out_dir,
            model=model,
            benchmark_root=benchmark_root,
            case_id=case_id,
            case_version=case_version,
            load_env=False,
        )
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        _fail(exc)

    typer.echo(f"review: {result.review_path}")
    if result.submission_path is not None:
        typer.echo(f"submission: {result.submission_path}")
    if result.evaluation_path is not None:
        typer.echo(f"evaluation: {result.evaluation_path}")
    if result.scorecard_json is not None:
        typer.echo(f"scorecard: {result.scorecard_json}")
    if result.scorecard_html is not None:
        typer.echo(f"scorecard_html: {result.scorecard_html}")
    if result.handoff is not None:
        typer.echo(result.handoff)
    else:
        typer.echo(CLAIMS_BANNER)
    typer.echo("claim authorization: NOT AUTHORIZED")

    if register:
        from opencritique_registry.config import RegistrySettings
        from opencritique_registry.live_import import import_live_run

        cfg = RegistrySettings.from_env().with_overrides(
            database_url=database_url,
            artifact_root=artifact_root,
        )
        try:
            imported = import_live_run(
                from_path=result.review_path,
                manuscript=manuscript,
                database_url=cfg.database_url,
                artifact_root=cfg.artifact_root,
                max_artifact_bytes=cfg.max_artifact_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        typer.echo("")
        typer.echo(
            f"Registered live case {imported.case_id}@{imported.case_version} "
            f"(evidence_class={imported.evidence_class}; export={imported.export_kind})."
        )
        typer.echo(f"Seeded adjudication task slots: {imported.seeded_tasks}")
        typer.echo("Administrator token (shown once):")
        typer.echo(imported.admin_token)
        typer.echo("Adjudicator token (shown once):")
        typer.echo(imported.adjudicator_token)
        typer.echo(f"Studio URL: {imported.studio_url}")
        typer.echo("Next steps:")
        typer.echo("  1. Start the registry if needed: opencritique-registry serve")
        typer.echo(f"  2. Open {imported.studio_url}")
        typer.echo("  3. Paste the adjudicator token and click Connect")
        typer.echo("  4. Click Claim adjudication and submit")
        typer.echo(CLAIMS_BANNER)
        typer.echo(
            "Refuse production MANIFEST promotion from runs/; "
            "performance_claims_authorized=false."
        )


@app.command("openreviewer")
def openreviewer_cmd(
    manuscript: Path | None = typer.Option(None, exists=True, dir_okay=False),
    from_export: Path | None = typer.Option(
        None,
        "--from-export",
        exists=True,
        dir_okay=False,
        help="Import/normalize a HF Space or local OpenReviewer export (no GPU).",
    ),
    output: Path = typer.Option(
        Path("runs/openreviewer/review.json"),
        "--output",
        "-o",
        help="Output path (must not be under fixtures/*/production/).",
    ),
    venue_template: str = typer.Option("ICLR2025"),
    title: str | None = typer.Option(None),
    allow_cpu: bool = typer.Option(
        False,
        help="Allow HF local without CUDA (explicit override; not recommended).",
    ),
    register: bool = typer.Option(
        False,
        "--register",
        help="After import/export, register the live case and seed Studio tasks.",
    ),
    register_manuscript: Path | None = typer.Option(
        None,
        "--register-manuscript",
        exists=True,
        dir_okay=False,
        help="Manuscript path required when using --register with --from-export.",
    ),
    database_url: str | None = typer.Option(None, help="Registry DB URL with --register."),
    artifact_root: Path | None = typer.Option(
        None, help="Artifact root when using --register."
    ),
) -> None:
    """Import an OpenReviewer export, or run HF local when ``[live-openreviewer]`` is installed.

    OpenAI/BYOK keys do not run OpenReviewer. Prefer --from-export without a GPU.
    """
    from .hf_local import OpenReviewerHFUnavailableError
    from .paths import assert_not_production_fixtures_path

    load_operator_env()
    try:
        assert_not_production_fixtures_path(output)
        if from_export is not None and manuscript is not None:
            raise typer.BadParameter("use either --from-export or --manuscript, not both")
        if from_export is not None:
            export = import_openreviewer_export(
                from_export,
                venue_template=venue_template,
                title=title,
            )
        elif manuscript is not None:
            export = run_openreviewer_review(
                manuscript=manuscript,
                venue_template=venue_template,
                allow_cpu=allow_cpu,
            )
            if title:
                export = export.model_copy(update={"title": title})
        else:
            raise typer.BadParameter("Provide --manuscript or --from-export")
        path = write_openreviewer_live_export(export, output)
    except OpenReviewerHFUnavailableError as exc:
        typer.secho(format_live_runner_error(exc), fg=typer.colors.RED, err=True)
        typer.secho(
            "Import mode (no GPU): "
            "`opencritique runners openreviewer --from-export path.json`",
            err=True,
        )
        typer.secho(
            "Blunt: an OpenAI/BYOK key does not run OpenReviewer "
            "(Llama-OpenReviewer-8B / Space export).",
            err=True,
        )
        raise typer.Exit(code=2) from exc
    except typer.Exit:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        _fail(exc)

    typer.echo(str(path))
    typer.echo(
        f"provenance: evidence_class=private_live "
        f"execution_mode={export.opencritique_provenance.execution_mode} "
        f"claims_authorized={export.opencritique_provenance.performance_claims_authorized}"
    )
    typer.echo(CLAIMS_BANNER)
    typer.echo("NOT AUTHORIZED: performance_claims_authorized=false (private live)")
    typer.echo(
        "Blunt: OpenAI/BYOK != OpenReviewer. Prefer Space --from-export; "
        "see docs/openreviewer-space-import.md."
    )

    if register:
        ms = register_manuscript or manuscript
        if ms is None:
            raise typer.BadParameter(
                "--register with --from-export requires --register-manuscript"
            )
        from opencritique_registry.config import RegistrySettings
        from opencritique_registry.live_import import import_live_run

        cfg = RegistrySettings.from_env().with_overrides(
            database_url=database_url,
            artifact_root=artifact_root,
        )
        try:
            imported = import_live_run(
                from_path=path,
                manuscript=ms,
                database_url=cfg.database_url,
                artifact_root=cfg.artifact_root,
                max_artifact_bytes=cfg.max_artifact_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        typer.echo("")
        typer.echo(
            f"Registered live case {imported.case_id}@{imported.case_version} "
            f"(evidence_class={imported.evidence_class})."
        )
        typer.echo(f"Seeded adjudication task slots: {imported.seeded_tasks}")
        typer.echo("Adjudicator token (shown once):")
        typer.echo(imported.adjudicator_token)
        typer.echo(f"Studio URL: {imported.studio_url}")
        typer.echo(CLAIMS_BANNER)
