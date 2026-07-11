from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.v1.schemas import IntelligenceRequest
from app.domain.auth.models import Permission, Principal
from app.domain.auth.policy import AuthorizationError, authorize, visible_resource_ids
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
from app.services.cases import build_case_from_analysis
from app.services.intelligence import IntelligenceResponse, analyze
from app.services.ml_runtime import model_metadata
from app.services.scenarios import ScenarioRunResponse, ScenarioSummary, list_scenarios, run_scenario

router = APIRouter(prefix="/api/v1")


class ScopedAnalysisResponse(BaseModel):
    principal: PrincipalView
    visible_resource_ids: list[str]
    hidden_resource_count: int
    scope_policy: str
    analysis: IntelligenceResponse
    case: object | None


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


@router.get("/intelligence/model")
def intelligence_model() -> dict[str, object]:
    return model_metadata()


@router.post("/intelligence/analyze", response_model=IntelligenceResponse)
def analyze_intelligence(payload: IntelligenceRequest) -> IntelligenceResponse:
    return analyze(payload)


@router.post("/intelligence/analyze-with-case")
def analyze_with_case(payload: IntelligenceRequest) -> dict[str, object]:
    analysis = analyze(payload)
    return {"analysis": analysis, "case": build_case_from_analysis(analysis)}


@router.post("/intelligence/analyze-scoped", response_model=ScopedAnalysisResponse)
def analyze_scoped(
    payload: IntelligenceRequest,
    principal: Principal = Depends(current_principal),
) -> ScopedAnalysisResponse:
    try:
        authorize(
            principal,
            Permission.ANALYSIS_CREATE,
            area_id=payload.area_id,
            outlet_id=payload.outlet_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    analysis = analyze(payload)
    all_resources = [payload.shared_cash.resource_id, *(provider.resource_id for provider in payload.providers)]
    visible = visible_resource_ids(
        principal,
        resource_ids=all_resources,
        area_id=payload.area_id,
        outlet_id=payload.outlet_id,
    )
    hidden_count = len(all_resources) - len(visible)
    scope_policy = (
        "Provider, area, and outlet scopes were enforced server-side. "
        "Shared-cash coordination is visible only where the user's area/outlet scope allows it; "
        "provider raw data remains restricted to scoped users."
    )
    return ScopedAnalysisResponse(
        principal=principal_view(principal),
        visible_resource_ids=visible,
        hidden_resource_count=hidden_count,
        scope_policy=scope_policy,
        analysis=analysis,
        case=build_case_from_analysis(analysis),
    )


@router.get("/demo/scenarios", response_model=list[ScenarioSummary])
def scenarios() -> list[ScenarioSummary]:
    return list_scenarios()


@router.post("/demo/scenarios/{scenario_id}", response_model=ScenarioRunResponse)
def demo_scenario(scenario_id: str) -> ScenarioRunResponse:
    try:
        return run_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

