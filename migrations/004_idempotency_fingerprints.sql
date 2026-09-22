-- Add request identity and durable idempotency result semantics.
ALTER TABLE ois_idempotency_results
    ADD COLUMN IF NOT EXISTS request_fingerprint TEXT;

CREATE INDEX IF NOT EXISTS idx_ois_idempotency_results_status
    ON ois_idempotency_results (status, created_at);
