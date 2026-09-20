# End-to-end execution example

This example describes the minimum evidence expected for one harmless, controlled execution. It is a documentation contract, not a claim that every step is currently wired end to end.

## Scenario

Execute a read-only local capability that returns a deterministic value. No external side effect is permitted.

## Sequence

1. Receive a structured objective.
2. Create an execution identity and idempotency key.
3. Produce a plan proposal.
4. Resolve the capability and immutable version.
5. Evaluate policy and authorization.
6. Persist the authorized execution before invoking the capability.
7. Execute within a bounded timeout.
8. Validate the result against the declared output contract.
9. Append evidence containing identity, state, authorization, capability version, timing, and outcome.
10. Materialize metrics and mark the execution terminal.

## Required evidence

The evidence record should make it possible to answer:

- What was requested?
- Which plan and capability version were used?
- Who or what authorized it?
- What state transitions occurred?
- Was this a duplicate delivery?
- What was executed and validated?
- What failure or recovery decision occurred?
- Which commit and environment produced the result?

## Negative cases

The example is incomplete unless it also demonstrates that:

- Missing authorization prevents execution.
- A duplicate idempotency key does not create a second side effect.
- An invalid state transition is rejected.
- A validation failure does not produce a successful terminal result.
- An evidence-write failure fails closed for consequential work.

## Maturity status

Record links to tests, runtime traces, deployment evidence, and rollback verification in the capability evidence matrix before describing this flow as production verified.
