"""Complete design capability blueprints.

This module defines the capability-tree layer: family -> sub-capability ->
workflow -> skills -> validators -> evidence -> provider adapter contract.
The blueprints are declarative so concrete providers can be added without
changing the ODI kernel.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ValidatorSpec:
    id: str
    purpose: str
    severity: str = "error"


@dataclass(frozen=True)
class EvidenceSpec:
    id: str
    kind: str
    required: bool = True


@dataclass(frozen=True)
class WorkflowSpec:
    id: str
    stages: tuple[str, ...]
    required_skills: tuple[str, ...]
    validators: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class SubCapabilitySpec:
    id: str
    name: str
    skills: tuple[str, ...]
    workflows: tuple[str, ...]
    validators: tuple[str, ...]
    evidence: tuple[str, ...]
    adapters: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityFamilySpec:
    id: str
    name: str
    sub_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class ProviderAdapterSpec:
    id: str
    capability_pattern: str
    interface: str
    modalities: tuple[str, ...]


# ---------------------------------------------------------------------------
# Shared validators, evidence, and provider contracts
# ---------------------------------------------------------------------------
VALIDATORS = {
    "brief_alignment": ValidatorSpec(
        "brief_alignment", "Checks output against explicit brief and acceptance criteria."
    ),
    "brand_consistency": ValidatorSpec(
        "brand_consistency", "Checks alignment with approved brand tokens and identity rules."
    ),
    "accessibility": ValidatorSpec(
        "accessibility", "Checks applicable accessibility requirements."
    ),
    "legibility": ValidatorSpec(
        "legibility", "Checks readable type, contrast, scale, and viewing conditions."
    ),
    "layout_integrity": ValidatorSpec(
        "layout_integrity", "Checks composition, spacing, alignment, and hierarchy."
    ),
    "asset_integrity": ValidatorSpec(
        "asset_integrity", "Checks files, dimensions, encoding, corruption, and required assets."
    ),
    "visual_fidelity": ValidatorSpec(
        "visual_fidelity", "Compares candidate against references and acceptance criteria."
    ),
    "production_preflight": ValidatorSpec(
        "production_preflight", "Checks production constraints before release."
    ),
    "content_integrity": ValidatorSpec(
        "content_integrity", "Checks text, data, labels, and required content."
    ),
    "platform_fit": ValidatorSpec("platform_fit", "Checks channel/platform-specific constraints."),
    "motion_integrity": ValidatorSpec(
        "motion_integrity", "Checks timing, transitions, continuity, and temporal readability."
    ),
    "story_integrity": ValidatorSpec(
        "story_integrity", "Checks narrative order, continuity, and message progression."
    ),
    "dieline_integrity": ValidatorSpec(
        "dieline_integrity", "Checks artwork against packaging structure and cut/fold constraints."
    ),
    "type_integrity": ValidatorSpec(
        "type_integrity", "Checks typography hierarchy, font availability, and rendering."
    ),
    "color_integrity": ValidatorSpec(
        "color_integrity", "Checks palette roles, contrast, and production color constraints."
    ),
    "qa_gate": ValidatorSpec(
        "qa_gate", "Aggregates required quality gates and determines pass/fail."
    ),
}

EVIDENCE = {
    "brief": EvidenceSpec("brief", "source_brief"),
    "brand_research": EvidenceSpec("brand_research", "research"),
    "reference_assets": EvidenceSpec("reference_assets", "reference"),
    "design_rationale": EvidenceSpec("design_rationale", "decision"),
    "design_tokens": EvidenceSpec("design_tokens", "knowledge"),
    "content_source": EvidenceSpec("content_source", "source"),
    "generation_trace": EvidenceSpec("generation_trace", "execution_trace"),
    "edit_trace": EvidenceSpec("edit_trace", "execution_trace"),
    "render_trace": EvidenceSpec("render_trace", "execution_trace"),
    "validation_report": EvidenceSpec("validation_report", "validation"),
    "visual_comparison": EvidenceSpec("visual_comparison", "comparison"),
    "production_spec": EvidenceSpec("production_spec", "constraint"),
    "platform_spec": EvidenceSpec("platform_spec", "constraint"),
    "approval": EvidenceSpec("approval", "authorization", required=False),
}

ADAPTERS = {
    "llm": ProviderAdapterSpec("llm", "*", "TextModelProvider", ("text", "reasoning")),
    "image_generation": ProviderAdapterSpec(
        "image_generation", "visual.image_generation", "ImageGenerationProvider", ("image",)
    ),
    "image_editing": ProviderAdapterSpec(
        "image_editing", "visual.image_editing", "ImageEditingProvider", ("image",)
    ),
    "video_generation": ProviderAdapterSpec(
        "video_generation", "visual.video", "VideoProvider", ("video",)
    ),
    "motion_renderer": ProviderAdapterSpec(
        "motion_renderer", "visual.motion", "MotionProvider", ("motion",)
    ),
    "design_renderer": ProviderAdapterSpec(
        "design_renderer",
        "ui.*|brand.*|marketing.*",
        "DesignRendererProvider",
        ("vector", "raster", "document"),
    ),
    "document_renderer": ProviderAdapterSpec(
        "document_renderer",
        "production.presentation|production.print",
        "DocumentRendererProvider",
        ("pdf", "presentation", "document"),
    ),
    "production_tool": ProviderAdapterSpec(
        "production_tool", "production.*", "ProductionProvider", ("preflight", "print", "packaging")
    ),
    "vision_qa": ProviderAdapterSpec(
        "vision_qa",
        "quality.visual_qa|production.preflight",
        "VisionQAProvider",
        ("vision", "comparison"),
    ),
}


# ---------------------------------------------------------------------------
# Declarative capability tree
# ---------------------------------------------------------------------------
def S(
    id: str,
    name: str,
    skills: tuple[str, ...],
    workflows: tuple[str, ...],
    validators: tuple[str, ...],
    evidence: tuple[str, ...],
    adapters: tuple[str, ...],
) -> SubCapabilitySpec:
    return SubCapabilitySpec(id, name, skills, workflows, validators, evidence, adapters)


def W(
    id: str,
    stages: tuple[str, ...],
    skills: tuple[str, ...],
    validators: tuple[str, ...],
    evidence: tuple[str, ...],
) -> WorkflowSpec:
    return WorkflowSpec(id, stages, skills, validators, evidence)


SUBCAPABILITIES = {
    # Brand identity
    "brand.strategy": S(
        "brand.strategy",
        "Brand Strategy",
        ("brand_research", "positioning", "audience_modeling", "brand_architecture"),
        ("brand.strategy.develop",),
        ("brief_alignment", "brand_consistency"),
        ("brief", "brand_research", "design_rationale"),
        ("llm",),
    ),
    "brand.identity_system": S(
        "brand.identity_system",
        "Identity System",
        ("identity_direction", "visual_language", "identity_rules", "brand_guidelines"),
        ("brand.identity.build",),
        ("brand_consistency", "layout_integrity", "color_integrity", "type_integrity"),
        ("brand_research", "design_tokens", "design_rationale", "validation_report"),
        ("llm", "design_renderer"),
    ),
    "brand.logo_system": S(
        "brand.logo_system",
        "Logo System",
        ("mark_development", "lockups", "clear_space", "usage_rules"),
        ("brand.logo.develop",),
        ("brief_alignment", "legibility", "brand_consistency", "visual_fidelity"),
        ("brief", "reference_assets", "design_rationale", "visual_comparison"),
        ("llm", "design_renderer", "vision_qa"),
    ),
    "brand.typography_system": S(
        "brand.typography_system",
        "Typography System",
        ("type_selection", "pairing", "hierarchy", "responsive_type"),
        ("brand.typography.define",),
        ("legibility", "type_integrity", "brand_consistency"),
        ("brand_research", "design_tokens", "validation_report"),
        ("llm", "design_renderer"),
    ),
    "brand.color_system": S(
        "brand.color_system",
        "Color System",
        ("palette_development", "semantic_roles", "contrast_mapping", "production_color"),
        ("brand.color.define",),
        ("color_integrity", "accessibility", "brand_consistency"),
        ("brand_research", "design_tokens", "validation_report"),
        ("llm", "design_renderer"),
    ),
    # Digital
    "uiux.information_architecture": S(
        "uiux.information_architecture",
        "Information Architecture",
        ("user_flows", "navigation", "content_structure", "task_mapping"),
        ("uiux.flow.design",),
        ("brief_alignment", "accessibility", "layout_integrity"),
        ("brief", "content_source", "design_rationale"),
        ("llm",),
    ),
    "uiux.interface_design": S(
        "uiux.interface_design",
        "Interface Design",
        ("wireframing", "layout", "interaction", "responsive_design"),
        ("uiux.interface.build",),
        ("layout_integrity", "accessibility", "brand_consistency", "visual_fidelity"),
        ("brief", "design_tokens", "reference_assets", "visual_comparison"),
        ("llm", "design_renderer", "vision_qa"),
    ),
    "uiux.prototype": S(
        "uiux.prototype",
        "Prototype",
        ("interaction_prototyping", "state_design", "microinteraction"),
        ("uiux.prototype.build",),
        ("accessibility", "brief_alignment", "visual_fidelity"),
        ("brief", "design_rationale", "validation_report"),
        ("llm", "design_renderer"),
    ),
    "system.tokens": S(
        "system.tokens",
        "Design Tokens",
        ("token_modeling", "semantic_tokens", "theme_tokens", "export_mapping"),
        ("system.tokens.build",),
        ("brand_consistency", "type_integrity", "color_integrity"),
        ("design_tokens", "design_rationale"),
        ("llm", "design_renderer"),
    ),
    "system.components": S(
        "system.components",
        "Component System",
        ("component_architecture", "variants", "states", "documentation"),
        ("system.components.build",),
        ("layout_integrity", "accessibility", "brand_consistency"),
        ("design_tokens", "validation_report"),
        ("llm", "design_renderer"),
    ),
    "system.patterns": S(
        "system.patterns",
        "Pattern Library",
        ("pattern_composition", "content_patterns", "responsive_patterns"),
        ("system.patterns.build",),
        ("layout_integrity", "accessibility", "brand_consistency"),
        ("design_tokens", "reference_assets", "validation_report"),
        ("llm", "design_renderer"),
    ),
    # Visual generation
    "image.concept_generation": S(
        "image.concept_generation",
        "Concept Generation",
        ("prompt_engineering", "composition_direction", "style_direction", "reference_control"),
        ("image.generate.concept",),
        ("brief_alignment", "visual_fidelity", "asset_integrity"),
        ("brief", "reference_assets", "generation_trace"),
        ("llm", "image_generation", "vision_qa"),
    ),
    "image.production_generation": S(
        "image.production_generation",
        "Production Image Generation",
        ("composition", "art_direction", "lighting", "material_direction", "format_control"),
        ("image.generate.production",),
        ("brief_alignment", "brand_consistency", "visual_fidelity", "asset_integrity"),
        ("brief", "generation_trace", "visual_comparison"),
        ("llm", "image_generation", "vision_qa"),
    ),
    "image.retouching": S(
        "image.retouching",
        "Retouching",
        ("cleanup", "masking", "color_correction", "artifact_removal"),
        ("image.edit.retouch",),
        ("asset_integrity", "visual_fidelity", "color_integrity"),
        ("reference_assets", "edit_trace", "validation_report"),
        ("image_editing", "vision_qa"),
    ),
    "image.compositing": S(
        "image.compositing",
        "Compositing",
        ("layering", "masking", "perspective_matching", "lighting_matching"),
        ("image.edit.composite",),
        ("visual_fidelity", "layout_integrity", "asset_integrity"),
        ("reference_assets", "edit_trace", "visual_comparison"),
        ("image_editing", "vision_qa"),
    ),
    # Video/motion
    "video.preproduction": S(
        "video.preproduction",
        "Video Preproduction",
        ("concepting", "scripting", "storyboarding", "shot_planning"),
        ("video.plan",),
        ("brief_alignment", "story_integrity"),
        ("brief", "content_source", "design_rationale"),
        ("llm",),
    ),
    "video.generation": S(
        "video.generation",
        "Video Generation",
        ("prompt_chaining", "shot_generation", "continuity_control", "camera_direction"),
        ("video.generate",),
        ("story_integrity", "motion_integrity", "visual_fidelity"),
        ("brief", "generation_trace", "visual_comparison"),
        ("llm", "video_generation", "vision_qa"),
    ),
    "video.editing": S(
        "video.editing",
        "Video Editing",
        ("assembly", "timing", "transitions", "sound_sync"),
        ("video.edit",),
        ("story_integrity", "motion_integrity", "asset_integrity"),
        ("content_source", "render_trace", "validation_report"),
        ("video_generation", "motion_renderer", "vision_qa"),
    ),
    "motion.graphics": S(
        "motion.graphics",
        "Motion Graphics",
        ("animation", "kinetics", "transitions", "motion_systems"),
        ("motion.build",),
        ("motion_integrity", "brand_consistency", "legibility"),
        ("design_tokens", "reference_assets", "render_trace"),
        ("motion_renderer", "design_renderer", "vision_qa"),
    ),
    # Production
    "packaging.structure": S(
        "packaging.structure",
        "Packaging Structure",
        ("dieline_reading", "panel_mapping", "structural_constraints"),
        ("packaging.structure.plan",),
        ("dieline_integrity", "production_preflight"),
        ("brief", "production_spec", "reference_assets"),
        ("production_tool",),
    ),
    "packaging.artwork": S(
        "packaging.artwork",
        "Packaging Artwork",
        ("panel_design", "label_design", "regulatory_content", "print_artwork"),
        ("packaging.artwork.build",),
        ("dieline_integrity", "brand_consistency", "legibility", "production_preflight"),
        ("production_spec", "content_source", "validation_report"),
        ("design_renderer", "production_tool", "vision_qa"),
    ),
    "print.collateral": S(
        "print.collateral",
        "Print Collateral",
        ("layout", "prepress", "print_color", "proofing"),
        ("print.artwork.build",),
        ("production_preflight", "legibility", "color_integrity", "asset_integrity"),
        ("brief", "production_spec", "render_trace"),
        ("design_renderer", "document_renderer", "production_tool"),
    ),
    "signage.environmental": S(
        "signage.environmental",
        "Environmental Signage",
        ("wayfinding", "scale", "distance_readability", "placement"),
        ("signage.system.build",),
        ("legibility", "brand_consistency", "production_preflight"),
        ("brief", "production_spec", "reference_assets"),
        ("design_renderer", "production_tool", "vision_qa"),
    ),
    "presentation.narrative": S(
        "presentation.narrative",
        "Presentation Narrative",
        ("storytelling", "slide_architecture", "content_prioritization"),
        ("presentation.narrative.build",),
        ("brief_alignment", "story_integrity", "content_integrity"),
        ("brief", "content_source", "design_rationale"),
        ("llm",),
    ),
    "presentation.design": S(
        "presentation.design",
        "Presentation Design",
        ("slide_layout", "data_visualization", "template_system", "export"),
        ("presentation.design.build",),
        ("layout_integrity", "legibility", "brand_consistency", "asset_integrity"),
        ("design_tokens", "content_source", "validation_report"),
        ("design_renderer", "document_renderer", "vision_qa"),
    ),
    "social.campaign": S(
        "social.campaign",
        "Social Campaign",
        ("content_strategy", "platform_adaptation", "variant_generation", "campaign_systems"),
        ("social.campaign.build",),
        ("platform_fit", "brand_consistency", "brief_alignment"),
        ("brief", "platform_spec", "content_source"),
        ("llm", "design_renderer"),
    ),
    "social.asset": S(
        "social.asset",
        "Social Asset Production",
        ("format_adaptation", "caption_layout", "thumbnail_design", "variant_control"),
        ("social.asset.produce",),
        ("platform_fit", "legibility", "visual_fidelity"),
        ("platform_spec", "design_tokens", "visual_comparison"),
        ("design_renderer", "image_generation", "vision_qa"),
    ),
    # Quality
    "preflight.file": S(
        "preflight.file",
        "File Preflight",
        ("file_inspection", "dimension_check", "format_check", "font_check"),
        ("preflight.file.run",),
        ("asset_integrity", "production_preflight", "type_integrity", "color_integrity"),
        ("production_spec", "validation_report"),
        ("production_tool",),
    ),
    "preflight.print": S(
        "preflight.print",
        "Print Preflight",
        ("bleed_check", "resolution_check", "color_mode_check", "overprint_check"),
        ("preflight.print.run",),
        ("production_preflight", "asset_integrity", "color_integrity"),
        ("production_spec", "validation_report"),
        ("production_tool",),
    ),
    "qa.visual": S(
        "qa.visual",
        "Visual Comparison QA",
        ("reference_comparison", "defect_detection", "layout_analysis", "typography_analysis"),
        ("qa.visual.compare",),
        ("visual_fidelity", "layout_integrity", "legibility", "qa_gate"),
        ("reference_assets", "visual_comparison", "validation_report"),
        ("vision_qa",),
    ),
    "qa.brand": S(
        "qa.brand",
        "Brand QA",
        ("brand_rule_checking", "token_comparison", "identity_compliance"),
        ("qa.brand.check",),
        ("brand_consistency", "color_integrity", "type_integrity", "qa_gate"),
        ("design_tokens", "reference_assets", "validation_report"),
        ("vision_qa", "llm"),
    ),
}

# Workflows are reusable lifecycle definitions. Stages are intentionally
# provider-neutral and map to the ODI planner/orchestrator contracts.
WORKFLOWS = {
    "brand.strategy.develop": W(
        "brand.strategy.develop",
        ("intake", "research", "position", "synthesize", "review"),
        ("brand_research", "positioning", "audience_modeling", "brand_architecture"),
        ("brief_alignment", "brand_consistency"),
        ("brief", "brand_research", "design_rationale", "validation_report"),
    ),
    "brand.identity.build": W(
        "brand.identity.build",
        ("intake", "context", "direction", "systemize", "document", "validate"),
        ("identity_direction", "visual_language", "identity_rules", "brand_guidelines"),
        ("brand_consistency", "layout_integrity", "color_integrity", "type_integrity"),
        ("brand_research", "design_tokens", "design_rationale", "validation_report"),
    ),
    "brand.logo.develop": W(
        "brand.logo.develop",
        ("brief", "research", "concept", "refine", "test", "deliver"),
        ("mark_development", "lockups", "clear_space", "usage_rules"),
        ("brief_alignment", "legibility", "brand_consistency", "visual_fidelity"),
        ("brief", "reference_assets", "design_rationale", "visual_comparison"),
    ),
    "brand.typography.define": W(
        "brand.typography.define",
        ("content_analysis", "selection", "pairing", "hierarchy", "testing", "document"),
        ("type_selection", "pairing", "hierarchy", "responsive_type"),
        ("legibility", "type_integrity", "brand_consistency"),
        ("brand_research", "design_tokens", "validation_report"),
    ),
    "brand.color.define": W(
        "brand.color.define",
        ("research", "palette", "semantic_roles", "accessibility", "production", "document"),
        ("palette_development", "semantic_roles", "contrast_mapping", "production_color"),
        ("color_integrity", "accessibility", "brand_consistency"),
        ("brand_research", "design_tokens", "validation_report"),
    ),
    "uiux.flow.design": W(
        "uiux.flow.design",
        ("research", "model", "map", "test", "validate"),
        ("user_flows", "navigation", "content_structure", "task_mapping"),
        ("brief_alignment", "accessibility", "layout_integrity"),
        ("brief", "content_source", "design_rationale"),
    ),
    "uiux.interface.build": W(
        "uiux.interface.build",
        ("context", "wireframe", "visualize", "responsive", "qa"),
        ("wireframing", "layout", "interaction", "responsive_design"),
        ("layout_integrity", "accessibility", "brand_consistency", "visual_fidelity"),
        ("brief", "design_tokens", "reference_assets", "visual_comparison"),
    ),
    "uiux.prototype.build": W(
        "uiux.prototype.build",
        ("flow", "states", "interactions", "test", "refine"),
        ("interaction_prototyping", "state_design", "microinteraction"),
        ("accessibility", "brief_alignment", "visual_fidelity"),
        ("brief", "design_rationale", "validation_report"),
    ),
    "system.tokens.build": W(
        "system.tokens.build",
        ("inventory", "model", "semanticize", "export", "validate"),
        ("token_modeling", "semantic_tokens", "theme_tokens", "export_mapping"),
        ("brand_consistency", "type_integrity", "color_integrity"),
        ("design_tokens", "design_rationale"),
    ),
    "system.components.build": W(
        "system.components.build",
        ("inventory", "architecture", "variants", "states", "document", "validate"),
        ("component_architecture", "variants", "states", "documentation"),
        ("layout_integrity", "accessibility", "brand_consistency"),
        ("design_tokens", "validation_report"),
    ),
    "system.patterns.build": W(
        "system.patterns.build",
        ("inventory", "compose", "responsive", "document", "validate"),
        ("pattern_composition", "content_patterns", "responsive_patterns"),
        ("layout_integrity", "accessibility", "brand_consistency"),
        ("design_tokens", "reference_assets", "validation_report"),
    ),
    "image.generate.concept": W(
        "image.generate.concept",
        ("brief", "prompt", "generate", "rank", "refine", "qa"),
        ("prompt_engineering", "composition_direction", "style_direction", "reference_control"),
        ("brief_alignment", "visual_fidelity", "asset_integrity"),
        ("brief", "reference_assets", "generation_trace"),
    ),
    "image.generate.production": W(
        "image.generate.production",
        ("brief", "art_direction", "generate", "refine", "upscale", "qa"),
        ("composition", "art_direction", "lighting", "material_direction", "format_control"),
        ("brief_alignment", "brand_consistency", "visual_fidelity", "asset_integrity"),
        ("brief", "generation_trace", "visual_comparison"),
    ),
    "image.edit.retouch": W(
        "image.edit.retouch",
        ("inspect", "mask", "edit", "color", "artifact_scan", "qa"),
        ("cleanup", "masking", "color_correction", "artifact_removal"),
        ("asset_integrity", "visual_fidelity", "color_integrity"),
        ("reference_assets", "edit_trace", "validation_report"),
    ),
    "image.edit.composite": W(
        "image.edit.composite",
        ("inspect", "segment", "compose", "match", "render", "qa"),
        ("layering", "masking", "perspective_matching", "lighting_matching"),
        ("visual_fidelity", "layout_integrity", "asset_integrity"),
        ("reference_assets", "edit_trace", "visual_comparison"),
    ),
    "video.plan": W(
        "video.plan",
        ("brief", "concept", "script", "storyboard", "shotlist", "review"),
        ("concepting", "scripting", "storyboarding", "shot_planning"),
        ("brief_alignment", "story_integrity"),
        ("brief", "content_source", "design_rationale"),
    ),
    "video.generate": W(
        "video.generate",
        ("prompt", "shots", "generate", "continuity", "assemble", "qa"),
        ("prompt_chaining", "shot_generation", "continuity_control", "camera_direction"),
        ("story_integrity", "motion_integrity", "visual_fidelity"),
        ("brief", "generation_trace", "visual_comparison"),
    ),
    "video.edit": W(
        "video.edit",
        ("ingest", "assemble", "timing", "transitions", "sync", "export", "qa"),
        ("assembly", "timing", "transitions", "sound_sync"),
        ("story_integrity", "motion_integrity", "asset_integrity"),
        ("content_source", "render_trace", "validation_report"),
    ),
    "motion.build": W(
        "motion.build",
        ("intent", "storyboard", "animate", "render", "inspect", "refine"),
        ("animation", "kinetics", "transitions", "motion_systems"),
        ("motion_integrity", "brand_consistency", "legibility"),
        ("design_tokens", "reference_assets", "render_trace"),
    ),
    "packaging.structure.plan": W(
        "packaging.structure.plan",
        ("brief", "dieline", "panel_map", "constraints", "approve"),
        ("dieline_reading", "panel_mapping", "structural_constraints"),
        ("dieline_integrity", "production_preflight"),
        ("brief", "production_spec", "reference_assets"),
    ),
    "packaging.artwork.build": W(
        "packaging.artwork.build",
        ("content", "panel_layout", "brand", "regulatory", "preflight", "proof"),
        ("panel_design", "label_design", "regulatory_content", "print_artwork"),
        ("dieline_integrity", "brand_consistency", "legibility", "production_preflight"),
        ("production_spec", "content_source", "validation_report"),
    ),
    "print.artwork.build": W(
        "print.artwork.build",
        ("brief", "layout", "prepress", "proof", "preflight", "release"),
        ("layout", "prepress", "print_color", "proofing"),
        ("production_preflight", "legibility", "color_integrity", "asset_integrity"),
        ("brief", "production_spec", "render_trace"),
    ),
    "signage.system.build": W(
        "signage.system.build",
        ("site", "message", "wayfinding", "scale", "visualize", "preflight"),
        ("wayfinding", "scale", "distance_readability", "placement"),
        ("legibility", "brand_consistency", "production_preflight"),
        ("brief", "production_spec", "reference_assets"),
    ),
    "presentation.narrative.build": W(
        "presentation.narrative.build",
        ("objective", "audience", "story", "slide_map", "review"),
        ("storytelling", "slide_architecture", "content_prioritization"),
        ("brief_alignment", "story_integrity", "content_integrity"),
        ("brief", "content_source", "design_rationale"),
    ),
    "presentation.design.build": W(
        "presentation.design.build",
        ("system", "layout", "data", "template", "render", "qa"),
        ("slide_layout", "data_visualization", "template_system", "export"),
        ("layout_integrity", "legibility", "brand_consistency", "asset_integrity"),
        ("design_tokens", "content_source", "validation_report"),
    ),
    "social.campaign.build": W(
        "social.campaign.build",
        ("objective", "platforms", "concept", "variants", "review", "schedule"),
        ("content_strategy", "platform_adaptation", "variant_generation", "campaign_systems"),
        ("platform_fit", "brand_consistency", "brief_alignment"),
        ("brief", "platform_spec", "content_source"),
    ),
    "social.asset.produce": W(
        "social.asset.produce",
        ("format", "design", "variant", "render", "qa"),
        ("format_adaptation", "caption_layout", "thumbnail_design", "variant_control"),
        ("platform_fit", "legibility", "visual_fidelity"),
        ("platform_spec", "design_tokens", "visual_comparison"),
    ),
    "preflight.file.run": W(
        "preflight.file.run",
        ("inspect", "measure", "check", "report", "gate"),
        ("file_inspection", "dimension_check", "format_check", "font_check"),
        ("asset_integrity", "production_preflight", "type_integrity", "color_integrity"),
        ("production_spec", "validation_report"),
    ),
    "preflight.print.run": W(
        "preflight.print.run",
        ("inspect", "bleed", "resolution", "color", "overprint", "report"),
        ("bleed_check", "resolution_check", "color_mode_check", "overprint_check"),
        ("production_preflight", "asset_integrity", "color_integrity"),
        ("production_spec", "validation_report"),
    ),
    "qa.visual.compare": W(
        "qa.visual.compare",
        ("ingest", "align", "compare", "detect", "score", "report"),
        ("reference_comparison", "defect_detection", "layout_analysis", "typography_analysis"),
        ("visual_fidelity", "layout_integrity", "legibility", "qa_gate"),
        ("reference_assets", "visual_comparison", "validation_report"),
    ),
    "qa.brand.check": W(
        "qa.brand.check",
        ("load_rules", "inspect", "compare", "score", "report"),
        ("brand_rule_checking", "token_comparison", "identity_compliance"),
        ("brand_consistency", "color_integrity", "type_integrity", "qa_gate"),
        ("design_tokens", "reference_assets", "validation_report"),
    ),
}

FAMILIES = {
    "brand_identity": CapabilityFamilySpec(
        "brand_identity", "Brand Identity", ("brand.strategy", "brand.identity_system")
    ),
    "logo": CapabilityFamilySpec("logo", "Logo", ("brand.logo_system",)),
    "typography": CapabilityFamilySpec("typography", "Typography", ("brand.typography_system",)),
    "color": CapabilityFamilySpec("color", "Color", ("brand.color_system",)),
    "ui_ux": CapabilityFamilySpec(
        "ui_ux",
        "UI/UX",
        ("uiux.information_architecture", "uiux.interface_design", "uiux.prototype"),
    ),
    "design_systems": CapabilityFamilySpec(
        "design_systems",
        "Design Systems",
        ("system.tokens", "system.components", "system.patterns"),
    ),
    "image_generation": CapabilityFamilySpec(
        "image_generation",
        "Image Generation",
        ("image.concept_generation", "image.production_generation"),
    ),
    "image_editing": CapabilityFamilySpec(
        "image_editing", "Image Editing", ("image.retouching", "image.compositing")
    ),
    "video": CapabilityFamilySpec(
        "video", "Video", ("video.preproduction", "video.generation", "video.editing")
    ),
    "motion": CapabilityFamilySpec("motion", "Motion", ("motion.graphics",)),
    "packaging": CapabilityFamilySpec(
        "packaging", "Packaging", ("packaging.structure", "packaging.artwork")
    ),
    "print": CapabilityFamilySpec("print", "Print", ("print.collateral",)),
    "signage": CapabilityFamilySpec("signage", "Signage", ("signage.environmental",)),
    "presentations": CapabilityFamilySpec(
        "presentations", "Presentations", ("presentation.narrative", "presentation.design")
    ),
    "social_content": CapabilityFamilySpec(
        "social_content", "Social Content", ("social.campaign", "social.asset")
    ),
    "production_preflight": CapabilityFamilySpec(
        "production_preflight", "Production Preflight", ("preflight.file", "preflight.print")
    ),
    "visual_qa": CapabilityFamilySpec("visual_qa", "Visual QA", ("qa.visual", "qa.brand")),
}


class CapabilityProvider(Protocol):
    def invoke(self, capability_id: str, workflow_id: str, payload: dict[str, Any]) -> Any: ...


def family(name: str) -> CapabilityFamilySpec:
    return FAMILIES[name]


def sub_capability(name: str) -> SubCapabilitySpec:
    return SUBCAPABILITIES[name]


def workflow(name: str) -> WorkflowSpec:
    return WORKFLOWS[name]


def validate_catalog() -> list[str]:
    errors: list[str] = []
    for f in FAMILIES.values():
        for sid in f.sub_capabilities:
            if sid not in SUBCAPABILITIES:
                errors.append(f"Missing sub-capability: {sid}")
    for s in SUBCAPABILITIES.values():
        for wid in s.workflows:
            if wid not in WORKFLOWS:
                errors.append(f"Missing workflow: {wid}")
        for vid in s.validators:
            if vid not in VALIDATORS:
                errors.append(f"Missing validator: {vid}")
        for eid in s.evidence:
            if eid not in EVIDENCE:
                errors.append(f"Missing evidence: {eid}")
        for aid in s.adapters:
            if aid not in ADAPTERS:
                errors.append(f"Missing adapter: {aid}")
    return errors
