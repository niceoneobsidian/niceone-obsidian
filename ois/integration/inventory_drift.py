"""Detect drift between the declared provider inventory and the canonical registry.

``config/integration-provider-certificate.json`` is a hand-maintained inventory.
The canonical truth for governed sources is ``SourceAdapterRegistry``. This module
never promotes anything: it only reports which inventory providers are absent from
the registry (and vice versa) so the gap stays visible in the certificate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ois.infrastructure.source_adapters.base import SourceAdapterRegistry

DEFAULT_INVENTORY_PATH = "config/integration-provider-certificate.json"
DEFAULT_BACKLOG_PATH = "manifests/provider_registration_backlog.json"
BACKLOG_REQUIRED_EVIDENCE = (
    "client",
    "credential_injection",
    "scopes",
    "policy",
    "tests",
    "live_verification",
)
BACKLOG_ALLOWED_STATES = frozenset({"UNKNOWN", "MISSING", "NOT_STARTED"})
_PLACEHOLDER_PREFIX = "not-"


@dataclass(frozen=True)
class InventoryDrift:
    inventory_path: str
    inventory_present: bool
    in_both: tuple[str, ...]
    inventory_only: tuple[str, ...]
    registry_only: tuple[str, ...]
    unreadable: bool = False
    backlog_path: str = DEFAULT_BACKLOG_PATH
    backlog_present: bool = False
    backlog_ids: tuple[str, ...] = ()
    backlog_problems: tuple[str, ...] = ()

    @property
    def explained(self) -> tuple[str, ...]:
        """Inventory providers absent from the registry that the backlog documents."""
        return tuple(sorted(set(self.inventory_only) & set(self.backlog_ids)))

    @property
    def unexplained(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.inventory_only) - set(self.backlog_ids)))

    @property
    def drifted(self) -> bool:
        return bool(self.failures())

    def failures(self) -> tuple[str, ...]:
        """Hard failures: only *unexplained* drift or an invalid backlog."""
        out = [f"{sid}:INVENTORY:unexplained-not-in-source-registry" for sid in self.unexplained]
        out += [f"{sid}:INVENTORY:registered-but-not-in-inventory" for sid in self.registry_only]
        out += [
            f"{sid}:BACKLOG:stale-provider-is-registered"
            for sid in self.in_both
            if sid in self.backlog_ids
        ]
        out += [
            f"{sid}:BACKLOG:not-in-inventory"
            for sid in self.backlog_ids
            if sid not in set(self.in_both) | set(self.inventory_only)
        ]
        out += list(self.backlog_problems)
        if self.unreadable:
            out.append("INVENTORY:unreadable")
        return tuple(sorted(set(out)))

    def to_dict(self) -> dict[str, object]:
        return {
            "inventory_path": self.inventory_path,
            "inventory_present": self.inventory_present,
            "unreadable": self.unreadable,
            "in_both": list(self.in_both),
            "inventory_only": list(self.inventory_only),
            "registry_only": list(self.registry_only),
            "backlog_path": self.backlog_path,
            "backlog_present": self.backlog_present,
            "registration_backlog": list(self.explained),
            "unexplained_drift": list(self.unexplained),
            "backlog_problems": list(self.backlog_problems),
            "failures": list(self.failures()),
            "drifted": self.drifted,
        }


def _load_backlog(path: Path) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """Return (present, ids, problems) for the registration backlog."""
    if not path.is_file():
        return False, (), ()
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
        if not isinstance(entries, list):
            raise ValueError("entries")
    except (OSError, ValueError, AttributeError):
        return True, (), ("BACKLOG:unreadable",)
    ids: list[str] = []
    problems: list[str] = []
    for entry in entries:
        sid = entry.get("source_id") if isinstance(entry, dict) else None
        if not isinstance(sid, str) or not sid:
            problems.append("BACKLOG:entry-missing-source-id")
            continue
        if sid in ids:
            problems.append(f"{sid}:BACKLOG:duplicate")
        ids.append(sid)
        if entry.get("registration_state") != "NOT_REGISTERED":
            problems.append(f"{sid}:BACKLOG:unsupported-registration-claim")
        evidence = entry.get("required_evidence")
        if not isinstance(evidence, dict):
            problems.append(f"{sid}:BACKLOG:required-evidence-missing")
            continue
        for key in BACKLOG_REQUIRED_EVIDENCE:
            state = evidence.get(key)
            if state is None:
                problems.append(f"{sid}:BACKLOG:required-evidence-missing={key}")
            elif state not in BACKLOG_ALLOWED_STATES:
                problems.append(f"{sid}:BACKLOG:unsupported-evidence-claim={key}:{state}")
    return True, tuple(sorted(set(ids))), tuple(sorted(set(problems)))


def compare_inventory_to_registry(
    root: Path,
    registry: SourceAdapterRegistry,
    inventory_path: Path | None = None,
    backlog_path: Path | None = None,
) -> InventoryDrift:
    path = inventory_path or (root / DEFAULT_INVENTORY_PATH)
    backlog = backlog_path or (root / DEFAULT_BACKLOG_PATH)
    present, backlog_ids, problems = _load_backlog(backlog)
    registered = set(registry.list())
    rel = _rel(root, path)

    def build(
        inventory_present: bool,
        in_both: tuple[str, ...],
        inventory_only: tuple[str, ...],
        registry_only: tuple[str, ...],
        unreadable: bool = False,
    ) -> InventoryDrift:
        return InventoryDrift(
            inventory_path=rel,
            inventory_present=inventory_present,
            in_both=in_both,
            inventory_only=inventory_only,
            registry_only=registry_only,
            unreadable=unreadable,
            backlog_path=_rel(root, backlog),
            backlog_present=present,
            backlog_ids=backlog_ids,
            backlog_problems=problems,
        )

    if not path.is_file():
        return build(False, (), (), tuple(sorted(registered)))
    try:
        providers = json.loads(path.read_text(encoding="utf-8")).get("providers", [])
        declared = {
            str(item["source_id"])
            for item in providers
            if isinstance(item, dict)
            and isinstance(item.get("source_id"), str)
            and not item["source_id"].startswith(_PLACEHOLDER_PREFIX)
        }
    except (OSError, ValueError, AttributeError):
        return build(True, (), (), tuple(sorted(registered)), unreadable=True)
    return build(
        True,
        tuple(sorted(declared & registered)),
        tuple(sorted(declared - registered)),
        tuple(sorted(registered - declared)),
    )


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
