"""CLI for deterministic evaluation, scorecards, sensitivity, and signing."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .engine import evaluate, load_manifest
from .models import EvaluationResult, EvaluationSubmission, PublicScorecard, SignedScorecardEnvelope
from .novel import build_novel_queue
from .scorecard import build_scorecard, write_html, write_json
from .sensitivity import analyze_sensitivity
from .signing import generate_keypair, sign_scorecard

app = typer.Typer(no_args_is_help=True)


def _write_model(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dump = getattr(payload, "model_dump", None)
    if callable(dump):
        text = json.dumps(dump(mode="json"), indent=2, sort_keys=True)
    else:
        text = json.dumps(payload, indent=2, sort_keys=True)
    path.write_text(text, encoding="utf-8")


@app.command("run")
def run_evaluation(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    benchmark_root: Path = typer.Option(..., exists=True, file_okay=False),
    submission: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("evaluation-result.json")),
) -> None:
    benchmark = load_manifest(manifest)
    payload = EvaluationSubmission.model_validate_json(submission.read_text(encoding="utf-8"))
    result = evaluate(
        benchmark=benchmark,
        benchmark_root=benchmark_root,
        submission=payload,
    )
    _write_model(output, result)
    typer.echo(str(output))
    typer.echo(
        f"claim authorization: "
        f"{'AUTHORIZED' if result.performance_claim_authorized else 'NOT AUTHORIZED'} "
        f"(claim_scope={result.claim_authorization.claim_scope.value})"
    )


@app.command("scorecard")
def make_scorecard(
    result: Path = typer.Option(..., exists=True, dir_okay=False),
    json_output: Path = typer.Option(Path("scorecard.json")),
    html_output: Path | None = typer.Option(None),
) -> None:
    evaluation = EvaluationResult.model_validate_json(result.read_text(encoding="utf-8"))
    scorecard = build_scorecard(evaluation)
    write_json(scorecard, json_output)
    typer.echo(str(json_output))
    if html_output is not None:
        write_html(scorecard, html_output)
        typer.echo(str(html_output))


@app.command("sensitivity")
def sensitivity(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    benchmark_root: Path = typer.Option(..., exists=True, file_okay=False),
    submission: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("matcher-sensitivity.json")),
) -> None:
    benchmark = load_manifest(manifest)
    payload = EvaluationSubmission.model_validate_json(submission.read_text(encoding="utf-8"))
    report = analyze_sensitivity(
        benchmark=benchmark,
        benchmark_root=benchmark_root,
        submission=payload,
    )
    _write_model(output, report)
    typer.echo(str(output))


@app.command("novel-queue")
def novel_queue(
    result: Path = typer.Option(..., exists=True, dir_okay=False),
    submission: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("novel-concern-queue.json")),
) -> None:
    evaluation = EvaluationResult.model_validate_json(result.read_text(encoding="utf-8"))
    payload = EvaluationSubmission.model_validate_json(submission.read_text(encoding="utf-8"))
    queue = build_novel_queue(evaluation, payload)
    _write_model(output, queue)
    typer.echo(f"{output} ({len(queue.candidates)} candidate(s))")


@app.command("keygen")
def keygen(
    private_key: Path = typer.Option(...),
    public_key: Path = typer.Option(...),
) -> None:
    key_id = generate_keypair(private_key, public_key)
    typer.echo(key_id)


@app.command("sign-scorecard")
def sign_scorecard_cmd(
    scorecard: Path = typer.Option(..., exists=True, dir_okay=False),
    private_key: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("scorecard.signed.json")),
) -> None:
    payload = PublicScorecard.model_validate_json(scorecard.read_text(encoding="utf-8"))
    envelope = sign_scorecard(payload, private_key)
    _write_model(output, envelope)
    typer.echo(str(output))


@app.command("verify-scorecard")
def verify_scorecard_cmd(
    envelope: Path = typer.Option(..., exists=True, dir_okay=False),
    trusted_public_key: Path | None = typer.Option(None, exists=True, dir_okay=False),
    trust_store: Path | None = typer.Option(None, exists=True, dir_okay=False),
    policy_mode: str = typer.Option("production"),
) -> None:
    from .signing import verify_envelope_detailed
    from .trust import TrustPolicyMode, load_trust_store

    payload = SignedScorecardEnvelope.model_validate_json(envelope.read_text(encoding="utf-8"))
    mode = TrustPolicyMode(policy_mode)
    store = load_trust_store(trust_store) if trust_store is not None else None
    result = verify_envelope_detailed(
        payload,
        trust_store=store,
        trusted_public_key_path=trusted_public_key,
        policy_mode=mode,
    )
    if not result.ok:
        typer.echo(f"FAIL {result.reason}: {result.detail}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"PASS signature verification ({result.policy_mode.value})")
