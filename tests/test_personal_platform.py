"""Personal platform contract tests."""
from ois.personal import PersonalPlatform, PlatformConfig


class FakeDurableStore:
    def __init__(self):
        self.initialized = False

    def initialize(self):
        self.initialized = True


def test_personal_platform_requires_durable_store():
    try:
        PersonalPlatform()
    except RuntimeError as exc:
        assert "PostgreSQL" in str(exc)
    else:
        raise AssertionError("platform must not silently fall back to ephemeral state")


def test_personal_platform_core_state_and_approval():
    store = FakeDurableStore()
    platform = PersonalPlatform(
        config=PlatformConfig(require_postgres=True), durable_store=store
    )
    platform.initialize()
    assert store.initialized
    session_id = platform.open_session()
    assert platform.sessions[session_id]["status"] == "active"

    execution = platform.create_execution("research the current project readiness")
    approval = platform.request_approval(execution.execution_id, "external side effect", "high")
    decided = platform.decide_approval(approval.approval_id, approved=True)
    assert decided.status == "approved"
    assert platform.health()["pending_approvals"] == 0


def test_semantic_world_requires_known_entities():
    platform = PersonalPlatform(
        config=PlatformConfig(require_postgres=False), durable_store=FakeDurableStore()
    )
    platform.add_entity("project", "project", name="OIS")
    platform.add_entity("workflow", "workflow", name="research")
    platform.relate("project", "contains", "workflow")
    assert len(platform.relationships) == 1


def test_learning_requires_evaluation_gate():
    platform = PersonalPlatform(
        config=PlatformConfig(require_postgres=False), durable_store=FakeDurableStore()
    )
    platform.propose_learning("candidate-1", "prefer route A", ["evidence-1"])
    try:
        platform.promote_learning("candidate-1", approved=True, evaluation={"passed": False})
    except ValueError:
        pass
    else:
        raise AssertionError("learning promotion must require a passing evaluation")
