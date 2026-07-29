"""Runner plugin contract for optional live upstream runners.

Coarse and OpenReviewer implement this protocol via thin adapter classes.
Optional extras stay ``[live-coarse]`` / ``[live-openreviewer]`` in pyproject.
Private live outputs must refuse ``fixtures/*/production/`` paths and keep
``performance_claims_authorized=false``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RunnerRunResult:
    """Normalized result of ``LiveRunnerPlugin.run``.

    ``review`` is the upstream-shaped review model (e.g. ``CoarseReview`` or
    ``OpenReviewerLiveExport``). ``provenance`` carries live evidence metadata
    and must keep claims locked. ``markdown`` is the rendered review text when
    available (empty string when the upstream path has none).
    """

    review: Any
    provenance: Any
    markdown: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


@runtime_checkable
class LiveRunnerPlugin(Protocol):
    """Contract for a fourth (or later) live runner plugin.

    Implementations must:

    - return private-live evidence only (never production authenticity);
    - refuse writes under ``fixtures/*/production/`` (use ``paths`` helpers);
    - keep ``performance_claims_authorized`` false on provenance / exports;
    - declare an optional ``[live-*]`` extra when heavy deps are required.
    """

    @property
    def name(self) -> str:
        """Stable plugin id (e.g. ``coarse``, ``openreviewer``)."""
        ...

    @property
    def live_extra(self) -> str | None:
        """Optional-dependencies extra name, or ``None`` when import-only."""
        ...

    def run(self, manuscript: Path, **kwargs: Any) -> RunnerRunResult:
        """Invoke upstream (or import path) for ``manuscript``.

        Default CI must not call paid APIs; inject fakes / skip without secrets.
        """
        ...

    def write_export(
        self,
        result: RunnerRunResult,
        output: Path,
        *,
        markdown_output: Path | None = None,
    ) -> Path:
        """Serialize ``result``; refuse production fixture paths."""
        ...
