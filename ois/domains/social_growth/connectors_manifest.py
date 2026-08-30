"""Platform connector inventory.

Only the contract and capability declarations belong in the domain package.
Credentials and vendor-specific HTTP clients are intentionally externalized.
"""

SOCIAL_PLATFORMS = {
    "tiktok": {"read_events", "publish", "analytics"},
    "instagram": {"read_events", "publish", "analytics"},
    "facebook": {"read_events", "publish", "analytics"},
    "x": {"read_events", "publish", "analytics"},
    "linkedin": {"read_events", "publish", "analytics"},
    "youtube": {"read_events", "publish", "analytics"},
    "pinterest": {"read_events", "publish", "analytics"},
    "reddit": {"read_events", "analytics"},
    "threads": {"read_events", "publish", "analytics"},
    "telegram": {"read_events", "publish"},
    "whatsapp": {"read_events", "publish"},
}


def connector_manifest() -> list[dict[str, object]]:
    return [
        {"platform": platform, "capabilities": sorted(capabilities), "status": "adapter_contract"}
        for platform, capabilities in sorted(SOCIAL_PLATFORMS.items())
    ]
