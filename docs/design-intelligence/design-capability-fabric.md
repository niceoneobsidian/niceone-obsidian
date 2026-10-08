# Design Capability Fabric

The Design Capability Fabric is the governed capability layer for design work. It contains contracts and routing metadata, not vendor-specific generation implementations.

## Capability Families

| Family | Capability ID |
|---|---|
| Brand Identity | `brand.identity` |
| Logo | `brand.logo` |
| Typography | `brand.typography` |
| Color | `brand.color` |
| UI/UX | `uiux.design` |
| Design Systems | `ui.design_system` |
| Image Generation | `visual.image_generation` |
| Image Editing | `visual.image_editing` |
| Video | `visual.video` |
| Motion | `visual.motion` |
| Packaging | `production.packaging` |
| Print | `production.print` |
| Signage | `production.signage` |
| Presentations | `production.presentation` |
| Social Content | `marketing.social` |
| Production Preflight | `production.preflight` |
| Visual QA | `quality.visual_qa` |

## Execution Contract

Every capability declares:

- input types
- output types
- validation requirements
- evidence requirements
- risk class

Providers are registered behind the capability contract. This keeps the ODI kernel independent of image, video, model, rendering, or SaaS vendors.

## Lifecycle

```text
Design Intent
    ↓
Capability Selection
    ↓
Context + Evidence
    ↓
Capability Execution
    ↓
Artifact
    ↓
Validation
    ↓
Evidence Package
    ↓
Observability
```

## Scope

The initial fabric covers the requested 17 families. Provider integrations and advanced implementations are intentionally added behind these contracts rather than embedded into the kernel.
