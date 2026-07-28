"""OpenCritique Commons foundation schemas."""

from .canonical import canonical_json_bytes, content_hash
from .models import *  # noqa: F403
from .registry import (
    RECORD_SCHEMA_VERSION,
    SCHEMA_FREEZE_RELEASE,
    SCHEMA_REGISTRY,
    SchemaRegistryError,
    SchemaValidationError,
    UnknownSchemaError,
    export_json_schemas,
    get_schema,
    list_schemas,
    schema_id_for_model,
    validate_payload,
)

__version__ = "0.1.0a1"

__all__ = [
    "RECORD_SCHEMA_VERSION",
    "SCHEMA_FREEZE_RELEASE",
    "SCHEMA_REGISTRY",
    "SchemaRegistryError",
    "SchemaValidationError",
    "UnknownSchemaError",
    "canonical_json_bytes",
    "content_hash",
    "export_json_schemas",
    "get_schema",
    "list_schemas",
    "schema_id_for_model",
    "validate_payload",
]
