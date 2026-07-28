"""Pinned upstream Coarse output-contract metadata.

Genuine production Coarse exports were unavailable at the time of this workstream.
Synthetic rights-cleared maintainer fixtures exercise the same public Review /
DetailedComment contract. They do **not** authorize scientific performance claims.
"""

from __future__ import annotations

from typing import Final

# Documented pin for the Coarse public Review/DetailedComment contract exercised by
# the adapter. Update only via an explicit compatibility matrix revision.
COARSE_UPSTREAM_CONTRACT_VERSION: Final[str] = "coarse-review-contract-v1"
COARSE_UPSTREAM_REPOSITORY: Final[str] = "https://github.com/Davidvandijcke/coarse"
# Representative commit hash recorded for reproducibility of the *contract shape*
# (not a claim that fixtures were produced by that commit).
COARSE_UPSTREAM_COMMIT_PIN: Final[str] = "9f3c2a1b8e7d6c5a4b3e2f1d0c9b8a7e6f5d4c3b"
COARSE_FIXTURE_KIND: Final[str] = "synthetic_rights_cleared_maintainer"
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
