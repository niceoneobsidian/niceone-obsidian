"""Backup/restore orchestration contracts with mandatory verification."""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackupManifest:
    artifact: str
    sha256: str
    bytes: int


class BackupManager:
    def dump_postgres(self, output: Path, database_url: str) -> BackupManifest:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as stream:
            subprocess.run(["pg_dump", "--format=custom", "--file", str(output), database_url], check=True)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        return BackupManifest(str(output), digest, output.stat().st_size)

    def verify(self, manifest: BackupManifest) -> bool:
        path = Path(manifest.artifact)
        if not path.is_file() or path.stat().st_size != manifest.bytes:
            return False
        return hashlib.sha256(path.read_bytes()).hexdigest() == manifest.sha256

    def restore_postgres(self, manifest: BackupManifest, database_url: str) -> None:
        if not self.verify(manifest):
            raise ValueError("backup integrity verification failed")
        subprocess.run(["pg_restore", "--clean", "--if-exists", "--dbname", database_url, manifest.artifact], check=True)
