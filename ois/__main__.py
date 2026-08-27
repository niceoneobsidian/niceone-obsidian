"""OIS command-line entrypoint."""

from __future__ import annotations

import sys

from .verify import main as verify_main


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m ois verify [--artifact ARTIFACT]")
        return 2

    command = sys.argv[1]
    if command == "verify":
        return verify_main(sys.argv[2:])

    print(f"ois: unknown command: {command}")
    print("usage: python -m ois verify [--artifact ARTIFACT]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
