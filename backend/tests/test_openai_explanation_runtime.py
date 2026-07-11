from __future__ import annotations

import sys
from types import SimpleNamespace

from app.services import openai_explanation as service
from app.services.openai_explanation import ExplanationInput


def _payload() -> ExplanationInput:
    return ExplanationInput(
        classification="liquidity_pressure_with_unusual_activity",
        severity="high",
        affected_resource="bkash",
        confidence=0.83,
        evidence=[
            "Cash-out velocity is above baseline.",
            "Provider balance is approaching the safe buffer.",
        ],
        recommended_action="Area manager and risk reviewer should verify the outlet.",
        language="banglish",
    )


def _settings():
    return SimpleNamespace(
        openai_enabled=True,
        openai_api_key="test-key",
        openai_model="gpt-5-mini",
    )


def _fake_openai(
    monkeypatch,
    *,
    output_text: str = "",
    nested_text: str = "",
    error: Exception | None = None,
):
    calls: list[dict] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            if error:
                raise error
            output = []
            if nested_text:
                output = [
                    SimpleNamespace(
                        type="message",
                        content=[
                            SimpleNamespace(
                                type="output_text",
                                text=nested_text,
                            )
                        ],
                    )
                ]
            return SimpleNamespace(
                output_text=output_text,
                output=output,
                status="completed",
                incomplete_details=None,
            )

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 30.0
            assert kwargs["max_retries"] == 1
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    monkeypatch.setattr(service, "get_settings", _settings)
    return calls


def test_openai_success_mode(monkeypatch):
    calls = _fake_openai(
        monkeypatch,
        output_text=(
            "bKash liquidity pressure is high with 83% confidence. "
            "The area manager and risk reviewer should verify the outlet."
        ),
    )
    result = service.explain_with_optional_openai(_payload(), allow_openai=True)
    assert result.mode == "openai"
    assert "max_output_tokens" not in calls[0]


def test_nested_output_text_is_supported(monkeypatch):
    _fake_openai(
        monkeypatch,
        nested_text="The assigned humans should review the bKash outlet.",
    )
    result = service.explain_with_optional_openai(_payload(), allow_openai=True)
    assert result.mode == "openai"


def test_safe_negation_does_not_trigger_false_positive(monkeypatch):
    _fake_openai(
        monkeypatch,
        output_text=(
            "This result does not authorize freezing an account. "
            "The outlet should be reviewed by the assigned humans."
        ),
    )
    result = service.explain_with_optional_openai(_payload(), allow_openai=True)
    assert result.mode == "openai"


def test_active_unsafe_action_falls_back(monkeypatch):
    _fake_openai(
        monkeypatch,
        output_text="You should freeze the account immediately.",
    )
    result = service.explain_with_optional_openai(_payload(), allow_openai=True)
    assert result.mode == "deterministic_fallback"


def test_empty_output_falls_back(monkeypatch):
    _fake_openai(monkeypatch)
    result = service.explain_with_optional_openai(_payload(), allow_openai=True)
    assert result.mode == "deterministic_fallback"


def test_api_exception_falls_back(monkeypatch):
    _fake_openai(monkeypatch, error=TimeoutError("simulated timeout"))
    result = service.explain_with_optional_openai(_payload(), allow_openai=True)
    assert result.mode == "deterministic_fallback"