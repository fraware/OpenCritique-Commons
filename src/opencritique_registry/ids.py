from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    # UUIDv7 is not available in Python 3.12's stdlib. UUIDv4 remains opaque and safe;
    # migration to UUIDv7 can occur without changing external identifier semantics.
    return f"{prefix}_{uuid.uuid4().hex}"
