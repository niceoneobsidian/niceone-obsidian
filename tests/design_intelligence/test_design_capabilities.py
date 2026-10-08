"""Tests for the design capability fabric."""

from ois.design_intelligence.catalog import DESIGN_CAPABILITIES, get_capability, list_capabilities


def test_all_requested_capability_families_are_registered() -> None:
    expected = {
        "brand_identity",
        "logo",
        "typography",
        "color",
        "ui_ux",
        "design_systems",
        "image_generation",
        "image_editing",
        "video",
        "motion",
        "packaging",
        "print",
        "signage",
        "presentations",
        "social_content",
        "production_preflight",
        "visual_qa",
    }
    assert {c.family for c in DESIGN_CAPABILITIES} == expected


def test_capability_contracts_have_validation_and_evidence() -> None:
    assert all(c.validation and c.evidence for c in DESIGN_CAPABILITIES)


def test_lookup_and_family_filter() -> None:
    assert get_capability("brand.identity").name == "Brand Identity"
    assert list_capabilities("visual_qa")[0].id == "quality.visual_qa"
