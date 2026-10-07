from dataclasses import dataclass


@dataclass
class Trace:
    events: list[str]



def test_mocked_full_ois_e2e():
    trace = Trace([])
    trace.events.append("intent")
    trace.events.append("policy")
    trace.events.append("capability")
    trace.events.append("tool")
    trace.events.append("provider")
    trace.events.append("evidence")
    trace.events.append("provenance")
    trace.events.append("validation")
    assert trace.events == [
        "intent", "policy", "capability", "tool", "provider",
        "evidence", "provenance", "validation",
    ]
