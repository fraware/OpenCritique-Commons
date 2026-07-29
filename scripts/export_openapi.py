"""Export frozen OpenAPI documents from FastAPI apps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def registry_openapi() -> dict[str, Any]:
    from opencritique_registry.api import create_app

    return create_app(initialize=False).openapi()


def write_openapi(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("openapi/registry.openapi.json"),
        help="Destination path for the registry OpenAPI document",
    )
    args = parser.parse_args()
    write_openapi(args.output, registry_openapi())
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
