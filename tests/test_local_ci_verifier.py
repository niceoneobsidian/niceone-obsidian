from ois.verify import CHECKS, Check, classify_output, overall_state, run_check


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


def test_missing_optional_tool_is_skipped(monkeypatch) -> None:
    check = Check("Bandit", ("bandit", "-r", "."), "bandit")
    monkeypatch.setattr("ois.verify.executable", lambda _: None)
    assert run_check(check) == (
        "SKIPPED",
        None,
        "required executable is not installed",
    )


def test_missing_mypy_module_is_skipped() -> None:
    check = Check("Mypy", ("python", "-m", "mypy", "ois"), "python")
    output = "/venv/bin/python: No module named mypy"
    assert classify_output(check, 1, output) == "SKIPPED"


def test_pydantic_collection_failure_is_environment_limited() -> None:
    check = Check("Tests", ("python", "-m", "pytest", "-q"), "python")
    output = "E ModuleNotFoundError: No module named 'pydantic'"
    assert classify_output(check, 1, output) == "ENV_LIMITED"


def test_real_check_failure_remains_failure() -> None:
    check = Check("Ruff lint", ("ruff", "check", "."), "ruff")
    assert classify_output(check, 1, "E501 line too long") == "FAIL"


def test_overall_state_preserves_real_failures() -> None:
    assert overall_state(["PASS", "SKIPPED", "ENV_LIMITED"]) == "PASS WITH LIMITATIONS"
    assert overall_state(["PASS", "FAIL", "SKIPPED"]) == "FAIL"
    assert overall_state(["PASS", "PASS"]) == "PASS"
