from ois.verify import CHECKS


def test_local_ci_covers_all_repository_ci_gates() -> None:
    names = {check.name for check in CHECKS}
    assert names == {
        "Ruff lint",
        "Ruff format",
        "Mypy",
        "Bandit",
        "Gitleaks",
        "License compliance",
        "OIS governance",
        "Tests",
    }


def test_python_checks_use_current_interpreter() -> None:
    python_checks = [check for check in CHECKS if check.command[0] == "python"]
    assert {check.required_tool for check in python_checks} == {"python"}
