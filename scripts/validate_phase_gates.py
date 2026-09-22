#!/usr/bin/env python3
"""Validate the repository's strictly ordered implementation contract.

This is intentionally dependency-free so it can run before project dependencies
are installed. A later phase cannot become active until its predecessor is
marked complete and the active phase is advanced explicitly in the manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "phase-gates.json"
EXPECTED_NAMES = [
    "Repository Integrity",
    "Kernel Conformance",
    "Recovery Conformance",
    "Real PostgreSQL + Redis",
    "Supervisor + Agent + Tool E2E",
    "Security / Tenant Isolation",
    "Observability",
    "Real External APIs",
    "Production Canary",
    "Measured Optimization",
    "Controlled Evolution",
]
ALLOWED_STATUSES = {"planned", "active", "complete"}


def fail(message: str) -> None:
    raise SystemExit(f"phase-gate validation failed: {message}")


def main() -> None:
    if not MANIFEST.is_file():
        fail(f"missing manifest: {MANIFEST.relative_to(ROOT)}")

    try:
        document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {exc}")

    phases = document.get("phases")
    if document.get("schema_version") != 1:
        fail("unsupported schema_version")
    if document.get("promotion_policy") != "strict_order":
        fail("promotion_policy must remain strict_order")
    if not isinstance(phases, list) or len(phases) != len(EXPECTED_NAMES):
        fail("manifest must contain exactly 11 phases")

    ids = [phase.get("id") for phase in phases]
    if ids != list(range(1, 12)):
        fail(f"phase ids must be contiguous 1..11, got {ids}")

    active = []
    for expected_id, (phase, expected_name) in enumerate(
        zip(phases, EXPECTED_NAMES, strict=True), 1
    ):
        if phase.get("name") != expected_name:
            fail(f"phase {expected_id} has unexpected name")
        if phase.get("status") not in ALLOWED_STATUSES:
            fail(f"phase {expected_id} has invalid status")
        if not phase.get("exit_evidence") or not phase.get("required_checks"):
            fail(f"phase {expected_id} must declare evidence and checks")
        if phase.get("status") == "active":
            active.append(expected_id)
        expected_entry = None if expected_id == 1 else expected_id - 1
        if phase.get("entry_gate") != expected_entry:
            fail(f"phase {expected_id} has an invalid entry_gate")

    if len(active) != 1:
        fail(f"exactly one phase must be active, got {active}")
    active_phase = document.get("active_phase")
    if active_phase != active[0]:
        fail("active_phase does not match the active phase status")

    for phase in phases:
        phase_id = phase["id"]
        status = phase["status"]
        if phase_id < active[0] and status != "complete":
            fail(f"phase {phase_id} must be complete before phase {active[0]} is active")
        if phase_id > active[0] and status != "planned":
            fail(f"phase {phase_id} must remain planned until promoted in order")

    print(f"phase-gate validation passed: phase {active[0]} active; strict order enforced")


if __name__ == "__main__":
    main()
