"""Design capability catalog and contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignCapability:
    id: str
    family: str
    name: str
    description: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    validation: tuple[str, ...]
    evidence: tuple[str, ...]
    risk_class: str = "low"


DESIGN_CAPABILITIES: tuple[DesignCapability, ...] = (
    DesignCapability(
        "brand.identity",
        "brand_identity",
        "Brand Identity",
        "Brand strategy and identity systems.",
        ("brief", "brand_context"),
        ("identity_system", "brand_guidelines"),
        ("brand_consistency", "strategic_alignment"),
        ("brand_research",),
    ),
    DesignCapability(
        "brand.logo",
        "logo",
        "Logo Design",
        "Logo concepts, marks, lockups, and usage systems.",
        ("brief", "identity_context"),
        ("logo_assets", "logo_spec"),
        ("legibility", "scalability", "distinctiveness"),
        ("references",),
    ),
    DesignCapability(
        "brand.typography",
        "typography",
        "Typography",
        "Type selection, hierarchy, pairing, and systems.",
        ("content", "brand_context"),
        ("type_system", "typography_spec"),
        ("hierarchy", "readability", "consistency"),
        ("type_references",),
    ),
    DesignCapability(
        "brand.color",
        "color",
        "Color",
        "Color systems, palettes, semantic roles, and accessibility.",
        ("brand_context", "visual_goal"),
        ("color_system", "palette"),
        ("contrast", "harmony", "semantic_consistency"),
        ("color_research",),
    ),
    DesignCapability(
        "uiux.design",
        "ui_ux",
        "UI/UX Design",
        "Interface structure, interaction, layout, and experience design.",
        ("requirements", "content", "brand_context"),
        ("wireframes", "ui_design", "ux_spec"),
        ("usability", "accessibility", "responsive_integrity"),
        ("ux_research",),
    ),
    DesignCapability(
        "ui.design_system",
        "design_systems",
        "Design Systems",
        "Reusable tokens, components, patterns, and usage rules.",
        ("product_context", "brand_context"),
        ("tokens", "components", "guidelines"),
        ("consistency", "coverage", "accessibility"),
        ("component_evidence",),
    ),
    DesignCapability(
        "visual.image_generation",
        "image_generation",
        "Image Generation",
        "Generate visual assets from governed design intent.",
        ("prompt", "context", "references"),
        ("image", "image_set"),
        ("composition", "prompt_fidelity", "brand_fidelity"),
        ("generation_metadata",),
    ),
    DesignCapability(
        "visual.image_editing",
        "image_editing",
        "Image Editing",
        "Controlled transformation, cleanup, compositing, and retouching.",
        ("image", "edit_spec"),
        ("edited_image",),
        ("edit_fidelity", "artifact_check", "subject_integrity"),
        ("source_asset", "edit_trace"),
    ),
    DesignCapability(
        "visual.video",
        "video",
        "Video",
        "Video concepting, generation, assembly, and finishing.",
        ("brief", "script", "visual_context"),
        ("video", "storyboard"),
        ("continuity", "timing", "brief_fidelity"),
        ("shot_evidence",),
    ),
    DesignCapability(
        "visual.motion",
        "motion",
        "Motion Design",
        "Motion graphics, transitions, animation, and temporal systems.",
        ("design_spec", "timing_spec"),
        ("motion_asset", "animation_spec"),
        ("timing", "readability", "system_consistency"),
        ("motion_reference",),
    ),
    DesignCapability(
        "production.packaging",
        "packaging",
        "Packaging",
        "Packaging structure, graphics, labeling, and production-ready artwork.",
        ("brand_context", "dieline", "content"),
        ("packaging_artwork", "production_spec"),
        ("dieline_integrity", "legibility", "print_readiness"),
        ("production_requirements",),
    ),
    DesignCapability(
        "production.print",
        "print",
        "Print",
        "Print collateral and production artwork.",
        ("content", "design_spec", "print_spec"),
        ("print_artwork", "proof"),
        ("bleed", "resolution", "color_mode", "typography"),
        ("printer_spec",),
    ),
    DesignCapability(
        "production.signage",
        "signage",
        "Signage",
        "Environmental, wayfinding, and promotional signage.",
        ("location_context", "brand_context", "message"),
        ("signage_artwork",),
        ("distance_readability", "scale", "placement"),
        ("site_constraints",),
    ),
    DesignCapability(
        "production.presentation",
        "presentations",
        "Presentations",
        "Narrative, slide systems, layouts, and presentation assets.",
        ("story", "content", "brand_context"),
        ("deck", "slide_system"),
        ("narrative_flow", "readability", "consistency"),
        ("content_sources",),
    ),
    DesignCapability(
        "marketing.social",
        "social_content",
        "Social Content",
        "Platform-aware social graphics, campaigns, and content systems.",
        ("campaign", "platform", "brand_context"),
        ("social_assets", "content_variants"),
        ("platform_fit", "message_clarity", "brand_consistency"),
        ("platform_spec",),
    ),
    DesignCapability(
        "production.preflight",
        "production_preflight",
        "Production Preflight",
        "Automated and rule-based checks before production or delivery.",
        ("asset", "production_spec"),
        ("preflight_report",),
        ("file_integrity", "dimensions", "color", "fonts", "safe_area"),
        ("production_spec",),
    ),
    DesignCapability(
        "quality.visual_qa",
        "visual_qa",
        "Visual QA",
        "Visual comparison, defect detection, and quality assessment.",
        ("reference", "candidate", "acceptance_criteria"),
        ("qa_report", "defect_list"),
        ("visual_fidelity", "layout", "typography", "color", "artifact_detection"),
        ("reference_asset", "comparison_trace"),
    ),
)


def get_capability(capability_id: str) -> DesignCapability:
    for capability in DESIGN_CAPABILITIES:
        if capability.id == capability_id:
            return capability
    raise KeyError(capability_id)


def list_capabilities(family: str | None = None) -> tuple[DesignCapability, ...]:
    if family is None:
        return DESIGN_CAPABILITIES
    return tuple(c for c in DESIGN_CAPABILITIES if c.family == family)
