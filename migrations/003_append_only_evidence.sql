-- Enforce append-only semantics for execution_evidence
CREATE OR REPLACE FUNCTION reject_execution_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'execution_evidence is append-only: updates and deletes are prohibited';
END;
$$;

DROP TRIGGER IF EXISTS execution_evidence_append_only ON execution_evidence;

CREATE TRIGGER execution_evidence_append_only
BEFORE UPDATE OR DELETE ON execution_evidence
FOR EACH ROW
EXECUTE FUNCTION reject_execution_evidence_mutation();
