"""Deterministic matching, scoring, sensitivity analysis, and signed scorecards."""

from .engine import MATCHER_VERSION, evaluate, load_case, load_manifest
from .models import (
    BenchmarkManifest,
    ClaimAuthorization,
    ClaimScope,
    EvaluationResult,
    EvaluationSubmission,
    MatcherConfig,
    NovelConcernDetermination,
    PublicScorecard,
    SignedScorecardEnvelope,
)
from .novel import build_novel_queue
from .novel_determination import (
    NOVEL_POLICY_VERSION,
    determine_novel,
    outcome_affects_precision_recall,
)
from .scorecard import build_scorecard

__all__ = [
    "MATCHER_VERSION",
    "NOVEL_POLICY_VERSION",
    "BenchmarkManifest",
    "ClaimAuthorization",
    "ClaimScope",
    "EvaluationResult",
    "EvaluationSubmission",
    "MatcherConfig",
    "NovelConcernDetermination",
    "PublicScorecard",
    "SignedScorecardEnvelope",
    "build_novel_queue",
    "build_scorecard",
    "determine_novel",
    "evaluate",
    "load_case",
    "load_manifest",
    "outcome_affects_precision_recall",
]

__version__ = "0.5.0a1"
