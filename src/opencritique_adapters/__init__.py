"""Production adapters for external reviewer outputs."""

from .coarse import CoarseReview, convert_coarse_benchmark
from .contract import (
    COARSE_PERFORMANCE_CLAIMS_AUTHORIZED,
    COARSE_UPSTREAM_CONTRACT_VERSION,
)
from .coarse_loss import CoarseConversionLossReport, build_conversion_loss_report
from .openreviewer import OpenReviewerReview, convert_openreviewer_benchmark

__all__ = [
    "COARSE_PERFORMANCE_CLAIMS_AUTHORIZED",
    "COARSE_UPSTREAM_CONTRACT_VERSION",
    "CoarseConversionLossReport",
    "CoarseReview",
    "OpenReviewerReview",
    "build_conversion_loss_report",
    "convert_coarse_benchmark",
    "convert_openreviewer_benchmark",
]
