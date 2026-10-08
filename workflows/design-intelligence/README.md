# Workflows

Workflows compose governed capabilities into inspectable execution graphs.

A workflow should define:

- input contract
- context requirements
- capability nodes
- routing conditions
- policy gates
- validation gates
- evidence outputs
- failure/recovery paths
- version

Example conceptual graph:

```text
INTAKE
  ↓
CONTEXT
  ↓
RESEARCH
  ↓
DESIGN SYSTEM
  ↓
GENERATION
  ↓
VISUAL REVIEW
  ↓
PRODUCTION PREFLIGHT
  ↓
EVIDENCE PACKAGE
```

Workflows are not allowed to bypass the execution boundary.
