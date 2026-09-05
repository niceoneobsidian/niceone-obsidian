"""Compatibility boundary exposing canonical Social Growth kernel capabilities."""

from ois.domains.social_growth.kernel_integration import (
    SocialIngestCapability,
    SocialResearchCapability,
    register_social_kernel_capabilities,
)

__all__ = [
    "SocialIngestCapability",
    "SocialResearchCapability",
    "register_social_kernel_capabilities",
]
