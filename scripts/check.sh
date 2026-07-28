#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> compileall"
python -m compileall -q src

echo "==> ruff (new modules; recovered tree lint deferred)"
RUFF_PATHS=(
  src/opencritique_schema/registry.py
  src/opencritique_schema/document_graph.py
  src/opencritique_evaluation/novel_determination.py
  src/opencritique_evaluation/trust.py
  src/opencritique_evaluation/signing.py
  src/opencritique_evaluation/matcher_audit.py
  src/opencritique_registry/novel_service.py
  src/opencritique_registry/matcher_audit_api.py
  src/opencritique_evaluation/scorecard.py
  src/opencritique_adapters/contract.py
  src/opencritique_adapters/coarse_loss.py
  src/opencritique_adapters/openreviewer.py
  src/opencritique_adapters/openreviewer_loss.py
  src/opencritique_adapters/cli.py
  tests/test_schema_freeze.py
  tests/test_novel_determinations.py
  tests/test_migrations.py
  tests/test_release_packaging.py
  tests/test_coarse_validation.py
  tests/test_signing_governance.py
  tests/test_openreviewer_adapter.py
  tests/test_document_graph.py
  tests/test_matcher_audit.py
  tests/test_rights_path.py
  scripts
)
if command -v ruff >/dev/null 2>&1; then
  ruff check "${RUFF_PATHS[@]}"
else
  echo "ruff not installed; skipping"
fi

echo "==> schema export drift"
python - <<'PY'
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
    path.name: hashlib.sha256(canonical_json_bytes(json.loads(path.read_text(encoding="utf-8")))).hexdigest()
    for path in sorted(root.glob("*.schema.json"))
}
actual["inventory.json"] = hashlib.sha256(canonical_json_bytes(inventory)).hexdigest()
assert actual == golden, "GOLDEN_HASHES.json drift"
print("schema freeze OK")
PY

echo "==> alembic current/head smoke"
python - <<'PY'
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
python scripts/secret_scan.py

echo "==> pytest"
pytest -q

echo "==> import smoke (outside src layout assumptions)"
python - <<'PY'
from opencritique_registry.api import app
from opencritique_schema.models import Concern
from opencritique_evaluation.engine import evaluate, load_case, load_manifest
from opencritique_adapters.coarse import CoarseReview
from opencritique_acquisition.models import AcquisitionLedger
from opencritique_schema.registry import SCHEMA_FREEZE_RELEASE
from opencritique_evaluation.novel_determination import NOVEL_POLICY_VERSION

assert app.title
assert Concern.__name__ == "Concern"
assert callable(evaluate) and callable(load_case) and callable(load_manifest)
assert CoarseReview.__name__ == "CoarseReview"
assert AcquisitionLedger.__name__ == "AcquisitionLedger"
assert SCHEMA_FREEZE_RELEASE == "0.5.0a1"
assert NOVEL_POLICY_VERSION.startswith("novel-determination-")
print("import smoke OK")
PY

echo "==> publication paths"
python - <<'PY'
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
    "docs/rights-memorandum.md",
    "docs/MILESTONES.md",
    "docs/cross-adapter-conformance.md",
    "SECURITY.md",
    "trust/scorecard-trust-store.json",
    "fixtures/coarse/UPSTREAM_CONTRACT.json",
    "fixtures/openreviewer/UPSTREAM_CONTRACT.json",
    "fixtures/document_graph/hidden_text_malicious.json",
    "benchmarks/coarse-synth-v0.1/manifest.json",
    "benchmarks/openreviewer-synth-v0.1/manifest.json",
    "corpus/acquisition-ledger.json",
    "governance/decisions/ADR-0003-second-adapter.md",
    "schemas/inventory.json",
    "schemas/GOLDEN_HASHES.json",
    "migrations/env.py",
    "alembic.ini",
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
