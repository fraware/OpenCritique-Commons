"""Typed fail-closed errors for production adapter intake (issues #3 / #5)."""

from __future__ import annotations


class ProductionIntakeError(ValueError):
    """Base class for production intake failures (also a ValueError for fail-closed callers)."""

    code: str = "production_intake_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ProductionManifestError(ProductionIntakeError):
    code = "production_manifest_error"


class ProductionHashMismatchError(ProductionIntakeError):
    code = "production_hash_mismatch"


class ProductionRightsBindingError(ProductionIntakeError):
    code = "production_rights_binding"


class ProductionUpstreamPinError(ProductionIntakeError):
    code = "production_upstream_pin"


class ProductionReadyIncompleteError(ProductionIntakeError):
    code = "production_ready_incomplete"


class ProductionClaimsUnauthorizedError(ProductionIntakeError):
    code = "production_claims_unauthorized"


class ProductionSampleContaminationError(ProductionIntakeError):
    code = "production_sample_contamination"


class ProductionPackageUnauthorizedError(ProductionIntakeError):
    code = "production_package_unauthorized"
