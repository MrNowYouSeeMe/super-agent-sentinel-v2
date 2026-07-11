from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)


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


_ACTIVE_UNSAFE_PATTERNS = (
    re.compile(r"\bfraud\s+(?:is\s+)?confirmed\b", re.IGNORECASE),
    re.compile(
        r"\b(?:should|must|recommend(?:ed)?\s+to|immediately)\s+"
        r"(?:freeze|block|suspend)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:should|must|recommend(?:ed)?\s+to|immediately)\s+"
        r"(?:move|transfer|send)\s+(?:the\s+)?money\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:freeze|block|suspend)\s+(?:the\s+)?(?:account|customer)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:move|transfer|send)\s+(?:the\s+)?money\b",
        re.IGNORECASE,
    ),
)


def deterministic_operator_explanation(payload: ExplanationInput) -> ExplanationOutput:
    evidence_text = (
        "; ".join(payload.evidence[:4])
        if payload.evidence
        else "No specific evidence was supplied."
    )
    text = (
        f"{payload.affected_resource} is flagged as {payload.classification} with "
        f"{payload.severity} severity and {round(payload.confidence * 100)}% confidence. "
        f"Evidence: {evidence_text}. Recommended human action: "
        f"{payload.recommended_action}. This is not a fraud verdict."
    )
    return ExplanationOutput(mode="deterministic_fallback", text=text)


def _build_prompt(payload: ExplanationInput) -> str:
    evidence = "\n".join(f"- {item}" for item in payload.evidence[:6])
    return (
        "Rewrite the supplied machine-generated decision-support result for a human "
        "mobile-financial-service operator.\n\n"
        "Rules:\n"
        "- Use only the supplied facts.\n"
        "- Return 2 to 4 concise sentences.\n"
        "- Preserve the confidence, severity, affected resource, and human-review action.\n"
        "- Do not invent evidence.\n"
        "- Do not claim fraud is confirmed.\n"
        "- Do not instruct account freezing, customer blocking, or money movement.\n"
        "- Do not add autonomous actions.\n"
        f"- Language/style: {payload.language}.\n\n"
        f"Classification: {payload.classification}\n"
        f"Severity: {payload.severity}\n"
        f"Affected resource: {payload.affected_resource}\n"
        f"Confidence: {round(payload.confidence * 100)}%\n"
        f"Evidence:\n{evidence or '- No specific evidence supplied.'}\n"
        f"Recommended human-review action: {payload.recommended_action}"
    )


def _read_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _extract_output_text(response: Any) -> str:
    direct = str(_read_value(response, "output_text", "") or "").strip()
    if direct:
        return direct

    chunks: list[str] = []
    for item in _read_value(response, "output", []) or []:
        for content in _read_value(item, "content", []) or []:
            content_type = str(_read_value(content, "type", "") or "")
            text = _read_value(content, "text", "")
            if content_type in {"output_text", "text"} and text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def _contains_active_unsafe_action(text: str) -> bool:
    return any(pattern.search(text) for pattern in _ACTIVE_UNSAFE_PATTERNS)


def _log_fallback(
    reason: str,
    *,
    response: Any | None = None,
    exc: Exception | None = None,
) -> None:
    logger.warning(
        "openai_explanation_fallback %s",
        {
            "reason": reason,
            "error_type": type(exc).__name__ if exc else None,
            "status_code": getattr(exc, "status_code", None) if exc else None,
            "response_status": _read_value(response, "status", None)
            if response is not None
            else None,
            "incomplete_details": str(
                _read_value(response, "incomplete_details", None)
            )[:240]
            if response is not None
            else None,
            "output_item_types": [
                str(_read_value(item, "type", "unknown"))
                for item in (_read_value(response, "output", []) or [])
            ][:10]
            if response is not None
            else [],
        },
    )


def explain_with_optional_openai(
    payload: ExplanationInput,
    *,
    allow_openai: bool = False,
) -> ExplanationOutput:
    settings = get_settings()
    if not allow_openai:
        return deterministic_operator_explanation(payload)
    if not settings.openai_enabled or not settings.openai_api_key:
        _log_fallback("openai_not_configured")
        return deterministic_operator_explanation(payload)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
            max_retries=1,
        )

        # Deliberately omit max_output_tokens here. GPT-5 reasoning tokens share
        # the output budget, and a small cap can complete reasoning without
        # leaving visible text. The prompt itself enforces a 2–4 sentence result.
        response = client.responses.create(
            model=settings.openai_model,
            input=_build_prompt(payload),
        )
        text = _extract_output_text(response)

        if not text:
            _log_fallback("empty_output", response=response)
            return deterministic_operator_explanation(payload)
        if _contains_active_unsafe_action(text):
            _log_fallback("unsafe_active_action", response=response)
            return deterministic_operator_explanation(payload)

        return ExplanationOutput(mode="openai", text=text)
    except Exception as exc:
        _log_fallback("api_exception", exc=exc)
        return deterministic_operator_explanation(payload)