from fastapi import APIRouter, HTTPException

from app.api.v1.schemas import IntelligenceRequest
from app.services.cases import build_case_from_analysis
from app.services.intelligence import IntelligenceResponse, analyze
from app.services.ml_runtime import model_metadata
from app.services.scenarios import ScenarioRunResponse, ScenarioSummary, list_scenarios, run_scenario

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "superagent-sentinel-v2"}


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


@router.get("/demo/scenarios", response_model=list[ScenarioSummary])
def scenarios() -> list[ScenarioSummary]:
    return list_scenarios()


@router.post("/demo/scenarios/{scenario_id}", response_model=ScenarioRunResponse)
def demo_scenario(scenario_id: str) -> ScenarioRunResponse:
    try:
        return run_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

