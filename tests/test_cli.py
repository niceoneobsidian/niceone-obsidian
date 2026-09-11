from __future__ import annotations

from ois.cli import build_parser, main


def test_parser_exposes_operator_commands() -> None:
    parser = build_parser()
    commands = set(parser._subparsers._group_actions[0].choices)
    assert {
        "status",
        "doctor",
        "verify",
        "capabilities",
        "agents",
        "tools",
        "workflows",
        "health",
        "version",
    } <= commands


def test_version(capsys) -> None:
    assert main(["version"]) == 0
    assert "OIS CLI v1" in capsys.readouterr().out


def test_status(capsys) -> None:
    assert main(["status"]) == 0
    output = capsys.readouterr().out
    assert "OIS STATUS" in output
    assert "Evidence" in output


def test_health(capsys) -> None:
    assert main(["health"]) == 0
    output = capsys.readouterr().out
    assert "kernel" in output
    assert "verification" in output


def test_inventory_commands(capsys) -> None:
    for command in ("capabilities", "agents", "tools", "workflows"):
        assert main([command]) == 0
        assert "SOURCE INVENTORY" in capsys.readouterr().out
