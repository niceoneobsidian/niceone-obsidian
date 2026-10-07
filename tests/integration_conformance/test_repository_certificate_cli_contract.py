from __future__ import annotations

import json
from pathlib import Path

from ois.infrastructure.source_adapters.bootstrap import build_application_source_adapter_registry
from ois.integration.repository_certificate import (
    DEFAULT_REGISTRY_FACTORY,
    main,
)


def test_application_bootstrap_is_the_canonical_source_registry() -> None:
    registry = build_application_source_adapter_registry()

    assert registry.list() == ("sportmonks:football:v3",)
    assert registry.spec("sportmonks:football:v3").provider == "sportmonks"


def test_repository_certificate_cli_uses_application_bootstrap(tmp_path: Path) -> None:
    output = tmp_path / "integration-conformance-certificate.json"
    root = Path(__file__).resolve().parents[2]

    exit_code = main(
        [
            "--root",
            str(root),
            "--commit",
            "cli-regression",
            "--registry-factory",
            DEFAULT_REGISTRY_FACTORY,
            "--strict",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    certificate = json.loads(output.read_text(encoding="utf-8"))
    assert certificate["valid"] is True
    assert certificate["commit"] == "cli-regression"
    assert certificate["report"]["matrix"][0]["ADAPTER"] == "IMPLEMENTED"
    assert certificate["report"]["matrix"][0]["REGISTRATION"] == "IMPLEMENTED"
    assert certificate["report"]["matrix"][0]["CAPABILITY"] == "IMPLEMENTED"
    assert certificate["report"]["matrix"][0]["CONTRACT TEST"] == "TESTED"
    assert certificate["report"]["matrix"][0]["CI GATE"] == "TESTED"
