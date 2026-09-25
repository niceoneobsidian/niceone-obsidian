from ois.kernel import (
    AgentRegistry,
    CapabilityRegistry,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    PlanBuilder,
    PlanOrchestrator,
    Supervisor,
)


class DelegatedCapability:
    @property
    def contract(self):  # type: ignore
        from ois.kernel import CapabilityContract, RiskLevel, SideEffectLevel

        return CapabilityContract(
            capability_id="test.supervisor.orchestrated",
            version="1.0.0",
            description="Capability used for supervisor/orchestrator integration.",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request):  # type: ignore
        from ois.kernel import InvocationResult, InvocationStatus

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"delegated": True},
        )


def test_supervisor_delegates_plan_to_orchestrator():  # type: ignore
    registry = CapabilityRegistry()
    registry.register(DelegatedCapability())

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )
    orchestrator = PlanOrchestrator(runtime)
    supervisor = Supervisor(
        agent_registry=AgentRegistry(),
        orchestrator=orchestrator,
    )

    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-integration"),
        objective="Verify Supervisor to Orchestrator delegation",
    )
    plan = (
        PlanBuilder(objective=context.objective)
        .task(
            task_id="delegated-step",
            capability_id="test.supervisor.orchestrated",
            capability_version="1.0.0",
        )
        .build()
    )

    result = supervisor.execute(plan, context)

    assert result.is_complete() is True
    assert result.has_failed() is False
    assert result.tasks["delegated-step"].output == {"delegated": True}
