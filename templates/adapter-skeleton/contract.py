"""Pinned sample-adapter contract metadata for a third upstream skeleton.

Replace EXAMPLE_* names with your adapter slug. Do not invent a pretend Git SHA
or set performance claims authorized.
"""

from __future__ import annotations

from typing import Final

EXAMPLE_UPSTREAM_CONTRACT_VERSION: Final[str] = "example-review-contract-v1"
EXAMPLE_UPSTREAM_REPOSITORY: Final[str] = "https://example.invalid/your-upstream"
EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID: Final[str] = "opencritique-sample-adapter-contract-v1"
# Alias used by maps / SystemManifest.code_commit for sample fixtures.
EXAMPLE_UPSTREAM_COMMIT_PIN: Final[str] = EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID
EXAMPLE_FIXTURE_KIND: Final[str] = "maintainer_owned_sample_corpus"
EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED: Final[bool] = False

EXAMPLE_CONTRACT_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "review": (
        "title",
        "findings",
    ),
    "finding": (
        "finding_id",
        "title",
        "body",
        "quote",
    ),
}
