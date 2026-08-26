# `ois verify`

`ois verify` is the canonical P0 repository verification entry point.

It executes, in order:

1. `git diff --check`
2. Python compilation of `ois/`
3. the full pytest suite
4. evidence artifact generation
5. evidence integrity and conformance validation

The generated artifact is `.ois/evidence/verification.json` by default. It is intentionally ignored by Git because it is run output, not source configuration.

The artifact records the repository URL, commit SHA, branch, working-tree state, verification run ID, check results, and a SHA-256 content hash. The conformance decision is derived from observed check results and then independently revalidated.

P0 verification **does not activate production**. `activation_eligible` is always `false`; production promotion must be handled by a separate governed promotion gate with independent deployment/runtime evidence.

## Local usage

```bash
ois verify
```

or, without installing the console entry point:

```bash
python -m ois verify
```

A custom evidence path can be supplied with `--artifact`.
