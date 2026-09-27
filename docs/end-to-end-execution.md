# Complete End-to-End Execution Example

Client intent -> Control Plane authentication -> intent normalization -> policy/risk decision -> capability resolution -> versioned execution contract -> Execution Runtime -> PostgreSQL state transition -> worker lease/epoch ownership -> checkpoint/idempotency/outbox persistence -> validation -> evidence -> terminal state.

The path is complete only when tests demonstrate unauthorized requests cannot cross the execution boundary, duplicate requests converge on one idempotent result, stale workers cannot mutate fenced state, checkpoints reject stale epochs, side-effect completion is durable, crashed workers can be recovered, and evidence matches execution identity and terminal state.

Repository integration tests are executable evidence; deployment evidence remains separate.
