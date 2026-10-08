"""Expanded operator commands for OIS secrets; registry contains metadata only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import UTC, datetime

DEFAULT_REGISTRY = Path(os.getenv("OIS_SECRET_REGISTRY", "~/.config/ois/secret-registry.json")).expanduser()


def _read(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "secrets": {}, "events": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("secrets"), dict):
        raise ValueError("invalid OIS secret registry schema")
    return value


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def _event(data: dict, action: str, name: str, actor: str) -> None:
    data["events"].append({"at": datetime.now(UTC).isoformat(), "action": action,
                           "name": name, "actor": actor})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ois secrets")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="initialize metadata registry")
    commands.add_parser("list", help="list secret metadata, never values")
    inspect = commands.add_parser("inspect", help="inspect secret metadata")
    inspect.add_argument("name")
    set_cmd = commands.add_parser("set", help="register secret metadata (value stays in provider)")
    set_cmd.add_argument("name")
    set_cmd.add_argument("--provider", required=True)
    set_cmd.add_argument("--environment", choices=["development", "test", "staging", "production"], required=True)
    set_cmd.add_argument("--owner", required=True)
    set_cmd.add_argument("--purpose", required=True)
    for command in ("get", "rotate", "revoke"):
        item = commands.add_parser(command, help=f"{command} a provider-backed secret")
        item.add_argument("name")
    commands.add_parser("health", help="report metadata registry health")
    commands.add_parser("audit", help="show metadata-only registry events")
    incident = commands.add_parser("incident", help="record an incident against a secret")
    incident.add_argument("name")
    incident.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    path = args.registry
    data = _read(path)
    actor = os.getenv("USER", "unknown")

    if args.command == "init":
        _write(path, data)
        print(f"Initialized metadata registry: {path}")
        return 0
    if args.command == "list":
        print(json.dumps(data["secrets"], indent=2, sort_keys=True))
        return 0
    if args.command == "health":
        print(json.dumps({"registry_exists": path.exists(), "secret_count": len(data["secrets"]),
                          "raw_values_stored": False, "permissions_checked": path.exists() and (path.stat().st_mode & 0o077) == 0}, indent=2))
        return 0 if not path.exists() or (path.stat().st_mode & 0o077) == 0 else 1
    if args.command == "audit":
        print(json.dumps(data["events"], indent=2))
        return 0
    if args.command == "inspect":
        record = data["secrets"].get(args.name)
        if record is None:
            print("secret metadata not found", file=sys.stderr)
            return 2
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0
    if args.command == "set":
        data["secrets"][args.name] = {
            "name": args.name, "provider": args.provider, "environment": args.environment,
            "owner": args.owner, "purpose": args.purpose, "state": "registered",
            "created_at": datetime.now(UTC).isoformat(),
        }
        _event(data, "metadata.register", args.name, actor)
        _write(path, data)
        print("Metadata registered. Secret value was not accepted or stored.")
        return 0
    if args.command == "incident":
        record = data["secrets"].get(args.name)
        if record is None:
            print("secret metadata not found", file=sys.stderr)
            return 2
        record["state"] = "quarantined"
        record["incident_reason"] = args.reason
        record["incident_at"] = datetime.now(UTC).isoformat()
        _event(data, "incident.quarantine_requested", args.name, actor)
        _write(path, data)
        print("Metadata quarantined. Provider revocation must be confirmed separately.")
        return 0
    if args.command in {"get", "rotate", "revoke"}:
        if args.name not in data["secrets"]:
            print("secret metadata not found", file=sys.stderr)
            return 2
        print(f"{args.command} requires a configured provider adapter; no secret value was emitted.", file=sys.stderr)
        return 3
    return 2
