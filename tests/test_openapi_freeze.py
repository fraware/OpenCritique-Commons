"""OpenAPI freeze drift tests."""

from __future__ import annotations

import json
from pathlib import Path

from opencritique_registry.api import create_app

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "openapi" / "registry.openapi.json"


def test_registry_openapi_freeze_matches_app() -> None:
    assert FROZEN.is_file(), "missing openapi/registry.openapi.json; run scripts/export_openapi.py"
    on_disk = json.loads(FROZEN.read_text(encoding="utf-8"))
    generated = create_app(initialize=False).openapi()
    assert on_disk == generated, "OpenAPI drift: regenerate with python scripts/export_openapi.py"
    assert "paths" in on_disk
    assert "/healthz" in on_disk["paths"]
    assert "/v1/matcher-audit/protocol" in on_disk["paths"]
