"""Sandboxed deterministic Python recomputation."""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
from typing import Any

from .base import VerifierResult, build_verifier_result

_ALLOWED_NODES = (
    ast.Module,
    ast.Assign,
    ast.AnnAssign,
    ast.Expr,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.If,
    ast.IfExp,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Call,
    ast.keyword,
    ast.Return,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Pass,
)

_ALLOWED_FUNCS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "sum": sum,
    "len": len,
    "float": float,
    "int": int,
    "pow": pow,
}
_ALLOWED_MATH = {name: getattr(math, name) for name in ("sqrt", "log", "exp", "fabs")}
_MAX_SOURCE_CHARS = 4000
_MAX_AST_NODES = 256


class _SandboxVisitor(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"disallowed AST node: {type(node).__name__}")
        super().generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name):
            raise ValueError("only simple function calls are allowed")
        if node.func.id not in _ALLOWED_FUNCS and node.func.id not in _ALLOWED_MATH:
            raise ValueError(f"disallowed function: {node.func.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # pragma: no cover
        raise ValueError("attribute access is not allowed")

    def visit_Import(self, node: ast.Import) -> None:  # pragma: no cover
        raise ValueError("imports are not allowed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # pragma: no cover
        raise ValueError("imports are not allowed")


def recompute_python(
    *,
    source: str,
    expected: Any,
    result_name: str = "result",
    verifier_id: str = "python-recompute-v1",
    time_limit_seconds: float = 3.0,
) -> VerifierResult:
    """Execute a tiny arithmetic program with no network and no imports."""
    payload: dict[str, Any] = {
        "source": source,
        "expected": expected,
        "result_name": result_name,
        "time_limit_seconds": time_limit_seconds,
    }
    try:
        if len(source) > _MAX_SOURCE_CHARS:
            raise ValueError("sandbox source exceeds maximum size")
        tree = ast.parse(source, mode="exec")
        if sum(1 for _ in ast.walk(tree)) > _MAX_AST_NODES:
            raise ValueError("sandbox source is too complex")
        runner = """
import json, math, sys
source = sys.stdin.read()
env = {"__builtins__": {}}
env.update({
    "abs": abs, "min": min, "max": max, "round": round, "sum": sum,
    "len": len, "float": float, "int": int, "pow": pow,
    "sqrt": math.sqrt, "log": math.log, "exp": math.exp, "fabs": math.fabs,
})
try:
    compiled = compile(source, "<opencritique-python-sandbox>", "exec")
    exec(compiled, env, env)
    name = sys.argv[1]
    if name not in env:
        raise ValueError(f"sandbox program did not bind {name!r}")
    print(json.dumps({"ok": True, "actual": env[name]}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", runner, result_name],
            input=source,
            capture_output=True,
            text=True,
            timeout=time_limit_seconds,
        )
        if completed.returncode != 0:
            payload["error"] = "sandbox execution timed out"
            return build_verifier_result(
                verifier_id=verifier_id,
                status="error",
                summary="Python sandbox failed to execute",
                payload=payload,
                details={"error": completed.stderr.strip() or "sandbox process failed"},
                error_kind="sandbox_error",
            )
        result = json.loads(
            completed.stdout.strip()
            or '{"ok": false, "error": "sandbox exited without result"}'
        )
        if not result.get("ok"):
            payload["error"] = result["error"]
            return build_verifier_result(
                verifier_id=verifier_id,
                status="error",
                summary=f"Python sandbox rejected or failed: {result['error']}",
                payload=payload,
                details={"error": result["error"]},
                error_kind="sandbox_error",
            )
        actual = result["actual"]
        ok = actual == expected
        payload["actual"] = actual
        return build_verifier_result(
            verifier_id=verifier_id,
            status="pass" if ok else "fail",
            summary=(
                "Python recompute matched expected value"
                if ok
                else f"Python recompute mismatch: got {actual!r}, expected {expected!r}"
            ),
            payload=payload,
            details={"actual": actual, "expected": expected},
        )
    except subprocess.TimeoutExpired:
        payload["error"] = "sandbox execution timed out"
        return build_verifier_result(
            verifier_id=verifier_id,
            status="error",
            summary="Python sandbox timed out",
            payload=payload,
            details={"error": "sandbox execution timed out"},
            error_kind="timeout",
        )
    except Exception as exc:  # noqa: BLE001 — surface as verifier error
        payload["error"] = str(exc)
        return build_verifier_result(
            verifier_id=verifier_id,
            status="error",
            summary=f"Python sandbox rejected or failed: {exc}",
            payload=payload,
            details={"error": str(exc)},
            error_kind="sandbox_error",
        )
