"""Golden schema hashes and registry freeze tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from opencritique_schema.canonical import canonical_json_bytes, content_hash
from opencritique_schema.models import ActorReference, ActorType, Manuscript, RightsClassification
from opencritique_schema.registry import (
    SCHEMA_FREEZE_RELEASE,
    SCHEMA_REGISTRY,
    SchemaValidationError,
    UnknownSchemaError,
    export_json_schemas,
    get_schema,
    list_schemas,
    load_extended_registry,
    schema_id_for_model,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
GOLDEN = SCHEMAS / "GOLDEN_HASHES.json"


@pytest.fixture(scope="module", autouse=True)
def _extended_registry() -> None:
    load_extended_registry()


def test_every_persistent_object_has_schema_id_and_version() -> None:
    entries = list_schemas(persistent_only=True)
    assert entries
    for entry in entries:
        assert entry.schema_id.startswith("opencritique.")
        assert entry.schema_version
        assert entry.model is SCHEMA_REGISTRY[entry.schema_id].model


def test_schema_freeze_release() -> None:
    assert SCHEMA_FREEZE_RELEASE == "0.5.0a1"
    inventory = json.loads((SCHEMAS / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["freeze_release"] == SCHEMA_FREEZE_RELEASE
    assert len(inventory["schemas"]) == len(list_schemas())


def test_golden_schema_hashes_are_stable() -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual: dict[str, str] = {}
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        actual[path.name] = hashlib.sha256(canonical_json_bytes(data)).hexdigest()
    inventory = json.loads((SCHEMAS / "inventory.json").read_text(encoding="utf-8"))
    actual["inventory.json"] = hashlib.sha256(canonical_json_bytes(inventory)).hexdigest()
    assert actual == expected


def test_exported_schemas_match_registry_models() -> None:
    exported = export_json_schemas()
    for entry in list_schemas():
        assert entry.model.__name__ in exported
        on_disk = json.loads((SCHEMAS / f"{entry.model.__name__}.schema.json").read_text())
        assert on_disk == exported[entry.model.__name__]


def test_schema_id_for_model() -> None:
    assert schema_id_for_model(Manuscript) == "opencritique.Manuscript"
    assert get_schema("opencritique.EvidenceItem").model.__name__ == "EvidenceItem"
    assert get_schema("opencritique.PublicScorecard").model.__name__ == "PublicScorecard"


def test_unknown_schema_raises_typed_error() -> None:
    with pytest.raises(UnknownSchemaError) as exc:
        get_schema("opencritique.DoesNotExist")
    assert exc.value.schema_id == "opencritique.DoesNotExist"


def test_malformed_fixture_fails_with_typed_error() -> None:
    with pytest.raises(SchemaValidationError) as exc:
        validate_payload("opencritique.Manuscript", {"id": "bad"})
    assert exc.value.schema_id == "opencritique.Manuscript"
    assert exc.value.errors


def test_malformed_manuscript_fails_pydantic_validation() -> None:
    with pytest.raises(ValidationError):
        Manuscript.model_validate(
            {
                "id": "not-a-valid-id",
                "schema_version": "0.1.0",
                "created_at": "2026-01-01T00:00:00+00:00",
                "created_by": {
                    "actor_id": "system",
                    "actor_type": "system",
                },
                "content_hash": "0" * 64,
                "manuscript_id": "not-a-valid-id",
                "title": None,
                "rights_classification": "public",
                "consent_policy_id": "policy",
                "current_version_id": "ocver_1",
            }
        )


def test_canonical_hash_excludes_content_hash_field() -> None:
    actor = ActorReference(actor_id="system:test", actor_type=ActorType.SYSTEM)
    payload = {
        "id": "ocms_abcdef0123456789",
        "schema_version": "0.1.0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "created_by": actor.model_dump(mode="python"),
        "content_hash": "0" * 64,
        "manuscript_id": "ocms_abcdef0123456789",
        "title": "Example",
        "rights_classification": RightsClassification.PUBLIC,
        "consent_policy_id": "consent-v1",
        "current_version_id": "ocver_abcdef0123456789",
    }
    left = content_hash(payload)
    payload["content_hash"] = "f" * 64
    right = content_hash(payload)
    assert left == right
    assert len(left) == 64
