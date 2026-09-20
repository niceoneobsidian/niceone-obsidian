"""OIS operator CLI.

The CLI is an operator interface, not a second execution kernel. It reports
repository/runtime evidence and delegates verification to the canonical local
CI verifier. It intentionally does not bypass policy, authorization, or kernel
execution boundaries.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
OIS_ROOT = ROOT / "ois"


class InventoryData(TypedDict):
    kind: str
    evidence: str
    verified: bool
    count: int
    files: list[str]


class StatusData(TypedDict):
    branch: str
    commit: str
    working_tree: str


class SummaryData(TypedDict):
    status: StatusData
    inventory: dict[str, int]
    evidence: str
    production_verified: bool


def _run(*command: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout.strip()


def _git(*args: str) -> str:
    code, output = _run("git", *args)
    return output if code == 0 else ""


def _mark(ok: bool, label: str) -> str:
    return f"{'PASS' if ok else 'FAIL':<5} {label}"


def _source_files(*roots: Path, patterns: tuple[str, ...] = ("*.py",)) -> list[str]:
    """Return deterministic source-level evidence without importing modules."""
    files: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            files.extend(
                path.relative_to(ROOT).as_posix()
                for path in root.rglob(pattern)
                if path.is_file() and path.name != "__init__.py"
            )
    return sorted(set(files))


def _inventory_data(kind: str) -> InventoryData:
    roots = {
        "capabilities": (OIS_ROOT / "capabilities", OIS_ROOT / "domains"),
        "agents": (OIS_ROOT / "agents", OIS_ROOT / "domains"),
        "tools": (OIS_ROOT / "integration", OIS_ROOT / "tools", OIS_ROOT / "domains"),
        "workflows": (OIS_ROOT / "workflows", OIS_ROOT / "domains"),
    }
    files = _source_files(*roots.get(kind, ()))
    return {
        "kind": kind,
        "evidence": "source_discovery",
        "verified": False,
        "count": len(files),
        "files": files,
    }


def cmd_status(args: argparse.Namespace) -> int:
    branch = _git("branch", "--show-current") or "unknown"
    commit = _git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = bool(_git("status", "--porcelain"))
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    data = {
        "repository": str(ROOT),
        "branch": branch,
        "commit": commit,
        "working_tree": "dirty" if dirty else "clean",
        "python": python_version,
        "environment": os.getenv("OIS_ENV", "development"),
        "architecture": "capability-driven, governed execution",
        "evidence": "source/CI evidence only; no production claim",
    }
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0
    print("NICEONE OBSIDIAN — OIS STATUS")
    print("=" * 56)
    print(f"Repository : {data['repository']}")
    print(f"Branch     : {data['branch']}")
    print(f"Commit     : {data['commit']}")
    print(f"Working tree: {data['working_tree'].upper()}")
    print(f"Python     : {data['python']}")
    print(f"Environment: {data['environment']}")
    print(f"Architecture: {data['architecture']}")
    print(f"Evidence   : {data['evidence']}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = [
        ("Python >= 3.12", sys.version_info >= (3, 12)),
        ("Git", shutil.which("git") is not None),
        ("OIS package", importlib.util.find_spec("ois") is not None),
        ("pyproject.toml", (ROOT / "pyproject.toml").is_file()),
        ("pytest", shutil.which("pytest") is not None),
        ("Ruff", shutil.which("ruff") is not None),
        ("Mypy", shutil.which("mypy") is not None),
        ("Bandit", shutil.which("bandit") is not None),
        ("Gitleaks", shutil.which("gitleaks") is not None),
        ("GitHub CLI", shutil.which("gh") is not None),
    ]
    if args.json:
        print(json.dumps({"checks": [{"name": label, "ok": ok} for label, ok in checks]}, indent=2))
        return 0 if all(ok for _, ok in checks) else 1
    print("OIS DOCTOR")
    print("=" * 56)
    for label, ok in checks:
        print(_mark(ok, label))
    failures = [label for label, ok in checks if not ok]
    print("-" * 56)
    print(f"RESULT: {'PASS' if not failures else 'ATTENTION'}")
    return 0


def cmd_verify(_: argparse.Namespace) -> int:
    print("OIS VERIFICATION")
    print("=" * 56)
    from ois.verify import main as verify_main

    return verify_main()


def _inventory(kind: str, title: str, as_json: bool) -> int:
    data = _inventory_data(kind)
    if as_json:
        print(json.dumps(data, indent=2))
        return 0
    print(f"OIS {title.upper()} — SOURCE INVENTORY")
    print("=" * 56)
    files = data["files"]
    if not files:
        print("No matching source evidence found.")
    else:
        for item in files:
            print(f"- {item}")
    print("-" * 56)
    print(
        f"COUNT: {data['count']} | EVIDENCE: {data['evidence']} | "
        f"VERIFIED: {str(data['verified']).lower()}"
    )
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    return _inventory("capabilities", "capabilities", args.json)


def cmd_agents(args: argparse.Namespace) -> int:
    return _inventory("agents", "agents", args.json)


def cmd_tools(args: argparse.Namespace) -> int:
    return _inventory("tools", "tools", args.json)


def cmd_workflows(args: argparse.Namespace) -> int:
    return _inventory("workflows", "workflows", args.json)


def cmd_health(args: argparse.Namespace) -> int:
    checks = {
        "kernel": OIS_ROOT / "kernel",
        "control_plane": OIS_ROOT / "control_plane",
        "runtime": OIS_ROOT / "runtime",
        "verification": OIS_ROOT / "verify.py",
        "integration": OIS_ROOT / "integration",
    }
    results = {name: path.exists() for name, path in checks.items()}
    if args.json:
        print(
            json.dumps({"evidence": "source_presence", "checks": results}, indent=2, sort_keys=True)
        )
        return 0 if all(results.values()) else 1
    print("OIS HEALTH")
    print("=" * 56)
    for name, ok in results.items():
        print(_mark(ok, name))
    return 0 if all(results.values()) else 1


def cmd_summary(args: argparse.Namespace) -> int:
    inventory: dict[str, InventoryData] = {
        kind: _inventory_data(kind)
        for kind in ("capabilities", "agents", "tools", "workflows")
    }

    status: StatusData = {
        "branch": _git("branch", "--show-current") or "unknown",
        "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
        "working_tree": "dirty" if _git("status", "--porcelain") else "clean",
    }

    data: SummaryData = {
        "status": status,
        "inventory": {kind: value["count"] for kind, value in inventory.items()},
        "evidence": "source_discovery",
        "production_verified": False,
    }
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0
    print("NICEONE OBSIDIAN — OIS OPERATOR SUMMARY")
    print("=" * 56)
    print(f"Repository : {data['status']['branch']} @ {data['status']['commit']}")
    print(f"Working tree: {data['status']['working_tree'].upper()}")
    print("Inventory  :")
    for kind, count in data["inventory"].items():
        print(f"  {kind:<13} {count}")
    print("-" * 56)
    print("Evidence   : source discovery")
    print("Production : NOT VERIFIED")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print("OIS CLI v1.1")
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return 0


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ois",
        description="Niceone Obsidian Intelligence System operator CLI",
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    handlers = {
        "status": cmd_status,
        "doctor": cmd_doctor,
        "verify": cmd_verify,
        "capabilities": cmd_capabilities,
        "agents": cmd_agents,
        "tools": cmd_tools,
        "workflows": cmd_workflows,
        "health": cmd_health,
        "summary": cmd_summary,
        "version": cmd_version,
    }
    for name, handler in handlers.items():
        child = sub.add_parser(name)
        if name != "verify":
            _add_json_flag(child)
        child.set_defaults(handler=handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
