#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if command -v python >/dev/null 2>&1 && python -c "import pydantic" >/dev/null 2>&1; then
  PYTHON=python
elif [ -n "${USERPROFILE:-}" ] && [ -x "${USERPROFILE//\\//}/miniconda3/python.exe" ]; then
  PYTHON="${USERPROFILE//\\//}/miniconda3/python.exe"
elif command -v cmd.exe >/dev/null 2>&1; then
  PYTHON="$(cmd.exe /c where python 2>/dev/null | tr -d '\r' | sed -n '1p')"
  if [ -z "$PYTHON" ]; then
    PYTHON="$(cmd.exe /c where py 2>/dev/null | tr -d '\r' | sed -n '1p') -3"
  fi
elif command -v python3 >/dev/null 2>&1 && python3 -c "import pydantic" >/dev/null 2>&1; then
  PYTHON=python3
elif command -v py >/dev/null 2>&1; then
  PYTHON="py -3"
else
  echo "python interpreter not found" >&2
  exit 1
fi

if [ -z "${PYTHON:-}" ]; then
  echo "python interpreter not found" >&2
  exit 1
fi

if [[ "$PYTHON" == ?:\\* ]]; then
  drive="$(printf '%s' "${PYTHON:0:1}" | tr '[:upper:]' '[:lower:]')"
  rest="${PYTHON:2}"
  rest="${rest//\\//}"
  PYTHON="/mnt/${drive}${rest}"
fi

echo "==> compileall"
$PYTHON -m compileall -q src

echo "==> ruff"
if "$PYTHON" -m ruff --version >/dev/null 2>&1; then
  "$PYTHON" -m ruff check src tests scripts
elif command -v ruff >/dev/null 2>&1; then
  ruff check src tests scripts
else
  echo "ruff not installed; skipping"
fi

echo "==> pyright"
if "$PYTHON" -m pyright --version >/dev/null 2>&1; then
  "$PYTHON" -m pyright
elif command -v pyright >/dev/null 2>&1; then
  pyright
else
  echo "pyright not installed; skipping"
fi

echo "==> schema export drift"
$PYTHON - <<'PY'
from pathlib import Path
import json
import hashlib
from opencritique_schema.canonical import canonical_json_bytes
from opencritique_schema.registry import export_json_schemas, list_schemas, load_extended_registry

load_extended_registry()
root = Path("schemas")
exported = export_json_schemas()
for name, schema in exported.items():
    path = root / f"{name}.schema.json"
    assert path.is_file(), f"missing exported schema: {path}"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == schema, f"schema drift: {path}"
inventory = json.loads((root / "inventory.json").read_text(encoding="utf-8"))
assert len(inventory["schemas"]) == len(list_schemas())
golden = json.loads((root / "GOLDEN_HASHES.json").read_text(encoding="utf-8"))
actual = {
    path.name: hashlib.sha256(
        canonical_json_bytes(json.loads(path.read_text(encoding="utf-8")))
    ).hexdigest()
    for path in sorted(root.glob("*.schema.json"))
}
actual["inventory.json"] = hashlib.sha256(canonical_json_bytes(inventory)).hexdigest()
assert actual == golden, "GOLDEN_HASHES.json drift"
print("schema freeze OK")
PY

echo "==> openapi freeze drift"
$PYTHON - <<'PY'
import json
from pathlib import Path
from opencritique_registry.api import create_app

path = Path("openapi/registry.openapi.json")
assert path.is_file(), "missing openapi/registry.openapi.json"
on_disk = json.loads(path.read_text(encoding="utf-8"))
generated = create_app(initialize=False).openapi()
assert on_disk == generated, "OpenAPI drift; run python scripts/export_openapi.py"
print("openapi freeze OK")
PY

echo "==> alembic current/head smoke"
$PYTHON - <<'PY'
from pathlib import Path
import os
import tempfile
from alembic import command
from alembic.config import Config

root = Path(".").resolve()
with tempfile.TemporaryDirectory() as tmp:
    db = Path(tmp) / "check.db"
    url = f"sqlite:///{db.as_posix()}"
    os.environ["OPENCRITIQUE_DATABASE_URL"] = url
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")
print("alembic upgrade head OK")
PY

echo "==> secret scan"
$PYTHON scripts/secret_scan.py

echo "==> pytest"
"$PYTHON" -m pytest -q

echo "==> import smoke (outside src layout assumptions)"
$PYTHON - <<'PY'
from opencritique_registry.api import app
from opencritique_schema.models import Concern
from opencritique_evaluation.engine import evaluate, load_case, load_manifest
from opencritique_adapters.coarse import CoarseReview
from opencritique_acquisition.models import AcquisitionLedger
from opencritique_schema.registry import SCHEMA_FREEZE_RELEASE
from opencritique_evaluation.novel_determination import NOVEL_POLICY_VERSION
from opencritique_ingestion import ingest_path
from opencritique_verification import recompute_python

assert app.title
assert Concern.__name__ == "Concern"
assert callable(evaluate) and callable(load_case) and callable(load_manifest)
assert CoarseReview.__name__ == "CoarseReview"
assert AcquisitionLedger.__name__ == "AcquisitionLedger"
assert SCHEMA_FREEZE_RELEASE == "0.5.0a1"
assert NOVEL_POLICY_VERSION.startswith("novel-determination-")
assert callable(ingest_path) and callable(recompute_python)
print("import smoke OK")
PY

echo "==> publication paths"
$PYTHON - <<'PY'
from pathlib import Path

root = Path(".")
required = [
    "src/opencritique_schema/models.py",
    "src/opencritique_schema/registry.py",
    "src/opencritique_registry/api.py",
    "src/opencritique_evaluation/engine.py",
    "src/opencritique_evaluation/novel_determination.py",
    "src/opencritique_adapters/coarse.py",
    "src/opencritique_acquisition/models.py",
    "src/opencritique_registry/studio_assets/app.js",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CITATION.cff",
    "governance/decisions/ADR-0001-source-recovery.md",
    "governance/decisions/ADR-0002-naming-deltas.md",
    "docs/canonicalization.md",
    "docs/schema-compatibility.md",
    "docs/novel-discovery-limits.md",
    "docs/coarse-conversion-loss.md",
    "docs/signing-governance.md",
    "docs/document-graph-alpha.md",
    "docs/matcher-audit-protocol.md",
    "docs/deployment-local.md",
    "docs/deployment-byok.md",
    "docs/rights-memorandum.md",
    "docs/rights-clearance-status.md",
    "docs/core-integrity-review.md",
    "docs/adapter-authenticity.md",
    "docs/MILESTONES.md",
    "docs/cross-adapter-conformance.md",
    "docs/expert-program-ops.md",
    "docs/matcher-audit-denominators.md",
    "docs/v0.9-beta-go-no-go.md",
    "SECURITY.md",
    "trust/scorecard-trust-store.json",
    "fixtures/coarse/UPSTREAM_CONTRACT.json",
    "fixtures/openreviewer/UPSTREAM_CONTRACT.json",
    "fixtures/coarse/production/MANIFEST.json",
    "fixtures/openreviewer/production/MANIFEST.json",
    "fixtures/document_graph/hidden_text_malicious.json",
    "benchmarks/coarse-synth-v0.1/manifest.json",
    "benchmarks/openreviewer-synth-v0.1/manifest.json",
    "corpus/acquisition-ledger.json",
    "corpus/samples/sample-econ-01/manuscript.md",
    "cases/reference/REF-01/case.json",
    "cases/rights-candidates/rc-01/case.json",
    "governance/decisions/ADR-0003-second-adapter.md",
    "governance/policies/expert-qualification-thresholds.v0.1.json",
    "governance/policies/calibration-task-seeds.v0.1.json",
    "schemas/inventory.json",
    "schemas/GOLDEN_HASHES.json",
    "openapi/registry.openapi.json",
    "docker-compose.yml",
    "Dockerfile",
    "migrations/env.py",
    "alembic.ini",
    "scripts/signing_ceremony_dev.py",
    "scripts/signing_ceremony_prod.py",
    "scripts/export_openapi.py",
    "governance/decisions/ADR-0004-appeals-and-corrections.md",
]
missing = [p for p in required if not (root / p).is_file()]
prohibited = [
    ".bootstrap",
    ".github/workflows/bootstrap-source.yml",
    ".github/workflows/publish-blobs.yml",
    ".github/workflows/repair-publish.yml",
]
present = [p for p in prohibited if (root / p).exists()]
assert not missing, missing
assert not present, present
print("publication paths OK")
PY

echo "check.sh passed"
