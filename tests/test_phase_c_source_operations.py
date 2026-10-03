"""Tests for Phase C source policies, pipeline, configuration, and recovery."""

from ois.control_plane.source_configuration import SourceConfiguration, SourceConfigurationService
from ois.control_plane.source_policies import SourcePolicy, SourcePolicyStore
from ois.domains.social_intelligence.events import CanonicalSourceEvent
from ois.runtime.source_pipeline import SourceIntelligencePipeline
from ois.runtime.source_recovery import DeadLetterStore, SourceRecovery


def event() -> CanonicalSourceEvent:
    return CanonicalSourceEvent(
        event_id="evt-1",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        source_id="google:source",
        source_record_id="record-1",
        event_type="source.created",
        payload={"text": "hello"},
        payload_hash="hash",
    )


def test_source_policy_enforces_tenant_and_credential() -> None:
    store = SourcePolicyStore()
    store.put(SourcePolicy("tenant-a", "workspace-a", "google:source"))
    assert store.authorize(
        "tenant-a", "workspace-a", "google:source", credential_present=True
    ).source_id == "google:source"


def test_source_configuration_creates_policy_and_can_disable() -> None:
    service = SourceConfigurationService()
    service.upsert(
        SourceConfiguration(
            "tenant-a", "workspace-a", "google:source", "google", credential_id="cred-1"
        )
    )
    disabled = service.disable("tenant-a", "workspace-a", "google:source")
    assert disabled.enabled is False
    assert service.policies.get("tenant-a", "workspace-a", "google:source").enabled is False


def test_pipeline_processes_authorized_event() -> None:
    policies = SourcePolicyStore()
    policies.put(SourcePolicy("tenant-a", "workspace-a", "google:source"))
    dead_letters = DeadLetterStore()
    pipeline = SourceIntelligencePipeline(
        policies=policies,
        recovery=SourceRecovery(dead_letters),
        dead_letters=dead_letters,
    )
    seen: list[str] = []
    result = pipeline.process(event(), lambda item: seen.append(item.event_id))
    assert result.accepted is True
    assert seen == ["evt-1"]


def test_pipeline_dead_letters_after_bounded_failures() -> None:
    policies = SourcePolicyStore()
    policies.put(SourcePolicy("tenant-a", "workspace-a", "google:source"))
    dead_letters = DeadLetterStore()
    pipeline = SourceIntelligencePipeline(
        policies=policies,
        recovery=SourceRecovery(dead_letters, max_attempts=2),
        dead_letters=dead_letters,
    )
    result = pipeline.process(event(), lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert result.accepted is False
    assert result.dead_lettered is True
    assert dead_letters.get("evt-1").attempts == 2


def test_dead_letter_replay_removes_successfully_replayed_event() -> None:
    store = DeadLetterStore()
    recovery = SourceRecovery(store, max_attempts=1)
    recovery.run(event(), lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert recovery.replay("evt-1", lambda _: None) is True
    assert store.size() == 0
