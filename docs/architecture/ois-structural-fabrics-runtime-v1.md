# OIS Structural Fabrics Runtime v1

This document records the first runtime binding of the 15 structural fabric contracts to the existing OIS Kernel.

## Runtime boundary

```text
Workflow / Agent / LLM / Knowledge / Social / Learning request
                         |
                         v
              OIS Kernel CapabilityRegistry
                         |
                         v
               ExecutionRuntime.execute()
                         |
          +--------------+--------------+
          | policy -> validation -> evidence
          | checkpoint -> idempotency -> recovery
          v
                FabricCapability adapter
                         |
                         v
                  FabricRuntime
```

The Kernel remains authoritative for authorization, validation, evidence, checkpointing, idempotency and recovery. Fabric implementations do not bypass that boundary.

## Bound fabrics

| Fabric | Runtime binding | v1 state |
|---|---|---|
| Production workflow | `InMemoryWorkflowEngine` | executable |
| Distributed workers | `InMemoryWorkerFabric` | queue/claim/retry abstraction |
| LLM gateway | `InMemoryLLMGateway` + `InMemoryModelRouter` | executable provider adapter boundary |
| Evaluation/experimentation | `EvaluationSpec` + learning boundary | contract/runtime boundary; evaluator execution next |
| Agent runtime/workspace | `InMemoryAgentRuntime` | executable sessions/workspaces |
| Context engineering | `InMemoryContextEngine` | executable context assembly |
| Advanced RAG/knowledge | `InMemoryKnowledgeEngine` | executable ingest/retrieve baseline |
| Agent middleware | `InMemoryMiddleware` | executable staged hooks |
| Reasoning registry | `InMemoryReasoningRegistry` | executable selection |
| Visual studio | `InMemoryStudio` | executable graph validation |
| Component registry | `InMemoryComponentRegistry` | executable registration |
| Model routing/runtime | `InMemoryModelRouter` | executable capability/constraint routing |
| Multimodal | `InMemoryMultimodalEngine` | executable artifact boundary |
| Social Intelligence | `InMemorySocialFabric` | executable signal ingestion/query baseline |
| Attribution/experimentation/learning | `InMemoryLearningFabric` | candidate/propose/promote gate |

## Provider rule

The in-memory implementations are reference runtime bindings, not claims that external systems are already integrated. Production providers should implement the same boundary. Candidate providers include n8n/LangGraph-style workflow engines, TensorZero-style LLM gateway/evaluation, RAGFlow-style knowledge, vLLM/Ollama/llama.cpp model runtimes, Whisper speech processing and social platform connectors.

## Learning governance

Learning proposals always enter as `candidate`. Promotion requires explicit approval and evaluation evidence. The runtime does not permit an experiment result to mutate production architecture directly.

## Verification

`test_structural_fabric_runtime.py` verifies the core fabric primitives. `test_structural_fabric_kernel_integration.py` verifies that a fabric capability is executed through `ExecutionRuntime`, including authorization, evidence and checkpoint boundaries.

CI remains the authoritative source for full repository test status.
