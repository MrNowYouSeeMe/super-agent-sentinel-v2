from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import get_settings


class ExplanationInput(BaseModel):
    classification: str
    severity: str
    affected_resource: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    recommended_action: str
    language: str = "banglish"


class ExplanationOutput(BaseModel):
    mode: str
    text: str
    safety_boundary: str = (
        "This is decision support only. It is not a fraud verdict and it does not authorize financial action."
    )


def deterministic_operator_explanation(payload: ExplanationInput) -> ExplanationOutput:
    evidence_text = "; ".join(payload.evidence[:4]) if payload.evidence else "No specific evidence was supplied."
    text = (
        f"{payload.affected_resource} is flagged as {payload.classification} with "
        f"{payload.severity} severity and {round(payload.confidence * 100)}% confidence. "
        f"Evidence: {evidence_text}. Recommended human action: {payload.recommended_action}. "
        "This is not a fraud verdict."
    )
    return ExplanationOutput(mode="deterministic_fallback", text=text)


def _build_prompt(payload: ExplanationInput) -> str:
    return (
        "Rewrite this MFS decision-support result clearly. "
        "Do not invent facts, accuse fraud, recommend moving money, freeze accounts, or block customers. "
        f"Language: {payload.language}. "
        f"Classification: {payload.classification}. Severity: {payload.severity}. "
        f"Affected resource: {payload.affected_resource}. Confidence: {payload.confidence}. "
        f"Evidence: {payload.evidence}. Recommended human action: {payload.recommended_action}."
    )


def explain_with_optional_openai(
    payload: ExplanationInput,
    *,
    allow_openai: bool = False,
) -> ExplanationOutput:
    settings = get_settings()
    if not allow_openai or not settings.openai_enabled or not settings.openai_api_key:
        return deterministic_operator_explanation(payload)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, timeout=8.0)
        response = client.responses.create(
            model=settings.openai_model,
            input=_build_prompt(payload),
        )
        text = getattr(response, "output_text", "") or ""
        if not text.strip():
            return deterministic_operator_explanation(payload)
        lowered = text.lower()
        forbidden = [
            "fraud confirmed",
            "move money",
            "transfer money",
            "freeze account",
            "block customer",
        ]
        if any(item in lowered for item in forbidden):
            return deterministic_operator_explanation(payload)
        return ExplanationOutput(mode="openai", text=text.strip())
    except Exception:
        return deterministic_operator_explanation(payload)