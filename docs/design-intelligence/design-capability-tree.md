# Design Capability Tree

The Design Capability Fabric is now a five-level executable structure:

```text
Family
  └── Sub-capability
        ├── Skills
        ├── Workflow(s)
        │     ├── Stages
        │     ├── Required skills
        │     ├── Validators
        │     └── Evidence
        ├── Validators
        ├── Evidence requirements
        └── Provider adapters
```

## Coverage

| Family | Sub-capabilities |
|---|---|
| Brand Identity | strategy, identity system |
| Logo | logo system |
| Typography | typography system |
| Color | color system |
| UI/UX | information architecture, interface design, prototype |
| Design Systems | tokens, components, patterns |
| Image Generation | concept generation, production generation |
| Image Editing | retouching, compositing |
| Video | preproduction, generation, editing |
| Motion | motion graphics |
| Packaging | structure, artwork |
| Print | print collateral |
| Signage | environmental signage |
| Presentations | narrative, design |
| Social Content | campaign, asset |
| Production Preflight | file preflight, print preflight |
| Visual QA | visual comparison QA, brand QA |

## Workflow contract

A workflow is provider-neutral and executable through the ODI planner/orchestrator:

```text
Intake / Context
      ↓
Skill execution
      ↓
Artifact generation or transformation
      ↓
Validation
      ↓
Evidence capture
      ↓
Release / recovery decision
```

## Skills

Skills are atomic competencies used by workflows. Examples include prompt engineering, art direction, typography hierarchy, responsive design, token modeling, dieline reading, prepress, wayfinding, storyboarding, visual comparison, and defect detection.

## Validators

Validators are explicit quality gates rather than informal prompt instructions. The catalog includes brief alignment, brand consistency, accessibility, legibility, layout integrity, asset integrity, visual fidelity, production preflight, content integrity, platform fit, motion integrity, story integrity, dieline integrity, typography integrity, color integrity, and an aggregate QA gate.

## Evidence

Every sub-capability declares evidence requirements. Evidence types include source briefs, research, reference assets, design rationale, design tokens, content sources, generation traces, edit traces, render traces, production specifications, validation reports, visual comparisons, and optional approvals.

## Provider adapters

Providers are isolated behind contracts:

- `TextModelProvider`
- `ImageGenerationProvider`
- `ImageEditingProvider`
- `VideoProvider`
- `MotionProvider`
- `DesignRendererProvider`
- `DocumentRendererProvider`
- `ProductionProvider`
- `VisionQAProvider`

No vendor is embedded into the capability definitions. A provider can therefore be replaced without changing the capability tree, workflows, validators, or evidence contracts.

## Governance boundary

A capability is not considered complete merely because an artifact was produced. The executable lifecycle requires validation and evidence. Provider execution is an implementation detail; the capability contract remains the system-of-record for what must be done and what must be proven.
