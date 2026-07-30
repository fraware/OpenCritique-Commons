# Offline Track A demo: synthetic Coarse convert -> evaluate -> scorecard.
# Mirrors the README golden path. No paid APIs. Safe for local smoke; not default CI.
param(
  [string]$OutDir = "runs/demo/adapter-path"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$OpenCritique = $env:OPENCRITIQUE
if (-not $OpenCritique) {
  $cmd = Get-Command opencritique -ErrorAction SilentlyContinue
  if ($cmd) {
    $OpenCritique = $cmd.Source
  }
}
if (-not $OpenCritique) {
  Write-Error "FAIL: opencritique not on PATH; run: python -m pip install -e '.[dev]'"
  exit 1
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "============================================================"
Write-Host " OpenCritique offline adapter-path demo"
Write-Host " Sample fixtures != production authenticity"
Write-Host " performance_claims_authorized=false (NOT AUTHORIZED)"
Write-Host "============================================================"

$Submission = Join-Path $OutDir "coarse-submission.json"
$EvalResult = Join-Path $OutDir "evaluation-result.json"
$Scorecard = Join-Path $OutDir "scorecard.json"

& $OpenCritique adapters coarse `
  --manifest benchmarks/coarse-synth-v0.1/manifest.json `
  --benchmark-root benchmarks/coarse-synth-v0.1 `
  --mapping fixtures/coarse/maps/synth-map.json `
  --output $Submission
if ($LASTEXITCODE -ne 0) {
  Write-Error "FAIL: adapters coarse exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}

& $OpenCritique evaluation run `
  --manifest benchmarks/coarse-synth-v0.1/manifest.json `
  --benchmark-root benchmarks/coarse-synth-v0.1 `
  --submission $Submission `
  --output $EvalResult
if ($LASTEXITCODE -ne 0) {
  Write-Error "FAIL: evaluation run exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}

& $OpenCritique evaluation scorecard `
  --result $EvalResult `
  --json-output $Scorecard
if ($LASTEXITCODE -ne 0) {
  Write-Error "FAIL: evaluation scorecard exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}

foreach ($path in @($Submission, $EvalResult, $Scorecard)) {
  if (-not (Test-Path $path)) {
    Write-Error "FAIL: missing artifact: $path"
    exit 2
  }
}

$EvalText = Get-Content $EvalResult -Raw
$ScoreText = Get-Content $Scorecard -Raw
if (
  ($EvalText -match '"performance_claim_authorized"\s*:\s*true') -or
  ($ScoreText -match '"performance_claims_authorized"\s*:\s*true') -or
  ($ScoreText -match '"performance_claim_authorized"\s*:\s*true')
) {
  Write-Error "FAIL: performance claims must remain unauthorized"
  exit 3
}

Write-Host ""
Write-Host "Artifact checklist (PASS):"
Write-Host "  OK coarse-submission.json"
Write-Host "  OK evaluation-result.json"
Write-Host "  OK scorecard.json"
Write-Host "Artifacts under: $OutDir"
Write-Host ""
Write-Host "Claim status: NOT AUTHORIZED"
Write-Host "Banner: sample demo != production MANIFEST ready != scientific claims."
Write-Host "Next (optional Studio): see docs/examples/studio-walkthrough.md"
exit 0
