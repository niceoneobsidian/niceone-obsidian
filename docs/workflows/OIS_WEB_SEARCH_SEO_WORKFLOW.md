# OIS Web Search + SEO Workflow

## Workflow ID

`WF-SOCIAL-CONTENT-WEB-RESEARCH-SEO-v1`

## Purpose

Provide a governed, recoverable workflow for researching current information before social-content synthesis and verifying factual claims after generation.

## State machine

```text
RECEIVED
  ↓
SCOPE_ANALYZED
  ↓
SEARCH_REQUIRED
  ↓
QUERIES_GENERATED
  ↓
SEARCHING
  ├── RATE_LIMITED → BACKOFF → SEARCHING
  ├── EMPTY → REFORMULATE → SEARCHING
  └── RESULTS
        ↓
SOURCE_FILTERED
        ↓
EVIDENCE_BUILT
        ↓
BRIEF_READY
        ↓
CONTENT_GENERATED
        ↓
CLAIMS_EXTRACTED
        ↓
FACT_CHECKED
   ├── FAIL → REVISE → CLAIMS_EXTRACTED
   └── PASS
        ↓
CITATIONS_VALIDATED
        ↓
QUALITY_POLICY_GATE
   ├── BLOCK
   ├── HUMAN_REVIEW
   └── READY
        ↓
OUTPUT
```

## Recovery rules

### Rate limit

- respect provider response/backoff metadata when available
- exponential backoff with jitter
- bounded retry count
- workflow-level search budget
- circuit breaker after repeated failures
- cache valid prior research when freshness policy permits

### Empty results

- broaden query
- reformulate terminology
- remove non-essential filters
- retry within budget
- if still empty, classify research as insufficient

Current/factual content with insufficient evidence is blocked or deferred. Evergreen creative content may proceed only where the content contract permits non-current synthesis and no unsupported factual claims are introduced.

### Source conflict

When credible sources disagree, the Evidence Resolution step compares authority, recency, context, methodology, and directness. Unresolved conflicts become `CONTESTED` and require qualified content or review.

## Validation gates

1. Query validity
2. Search result integrity
3. Source quality
4. Evidence sufficiency
5. Content structure
6. Claim-to-evidence support
7. Citation coverage
8. Policy/compliance
9. Output schema

## Evidence record

The workflow must append evidence for query generation, search execution, source filtering, evidence extraction, generation, fact-checking, validation, recovery, and final disposition.

## SEO branch

After `BRIEF_READY`, the SEO capability may enrich the brief with target terms, search intent, entities, topic gaps, questions, metadata, and structured-data requirements. SEO enrichment does not bypass evidence validation.

## Publishing boundary

The workflow produces a content artifact and a readiness decision. External publishing requires the existing OIS authorization/execution boundary and any required human approval.
