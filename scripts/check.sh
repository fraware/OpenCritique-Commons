#!/usr/bin/env bash
set -euo pipefail
python -m compileall -q src
pytest -q
python - <<'PY'
from opencritique_registry.api import app
from opencritique_schema.models import Concern
assert app.title
assert Concern.__name__ == 'Concern'
PY
