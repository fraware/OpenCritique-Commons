"""Regenerate schemas/GOLDEN_HASHES.json from exported schema artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from opencritique_schema.canonical import canonical_json_bytes


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas"
    hashes: dict[str, str] = {}
    for path in sorted(root.glob("*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        hashes[path.name] = hashlib.sha256(canonical_json_bytes(data)).hexdigest()
    inventory = json.loads((root / "inventory.json").read_text(encoding="utf-8"))
    hashes["inventory.json"] = hashlib.sha256(canonical_json_bytes(inventory)).hexdigest()
    (root / "GOLDEN_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(hashes)} hashes")


if __name__ == "__main__":
    main()
