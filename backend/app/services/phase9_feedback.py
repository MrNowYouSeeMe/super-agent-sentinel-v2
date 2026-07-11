from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.services.phase9_audit import append_audit_event

ROOT = Path(__file__).resolve().parents[3]
FEEDBACK_DIR = ROOT / "runtime" / "phase9"
FEEDBACK_PATH = FEEDBACK_DIR / "feedback.jsonl"
_LOCK = threading.Lock()
SAFE_TEXT = re.compile(r"^[\w\s.,:;!?()/%+\-–—'\"#]+$", re.UNICODE)


class Phase9FeedbackRequest(BaseModel):
    analysis_id: str = Field(min_length=8, max_length=80)
    area_id: str = Field(min_length=2, max_length=64)
    outlet_id: str = Field(min_length=2, max_length=64)
    affected_resource: Literal["none", "shared_cash", "bkash", "nagad", "rocket"]
    decision: Literal[
        "confirmed_operational_risk",
        "false_positive",
        "needs_more_data",
        "resolved",
    ]
    note: str = Field(min_length=3, max_length=500)

    @field_validator("analysis_id", "area_id", "outlet_id", "note")
    @classmethod
    def validate_text(cls, value: str) -> str:
        clean = value.strip()
        lowered = clean.lower()
        forbidden = ("password", "otp", "pin=", "api_key", "secret=", "sk-proj-", "sk-")
        if any(token in lowered for token in forbidden):
            raise ValueError("Credentials or secrets are not allowed in feedback.")
        if not SAFE_TEXT.fullmatch(clean):
            raise ValueError("Unsupported characters found in feedback.")
        return clean


class Phase9FeedbackResponse(BaseModel):
    feedback_id: str
    stored: bool
    audit_event_id: str
    message: str


def store_feedback(
    payload: Phase9FeedbackRequest,
    *,
    actor_id: str,
    actor_role: str,
) -> Phase9FeedbackResponse:
    feedback_id = f"FDB-{uuid4().hex[:16].upper()}"
    record = {
        "feedback_id": feedback_id,
        "analysis_id": payload.analysis_id,
        "area_id": payload.area_id,
        "outlet_id": payload.outlet_id,
        "affected_resource": payload.affected_resource,
        "decision": payload.decision,
        "note": payload.note,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    audit_event_id = append_audit_event(
        analysis_id=payload.analysis_id,
        event="human_feedback_recorded",
        actor_id=actor_id,
        details={
            "feedback_id": feedback_id,
            "decision": payload.decision,
            "affected_resource": payload.affected_resource,
            "actor_role": actor_role,
        },
    )
    return Phase9FeedbackResponse(
        feedback_id=feedback_id,
        stored=True,
        audit_event_id=audit_event_id,
        message=(
            "Human feedback was recorded for audit and future offline model evaluation. "
            "It does not automatically retrain or change the current model."
        ),
    )
