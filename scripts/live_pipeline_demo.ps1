# Live Coarse operator demo (calls paid APIs when a real key is present).
# Default CI must not run this script.
param(
  [string]$OutDir = "runs/pipeline/coarse-sample-econ-01",
  [string]$Manuscript = "corpus/samples/sample-econ-01/manuscript.md",
  [string]$Model = "openai/gpt-4o"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $pair = $_ -split '=', 2
    if ($pair.Length -eq 2) {
      $name = $pair[0].Trim()
      $value = $pair[1].Trim().Trim('"').Trim("'")
      if (-not [string]::IsNullOrWhiteSpace($name)) {
        Set-Item -Path "Env:$name" -Value $value
      }
    }
  }
}

if (-not $env:OPENCRITIQUE_BYOK_API_KEY -and -not $env:OPENAI_API_KEY) {
  Write-Error "FAIL: set OPENCRITIQUE_BYOK_API_KEY or OPENAI_API_KEY before live demo."
  exit 1
}

Write-Host "============================================================"
Write-Host " OpenCritique live Coarse demo"
Write-Host " Private live / sample gold != production authenticity"
Write-Host " performance_claims_authorized=false (NOT AUTHORIZED)"
Write-Host "============================================================"

opencritique runners pipeline coarse `
  --manuscript $Manuscript `
  --out-dir $OutDir `
  --model $Model
if ($LASTEXITCODE -ne 0) {
  Write-Error "FAIL: live pipeline exited with code $LASTEXITCODE"
  exit $LASTEXITCODE
}

$Required = @(
  "coarse-review.json",
  "coarse-review.md",
  "provenance.json"
)
$Missing = @()
foreach ($name in $Required) {
  $path = Join-Path $OutDir $name
  if (-not (Test-Path $path)) { $Missing += $name }
}
if ($Missing.Count -gt 0) {
  Write-Error ("FAIL: missing required artifacts: " + ($Missing -join ", "))
  exit 2
}

$Review = Get-Content (Join-Path $OutDir "coarse-review.json") -Raw
if ($Review -match '"performance_claims_authorized"\s*:\s*true') {
  Write-Error "FAIL: performance_claims_authorized must remain false"
  exit 3
}

Write-Host ""
Write-Host "Artifact checklist (PASS):"
foreach ($name in $Required) {
  Write-Host "  OK $name"
}
if (Test-Path (Join-Path $OutDir "scorecard.json")) {
  Write-Host "  OK scorecard.json (gold path)"
}
if (Test-Path (Join-Path $OutDir "handoff.json")) {
  Write-Host "  OK handoff.json (registry path)"
}
Write-Host "Artifacts under: $OutDir"
Write-Host "Studio handoff:"
Write-Host "  opencritique-registry import-live-run --from $OutDir --manuscript $Manuscript"
Write-Host "  opencritique-registry serve"
Write-Host "Banner: private live != production MANIFEST ready != scientific claims."
exit 0
