# Reference Architecture Research

This document records structural patterns selected from the repositories supplied for ODI architecture research. The goal is to extract reusable architectural ideas, not copy implementations.

## Core System References

| Reference | Pattern to study | ODI application |
|---|---|---|
| FareedKhan-dev/all-agentic-architectures | Uniform architecture contract, many agentic patterns, benchmarks, notebooks, tests | Architecture pattern registry + benchmark discipline |
| infiniflow/ragflow | Deep document processing, retrieval, agent/context layer, orchestration | Knowledge ingestion, retrieval, context fabric |
| tensorzero/tensorzero | Unified gateway, observability, evaluation, optimization, experimentation | Model gateway + evaluation/evolution plane |
| openclaw/openclaw | Gateway, per-agent configuration, skill discovery, allowlists, nodes | Agent/skill routing and scoped capability visibility |
| n8n-io/n8n | Monorepo packages, execution core, nodes, shared types | Capability/plugin packaging and workflow runtime |
| langflow-ai/langflow | Visual flow construction and component-oriented AI applications | Inspectable workflow composition |
| langgenius/dify | Full AI application platform, workflow, model and knowledge abstractions | Application/control-plane separation |
| langchain-ai/langchain | Modular ecosystem and provider/tool abstractions | Adapter boundaries, integrations |
| open-webui/open-webui | UI + backend application boundary | Optional ODI control surface |
| ollama/ollama | Local model runtime and provider boundary | Local inference adapter |
| vllm-project/vllm | High-throughput model serving/runtime separation | Inference infrastructure adapter |
| ggml-org/llama.cpp | Portable inference runtime | Local/edge model adapter |
| crewAIInc/crewAI | Agent/team/task orchestration | Multi-agent capability provider, not kernel |
| openinterpreter/openinterpreter | Tool-using execution loop | Tool execution adapter and sandbox boundary |
| mem0ai/mem0 | Dedicated memory abstraction | Memory stream service |
| volcengine/OpenViking | Context/memory-oriented infrastructure | Context and memory indexing research |
| bytedance/deer-flow | Multi-agent workflow, subagents, skills | Complex workflow orchestration research |
| NVIDIA/GenerativeAIExamples | Production-oriented reference examples | Deployment and integration patterns |
| MetaGPT | Role-based multi-agent organization | Specialized agent provider patterns |
| ParlAI | Research framework and evaluation/task abstractions | Evaluation and experimentation patterns |

## Visual / Design Intelligence References

| Reference | Pattern to study | ODI application |
|---|---|---|
| nextlevelbuilder/ui-ux-pro-max-skill | Searchable design intelligence, design-system generation, sub-skill routing, persistence, pre-delivery checks | Design knowledge fabric + skill routing + visual QA |
| YubaNeupane/Research-AI-DesginPattern | AI design-pattern research | Design reasoning knowledge |
| vercel/og-image | Programmatic visual output | Deterministic visual artifact capability |
| andrewkirillov/AForge.NET | Image-processing primitives | Low-level image capability adapter |
| cliprise/awesome-ai-image-generator-resources | Curated visual-generation resources | Resource catalog, not runtime dependency |
| cliprise/awesome-ai-video-generator-prompts | Prompt/resource taxonomy | Prompt research dataset |
| coze-dev/coze-studio | Visual agent/workflow studio | Workflow UX and composition research |
| ningzimu/codex-ppt-skill | Specialized presentation skill | Presentation capability/skill package |
| open-xml-templating/docxtemplater | Template-driven documents | Document production capability |
| python-qrcode | Deterministic visual asset generation | QR artifact capability |

## Structural Decisions Extracted

### 1. Uniform contracts

Agentic architectures benefit from a stable execution contract. ODI therefore defines common task, capability, result, evidence, and validation contracts.

### 2. Gateway boundaries

Model providers should be behind a model gateway rather than called throughout the domain. This supports routing, retries, fallbacks, cost tracking, evaluation, and provider replacement.

### 3. Context engineering

Knowledge retrieval is broader than vector search. ODI treats ingestion, parsing, chunking, retrieval, reranking, context assembly, memory, tools, and current environment as coordinated context sources.

### 4. Skill discovery and gating

Skills need explicit metadata, scope, routing, precedence, and allowlists. A discovered skill never becomes execution authority by itself.

### 5. Package boundaries

Large systems benefit from explicit package boundaries around shared types, runtime, integrations, UI, and domain modules. ODI adopts this separation without copying another repository's package layout verbatim.

### 6. Evaluation as infrastructure

Evaluations should be executable artifacts with datasets, evaluators, thresholds, run metadata, and historical results. Evaluation is part of the system rather than a final manual review.

### 7. Visual feedback loop

Design generation should support an observe-review-iterate cycle. Visual artifacts should be rendered, inspected, scored, and revised before completion when the capability requires it.

### 8. Master + overrides

Design-system persistence should distinguish a canonical master system from scoped page/project overrides. This prevents local exceptions from silently redefining global design rules.

## Anti-Patterns to Avoid

- Building a giant `agents/` folder with no capability contracts.
- Treating RAG as only a vector database.
- Treating prompts as the architecture.
- Allowing model output to call infrastructure directly.
- Mixing knowledge, memory, and runtime state.
- Copying every referenced repository's structure into one monolith.
- Making visual generation the center of the kernel.
- Allowing learning code to mutate production automatically.
