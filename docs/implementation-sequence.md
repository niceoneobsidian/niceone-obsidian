# OIS Implementation Sequence

The repository advances through eleven phases in strict order. A phase may be marked complete only after its required evidence and CI checks pass in a reviewed pull request.

## Current status

- Phase 1, Repository Integrity: complete on the Phase 1 governance branch.
- Phase 2, Kernel Conformance: active.
- Phases 3 through 11: planned and blocked by the preceding phase.

## Phase 2 promotion rule

Phase 2 may be promoted to `complete` only when the `kernel-conformance` check passes on a clean runner and the executable contract tests remain present. The next phase must not be activated in the same change unless Phase 2 evidence is complete.

The canonical manifest is `config/phase-gates.json`. The phase validator must pass on every change to that manifest.
