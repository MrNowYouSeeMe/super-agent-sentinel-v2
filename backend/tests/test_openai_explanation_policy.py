
from app.services.openai_explanation import ExplanationInput, explain_with_optional_openai


def test_openai_explanation_falls_back_without_secret(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = explain_with_optional_openai(
        ExplanationInput(
            classification="liquidity_pressure",
            severity="medium",
            affected_resource="bkash",
            confidence=0.72,
            evidence=["bKash float runway is short", "cash-out velocity is high"],
            recommended_action="request_operator_verification",
            language="banglish",
        )
    )

    assert result.mode == "deterministic_fallback"
    assert "not a fraud verdict" in result.text.lower()
    assert "does not authorize financial action" in result.safety_boundary
