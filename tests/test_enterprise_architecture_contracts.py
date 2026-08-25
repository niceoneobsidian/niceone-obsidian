from dataclasses import FrozenInstanceError

import pytest

from ois.api.contracts import ApiRoute, ApiVersion
from ois.compliance.contracts import EvidenceRecord
from ois.configuration.contracts import ConfigurationVersion
from ois.data_governance.contracts import DataClassification
from ois.deployment.contracts import Environment
from ois.disaster_recovery.contracts import RecoveryPoint
from ois.distributed_execution.contracts import WorkItem
from ois.events.contracts import EventEnvelope
from ois.evolution.contracts import EvolutionCandidate, PromotionDecision
from ois.feature_flags.contracts import FeatureFlag
from ois.high_availability.contracts import FailureDomain
from ois.human_oversight.contracts import ApprovalRequest
from ois.identity.contracts import Principal
from ois.interoperability.contracts import AdapterContract
from ois.privacy.contracts import PrivacyDecision
from ois.release.contracts import ReleaseCandidate
from ois.secrets.contracts import SecretRef
from ois.security.contracts import SecurityContext
from ois.supply_chain.contracts import ArtifactProvenance
from ois.system.contracts import ArchitectureComponent, SystemManifest
from ois.tenancy.contracts import TenantScope


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ApiVersion(1, 0),
        lambda: ApiRoute("GET", "/health", ApiVersion(1, 0)),
        lambda: EvidenceRecord("control", "subject", "evidence", True),
        lambda: ConfigurationVersion("default", "1.0.0", (("mode", "safe"),)),
        lambda: DataClassification("internal", 30, "platform"),
        lambda: Environment("prod", "1.0.0"),
        lambda: RecoveryPoint("runtime", "checkpoint-1", "2026-08-25T00:00:00Z"),
        lambda: WorkItem("work-1", 1, {}),
        lambda: EventEnvelope("test", "event-1", "corr-1", {}),
        lambda: EvolutionCandidate("candidate-1", "baseline", "evidence"),
        lambda: PromotionDecision("candidate-1", False, "rollback"),
        lambda: FeatureFlag("feature", True),
        lambda: FailureDomain("zone-a", True, 10),
        lambda: ApprovalRequest("deploy", "high", "platform"),
        lambda: Principal("user-1", "user", "tenant-a"),
        lambda: AdapterContract("https", "1.0", "https://example.invalid"),
        lambda: PrivacyDecision("subject", "purpose", True),
        lambda: ReleaseCandidate("1.0.0", "artifact", "stable"),
        lambda: SecretRef("key", "1"),
        lambda: SecurityContext("user-1", "resource", "read"),
        lambda: ArtifactProvenance("artifact", "source", "sha256:abc"),
        lambda: ArchitectureComponent("kernel", "1.0.0"),
        lambda: SystemManifest("1.0.0", (ArchitectureComponent("kernel", "1.0.0"),)),
        lambda: TenantScope("tenant-a", "resources/*"),
    ],
)
def test_enterprise_architecture_contracts_are_frozen(factory) -> None:
    contract = factory()
    field_name = next(iter(contract.__dataclass_fields__))
    with pytest.raises(FrozenInstanceError):
        setattr(contract, field_name, None)
