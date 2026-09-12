# OIS CLI

`ois` is the operator interface for Niceone Obsidian. It reports repository and source-level evidence and delegates canonical verification to `ois.verify`.

The CLI is deliberately not an execution bypass. Policy, authorization, kernel execution, validation, recovery, and evidence remain authoritative in the OIS platform.

## Installation

From a checkout:

```bash
python -m pip install -e .
```

Or invoke it without installing the entry point:

```bash
python -m ois version
```

## Commands

```text
ois status         Repository/runtime status
ois doctor         Local development environment diagnostics
ois verify         Run the canonical local OIS CI verifier
ois health         Verify expected OIS architectural source surfaces exist
ois capabilities  Discover domain registry source surfaces
ois agents        Discover domain registry source surfaces
ois tools         Discover connector/tool manifest source surfaces
ois workflows     Discover workflow source surfaces
ois version       Show CLI version
```

### Evidence semantics

The CLI distinguishes **discovery** from **verification**:

- `status` reports local repository context.
- `doctor` reports local tool/dependency availability.
- `health` reports expected source surfaces.
- inventory commands report source-level discovery only.
- `verify` runs the repository's existing lint, format, type, security, governance, and test gates.

None of these commands alone establishes production readiness.

## Shell integration

The existing Oh My Posh/Zsh configuration can remain the presentation layer. A lightweight shell wrapper can expose `ois` without putting expensive repository checks into every prompt.

Recommended prompt rule:

```text
prompt -> cached/local state -> render
operator command -> OIS CLI -> authoritative repository/runtime evidence
```

Do not call GitHub, PostgreSQL, Redis, or the execution kernel on every prompt render.

## Safety boundary

The CLI intentionally does not expose an unrestricted `exec` command in v1. Any future action-oriented command must route through the OIS authorization and execution contracts rather than directly invoking external side effects.

## Design basis

The CLI follows the repository's operating doctrine:

```text
THINK
  ↓
VERIFY
  ↓
AUTHORIZE
  ↓
ACT
  ↓
VALIDATE
  ↓
MEASURE
  ↓
LEARN
  ↓
EVOLVE
```

The first release focuses on operator visibility and verification, not autonomous mutation.
