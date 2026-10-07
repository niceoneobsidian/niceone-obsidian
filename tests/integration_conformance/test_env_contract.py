import os


def test_live_environment_is_disabled_by_default() -> None:
    assert os.getenv("OIS_LIVE_TESTS", "").lower() not in {"1", "true", "yes"}
