#!/usr/bin/env python3
"""Adapter interchange compatibility helper (claim-safe).

Checks claims locks, sample contract presence, and refuses fake
production-ready pretenses. Emits short markdown suitable for PR bodies.

Not part of default ``scripts/check.sh`` — run explicitly before adapter PRs::

    python scripts/check_adapter_compatibility.py fixtures/coarse
    python scripts/check_adapter_compatibility.py --slug openreviewer
    python scripts/check_adapter_compatibility.py path/to/map.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs" / "community-adapters.json"
DEFAULT_SCHEMA = ROOT / "docs" / "community-adapters.schema.json"
SAMPLE_CONTRACT_ID = "opencritique-sample-adapter-contract-v1"
SCHEMA_FREEZE_RELEASE = "0.5.0a1"

_CLAIMS_TRUE_RE = re.compile(
    r"performance_claims_authorized\s*[:=]\s*True"
    r"|PERFORMANCE_CLAIMS_AUTHORIZED\s*[:=]\s*True"
    r'|["\']performance_claims_authorized["\']\s*:\s*true'
    r'|["\']claims["\']\s*:\s*true',
    re.IGNORECASE,
)
_SAMPLE_CONTRACT_RE = re.compile(
    r"opencritique-sample-adapter-contract-v1"
    r"|SAMPLE_ADAPTER_CONTRACT_ID",
)
_PRODUCTION_READY_PRETENSE_RE = re.compile(
    r"(?i)\b(production[- ]ready|ready for production|production authenticity "
    r"confirmed|status\s*=\s*ready\b.*\b(sample|synth))"
)


@dataclass(frozen=True, slots=True)
class CheckItem:
    name: str
    passed: bool
    detail: str


@dataclass
class CompatibilityReport:
    target: str
    items: list[CheckItem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(item.passed for item in self.items)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.items.append(CheckItem(name=name, passed=passed, detail=detail))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Minimal Draft 2020-12 subset validator (no external jsonschema dep)."""

    errors: list[str] = []

    def resolve_ref(ref: str) -> dict[str, Any]:
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref (local only): {ref}")
        node: Any = schema
        for part in ref[2:].split("/"):
            node = node[part]
        if not isinstance(node, dict):
            raise ValueError(f"$ref did not resolve to object: {ref}")
        return node

    def check(value: Any, subschema: dict[str, Any], loc: str) -> None:
        if "$ref" in subschema:
            check(value, resolve_ref(subschema["$ref"]), loc)
            return

        expected_type = subschema.get("type")
        if expected_type is not None:
            type_ok = False
            allowed = expected_type if isinstance(expected_type, list) else [expected_type]
            for candidate in allowed:
                if candidate == "object" and isinstance(value, dict):
                    type_ok = True
                elif candidate == "array" and isinstance(value, list):
                    type_ok = True
                elif candidate == "string" and isinstance(value, str):
                    type_ok = True
                elif candidate == "boolean" and isinstance(value, bool):
                    type_ok = True
                elif candidate == "integer" and isinstance(value, int) and not isinstance(
                    value, bool
                ):
                    type_ok = True
                elif candidate == "number" and isinstance(value, (int, float)) and not isinstance(
                    value, bool
                ):
                    type_ok = True
                elif candidate == "null" and value is None:
                    type_ok = True
            if not type_ok:
                errors.append(f"{loc}: expected type {expected_type}, got {type(value).__name__}")
                return

        if "const" in subschema and value != subschema["const"]:
            errors.append(f"{loc}: expected const {subschema['const']!r}, got {value!r}")

        if "enum" in subschema and value not in subschema["enum"]:
            errors.append(f"{loc}: value {value!r} not in enum {subschema['enum']}")

        if isinstance(value, str):
            pattern = subschema.get("pattern")
            if pattern and re.search(pattern, value) is None:
                errors.append(f"{loc}: string does not match pattern {pattern!r}")
            min_length = subschema.get("minLength")
            if min_length is not None and len(value) < min_length:
                errors.append(f"{loc}: string shorter than minLength {min_length}")

        if isinstance(value, list):
            min_items = subschema.get("minItems")
            if min_items is not None and len(value) < min_items:
                errors.append(f"{loc}: array shorter than minItems {min_items}")
            item_schema = subschema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    check(item, item_schema, f"{loc}[{index}]")

        if isinstance(value, dict):
            required = subschema.get("required", [])
            for key in required:
                if key not in value:
                    errors.append(f"{loc}: missing required property {key!r}")
            properties = subschema.get("properties", {})
            additional = subschema.get("additionalProperties", True)
            for key, child in value.items():
                if key in properties:
                    check(child, properties[key], f"{loc}.{key}")
                elif additional is False:
                    errors.append(f"{loc}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    check(child, additional, f"{loc}.{key}")

    check(instance, schema, path)
    return errors


def _scan_python_claims(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    if _CLAIMS_TRUE_RE.search(text):
        problems.append(f"{path}: claims flag set true in source")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        problems.append(f"{path}: could not parse Python ({exc})")
        return problems
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith(
                    "PERFORMANCE_CLAIMS_AUTHORIZED"
                ):
                    if isinstance(node.value, ast.Constant) and node.value.value is True:
                        problems.append(f"{path}: {target.id}=True")
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.endswith("PERFORMANCE_CLAIMS_AUTHORIZED"):
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    problems.append(f"{path}: {node.target.id}=True")
    return problems


def _json_claims_locked(payload: Any, path: Path, problems: list[str]) -> None:
    if isinstance(payload, dict):
        if payload.get("performance_claims_authorized") is True:
            problems.append(f"{path}: performance_claims_authorized=true")
        if payload.get("claims") is True:
            problems.append(f"{path}: claims=true")
        for value in payload.values():
            _json_claims_locked(value, path, problems)
    elif isinstance(payload, list):
        for item in payload:
            _json_claims_locked(item, path, problems)


def _find_sample_contract_signals(text: str) -> bool:
    return _SAMPLE_CONTRACT_RE.search(text) is not None


def _production_manifest_issues(manifest_path: Path) -> list[str]:
    problems: list[str] = []
    if not manifest_path.is_file():
        return problems
    data = _load_json(manifest_path)
    if not isinstance(data, dict):
        return [f"{manifest_path}: MANIFEST.json must be an object"]
    if data.get("performance_claims_authorized") is True:
        problems.append(f"{manifest_path}: performance_claims_authorized must be false")
    status = data.get("status")
    artifacts = data.get("artifacts") or []
    rights = data.get("rights_record_ids") or []
    pin = data.get("upstream_commit_or_config")
    if status == "ready":
        if not artifacts:
            problems.append(
                f"{manifest_path}: status=ready without artifacts is a fake production pretence"
            )
        if not rights:
            problems.append(
                f"{manifest_path}: status=ready without rights_record_ids is refused"
            )
        if not pin or pin == SAMPLE_CONTRACT_ID:
            problems.append(
                f"{manifest_path}: status=ready requires a real upstream pin "
                f"(not {SAMPLE_CONTRACT_ID!r})"
            )
        # Sample contract contamination
        blob = json.dumps(data)
        if SAMPLE_CONTRACT_ID in blob:
            problems.append(
                f"{manifest_path}: sample contract id must not appear in ready production MANIFEST"
            )
    return problems


def _collect_targets(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    found: list[Path] = []
    patterns = (
        "**/contract.py",
        "**/*_loss.py",
        "**/UPSTREAM_CONTRACT.json",
        "**/maps/*.json",
        "**/production/MANIFEST.json",
    )
    # Prefer shallow known layouts first.
    for name in (
        "contract.py",
        "UPSTREAM_CONTRACT.json",
        "production/MANIFEST.json",
    ):
        candidate = path / name
        if candidate.is_file():
            found.append(candidate)
    maps_dir = path / "maps"
    if maps_dir.is_dir():
        found.extend(sorted(maps_dir.glob("*.json")))
    # Python adapter modules when pointing at package paths.
    if path.name == "opencritique_adapters" or (path / "coarse.py").is_file():
        py_names = (
            "contract.py",
            "coarse.py",
            "openreviewer.py",
            "coarse_loss.py",
            "openreviewer_loss.py",
        )
        for py_name in py_names:
            candidate = path / py_name
            if candidate.is_file() and candidate not in found:
                found.append(candidate)
    # Generic walk for external drafts (bounded).
    if not found:
        for pattern in patterns:
            found.extend(sorted(path.glob(pattern)))
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for item in found:
        resolved = item.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(item)
    return unique


def check_path(path: Path) -> CompatibilityReport:
    report = CompatibilityReport(target=str(path))
    if not path.exists():
        report.add("path_exists", False, f"path does not exist: {path}")
        return report
    report.add("path_exists", True, f"checking {path}")

    targets = _collect_targets(path)
    if not targets:
        report.add(
            "inputs_found",
            False,
            "no adapter Python, UPSTREAM_CONTRACT.json, map, or MANIFEST found",
        )
        return report
    report.add("inputs_found", True, f"{len(targets)} file(s) inspected")

    claim_problems: list[str] = []
    sample_seen = False
    production_problems: list[str] = []
    pretenses: list[str] = []

    for target in targets:
        text = target.read_text(encoding="utf-8")
        if target.suffix == ".py":
            claim_problems.extend(_scan_python_claims(target))
            if _find_sample_contract_signals(text):
                sample_seen = True
        elif target.suffix == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                claim_problems.append(f"{target}: invalid JSON ({exc})")
                continue
            _json_claims_locked(payload, target, claim_problems)
            if _find_sample_contract_signals(text):
                sample_seen = True
            if target.name == "MANIFEST.json" and "production" in target.parts:
                production_problems.extend(_production_manifest_issues(target))
        if _PRODUCTION_READY_PRETENSE_RE.search(text) and "production" not in {
            p.lower() for p in target.parts
        }:
            # Allow discussing production rules in README under production/;
            # refuse readiness pretenses in sample maps / contracts.
            if target.name in {"UPSTREAM_CONTRACT.json"} or "maps" in target.parts:
                pretenses.append(f"{target}: production-ready language in sample surface")

    report.add(
        "claims_locked",
        not claim_problems,
        "ok" if not claim_problems else "; ".join(claim_problems),
    )
    report.add(
        "sample_contract_present",
        sample_seen,
        f"found {SAMPLE_CONTRACT_ID} (or SAMPLE_ADAPTER_CONTRACT_ID)"
        if sample_seen
        else "missing sample adapter contract id",
    )
    report.add(
        "no_fake_production_ready",
        not production_problems and not pretenses,
        "ok"
        if not production_problems and not pretenses
        else "; ".join(production_problems + pretenses),
    )
    return report


def check_registry(
    registry_path: Path = DEFAULT_REGISTRY,
    schema_path: Path = DEFAULT_SCHEMA,
) -> CompatibilityReport:
    report = CompatibilityReport(target=str(registry_path))
    if not registry_path.is_file():
        report.add("registry_exists", False, f"missing {registry_path}")
        return report
    if not schema_path.is_file():
        report.add("schema_exists", False, f"missing {schema_path}")
        return report
    report.add("registry_exists", True, registry_path.name)
    report.add("schema_exists", True, schema_path.name)

    data = _load_json(registry_path)
    schema = _load_json(schema_path)
    errors = validate_json_schema(data, schema)
    report.add(
        "schema_valid",
        not errors,
        "ok" if not errors else "; ".join(errors[:12]),
    )
    if isinstance(data, dict):
        freeze = data.get("schema_freeze_release")
        report.add(
            "schema_freeze_release",
            freeze == SCHEMA_FREEZE_RELEASE,
            f"schema_freeze_release={freeze!r} (expected {SCHEMA_FREEZE_RELEASE!r})",
        )
        report.add(
            "registry_claims_locked",
            data.get("performance_claims_authorized") is False,
            f"performance_claims_authorized={data.get('performance_claims_authorized')!r}",
        )
        raw_adapters = data.get("adapters")
        adapters: list[object] = raw_adapters if isinstance(raw_adapters, list) else []
        bad_claims = [
            entry.get("slug", "?")
            for entry in adapters
            if isinstance(entry, dict) and entry.get("claims") is not False
        ]
        report.add(
            "entry_claims_locked",
            not bad_claims,
            "ok" if not bad_claims else f"claims not false for: {', '.join(bad_claims)}",
        )
    return report


def resolve_slug(slug: str) -> Path:
    fixtures = ROOT / "fixtures" / slug
    if fixtures.is_dir():
        return fixtures
    adapters = ROOT / "src" / "opencritique_adapters"
    if slug == "coarse":
        return adapters / "contract.py"
    if slug == "openreviewer":
        return adapters / "openreviewer.py"
    raise FileNotFoundError(f"unknown in-tree slug: {slug}")


def report_to_markdown(reports: list[CompatibilityReport]) -> str:
    lines = [
        "## Adapter compatibility check",
        "",
        f"- Schema freeze: `{SCHEMA_FREEZE_RELEASE}`",
        "- Scope: interchange only; scientific performance claims remain locked",
        "",
    ]
    overall = all(report.ok for report in reports)
    lines.append(f"**Result:** `{'PASS' if overall else 'FAIL'}`")
    lines.append("")
    for report in reports:
        lines.append(f"### `{report.target}`")
        lines.append("")
        lines.append("| check | status | detail |")
        lines.append("|---|---|---|")
        for item in report.items:
            status = "PASS" if item.passed else "FAIL"
            detail = item.detail.replace("|", "\\|")
            lines.append(f"| `{item.name}` | {status} | {detail} |")
        lines.append("")
    lines.append(
        "Compatibility is not endorsement of reviewer quality. "
        "Do not unlock claims or fabricate production MANIFESTs."
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check OpenCritique adapter interchange compatibility (claims locked)."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Adapter module, fixture map, fixture directory, or package path",
    )
    parser.add_argument(
        "--slug",
        help="In-tree adapter slug (coarse, openreviewer, …)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        nargs="?",
        const=DEFAULT_REGISTRY,
        default=None,
        help="Validate community-adapters.json (optionally pass a path)",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help="JSON Schema for the community adapters registry",
    )
    parser.add_argument(
        "--markdown-only",
        action="store_true",
        help="Print markdown only (still exit non-zero on failure)",
    )
    args = parser.parse_args(argv)

    reports: list[CompatibilityReport] = []

    if args.registry is not None:
        reports.append(check_registry(args.registry, args.schema))

    targets: list[Path] = []
    if args.slug:
        try:
            targets.append(resolve_slug(args.slug))
        except FileNotFoundError as exc:
            report = CompatibilityReport(target=args.slug)
            report.add("slug_resolve", False, str(exc))
            reports.append(report)
    if args.path is not None:
        targets.append(args.path)

    if not reports and not targets:
        parser.error("provide path, --slug, and/or --registry")

    for target in targets:
        reports.append(check_path(target))

    markdown = report_to_markdown(reports)
    if args.markdown_only:
        print(markdown)
    else:
        print(markdown)
        for report in reports:
            status = "PASS" if report.ok else "FAIL"
            print(f"[{status}] {report.target}", file=sys.stderr)

    return 0 if all(report.ok for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
