from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "backend" / "app" / "api" / "v1" / "router.py"
text = ROUTER.read_text(encoding="utf-8-sig")

marker = "router = APIRouter"
imports = '''from fastapi import Header

from app.services.phase91_audit import verify_audit_chain
from app.services.phase91_case_workflow import (
    Phase91CaseError,
    create_case,
    get_case,
    transition_case,
)
from app.services.phase91_guard import (
    Phase91IdempotencyConflict,
    Phase91RateLimitError,
)
from app.services.phase91_metrics import load_phase91_metrics
from app.services.phase91_models import (
    AuditVerification,
    CaseTransitionRequest,
    CoordinationCase,
    Phase91AnalysisRequest,
    Phase91AnalysisResponse,
    Phase91Metrics,
    Phase91Status,
)
from app.services.phase91_service import (
    analyze_phase91,
    attach_case,
    phase91_status,
    redact_phase91_response,
)
'''

if "from app.services.phase91_service import (" not in text:
    index = text.find(marker)
    if index < 0:
        raise RuntimeError("Could not find APIRouter declaration.")
    text = text[:index] + imports + "\n" + text[index:]

endpoint_marker = '@router.get("/ml/phase91/status"'
endpoints = '''

@router.get("/ml/phase91/status", response_model=Phase91Status)
def phase91_final_status() -> Phase91Status:
    return phase91_status()


@router.post("/ml/phase91/analyze", response_model=Phase91AnalysisResponse)
def phase91_final_analysis(
    payload: Phase91AnalysisRequest,
    principal: Principal = Depends(current_principal),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> Phase91AnalysisResponse:
    try:
        authorize(
            principal,
            Permission.ANALYSIS_CREATE,
            area_id=payload.area_id,
            outlet_id=payload.outlet_id,
        )
        response = analyze_phase91(
            payload,
            actor_id=principal.user_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        allowed_providers: set[str] = set()
        for candidate_provider in ("bkash", "nagad", "rocket"):
            try:
                authorize(
                    principal,
                    Permission.ANALYSIS_CREATE,
                    provider_id=candidate_provider,
                    area_id=payload.area_id,
                    outlet_id=payload.outlet_id,
                )
                allowed_providers.add(candidate_provider)
            except AuthorizationError:
                continue

        provider_id = (
            response.provider_attribution.model_resource
            if response.provider_attribution.model_resource in {"bkash", "nagad", "rocket"}
            else None
        )
        if provider_id is not None and provider_id not in allowed_providers:
            raise AuthorizationError(
                "The predicted provider is outside the authenticated provider scope."
            )

        response = redact_phase91_response(
            response,
            allowed_providers=allowed_providers,
        )
        case = create_case(response, actor_id=principal.user_id)
        return attach_case(response, case)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Phase91RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except Phase91IdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (Phase91CaseError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/ml/phase91/cases/{case_id}", response_model=CoordinationCase)
def phase91_get_case(
    case_id: str,
    principal: Principal = Depends(current_principal),
) -> CoordinationCase:
    try:
        case = get_case(case_id)
        authorize(
            principal,
            Permission.CASE_REVIEW,
            provider_id=case.provider_id,
            area_id=case.area_id,
            outlet_id=case.outlet_id,
        )
        return case
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Phase91CaseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/ml/phase91/cases/{case_id}/transition",
    response_model=CoordinationCase,
)
def phase91_transition_case(
    case_id: str,
    payload: CaseTransitionRequest,
    principal: Principal = Depends(current_principal),
) -> CoordinationCase:
    try:
        case = get_case(case_id)
        authorize(
            principal,
            Permission.CASE_REVIEW,
            provider_id=case.provider_id,
            area_id=case.area_id,
            outlet_id=case.outlet_id,
        )
        return transition_case(case_id, payload, actor_id=principal.user_id)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Phase91CaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.get("/ml/phase91/audit/verify", response_model=AuditVerification)
def phase91_verify_audit(
    principal: Principal = Depends(current_principal),
) -> AuditVerification:
    return verify_audit_chain()


@router.get("/ml/phase91/metrics", response_model=Phase91Metrics)
def phase91_final_metrics(
    principal: Principal = Depends(current_principal),
) -> Phase91Metrics:
    return load_phase91_metrics()
'''

if endpoint_marker not in text:
    text = text.rstrip() + endpoints + "\n"

ROUTER.write_text(text, encoding="utf-8")
print("Phase 9.1 router endpoints patched.")
