from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.schemas import IntelligenceRequest
from app.domain.auth.models import Permission, Principal
from app.domain.auth.policy import AuthorizationError, authorize, visible_resource_ids
from app.domain.cases.models import CaseRecord
from app.domain.cases.workflow import CaseAction, WorkflowError
from app.domain.validation.models import ValidationReport
from app.domain.validation.service import validate_intelligence_request
from app.services.auth import (
    AuthTokenResponse,
    DemoLoginRequest,
    DemoUserProfile,
    PrincipalView,
    current_principal,
    demo_login,
    list_demo_users,
    principal_view,
)
from app.services.cases import apply_case_action, build_case_from_analysis
from app.services.intelligence import IntelligenceResponse, analyze
from app.services.ml_runtime import model_metadata
from app.services.phase6b_runtime import (
    Phase6BPredictionRequest,
    Phase6BPredictionResponse,
    Phase6BStatus,
    phase6b_status,
    predict_phase6b,
)
from app.services.scenarios import ScenarioRunResponse, ScenarioSummary, list_scenarios, run_scenario
from app.services.scope_redaction import redact_analysis_for_scope
from app.services.validation_evidence import ValidationEvidenceReport, build_validation_evidence_report
from app.services.phase9_feedback import (
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

from fastapi import Header

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

router = APIRouter(prefix="/api/v1")


class ScopedAnalysisResponse(BaseModel):
    principal: PrincipalView
    visible_resource_ids: list[str]
    hidden_resource_count: int
    scope_policy: str
    validation: ValidationReport
    analysis: IntelligenceResponse
    case: object | None


class CaseTransitionRequest(BaseModel):
    case: CaseRecord
    action: CaseAction
    note: str = Field(min_length=2, max_length=500)


class CaseTransitionResponse(BaseModel):
    principal: PrincipalView
    case: CaseRecord


def _validate_or_422(payload: IntelligenceRequest) -> ValidationReport:
    report = validate_intelligence_request(payload)
    if not report.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=report.model_dump(mode="json"),
        )
    return report


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "superagent-sentinel-v2"}


@router.get("/auth/demo-users", response_model=list[DemoUserProfile])
def auth_demo_users() -> list[DemoUserProfile]:
    return list_demo_users()


@router.post("/auth/demo-login", response_model=AuthTokenResponse)
def auth_demo_login(payload: DemoLoginRequest) -> AuthTokenResponse:
    return demo_login(payload)


@router.get("/auth/me", response_model=PrincipalView)
def auth_me(principal: Principal = Depends(current_principal)) -> PrincipalView:
    return principal_view(principal)


@router.post("/validation/check", response_model=ValidationReport)
def validation_check(payload: IntelligenceRequest) -> ValidationReport:
    return validate_intelligence_request(payload)


@router.get("/demo/validation-evidence", response_model=ValidationEvidenceReport)
def validation_evidence() -> ValidationEvidenceReport:
    return build_validation_evidence_report()


@router.get("/intelligence/model")
def intelligence_model() -> dict[str, object]:
    return model_metadata()


@router.get("/ml/phase6b/status", response_model=Phase6BStatus)
def trained_model_status() -> Phase6BStatus:
    return phase6b_status()


@router.post("/ml/phase6b/predict", response_model=Phase6BPredictionResponse)
def trained_model_predict(
    payload: Phase6BPredictionRequest,
    principal: Principal = Depends(current_principal),
) -> Phase6BPredictionResponse:
    try:
        authorize(
            principal,
            Permission.ANALYSIS_CREATE,
            area_id=payload.area_id,
            outlet_id=payload.outlet_id,
        )
        return predict_phase6b(payload)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/intelligence/analyze", response_model=IntelligenceResponse)
def analyze_intelligence(payload: IntelligenceRequest) -> IntelligenceResponse:
    _validate_or_422(payload)
    return analyze(payload)


@router.post("/intelligence/analyze-with-case")
def analyze_with_case(payload: IntelligenceRequest) -> dict[str, object]:
    validation = _validate_or_422(payload)
    analysis = analyze(payload)
    return {"validation": validation, "analysis": analysis, "case": build_case_from_analysis(analysis)}


@router.post("/intelligence/analyze-scoped", response_model=ScopedAnalysisResponse)
def analyze_scoped(
    payload: IntelligenceRequest,
    principal: Principal = Depends(current_principal),
) -> ScopedAnalysisResponse:
    validation = _validate_or_422(payload)
    try:
        authorize(
            principal,
            Permission.ANALYSIS_CREATE,
            area_id=payload.area_id,
            outlet_id=payload.outlet_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    full_analysis = analyze(payload)
    all_resources = [payload.shared_cash.resource_id, *(provider.resource_id for provider in payload.providers)]
    visible = visible_resource_ids(
        principal,
        resource_ids=all_resources,
        area_id=payload.area_id,
        outlet_id=payload.outlet_id,
    )
    hidden_count = len(all_resources) - len(visible)
    scoped = redact_analysis_for_scope(
        full_analysis,
        visible_resource_ids=visible,
    )
    scope_policy = (
        "Provider, area, and outlet scopes are enforced server-side. "
        "Hidden resources, evidence, decisions, explanations, and cases are redacted "
        "before the response is serialized."
    )
    return ScopedAnalysisResponse(
        principal=principal_view(principal),
        visible_resource_ids=visible,
        hidden_resource_count=hidden_count,
        scope_policy=scope_policy,
        validation=validation,
        analysis=scoped.analysis,
        case=build_case_from_analysis(scoped.analysis) if scoped.case_allowed else None,
    )


@router.post("/cases/transition", response_model=CaseTransitionResponse)
def transition_case(
    payload: CaseTransitionRequest,
    principal: Principal = Depends(current_principal),
) -> CaseTransitionResponse:
    provider_id = None if payload.case.affected_resource == "shared_cash" else payload.case.affected_resource
    permission = Permission.CASE_ESCALATE if payload.action == CaseAction.ESCALATE else Permission.CASE_REVIEW
    try:
        authorize(
            principal,
            permission,
            provider_id=provider_id,
            area_id=payload.case.area_id,
            outlet_id=payload.case.outlet_id,
        )
        updated = apply_case_action(
            payload.case,
            payload.action,
            actor_role=principal.role.value,
            note=payload.note,
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CaseTransitionResponse(principal=principal_view(principal), case=updated)


@router.get("/demo/scenarios", response_model=list[ScenarioSummary])
def scenarios() -> list[ScenarioSummary]:
    return list_scenarios()


@router.post("/demo/scenarios/{scenario_id}", response_model=ScenarioRunResponse)
def demo_scenario(scenario_id: str) -> ScenarioRunResponse:
    try:
        return run_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
