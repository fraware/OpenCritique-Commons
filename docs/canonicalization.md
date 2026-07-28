# Canonical JSON

OpenCritique Commons freezes a single canonical JSON encoding for content
hashing and golden fixtures. The implementation lives in
`opencritique_schema.canonical`.

## Rules

1. **Pydantic models** are dumped with `model_dump(mode="python", exclude_none=False)`
   before further normalization.
2. **Enums** become their `.value`.
3. **Datetimes** become ISO-8601 strings via `.isoformat()`.
4. **Strings** are Unicode NFC-normalized (`unicodedata.normalize("NFC", ...)`).
5. **Dicts** have string keys; values are normalized recursively.
6. **Lists and tuples** become lists of normalized values.
7. **JSON encoding** uses:
   - `ensure_ascii=False`
   - `sort_keys=True`
   - `separators=(",", ":")` (no whitespace)
   - `allow_nan=False`
   - UTF-8 bytes

## Content hashes

`content_hash(value)` is the SHA-256 hex digest of
`canonical_json_bytes(value, exclude_content_hash=True)`.

When `exclude_content_hash` is true and the top-level value is a dict, the
`content_hash` key is removed before encoding. Nested `content_hash` fields are
left intact so embedded records remain addressable.

Record types that inherit `RecordBase` expose:

- `expected_content_hash()` — hash of the record under these rules
- `verify_content_hash()` — equality check against the embedded `content_hash`

## Stability

These rules are part of the v0.5 schema freeze. Changing normalization,
key ordering, or datetime formatting is a breaking change and requires a major
schema bump plus an ADR. See `docs/schema-compatibility.md`.
