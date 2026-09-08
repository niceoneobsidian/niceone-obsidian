"""Append-only local backup/restore for personal OIS state."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .platform import BackupManifest, PersonalPlatform


def create_backup(platform: PersonalPlatform, destination: str) -> BackupManifest:
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "tenant": platform.tenant.__dict__,
        "sessions": platform.sessions,
        "executions": {k: v.__dict__ for k, v in platform.executions.items()},
        "approvals": {k: v.__dict__ for k, v in platform.approvals.items()},
        "knowledge": platform.knowledge,
        "memory": platform.memory,
        "entities": platform.entities,
        "relationships": platform.relationships,
        "learning_candidates": platform.learning_candidates,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    backup_id = checksum[:16]
    path = root / f"backup-{backup_id}.json"
    if path.exists():
        raise FileExistsError(f"backup already exists: {path}")
    path.write_text(canonical, encoding="utf-8")
    return BackupManifest(
        backup_id=backup_id,
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        tenant_id=platform.tenant.tenant_id,
        schema_version=1,
        included_domains=("sessions", "executions", "approvals", "knowledge", "memory", "semantic", "learning"),
        artifact_root=str(root),
        checksum=checksum,
    )


def verify_backup(path: str) -> bool:
    raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = Path(path).stem.removeprefix("backup-")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().startswith(expected)
