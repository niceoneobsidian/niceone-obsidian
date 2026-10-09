"""Production-shaped brand.identity Design Intelligence capability."""

from .contracts import (
    BrandContext,
    BrandDiagnosis,
    BrandIdentity,
    BrandIdentityIntent,
    BrandStrategy,
    DesignTerritory,
    IdentityEvaluation,
    ValidationResult,
)
from .provider import BrandIdentityProvider, build_brand_identity_provider
from .workflow import BrandIdentityWorkflow

__all__ = [
    "BrandContext",
    "BrandDiagnosis",
    "BrandIdentity",
    "BrandIdentityIntent",
    "BrandIdentityProvider",
    "BrandIdentityWorkflow",
    "BrandStrategy",
    "DesignTerritory",
    "IdentityEvaluation",
    "ValidationResult",
    "build_brand_identity_provider",
]
