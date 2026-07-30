"""Tests for docs/community-adapters.json registry + schema."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_adapter_compatibility.py"


def _load_compat() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_adapter_compatibility", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_compat = _load_compat()
SCHEMA_FREEZE_RELEASE = _compat.SCHEMA_FREEZE_RELEASE
validate_json_schema = _compat.validate_json_schema

REGISTRY = ROOT / "docs" / "community-adapters.json"
SCHEMA = ROOT / "docs" / "community-adapters.schema.json"
MARKDOWN = ROOT / "docs" / "community-adapters.md"


def test_registry_files_exist() -> None:
    assert REGISTRY.is_file()
    assert SCHEMA.is_file()
    assert MARKDOWN.is_file()


def test_registry_validates_against_schema() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = validate_json_schema(data, schema)
    assert errors == [], errors


def test_registry_claims_and_freeze_locked() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert data["registry_version"] == "0.1"
    assert data["schema_freeze_release"] == SCHEMA_FREEZE_RELEASE == "0.5.0a1"
    assert data["performance_claims_authorized"] is False
    adapters = data["adapters"]
    assert {entry["slug"] for entry in adapters} >= {"coarse", "openreviewer"}
    for entry in adapters:
        assert entry["claims"] is False
        assert entry["status"] in {"in-tree", "external", "planned"}
        assert entry["evidence_class"] in {"sample", "private_live", "production"}


def test_seeded_in_tree_adapters_are_sample() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_slug = {entry["slug"]: entry for entry in data["adapters"]}
    for slug in ("coarse", "openreviewer"):
        entry = by_slug[slug]
        assert entry["status"] == "in-tree"
        assert entry["evidence_class"] == "sample"
        assert entry["claims"] is False
        assert entry["sample_contract_id"] == "opencritique-sample-adapter-contract-v1"


def test_markdown_table_matches_json_slugs() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    md = MARKDOWN.read_text(encoding="utf-8")
    for entry in data["adapters"]:
        assert f"`{entry['slug']}`" in md
        assert entry["name"] in md


def test_schema_rejects_claims_true() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data["adapters"][0]["claims"] = True
    errors = validate_json_schema(data, schema)
    assert any("const" in err or "claims" in err for err in errors)


def test_schema_rejects_unknown_status() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data["adapters"][0]["status"] = "experimental"
    errors = validate_json_schema(data, schema)
    assert errors


def test_schema_rejects_wrong_freeze() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data["schema_freeze_release"] = "9.9.9"
    errors = validate_json_schema(data, schema)
    assert errors


def test_markdown_has_no_emoji() -> None:
    md = MARKDOWN.read_text(encoding="utf-8")
    # Common emoji / pictograph ranges — docs must stay plain.
    assert re.search(r"[\U0001F300-\U0001FAFF]", md) is None
