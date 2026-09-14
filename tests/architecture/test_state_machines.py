import pytest

from ois.application.state import ExecutionState, transition


def test_happy_path_is_explicit() -> None:
    state = transition(ExecutionState.PENDING, ExecutionState.AUTHORIZED)
    state = transition(state, ExecutionState.EXECUTING)
    state = transition(state, ExecutionState.VALIDATING)
    assert transition(state, ExecutionState.VERIFIED) is ExecutionState.VERIFIED


def test_invalid_transition_fails_closed() -> None:
    with pytest.raises(ValueError):
        transition(ExecutionState.PENDING, ExecutionState.EXECUTING)


def test_terminal_states_cannot_continue() -> None:
    with pytest.raises(ValueError):
        transition(ExecutionState.VERIFIED, ExecutionState.EXECUTING)
