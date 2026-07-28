#!/usr/bin/env python3
"""Fail closed on obvious secrets and private key material in the public tree."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "_inspect_wheel",
    "node_modules",
}

# High-signal patterns only; avoid matching documentation examples lightly.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-key-pem", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "generic-api-key-assignment",
        re.compile(r"(?i)(api[_-]?key|secret[_-]?key)\s*=\s*['\"][^'\"]{20,}"),
    ),
]

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".txt",
    ".sh",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
    ".cff",
}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            "LICENSE",
            "Dockerfile",
            "Makefile",
        }:
            continue
        files.append(path)
    return files


def main() -> int:
    findings: list[str] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS:
            if pattern.search(text):
                rel = path.relative_to(ROOT).as_posix()
                findings.append(f"{rel}: matched {label}")
    if findings:
        print("secret scan FAILED:")
        for item in findings:
            print(f"  - {item}")
        return 1
    print(f"secret scan OK ({len(list(iter_files()))} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
