import json
from pathlib import Path

from ops.p1.chaos.ois_chaos_interceptor import ChaosConfig, ChaosInjectionEngine


def test_chaos_disabled_by_default() -> None:
    engine = ChaosInjectionEngine()
    assert engine.enabled is False
    assert engine.choose_fault() is None


def test_chaos_activation_is_explicit() -> None:
    engine = ChaosInjectionEngine(ChaosConfig(failure_probability=1.0))
    engine.activate_chaos_matrix()
    assert engine.enabled is True
    engine.deactivate_chaos_matrix()
    assert engine.enabled is False


def test_dashboard_is_valid_json() -> None:
    path = Path("ops/p1/observability/grafana/ois_p1_operations.json")
    dashboard = json.loads(path.read_text())
    assert len(dashboard["panels"]) == 3
    assert any('status="423"' in t["expr"] for p in dashboard["panels"] for t in p["targets"])
