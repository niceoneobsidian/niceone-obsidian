"""Operator CLI for secret scanning and controlled secret use."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .scanner import SecretScanner


def main(argv: Sequence[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    operator_commands = {
        "init",
        "list",
        "get",
        "set",
        "rotate",
        "revoke",
        "inspect",
        "health",
        "audit",
        "incident",
    }
    if args_in and args_in[0] in operator_commands:
        from .operator_cli import main as operator_main

        return operator_main(args_in)

    parser = argparse.ArgumentParser(prog="ois secrets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("path", nargs="?", default=".")
    scan_parser.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--secret", action="append", default=[])
    run_parser.add_argument("exec_command", nargs=argparse.REMAINDER)

    args = parser.parse_args(args_in)
    if args.command == "scan":
        findings = SecretScanner().scan_path(Path(args.path))
        data = [
            {
                "detector": finding.detector,
                "path": finding.path,
                "line": finding.line,
                "fingerprint": finding.fingerprint,
            }
            for finding in findings
        ]
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(
                "\n".join(
                    f"{item['path']}:{item['line']} {item['detector']} "
                    f"[{item['fingerprint']}]"
                    for item in data
                )
            )
        return 1 if findings else 0

    if args.command == "run":
        from .runtime_cli import run_command

        command = list(args.exec_command)
        if command and command[0] == "--":
            command = command[1:]
        return run_command(args.secret, command)

    if args.command == "doctor":
        data = {
            "environment": os.getenv("OIS_ENV", "development"),
            "secret_files_allowed": False,
            "raw_secret_logging": False,
        }
        print(json.dumps(data, indent=2) if args.json else data)
        return 0

    raise SystemExit("secrets run requires configured SecretRuntime, broker and policy")
