"""OIS command-line entry point."""
from __future__ import annotations

import argparse

from ois.verify import main as verify_main


def main() -> int:
    parser = argparse.ArgumentParser(prog="ois")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify", help="run the canonical repository verification gate")
    verify.add_argument("--artifact", default=None)
    args = parser.parse_args()
    if args.command == "verify":
        argv = [] if args.artifact is None else ["--artifact", args.artifact]
        return verify_main(argv)
    return 2
