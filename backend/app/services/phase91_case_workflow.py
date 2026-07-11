from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.services.phase91_audit import append_chain_event
from app.services.phase91_models import (
    CaseEscalation,
    CaseNote,
    CaseTransitionRequest,
    CoordinationCase,
    Phase91AnalysisResponse,
)

ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = ROOT / "runtime" / "phase91"
CASE_PATH = CASE_DIR / "cases.json"
_LOCK = threading.Lock()


class Phase91CaseError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict[str, dict]:
    if not CASE_PATH.exists():
        return {}
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def _save(cases: dict[str, dict]) -> None:
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CASE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(CASE_PATH)


def get_case(case_id: str) -> CoordinationCase:
    with _LOCK:
        cases = _load()
        raw = cases.get(case_id)
        if raw is None:
            raise Phase91CaseError("Case not found.")
        return CoordinationCase.model_validate(raw)


def create_case(
    response: Phase91AnalysisResponse,
    *,
    actor_id: str,
) -> CoordinationCase:
    with _LOCK:
        cases = _load()
        for raw in cases.values():
            if raw.get("analysis_id") == response.analysis.analysis_id:
                return CoordinationCase.model_validate(raw)

        now = _now()
        model_resource = response.provider_attribution.model_resource
        provider_id = model_resource if model_resource in {"bkash", "nagad", "rocket"} else None
        case = CoordinationCase(
            case_id=f"CASE91-{uuid4().hex[:14].upper()}",
            analysis_id=response.analysis.analysis_id,
            provider_id=provider_id,
            area_id=response.area_id,
            outlet_id=response.outlet_id,
            severity=response.analysis.prediction.severity,
            recipient_role=response.analysis.prediction.primary_stakeholder,
            owner_id=None,
            acknowledgement_status="awaiting",
            acknowledged_at=None,
            escalation_status="not_escalated",
            resolution_status="open",
            recommended_action=response.analysis.prediction.recommended_action,
            notes=[],
            escalations=[],
            created_at=now,
            updated_at=now,
        )
        cases[case.case_id] = case.model_dump(mode="json")
        _save(cases)

    append_chain_event(
        analysis_id=case.analysis_id,
        event="coordination_case_created",
        actor_id=actor_id,
        details={
            "case_id": case.case_id,
            "provider_id": case.provider_id,
            "recipient_role": case.recipient_role,
        },
    )
    return case


def transition_case(
    case_id: str,
    request: CaseTransitionRequest,
    *,
    actor_id: str,
) -> CoordinationCase:
    with _LOCK:
        cases = _load()
        raw = cases.get(case_id)
        if raw is None:
            raise Phase91CaseError("Case not found.")
        case = CoordinationCase.model_validate(raw)
        now = _now()

        if request.action == "acknowledge":
            if case.acknowledgement_status == "acknowledged":
                return case
            case.acknowledgement_status = "acknowledged"
            case.acknowledged_at = now
            if case.resolution_status == "open":
                case.resolution_status = "under_review"

        elif request.action == "assign":
            if not request.owner_id:
                raise Phase91CaseError("owner_id is required for assign.")
            case.owner_id = request.owner_id
            if case.resolution_status == "open":
                case.resolution_status = "under_review"

        elif request.action == "add_note":
            if not request.note:
                raise Phase91CaseError("note is required for add_note.")
            case.notes.append(
                CaseNote(
                    note_id=f"NOTE91-{uuid4().hex[:12].upper()}",
                    actor_id=actor_id,
                    text=request.note,
                    created_at=now,
                )
            )

        elif request.action == "escalate":
            if not request.target_role or not request.note:
                raise Phase91CaseError("target_role and note are required for escalate.")
            case.escalation_status = "escalated"
            case.resolution_status = "under_review"
            case.escalations.append(
                CaseEscalation(
                    escalation_id=f"ESC91-{uuid4().hex[:12].upper()}",
                    actor_id=actor_id,
                    target_role=request.target_role,
                    reason=request.note,
                    created_at=now,
                )
            )

        elif request.action == "resolve":
            if case.acknowledgement_status != "acknowledged":
                raise Phase91CaseError("Case must be acknowledged before resolution.")
            if not request.note:
                raise Phase91CaseError("Resolution note is required.")
            case.resolution_status = "resolved"
            case.notes.append(
                CaseNote(
                    note_id=f"NOTE91-{uuid4().hex[:12].upper()}",
                    actor_id=actor_id,
                    text=request.note,
                    created_at=now,
                )
            )

        elif request.action == "close":
            if case.resolution_status != "resolved":
                raise Phase91CaseError("Only resolved cases may be closed.")
            case.resolution_status = "closed"

        else:
            raise Phase91CaseError("Unsupported case transition.")

        case.updated_at = now
        cases[case_id] = case.model_dump(mode="json")
        _save(cases)

    append_chain_event(
        analysis_id=case.analysis_id,
        event=f"case_{request.action}",
        actor_id=actor_id,
        details={
            "case_id": case.case_id,
            "owner_id": case.owner_id,
            "resolution_status": case.resolution_status,
            "escalation_status": case.escalation_status,
        },
    )
    return case


def case_count() -> int:
    with _LOCK:
        return len(_load())
