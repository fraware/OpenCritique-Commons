"""Pinned sample-adapter contract metadata.

Fixtures are derived from maintainer-owned open samples under corpus/samples/.
They exercise the public Coarse Review / DetailedComment shape without claiming
a genuine upstream Coarse production run. No pretend Git SHA is recorded.
"""

from __future__ import annotations

from typing import Final

# Public Review/DetailedComment contract shape exercised by the adapter.
COARSE_UPSTREAM_CONTRACT_VERSION: Final[str] = "coarse-review-contract-v1"
COARSE_UPSTREAM_REPOSITORY: Final[str] = "https://github.com/Davidvandijcke/coarse"
# Project-local contract id (not an upstream Git commit). Genuine production
# Coarse export pins belong on issue #3 when real runs are available.
COARSE_SAMPLE_ADAPTER_CONTRACT_ID: Final[str] = "opencritique-sample-adapter-contract-v1"
# Backward-compatible alias used by maps / SystemManifest.code_commit.
COARSE_UPSTREAM_COMMIT_PIN: Final[str] = COARSE_SAMPLE_ADAPTER_CONTRACT_ID
COARSE_FIXTURE_KIND: Final[str] = "maintainer_owned_sample_corpus"
COARSE_PERFORMANCE_CLAIMS_AUTHORIZED: Final[bool] = False

COARSE_CONTRACT_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "review": (
        "title",
        "domain",
        "taxonomy",
        "date",
        "overall_feedback",
        "detailed_comments",
        "language",
    ),
    "overall_feedback": (
        "summary",
        "assessment",
        "issues",
        "recommendation",
        "revision_targets",
    ),
    "detailed_comment": (
        "number",
        "title",
        "quote",
        "feedback",
        "status",
        "severity",
        "confidence",
    ),
}
