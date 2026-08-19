from ois.kernel import (
    AgentContract,
    AgentRegistry,
    CapabilityContract,
    CapabilityNotFoundError,
    CapabilityRegistry,
    DuplicateCapabilityError,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    ToolContract,
    ToolRegistry,
)
from ois.kernel.registry import RegistryError


class BasicCapability:
    def __init__(self, capability_id="test.basic", version="1.0.0"):
        self._contract = CapabilityContract(
            capability_id=capability_id,
            version=version,
            description="Basic registry test capability",
        )

    @property
    def contract(self):
        return self._contract

    def invoke(self, request: InvocationRequest):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={},
        )


class TestAgent:
    @property
    def contract(self):
        return AgentContract(
            capability_id="test.agent",
            version="1.0.0",
            description="Registry test agent",
        )

    def invoke(self, request):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={},
        )


class TestTool:
    @property
    def contract(self):
        return ToolContract(
            capability_id="test.tool",
            version="1.0.0",
            description="Registry test tool",
        )

    def invoke(self, request):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={},
        )


def test_capability_registration_and_retrieval():
    registry = CapabilityRegistry()

    capability = BasicCapability("test.echo", "1.0.0")
    registry.register(capability)

    assert registry.has("test.echo", "1.0.0") is True

    entry = registry.get("test.echo", "1.0.0")

    assert entry.capability is capability
    assert entry.contract.capability_id == "test.echo"
    assert entry.contract.version == "1.0.0"


def test_duplicate_capability_version_is_rejected():
    registry = CapabilityRegistry()

    registry.register(BasicCapability("test.echo", "1.0.0"))

    try:
        registry.register(BasicCapability("test.echo", "1.0.0"))
        raise AssertionError(
            "Duplicate capability/version should be rejected"
        )
    except DuplicateCapabilityError:
        pass


def test_multiple_capability_versions_can_coexist():
    registry = CapabilityRegistry()

    capability_v1 = BasicCapability("test.echo", "1.0.0")
    capability_v2 = BasicCapability("test.echo", "2.0.0")

    registry.register(capability_v1)
    registry.register(capability_v2)

    assert registry.has("test.echo", "1.0.0") is True
    assert registry.has("test.echo", "2.0.0") is True
    assert registry.get("test.echo", "1.0.0").capability is capability_v1
    assert registry.get("test.echo", "2.0.0").capability is capability_v2
    assert len(registry.list()) == 2


def test_missing_capability_is_rejected():
    registry = CapabilityRegistry()

    try:
        registry.get("test.missing", "1.0.0")
        raise AssertionError(
            "Missing capability should raise CapabilityNotFoundError"
        )
    except CapabilityNotFoundError:
        pass


def test_unregister_removes_only_requested_version():
    registry = CapabilityRegistry()

    registry.register(BasicCapability("test.echo", "1.0.0"))
    registry.register(BasicCapability("test.echo", "2.0.0"))

    registry.unregister("test.echo", "1.0.0")

    assert registry.has("test.echo", "1.0.0") is False
    assert registry.has("test.echo", "2.0.0") is True


def test_unregistering_missing_capability_is_rejected():
    registry = CapabilityRegistry()

    try:
        registry.unregister("test.echo", "1.0.0")
        raise AssertionError(
            "Unregistering a missing capability should fail"
        )
    except CapabilityNotFoundError:
        pass


def test_registries_are_isolated():
    registry = CapabilityRegistry()
    other_registry = CapabilityRegistry()

    registry.register(BasicCapability("test.echo", "2.0.0"))

    assert registry.has("test.echo", "2.0.0") is True
    assert other_registry.has("test.echo", "2.0.0") is False
    assert len(other_registry.list()) == 0


def test_agent_registry_requires_agent_contract():
    registry = AgentRegistry()
    agent = TestAgent()

    registry.register(agent)

    assert registry.has("test.agent", "1.0.0") is True
    assert registry.get("test.agent", "1.0.0").capability is agent

    try:
        registry.register(
            BasicCapability("test.not-agent", "1.0.0")
        )
        raise AssertionError(
            "AgentRegistry should require AgentContract"
        )
    except RegistryError:
        pass


def test_tool_registry_requires_tool_contract():
    registry = ToolRegistry()
    tool = TestTool()

    registry.register(tool)

    assert registry.has("test.tool", "1.0.0") is True
    assert registry.get("test.tool", "1.0.0").capability is tool

    try:
        registry.register(
            BasicCapability("test.not-tool", "1.0.0")
        )
        raise AssertionError(
            "ToolRegistry should require ToolContract"
        )
    except RegistryError:
        pass
