from ois.kernel import CapabilityRegistry as KernelCapabilityRegistry
from ois.kernel.registry import CapabilityRegistry as CompatibilityCapabilityRegistry
from ois.registries import CapabilityRegistry


def test_kernel_registry_is_only_a_compatibility_export() -> None:
    assert KernelCapabilityRegistry is CapabilityRegistry
    assert CompatibilityCapabilityRegistry is CapabilityRegistry
