# OIS Web Search + SEO Content Intelligence Integration

**Status:** DESIGNED / READY FOR CONTRACT + REGISTRY IMPLEMENTATION  
**Domain:** Social Content Intelligence  
**Architecture:** OIS — Obsidian Intelligence System

## Purpose

Integrate live Web Search into the social content generator as a governed research capability that runs before synthesis and is followed by claim-level fact checking and provenance validation.

The design follows the OIS execution boundary:

```text
OBJECTIVE
  ↓
COGNITION / SCOPE
  ↓
QUERY GENERATION
  ↓
SEARCH EXECUTION
  ↓
SOURCE FILTERING + RANKING
  ↓
EVIDENCE EXTRACTION
  ↓
RESEARCH BRIEF
  ↓
CONTENT SYNTHESIS
  ↓
CLAIM EXTRACTION
  ↓
FACT CHECK
  ↓
CITATION / PROVENANCE VALIDATION
  ↓
QUALITY + POLICY GATE
  ↓
HUMAN REVIEW / OUTPUT
  ↓
MEASUREMENT → LEARNING
```

## Architectural rule

Web Search is an OIS capability, not an unrestricted prompt primitive. The LLM may propose research queries and synthesize evidence, but it does not receive authority to bypass tool policy, validation, provenance, or execution controls.

## 1. Workflow

### 1.1 Objective intake

Input includes topic/content idea or script, platform, audience, objective, freshness requirement, language, geography when applicable, and whether citations/provenance are required.

The system decides whether current research is necessary. Search should be required for current events, current statistics, recent developments, regulations, market/trend claims, public-figure updates, and other rapidly changing facts.

### 1.2 Query generation

The Query Planner produces diversified queries rather than sending the original topic unchanged. Query classes:

- primary topic query
- intent/context query
- factual/statistical query
- trend/freshness query
- counterclaim/risk query
- terminology/entity query

Each query receives an ID and purpose so retrieved evidence can be traced back to the research plan.

### 1.3 Search execution

Use an abstract `SearchTool` contract. Provider selection remains outside the content agent.

Required request controls:

- freshness window
- language/region
- result limit
- timeout
- retry budget
- per-run search budget
- cache policy

Required result fields:

```json
{
  "query_id": "Q-001",
  "title": "...",
  "url": "...",
  "domain": "...",
  "snippet": "...",
  "published_at": "...",
  "retrieved_at": "..."
}
```

### 1.4 Source filtering and ranking

Never pass raw search results directly to generation.

Filter and rank sources using:

1. authority
2. relevance
3. freshness
4. primary-vs-secondary evidence
5. evidence directness
6. duplication
7. source availability

Primary/authoritative sources should be preferred. Low-authority pages can be discovery inputs but should not independently support important factual claims when stronger evidence is available.

### 1.5 Evidence extraction

Convert selected sources into structured evidence objects:

```json
{
  "evidence_id": "E-001",
  "claim": "...",
  "evidence_text": "...",
  "source_id": "SRC-001",
  "published_at": "...",
  "retrieved_at": "...",
  "confidence": 0.92
}
```

Evidence must preserve source provenance and important qualifiers.

### 1.6 Research brief

Compile a bounded research brief before generation:

- verified facts
- statistics
- current developments
- relevant entities
- questions
- competing/contradictory evidence
- uncertainties
- source/evidence map

The brief is the writer's factual knowledge base.

### 1.7 Content synthesis

The Content Agent receives the research brief plus the creative objective. It should synthesize original content rather than copy source language.

Creative framing may be flexible; externally verifiable factual claims must remain evidence-grounded.

### 1.8 Claim extraction and fact checking

A separate Fact Check capability extracts externally verifiable claims from the generated content and matches each claim against the evidence set.

Each claim receives one of:

- `VERIFIED`
- `PARTIALLY_SUPPORTED`
- `UNSUPPORTED`
- `CONTRADICTED`
- `CONTESTED`
- `NON_FACTUAL`

Material unsupported or contradicted claims block the output or route it back for revision.

### 1.9 Citation / provenance validation

Maintain an internal claim-to-source map even where the social platform does not display formal citations.

```json
{
  "claim_id": "C-004",
  "source_ids": ["SRC-001", "SRC-003"],
  "verification": "VERIFIED"
}
```

No factual claim may be marked verified without supporting source evidence.

## 2. Prompt-chaining strategy

The generation prompt should explicitly treat the research brief as evidence, not as text to copy.

Core instructions:

```text
You are the OIS Social Content Agent.

Use the supplied RESEARCH BRIEF as your factual knowledge base.

- Synthesize; do not copy source wording.
- Do not invent facts, statistics, quotations, or experience.
- Preserve dates, qualifiers, populations, and uncertainty.
- Prefer higher-authority evidence when sources differ.
- If evidence conflicts, represent the conflict rather than silently selecting a convenient claim.
- Every externally verifiable factual claim must map to one or more source IDs.
- Distinguish verified facts from interpretation, opinion, and prediction.
- If evidence is insufficient, state that limitation or request research expansion.
```

Recommended chain:

```text
Query Planner
 → Research Agent
 → Source Evaluator
 → Evidence Extractor
 → Brief Compiler
 → Content Strategist
 → Content Generator
 → Claim Extractor
 → Fact Checker
 → Citation Validator
 → Quality Gate
```

## 3. Error handling

### Empty result set

```text
EMPTY
 ↓
Broaden query
 ↓
Reformulate query
 ↓
Retry within budget
 ↓
Still empty?
 ├─ Current/factual content → BLOCK or DEFER
 └─ Evergreen creative content → continue only with explicit evidence limitation
```

The system must never silently convert missing evidence into model-generated facts.

### Rate limit / temporary search failure

Use bounded exponential backoff with jitter, retry budgets, request timeouts, and circuit breaking. Cache research by normalized query plus freshness window when policy permits.

If the retry budget is exhausted, route to fallback research, deferred execution, or a blocked state. The failure and recovery decision must be recorded in execution evidence.

### Conflicting sources

Compare authority, recency, methodology, context, and directness of evidence. If the conflict cannot be resolved, classify the claim as `CONTESTED` and require qualified wording or human review.

## 4. OIS contracts

Recommended capability contracts:

- `CAP-WEB-RESEARCH`
- `CAP-QUERY-GENERATION`
- `CAP-SOURCE-EVALUATION`
- `CAP-EVIDENCE-EXTRACTION`
- `CAP-RESEARCH-BRIEF`
- `CAP-CONTENT-SYNTHESIS`
- `CAP-FACT-CHECKING`
- `CAP-CITATION-VALIDATION`
- `CAP-SEO-CONTENT-INTELLIGENCE`

Recommended tools:

- `SearchTool`
- `SourceRetrieverTool`
- `SourceParserTool`
- `ResearchCache`
- `CitationResolver`

Agents remain replaceable execution providers behind these contracts.

## 5. SEO extension

The SEO layer consumes the same research brief and adds:

- target keywords
- search intent
- entities
- topic gaps
- related questions
- competitor topic patterns
- metadata requirements
- structured-data requirements

SEO must not override evidence or policy. Keyword coverage is a quality signal, not a reason to fabricate or stuff content.

Structured data must be generated only when supported by the visible content and then validated before delivery.

## 6. Output artifact

The generator should return a structured artifact rather than a bare string:

```json
{
  "content": {
    "hook": "...",
    "body": "...",
    "cta": "..."
  },
  "research": {
    "queries": [],
    "sources": [],
    "retrieved_at": "..."
  },
  "claims": [],
  "validation": {
    "fact_check": "PASS",
    "citation_coverage": 1.0,
    "research_sufficiency": 0.94
  },
  "status": "READY_FOR_REVIEW"
}
```

## 7. Evidence requirements

Every meaningful execution should record:

- execution ID
- workflow/version
- capability/version
- agent/model/tool selections
- queries
- retrieved source metadata
- evidence objects
- claim verification results
- validation results
- errors/recovery
- timestamps
- policy decision
- output version

Architecture remains `DESIGNED` until implementation, tests, integration, runtime, security, observability, recovery, deployment, and operational verification provide evidence.

## 8. OIS integration boundary

```text
OIS CONTROL PLANE
      ↓
COGNITION / RISK / SCOPE
      ↓
CAPABILITY ROUTER
      ↓
QUERY / RESEARCH WORKFLOW
      ↓
OIS KERNEL
      ↓
TOOLS / AGENTS / MODELS
      ↓
VALIDATION
      ↓
STATE + EVIDENCE
      ↓
MEASUREMENT / LEARNING
```

The implementation must preserve the OIS invariant:

> Reasoning can propose; policy, authorization, execution, validation, and evidence determine what may actually happen.
