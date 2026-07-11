from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ENV_FILE = ROOT / ".env"
sys.path.insert(0, str(BACKEND))

from dotenv import dotenv_values

SECRET_PATTERN = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{8,}")


def safe_error(exc: Exception) -> str:
    return SECRET_PATTERN.sub(
        "sk-***REDACTED***",
        f"{type(exc).__name__}: {exc}",
    )


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> None:
    values = dotenv_values(ENV_FILE)
    key = str(values.get("OPENAI_API_KEY") or "").strip()
    model = str(values.get("OPENAI_MODEL") or "gpt-5-mini").strip()
    enabled = str(values.get("OPENAI_ENABLED") or "").strip().lower()

    if enabled not in {"true", "1", "yes", "on"}:
        fail("OPENAI_ENABLED is not true in .env")
    if not key:
        fail("OPENAI_API_KEY is missing from .env")

    os.environ["OPENAI_ENABLED"] = "true"
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_MODEL"] = model

    from app.core.config import get_settings

    clear = getattr(get_settings, "cache_clear", None)
    if callable(clear):
        clear()

    from app.services.openai_explanation import (
        ExplanationInput,
        explain_with_optional_openai,
    )

    print("== SuperAgent OpenAI wrapper live test v2 ==")
    print(f"- model: {model}")
    print("- key_configured: True")

    try:
        result = explain_with_optional_openai(
            ExplanationInput(
                classification="liquidity_pressure_with_unusual_activity",
                severity="high",
                affected_resource="bkash",
                confidence=0.83,
                evidence=[
                    "Cash-out velocity is above the outlet baseline.",
                    "Provider balance is approaching the safe operating buffer.",
                ],
                recommended_action=(
                    "Area manager and risk reviewer should verify the outlet."
                ),
                language="banglish",
            ),
            allow_openai=True,
        )
    except Exception as exc:
        fail(safe_error(exc))

    print(f"- explanation_mode: {result.mode}")
    print(f"- explanation_preview: {result.text[:600]}")

    if result.mode != "openai":
        fail(
            "Wrapper still returned deterministic_fallback. "
            "Copy the sanitized warning and this output."
        )

    print("OPENAI WRAPPER LIVE TEST PASSED ✅")


if __name__ == "__main__":
    main()