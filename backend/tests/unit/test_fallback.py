"""Unit tests for primary-then-fallback model switching (AGENTS.md §5.9),
using `FakeLlm` so no network/API key is needed.
"""

import pytest

from app.llm.base import StreamToken
from app.llm.fake_llm import FakeLlm, ScriptedResponse
from app.llm.fallback import stream_with_fallback


def test_primary_model_success_never_triggers_fallback() -> None:
    llm = FakeLlm([ScriptedResponse(text="hello")])
    events, model_used, fallback_used = stream_with_fallback(
        llm, [], [], "primary-model", "fallback-model"
    )
    tokens = [event.text for event in events if isinstance(event, StreamToken)]
    assert "".join(tokens) == "hello"
    assert model_used == "primary-model"
    assert fallback_used is False
    assert len(llm.calls) == 1


def test_primary_failure_before_first_token_falls_back_silently() -> None:
    llm = FakeLlm(
        [
            ScriptedResponse(raise_error=ConnectionError("primary down")),
            ScriptedResponse(text="fallback answer"),
        ]
    )
    events, model_used, fallback_used = stream_with_fallback(
        llm, [], [], "primary-model", "fallback-model"
    )
    tokens = [event.text for event in events if isinstance(event, StreamToken)]
    assert "".join(tokens) == "fallback answer"
    assert model_used == "fallback-model"
    assert fallback_used is True
    assert [call.model for call in llm.calls] == ["primary-model", "fallback-model"]


def test_both_models_failing_raises_to_the_caller() -> None:
    llm = FakeLlm(
        [
            ScriptedResponse(raise_error=ConnectionError("primary down")),
            ScriptedResponse(raise_error=ConnectionError("fallback down too")),
        ]
    )
    with pytest.raises(ConnectionError):
        stream_with_fallback(llm, [], [], "primary-model", "fallback-model")


def test_same_primary_and_fallback_model_never_retries_twice() -> None:
    llm = FakeLlm([ScriptedResponse(raise_error=ConnectionError("down"))])
    with pytest.raises(ConnectionError):
        stream_with_fallback(llm, [], [], "same-model", "same-model")
    assert len(llm.calls) == 1
