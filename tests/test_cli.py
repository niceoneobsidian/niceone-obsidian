from __future__ import annotations

import json

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
        "summary",
        "version",
    } <= commands


def test_version(capsys) -> None:
    assert main(["version"]) == 0
    assert "OIS CLI v1.1" in capsys.readouterr().out


def test_status(capsys) -> None:
    assert main(["status"]) == 0
    output = capsys.readouterr().out
    assert "OIS STATUS" in output
    assert "Evidence" in output


def test_status_json(capsys) -> None:
    assert main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"]
    assert "production" in payload["evidence"].lower()


def test_health(capsys) -> None:
    assert main(["health"]) == 0
    output = capsys.readouterr().out
    assert "kernel" in output
    assert "verification" in output


def test_inventory_commands(capsys) -> None:
    for command in ("capabilities", "agents", "tools", "workflows"):
        assert main([command]) == 0
        assert "SOURCE INVENTORY" in capsys.readouterr().out


def test_inventory_json(capsys) -> None:
    assert main(["capabilities", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence"] == "source_discovery"
    assert payload["verified"] is False
    assert isinstance(payload["files"], list)


def test_summary(capsys) -> None:
    assert main(["summary"]) == 0
    output = capsys.readouterr().out
    assert "OPERATOR SUMMARY" in output
    assert "Production : NOT VERIFIED" in output


def test_summary_json(capsys) -> None:
    assert main(["summary", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["production_verified"] is False
    assert "inventory" in payload
