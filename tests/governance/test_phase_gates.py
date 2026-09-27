from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config" / "phase-gates.json"
VALIDATOR = ROOT / "scripts" / "validate_phase_gates.py"


def test_phase_manifest_has_phase_two_active_after_phase_one_completion() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["active_phase"] == 2
    statuses = [phase["status"] for phase in document["phases"]]
    assert statuses == [
        "complete",
        "active",
        *(["planned"] * 9),
    ]


def test_phase_validator_passes_for_repository_manifest() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_phase_validator_rejects_a_skipped_phase(tmp_path: Path) -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    document["active_phase"] = 3
    document["phases"][0]["status"] = "complete"
    document["phases"][1]["status"] = "planned"
    document["phases"][2]["status"] = "active"
    manifest = tmp_path / "phase-gates.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    validator = VALIDATOR.read_text(encoding="utf-8")
    isolated_validator = tmp_path / "validate_phase_gates.py"
    isolated_validator.write_text(
        validator.replace(
            'MANIFEST = ROOT / "config" / "phase-gates.json"',
            f"MANIFEST = Path({str(manifest)!r})",
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(isolated_validator)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "phase 2" in result.stderr
