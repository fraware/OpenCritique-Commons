#!/usr/bin/env bash
# Offline Track A demo: synthetic Coarse convert -> evaluate -> scorecard.
# Mirrors the README golden path. No paid APIs. Safe for local smoke; not default CI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

_win_to_unix() {
  # Convert C:\path or C:/path to /mnt/c/path when running under WSL.
  local p="$1"
  p="${p//\\//}"
  if [[ "$p" =~ ^([A-Za-z]):(.*)$ ]]; then
    local drive
    drive="$(echo "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
    echo "/mnt/${drive}${BASH_REMATCH[2]}"
    return 0
  fi
  echo "$p"
}

_python_has_package() {
  local py="$1"
  [[ -n "$py" ]] || return 1
  "$py" -c 'import opencritique_schema' >/dev/null 2>&1
}

# Resolve a Python that has the editable/install package, then invoke:
#   $PY -m opencritique_schema.cli ...
# Falls back to a bare opencritique on PATH when present.
PY="${OPENCRITIQUE_PYTHON:-}"
OPENCRITIQUE_CMD=()

if [[ -z "$PY" ]]; then
  for candidate in python python3; do
    if command -v "$candidate" >/dev/null 2>&1 && _python_has_package "$candidate"; then
      PY="$(command -v "$candidate")"
      break
    fi
  done
fi

if [[ -z "$PY" ]] && command -v where.exe >/dev/null 2>&1; then
  while IFS= read -r winpy || [[ -n "$winpy" ]]; do
    winpy="${winpy%$'\r'}"
    [[ -z "$winpy" ]] && continue
    unixpy="$(_win_to_unix "$winpy")"
    if [[ -x "$unixpy" ]] && _python_has_package "$unixpy"; then
      PY="$unixpy"
      break
    fi
  done < <(where.exe python 2>/dev/null || true)
fi

if [[ -n "$PY" ]]; then
  OPENCRITIQUE_CMD=("$PY" -m opencritique_schema.cli)
elif command -v opencritique >/dev/null 2>&1; then
  OPENCRITIQUE_CMD=(opencritique)
else
  echo "FAIL: could not find opencritique or a Python with opencritique_schema installed." >&2
  echo "      run: python -m pip install -e '.[dev]'" >&2
  exit 1
fi

OUT_DIR="${OUT_DIR:-runs/demo/adapter-path}"
mkdir -p "$OUT_DIR"

echo "============================================================"
echo " OpenCritique offline adapter-path demo"
echo " Sample fixtures != production authenticity"
echo " performance_claims_authorized=false (NOT AUTHORIZED)"
echo "============================================================"

SUBMISSION="$OUT_DIR/coarse-submission.json"
EVAL_RESULT="$OUT_DIR/evaluation-result.json"
SCORECARD="$OUT_DIR/scorecard.json"

"${OPENCRITIQUE_CMD[@]}" adapters coarse \
  --manifest benchmarks/coarse-synth-v0.1/manifest.json \
  --benchmark-root benchmarks/coarse-synth-v0.1 \
  --mapping fixtures/coarse/maps/synth-map.json \
  --output "$SUBMISSION"

"${OPENCRITIQUE_CMD[@]}" evaluation run \
  --manifest benchmarks/coarse-synth-v0.1/manifest.json \
  --benchmark-root benchmarks/coarse-synth-v0.1 \
  --submission "$SUBMISSION" \
  --output "$EVAL_RESULT"

"${OPENCRITIQUE_CMD[@]}" evaluation scorecard \
  --result "$EVAL_RESULT" \
  --json-output "$SCORECARD"

for path in "$SUBMISSION" "$EVAL_RESULT" "$SCORECARD"; do
  if [[ ! -f "$path" ]]; then
    echo "FAIL: missing artifact: $path" >&2
    exit 2
  fi
done

if grep -Eq '"performance_claim_authorized"[[:space:]]*:[[:space:]]*true' "$EVAL_RESULT" \
  || grep -Eq '"performance_claims_authorized"[[:space:]]*:[[:space:]]*true' "$SCORECARD" \
  || grep -Eq '"performance_claim_authorized"[[:space:]]*:[[:space:]]*true' "$SCORECARD"; then
  echo "FAIL: performance claims must remain unauthorized" >&2
  exit 3
fi

echo
echo "Artifact checklist (PASS):"
echo "  OK coarse-submission.json"
echo "  OK evaluation-result.json"
echo "  OK scorecard.json"
echo "Artifacts under: $OUT_DIR"
echo
echo "Claim status: NOT AUTHORIZED"
echo "Banner: sample demo != production MANIFEST ready != scientific claims."
echo "Next (optional Studio): see docs/examples/studio-walkthrough.md"
exit 0
