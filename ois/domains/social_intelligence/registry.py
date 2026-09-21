"""Social Intelligence provider/tool registry bindings."""

from __future__ import annotations

from ois.kernel.contracts import (
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
    ToolContract,
)
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.registries.tool_registry import ToolRegistry

from .providers import BundleSocialAdapter, ProviderError, SociaVaultAdapter
from .schemas import SocialPublishRequest


class SociaVaultTool:
    contract = ToolContract(
        capability_id="tool.social.sociavault",
        version="1.0.0",
        description="Read social intelligence data through SociaVault.",
        input_schema={"type": "object", "required": ["operation"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        permissions=("social.read",),
        allowed_domains=("social_intelligence",),
        timeout_seconds=30.0,
        max_retries=2,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        network_policy={"allowlist": ["api.sociavault.com"]},
        secrets_required=("SOCIAVAULT_API_KEY",),
    )

    def __init__(self, adapter: SociaVaultAdapter) -> None:
        self.adapter = adapter

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        try:
            operation = request.input.get("operation")
            if operation == "tiktok_profile":
                output = self.adapter.tiktok_profile(
                    str(request.input["handle"])
                ).model_dump(mode="json")
            elif operation == "tiktok_search":
                output = self.adapter.tiktok_search(
                    str(request.input["query"]),
                    str(request.input.get("kind", "keyword")),
                ).model_dump(mode="json")
            else:
                raise ValueError(f"unsupported operation: {operation}")

            return InvocationResult(
                request.invocation_id,
                self.contract.capability_id,
                InvocationStatus.SUCCEEDED,
                output=output,
            )
        except (KeyError, ValueError, ProviderError) as exc:
            return InvocationResult(
                request.invocation_id,
                self.contract.capability_id,
                InvocationStatus.FAILED,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )


class BundleSocialTool:
    contract = ToolContract(
        capability_id="tool.social.bundle_social",
        version="1.0.0",
        description="Publish and read social analytics through bundle.social.",
        input_schema={"type": "object", "required": ["operation"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.HIGH,
        permissions=("social.publish", "social.analytics"),
        allowed_domains=("social_intelligence", "social_growth"),
        timeout_seconds=60.0,
        max_retries=0,
        side_effects=SideEffectLevel.IRREVERSIBLE,
        idempotent=False,
        network_policy={"allowlist": ["api.bundle.social"]},
        secrets_required=("BUNDLE_SOCIAL_API_KEY",),
        requires_approval=True,
    )

    def __init__(self, adapter: BundleSocialAdapter) -> None:
        self.adapter = adapter

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        try:
            operation = request.input.get("operation")
            if operation == "analytics":
                output = self.adapter.post_analytics(
                    str(request.input["post_id"]),
                    str(request.input["platform"]),
                ).model_dump(mode="json")
            elif operation == "create_post":
                output = self.adapter.create_post(
                    SocialPublishRequest.model_validate(
                        request.input["request"]
                    )
                ).model_dump(mode="json")
            else:
                raise ValueError(f"unsupported operation: {operation}")

            return InvocationResult(
                request.invocation_id,
                self.contract.capability_id,
                InvocationStatus.SUCCEEDED,
                output=output,
            )
        except (KeyError, ValueError, ProviderError) as exc:
            return InvocationResult(
                request.invocation_id,
                self.contract.capability_id,
                InvocationStatus.FAILED,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )


def build_social_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "tool.social.sociavault",
        "1.0.0",
        SociaVaultTool(SociaVaultAdapter()),
        metadata={
            "provider": "sociavault",
            "status": "configured_unverified",
        },
    )
    registry.register(
        "tool.social.bundle_social",
        "1.0.0",
        BundleSocialTool(BundleSocialAdapter()),
        metadata={
            "provider": "bundle.social",
            "status": "configured_unverified",
        },
    )
    return registry


def provider_capability_contracts() -> tuple[CapabilityContract, ...]:
    return (
        CapabilityContract(
            capability_id="social.intelligence.sociavault.profile",
            version="1.0.0",
            description="Retrieve a normalized TikTok profile from SociaVault.",
            input_schema={
                "type": "object",
                "required": ["handle"],
            },
            output_schema={"$ref": "SocialProfile"},
            permissions=("social.read",),
            allowed_domains=("social_intelligence",),
        ),
        CapabilityContract(
            capability_id="social.intelligence.sociavault.search",
            version="1.0.0",
            description=(
                "Search TikTok users, hashtags, keywords, or top results "
                "through SociaVault."
            ),
            input_schema={
                "type": "object",
                "required": ["query"],
            },
            output_schema={"$ref": "SocialSearchResult"},
            permissions=("social.read",),
            allowed_domains=("social_intelligence",),
        ),
        CapabilityContract(
            capability_id="social.distribution.bundle_social.publish",
            version="1.0.0",
            description=(
                "Create a draft, scheduled, or publishable social post "
                "through bundle.social."
            ),
            input_schema={"$ref": "SocialPublishRequest"},
            output_schema={"$ref": "SocialPublishResult"},
            risk_level=RiskLevel.HIGH,
            permissions=("social.publish",),
            allowed_domains=("social_growth", "social_intelligence"),
            side_effects=SideEffectLevel.IRREVERSIBLE,
            idempotent=False,
        ),
        CapabilityContract(
            capability_id="social.analytics.bundle_social.post",
            version="1.0.0",
            description=(
                "Retrieve normalized post analytics through bundle.social."
            ),
            input_schema={
                "type": "object",
                "required": ["post_id", "platform"],
            },
            output_schema={"$ref": "SocialAnalytics"},
            permissions=("social.analytics",),
            allowed_domains=("social_intelligence",),
        ),
    )
