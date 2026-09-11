"""OIS operator CLI.

The CLI is an operator interface, not a second execution kernel. It reports
repository/runtime evidence and delegates verification to the canonical local
CI verifier. It intentionally does not bypass policy, authorization, or kernel
execution boundaries.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]


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


def _domain_inventory(kind: str) -> list[str]:
    """Return source-level domain evidence without claiming runtime activation."""
    base = ROOT / "ois" / "domains"
    if not base.exists():
        return []
    names: list[str] = []
    for path in sorted(base.iterdir()):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        if kind in {"capabilities", "agents"} and (path / "registry.py").exists():
            names.append(path.name)
        elif kind == "tools" and (path / "connectors_manifest.py").exists():
            names.append(path.name)
        elif kind == "workflows" and (path / "workflows.py").exists():
            names.append(path.name)
    return names


def cmd_status(_: argparse.Namespace) -> int:
    branch = _git("branch", "--show-current") or "unknown"
    commit = _git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = bool(_git("status", "--porcelain"))
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print("NICEONE OBSIDIAN — OIS STATUS")
    print("=" * 56)
    print(f"Repository : {ROOT}")
    print(f"Branch     : {branch}")
    print(f"Commit     : {commit}")
    print(f"Working tree: {'DIRTY' if dirty else 'CLEAN'}")
    print(f"Python     : {python_version}")
    print(f"Environment: {os.getenv('OIS_ENV', 'development')}")
    print("Architecture: capability-driven, governed execution")
    print("Evidence   : source/CI evidence only; no production claim")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    print("OIS DOCTOR")
    print("=" * 56)
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


def _inventory(kind: str, title: str) -> int:
    items = _domain_inventory(kind)
    print(f"OIS {title.upper()} — SOURCE INVENTORY")
    print("=" * 56)
    if not items:
        print("No matching domain source evidence found.")
    else:
        for item in items:
            print(f"- {item}")
    print("-" * 56)
    print("NOTE: inventory is discovery evidence, not activation or production verification.")
    return 0


def cmd_capabilities(_: argparse.Namespace) -> int:
    return _inventory("capabilities", "capabilities")


def cmd_agents(_: argparse.Namespace) -> int:
    return _inventory("agents", "agents")


def cmd_tools(_: argparse.Namespace) -> int:
    return _inventory("tools", "tools")


def cmd_workflows(_: argparse.Namespace) -> int:
    return _inventory("workflows", "workflows")


def cmd_health(_: argparse.Namespace) -> int:
    checks = {
        "kernel": ROOT / "ois" / "kernel",
        "control_plane": ROOT / "ois" / "control_plane",
        "runtime": ROOT / "ois" / "runtime",
        "verification": ROOT / "ois" / "verify.py",
    }
    print("OIS HEALTH")
    print("=" * 56)
    for name, path in checks.items():
        print(_mark(path.exists(), name))
    return 0 if all(path.exists() for path in checks.values()) else 1


def cmd_version(_: argparse.Namespace) -> int:
    print("OIS CLI v1")
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return 0


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
        "version": cmd_version,
    }
    for name, handler in handlers.items():
        child = sub.add_parser(name)
        child.set_defaults(handler=handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
