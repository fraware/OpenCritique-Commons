"""Optional live upstream runners (Coarse / OpenReviewer).

Private live runs are operator-local evidence. They do not authorize scientific
performance claims and must not auto-promote into fixtures/*/production/.
"""

from __future__ import annotations

from .coarse import CoarseRunnerPlugin, coarse_runner_plugin
from .env import (
    apply_openai_byok_alias,
    load_operator_env,
    require_byok_api_key,
    resolve_byok_api_key,
)
from .openreviewer import (
    OPENREVIEWER_HF_MODEL_ID,
    OPENREVIEWER_UPSTREAM_REPOSITORY,
    OpenReviewerLiveExport,
    OpenReviewerProvenance,
    OpenReviewerRunnerPlugin,
    import_openreviewer_export,
    openreviewer_runner_plugin,
    write_openreviewer_live_export,
)
from .protocol import LiveRunnerPlugin, RunnerRunResult
from .provenance import COARSE_LIVE_COMMIT_PIN, LiveProvenance

__all__ = [
    "COARSE_LIVE_COMMIT_PIN",
    "CoarseRunnerPlugin",
    "LiveProvenance",
    "LiveRunnerPlugin",
    "OPENREVIEWER_HF_MODEL_ID",
    "OPENREVIEWER_UPSTREAM_REPOSITORY",
    "OpenReviewerLiveExport",
    "OpenReviewerProvenance",
    "OpenReviewerRunnerPlugin",
    "RunnerRunResult",
    "apply_openai_byok_alias",
    "coarse_runner_plugin",
    "import_openreviewer_export",
    "load_operator_env",
    "openreviewer_runner_plugin",
    "require_byok_api_key",
    "resolve_byok_api_key",
    "write_openreviewer_live_export",
]
