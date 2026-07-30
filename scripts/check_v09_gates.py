#!/usr/bin/env python3
"""Compatibility orchestrator for v0.9-beta go/no-go checks.

Runs engineering (informational/scaffolding) then scientific (blocking
authenticity) evaluators. Exit status follows the **scientific** gate script:
v0.9-beta GO requires ``check_v09_scientific_gates.py`` to exit 0.

Prefer calling the split scripts directly:
  python scripts/check_v09_engineering_gates.py
  python scripts/check_v09_scientific_gates.py
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def _run_script(name: str) -> int:
    path = _SCRIPTS / name
    # Isolate module execution so each script's main() drives its own report.
    prior = sys.argv[:]
    try:
        sys.argv = [str(path), *prior[1:]]
        try:
            runpy.run_path(str(path), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            return 1
    finally:
        sys.argv = prior
    return 0


def main() -> int:
    print("=== v0.9 engineering gates ===")
    eng = _run_script("check_v09_engineering_gates.py")
    print()
    print("=== v0.9 scientific gates (authoritative for GO/NO-GO) ===")
    sci = _run_script("check_v09_scientific_gates.py")
    if eng not in (0, 1):
        print(f"engineering gate evaluator crashed with status {eng}", file=sys.stderr)
        return eng
    if sci not in (0, 1):
        print(f"scientific gate evaluator crashed with status {sci}", file=sys.stderr)
        return sci
    # Engineering failures are unexpected for scaffolding; surface them, but
    # scientific authenticity remains the GO authority.
    if eng != 0:
        print(
            "warning: engineering gates reported blocking failures "
            f"(exit {eng}); scientific status={sci}",
            file=sys.stderr,
        )
    return sci


if __name__ == "__main__":
    raise SystemExit(main())
