from __future__ import annotations

import pytest

from ois.runtime.llm_gateway import ModelOutput, ModelOutputError


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        None,
        {"command": "rm -rf /"},
        ["not", "text"],
    ],
    ids=["empty", "whitespace", "none", "command-object", "list"],
)
def test_model_output_contract_rejects_non_text_or_empty_content(
    content: object,
) -> None:
    with pytest.raises(ModelOutputError, match="non-empty string"):
        ModelOutput(content)  # type: ignore[arg-type]


def test_model_output_contract_preserves_valid_text_exactly() -> None:
    output = ModelOutput("  keep the model response as inert text  ")

    assert output.content == "  keep the model response as inert text  "
