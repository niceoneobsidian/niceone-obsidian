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


registry = CapabilityRegistry()

capability_v1 = BasicCapability(
    capability_id="test.echo",
    version="1.0.0",
)

registry.register(capability_v1)

assert registry.has("test.echo", "1.0.0") is True

entry = registry.get("test.echo", "1.0.0")

assert entry.capability is capability_v1
assert entry.contract.capability_id == "test.echo"
assert entry.contract.version == "1.0.0"


try:
    registry.register(
        BasicCapability(
            capability_id="test.echo",
            version="1.0.0",
        )
    )
    raise AssertionError(
        "Duplicate capability/version should be rejected"
    )
except DuplicateCapabilityError:
    pass


capability_v2 = BasicCapability(
    capability_id="test.echo",
    version="2.0.0",
)

registry.register(capability_v2)

assert registry.has("test.echo", "2.0.0") is True
assert registry.get(
    "test.echo",
    "2.0.0",
).capability is capability_v2

assert len(registry.list()) == 2


try:
    registry.get("test.missing", "1.0.0")
    raise AssertionError(
        "Missing capability should raise CapabilityNotFoundError"
    )
except CapabilityNotFoundError:
    pass


registry.unregister("test.echo", "1.0.0")

assert registry.has("test.echo", "1.0.0") is False
assert registry.has("test.echo", "2.0.0") is True


try:
    registry.unregister("test.echo", "1.0.0")
    raise AssertionError(
        "Unregistering a missing capability should fail"
    )
except CapabilityNotFoundError:
    pass


other_registry = CapabilityRegistry()

assert other_registry.has("test.echo", "2.0.0") is False
assert len(other_registry.list()) == 0


agent_registry = AgentRegistry()

agent = TestAgent()

agent_registry.register(agent)

assert agent_registry.has("test.agent", "1.0.0") is True
assert agent_registry.get(
    "test.agent",
    "1.0.0",
).capability is agent


try:
    agent_registry.register(
        BasicCapability(
            capability_id="test.not-agent",
            version="1.0.0",
        )
    )
    raise AssertionError(
        "AgentRegistry should require AgentContract"
    )
except RegistryError:
    pass


tool_registry = ToolRegistry()

tool = TestTool()

tool_registry.register(tool)

assert tool_registry.has("test.tool", "1.0.0") is True
assert tool_registry.get(
    "test.tool",
    "1.0.0",
).capability is tool


try:
    tool_registry.register(
        BasicCapability(
            capability_id="test.not-tool",
            version="1.0.0",
        )
    )
    raise AssertionError(
        "ToolRegistry should require ToolContract"
    )
except RegistryError:
    pass


print("KERNEL REGISTRY TEST: PASS")
