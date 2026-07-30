#!/usr/bin/env bash
# Live Coarse operator demo (calls paid APIs when a real key is present).
# Default CI must not run this script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${OPENCRITIQUE_BYOK_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "FAIL: set OPENCRITIQUE_BYOK_API_KEY or OPENAI_API_KEY before live demo." >&2
  exit 1
fi

echo "============================================================"
echo " OpenCritique live Coarse demo"
echo " Private live / sample gold != production authenticity"
echo " performance_claims_authorized=false (NOT AUTHORIZED)"
echo "============================================================"

OUT_DIR="${OUT_DIR:-runs/pipeline/coarse-sample-econ-01}"
MANUSCRIPT="${MANUSCRIPT:-corpus/samples/sample-econ-01/manuscript.md}"
MODEL="${MODEL:-openai/gpt-4o}"

opencritique runners pipeline coarse \
  --manuscript "$MANUSCRIPT" \
  --out-dir "$OUT_DIR" \
  --model "$MODEL"

required=(
  "coarse-review.json"
  "coarse-review.md"
  "provenance.json"
)
missing=()
for name in "${required[@]}"; do
  if [[ ! -f "$OUT_DIR/$name" ]]; then
    missing+=("$name")
  fi
done
if ((${#missing[@]} > 0)); then
  echo "FAIL: missing required artifacts: ${missing[*]}" >&2
  exit 2
fi

if grep -Eq '"performance_claims_authorized"[[:space:]]*:[[:space:]]*true' \
  "$OUT_DIR/coarse-review.json"; then
  echo "FAIL: performance_claims_authorized must remain false" >&2
  exit 3
fi

echo
echo "Artifact checklist (PASS):"
for name in "${required[@]}"; do
  echo "  OK $name"
done
if [[ -f "$OUT_DIR/scorecard.json" ]]; then
  echo "  OK scorecard.json (gold path)"
fi
if [[ -f "$OUT_DIR/handoff.json" ]]; then
  echo "  OK handoff.json (registry path)"
fi
echo "Artifacts under: $OUT_DIR"
echo "Studio handoff:"
echo "  opencritique-registry import-live-run --from $OUT_DIR --manuscript $MANUSCRIPT"
echo "  opencritique-registry serve"
echo "Banner: private live != production MANIFEST ready != scientific claims."
exit 0
