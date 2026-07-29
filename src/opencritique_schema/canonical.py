from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import AnyUrl, BaseModel


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python", exclude_none=False))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, AnyUrl):
        return _normalize(str(value))
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def canonical_json_bytes(value: Any, *, exclude_content_hash: bool = False) -> bytes:
    normalized = _normalize(value)
    if exclude_content_hash and isinstance(normalized, dict):
        normalized = dict(normalized)
        normalized.pop("content_hash", None)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value, exclude_content_hash=True)
    ).hexdigest()
