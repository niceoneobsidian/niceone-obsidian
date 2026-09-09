"""Minimal personal control interface for OIS."""

from __future__ import annotations

import argparse
import json
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ois")
    sub = parser.add_subparsers(dest="command", required=True)
    ask = sub.add_parser("ask", help="create an execution intent")
    ask.add_argument("objective")
    sub.add_parser("status", help="show runtime readiness")
    sub.add_parser("approvals", help="list pending approvals")
    inspect = sub.add_parser("inspect", help="inspect an execution")
    inspect.add_argument("execution_id")
    return parser


def main(platform=None, argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if platform is None:
        from .bootstrap import build_personal_platform

        platform = build_personal_platform()

    if args.command == "status":
        print(json.dumps(platform.health(), indent=2, sort_keys=True))
        return 0
    if args.command == "ask":
        record = platform.create_execution(args.objective)
        print(json.dumps(record.__dict__, indent=2, sort_keys=True))
        return 0
    if args.command == "approvals":
        pending = [a.__dict__ for a in platform.approvals.values() if a.status == "pending"]
        print(json.dumps(pending, indent=2, sort_keys=True))
        return 0
    if args.command == "inspect":
        record = platform.executions.get(args.execution_id)
        if record is None:
            print("execution not found", file=sys.stderr)
            return 1
        print(json.dumps(record.__dict__, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
