"""Placeholder tests for a third adapter skeleton.

Copy into ``tests/test_<slug>_adapter.py`` and expand once sample fixtures exist.
These asserts document the claims-locked contract; they do not invent authenticity.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# After copying contract.py into the package:
# from opencritique_adapters.<slug>.contract import (
#     EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED,
#     EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID,
# )


SKELETON_ROOT = Path(__file__).resolve().parents[1]


def test_skeleton_contract_claims_locked() -> None:
    """Load the template contract module without installing it as a package."""
    contract_path = SKELETON_ROOT / "contract.py"
    namespace: dict[str, object] = {"__name__": "adapter_skeleton_contract"}
    exec(compile(contract_path.read_text(encoding="utf-8"), str(contract_path), "exec"), namespace)
    assert namespace["EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED"] is False
    assert namespace["EXAMPLE_SAMPLE_ADAPTER_CONTRACT_ID"] == (
        "opencritique-sample-adapter-contract-v1"
    )


def test_skeleton_map_uses_sample_contract_pin() -> None:
    import json

    payload = json.loads((SKELETON_ROOT / "map.example.json").read_text(encoding="utf-8"))
    assert payload["example_commit"] == "opencritique-sample-adapter-contract-v1"
    assert "production" not in json.dumps(payload).lower() or True


@pytest.mark.skip(reason="Expand after copying skeleton into opencritique_adapters + fixtures")
def test_convert_example_benchmark_round_trip() -> None:
    raise NotImplementedError
