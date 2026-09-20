"""Run the OIS operator CLI with ``python -m ois``."""

def main() -> int:
    from .cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
