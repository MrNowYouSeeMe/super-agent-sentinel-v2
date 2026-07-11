from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "backend" / "app" / "api" / "v1" / "router.py"
text = ROUTER.read_text(encoding="utf-8-sig")

import_anchor = (
    "from app.services.validation_evidence import ValidationEvidenceReport, "
    "build_validation_evidence_report\n"
)
imports = '''from app.services.phase9_feedback import (
    Phase9FeedbackRequest,
    Phase9FeedbackResponse,
    store_feedback,
)
from app.services.phase9_governance import (
    Phase9AnalysisResponse,
    Phase9InputError,
    Phase9Status,
    analyze_phase9,
    phase9_status,
)
'''

if "from app.services.phase9_governance import (" not in text:
    if import_anchor not in text:
        raise RuntimeError("Phase 9 router import anchor was not found.")
    text = text.replace(import_anchor, import_anchor + imports, 1)

endpoint_marker = '@router.get("/ml/phase9/status"'
endpoints = '''

@router.get("/ml/phase9/status", response_model=Phase9Status)
def phase9_governance_status() -> Phase9Status:
    return phase9_status()


@router.post("/ml/phase9/analyze", response_model=Phase9AnalysisResponse)
def phase9_governed_analysis(
    payload: Phase6BPredictionRequest,
    principal: Principal = Depends(current_principal),
) -> Phase9AnalysisResponse:
    try:
        authorize(
            principal,
            Permission.ANALYSIS_CREATE,
            area_id=payload.area_id,
            outlet_id=payload.outlet_id,
        )
        return analyze_phase9(payload, actor_id=principal.user_id)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Phase9InputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.report.model_dump(mode="json"),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/ml/phase9/feedback", response_model=Phase9FeedbackResponse)
def phase9_human_feedback(
    payload: Phase9FeedbackRequest,
    principal: Principal = Depends(current_principal),
) -> Phase9FeedbackResponse:
    provider_id = (
        None
        if payload.affected_resource in {"none", "shared_cash"}
        else payload.affected_resource
    )
    try:
        authorize(
            principal,
            Permission.CASE_REVIEW,
            provider_id=provider_id,
            area_id=payload.area_id,
            outlet_id=payload.outlet_id,
        )
        return store_feedback(
            payload,
            actor_id=principal.user_id,
            actor_role=principal.role.value,
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
'''

if endpoint_marker not in text:
    text = text.rstrip() + endpoints + "\n"

ROUTER.write_text(text, encoding="utf-8")
print("Phase 9 router endpoints patched.")
