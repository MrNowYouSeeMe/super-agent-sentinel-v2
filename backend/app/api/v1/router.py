from fastapi import APIRouter

from app.api.v1.schemas import IntelligenceRequest
from app.services.intelligence import IntelligenceResponse, analyze

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "superagent-sentinel-v2"}


@router.post("/intelligence/analyze", response_model=IntelligenceResponse)
def analyze_intelligence(payload: IntelligenceRequest) -> IntelligenceResponse:
    return analyze(payload)
