---
name: design
description: Governed design-intelligence routing for brand, design systems, visual assets, UI/UX, presentation, and production design.
version: 0.1.0
---

# Design Skill

## Purpose

Route design requests to the appropriate ODI capability family while preserving context, evidence, policy, and validation requirements.

## Routing Families

- `brand` — identity, voice, brand assets
- `design-system` — tokens, typography, color, spacing, component rules
- `ui-ux` — interaction, layout, accessibility, responsive behavior
- `image` — image generation, editing, compositing, visual inspection
- `video` — motion, storyboard, generation, review
- `presentation` — decks, diagrams, slide systems
- `marketing` — banners, campaigns, social assets
- `production` — print, packaging, preflight, export requirements

## Required Lifecycle

```text
REQUEST
→ ROUTE
→ ASSEMBLE CONTEXT
→ SELECT CAPABILITY
→ AUTHORIZE
→ EXECUTE
→ VALIDATE
→ PACKAGE EVIDENCE
```

## Rules

1. Do not execute provider-specific actions directly from skill instructions.
2. Use capability contracts for consequential operations.
3. Preserve source provenance for design rules and references.
4. Run relevant visual/structural/production validation before completion.
5. Treat generated assets as untrusted until validated.
6. Record the selected capability, version, model/provider, and validation outcome.
