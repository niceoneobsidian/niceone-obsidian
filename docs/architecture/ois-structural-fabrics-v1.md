# OIS Structural Fabrics v1

This document defines the first canonical contract layer for the 15 requested structural upgrades. It is an integration layer above the existing OIS Kernel; it does not replace Kernel contracts, registries, policy, validation, recovery, or the Control Plane.

## Fabrics

1. Production workflow engine — `WorkflowSpec`
2. Distributed execution/worker fabric — `WorkerSpec`
3. LLM gateway — `LLMGatewaySpec`
4. LLM evaluation/experimentation fabric — `EvaluationSpec`
5. Agent runtime/workspace — `AgentWorkspace`
6. Context engineering engine — `ContextRequest`
7. Advanced RAG/knowledge engine — `KnowledgeArtifact`
8. Agent middleware — `MiddlewareSpec`
9. Reasoning-pattern registry — `ReasoningPattern`
10. Visual architecture/workflow studio — `StudioArtifact`
11. Component registry — `ComponentSpec`
12. Model routing/runtime abstraction — `ModelRoute`
13. Multimodal execution — `MultimodalArtifact`
14. Social Intelligence Fabric — `SocialSignal`
15. Attribution + experimentation + learning — `LearningCandidate`

## Integration rule

All runtime implementations must bind these contracts to the existing OIS Kernel and must pass through policy, authorization, validation, observability and recovery. The new layer is deliberately dependency-light so external runtimes such as LangGraph, n8n, RAGFlow, TensorZero, vLLM, Ollama, llama.cpp, Whisper and platform adapters remain replaceable providers.

## Governance rule

Learning creates candidates. It does not mutate production architecture automatically. Promotion requires evaluation, testing, approval/canary policy, monitoring and rollback evidence.

## Current evidence state

The repository already contains Kernel contracts, registries and Control Plane foundations. The project evidence still distinguishes architecture from verified production integration. This commit therefore establishes the shared structural contracts and tests first; provider/runtime activation is the next implementation layer.
