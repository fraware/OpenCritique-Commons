from __future__ import annotations

from pathlib import Path

import typer

from .approved_profile import (
    ApprovedProfileError,
    import_approved_profile,
    load_approved_profile,
    reject_outside_approved_profile,
)
from .models import (
    AcquisitionLedger,
    cancel_source,
    import_source,
    load_ledger,
    save_ledger,
    withdraw_source,
)

app = typer.Typer(no_args_is_help=True)
REPO_ROOT = Path(__file__).resolve().parents[2]


@app.command("validate")
def validate(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    ledger = AcquisitionLedger.model_validate_json(path.read_text(encoding="utf-8"))
    typer.echo(
        f"PASS {len(ledger.sources)} source(s); "
        f"{ledger.total_imported_cases} imported case(s)"
    )


@app.command("import-source")
def import_source_cmd(
    ledger_path: Path = typer.Argument(..., dir_okay=False),
    source_id: str = typer.Option(...),
    title: str = typer.Option(...),
    paper_url: str = typer.Option(...),
    declared_license: str = typer.Option(...),
    license_evidence_url: str = typer.Option(...),
    imported_case_count: int = typer.Option(..., min=1),
    grant_authority: str = typer.Option(...),
    grant_scope: str = typer.Option(...),
    note: list[str] = typer.Option([], "--note"),
) -> None:
    """Import an authorized source into the acquisition ledger (grant-checked)."""
    ledger = (
        load_ledger(ledger_path)
        if ledger_path.is_file()
        else AcquisitionLedger(sources=[], total_imported_cases=0)
    )
    updated = import_source(
        ledger,
        source_id=source_id,
        title=title,
        paper_url=paper_url,
        declared_license=declared_license,
        license_evidence_url=license_evidence_url,
        imported_case_count=imported_case_count,
        grant_authority=grant_authority,
        grant_scope=grant_scope,
        notes=list(note),
    )
    if updated.performance_claims_authorized:
        raise typer.BadParameter("refusing to persist ledger with performance claims authorized")
    save_ledger(ledger_path, updated)
    typer.echo(f"IMPORTED {source_id} ({imported_case_count} case(s))")


@app.command("withdraw")
def withdraw_cmd(
    ledger_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    source_id: str = typer.Option(...),
    reason: str = typer.Option(...),
) -> None:
    """Real withdrawal path: zero imported cases and revoke evaluation use."""
    ledger = load_ledger(ledger_path)
    updated = withdraw_source(ledger, source_id=source_id, reason=reason)
    save_ledger(ledger_path, updated)
    typer.echo(f"WITHDRAWN {source_id}")


@app.command("cancel")
def cancel_cmd(
    ledger_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    source_id: str = typer.Option(...),
    reason: str = typer.Option(...),
) -> None:
    """Cancel an in-flight or imported source (append-only status change)."""
    ledger = load_ledger(ledger_path)
    updated = cancel_source(ledger, source_id=source_id, reason=reason)
    save_ledger(ledger_path, updated)
    typer.echo(f"CANCELLED {source_id}")


@app.command("validate-approved-profile")
def validate_approved_profile_cmd(
    profile_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    repo_root: Path = typer.Option(REPO_ROOT, file_okay=False),
) -> None:
    """Validate an approved-profile JSON without writing the ledger."""
    try:
        profile = load_approved_profile(profile_path)
        reject_outside_approved_profile(profile, repo_root)
    except ApprovedProfileError as exc:
        typer.secho(f"{exc.code}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(
        f"PASS profile_kind={profile.profile_kind.value} source_id={profile.source_id} "
        f"case_id={profile.case_id}"
    )


@app.command("import-approved-profile")
def import_approved_profile_cmd(
    profile_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    ledger_path: Path = typer.Option(
        REPO_ROOT / "corpus" / "acquisition-ledger.json",
        dir_okay=False,
    ),
    repo_root: Path = typer.Option(REPO_ROOT, file_okay=False),
    dry_run: bool = typer.Option(True, help="Default dry-run; pass --no-dry-run to persist"),
) -> None:
    """Import one rights-cleared case via the approved profile (post-#7 path)."""
    try:
        profile = load_approved_profile(profile_path)
        updated = import_approved_profile(
            profile,
            ledger_path=ledger_path,
            repo_root=repo_root,
            dry_run=dry_run,
        )
    except ApprovedProfileError as exc:
        typer.secho(f"{exc.code}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    action = "DRY-RUN" if dry_run else "IMPORTED"
    typer.echo(
        f"{action} {profile.source_id} ({profile.profile_kind.value}); "
        f"ledger imported cases={updated.total_imported_cases}; "
        f"claims_authorized={updated.performance_claims_authorized}"
    )
