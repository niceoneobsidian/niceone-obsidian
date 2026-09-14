from ois.application.state import ExecutionState
from ois.infrastructure.postgres_execution import PostgresExecutionStore


class Cursor:
    def __init__(self):
        self.queries = []
        self.row = ("pending",)

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.cursor_obj = Cursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def test_state_and_evidence_use_explicit_transactions():
    connections = []

    def factory():
        connection = Connection()
        connections.append(connection)
        return connection

    store = PostgresExecutionStore(factory)
    store.set_state("job-1", ExecutionState.AUTHORIZED)
    store.append_evidence("job-1", "authorization", {"decision": "allow"})
    assert len(connections) == 2
    assert all(connection.commits == 1 for connection in connections)
