"""Contract tests for the complete capability tree."""

from ois.design_intelligence.blueprints import FAMILIES, SUBCAPABILITIES, WORKFLOWS, validate_catalog


def test_catalog_has_all_17_families() -> None:
    assert len(FAMILIES) == 17


def test_every_sub_capability_has_workflow_skill_validator_evidence_and_adapter() -> None:
    for spec in SUBCAPABILITIES.values():
        assert spec.skills
        assert spec.workflows
        assert spec.validators
        assert spec.evidence
        assert spec.adapters


def test_every_workflow_resolves() -> None:
    for spec in SUBCAPABILITIES.values():
        for workflow_id in spec.workflows:
            assert workflow_id in WORKFLOWS
            workflow = WORKFLOWS[workflow_id]
            assert workflow.stages
            assert workflow.required_skills
            assert workflow.validators
            assert workflow.evidence


def test_catalog_integrity() -> None:
    assert validate_catalog() == []
