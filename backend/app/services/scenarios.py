from pydantic import BaseModel

from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.cases.models import CaseRecord
from app.domain.common.enums import Language
from app.services.cases import build_case_from_analysis
from app.services.intelligence import IntelligenceResponse, analyze


class ScenarioSummary(BaseModel):
    scenario_id: str
    title: str
    purpose: str


class ScenarioRunResponse(BaseModel):
    scenario: ScenarioSummary
    analysis: IntelligenceResponse
    case: CaseRecord | None


def _scenarios() -> dict[str, tuple[ScenarioSummary, IntelligenceRequest]]:
    return {
        "normal": (
            ScenarioSummary(
                scenario_id="normal",
                title="Normal outlet operation",
                purpose="Shows a healthy baseline with no review-worthy pressure.",
            ),
            IntelligenceRequest(
                outlet_id="OUT-SYL-017",
                area_id="sylhet",
                language=Language.BANGLISH,
                festival_or_market_day=False,
                shared_cash=ResourceSnapshot(
                    resource_id="shared_cash",
                    balance=160_000,
                    safe_buffer=20_000,
                    cash_in_5m=24_000,
                    cash_out_5m=19_000,
                ),
                providers=[
                    ResourceSnapshot(resource_id="bkash", balance=75_000, safe_buffer=12_000, cash_in_5m=12_000, cash_out_5m=10_000),
                    ResourceSnapshot(resource_id="nagad", balance=95_000, safe_buffer=12_000, cash_in_5m=10_000, cash_out_5m=9_000),
                    ResourceSnapshot(resource_id="rocket", balance=60_000, safe_buffer=10_000, cash_in_5m=9_000, cash_out_5m=8_000),
                ],
            ),
        ),
        "hidden_provider_shortage": (
            ScenarioSummary(
                scenario_id="hidden_provider_shortage",
                title="Hidden bKash float shortage",
                purpose="Total money looks healthy, but one provider may fail soon.",
            ),
            IntelligenceRequest(
                outlet_id="OUT-SYL-017",
                area_id="sylhet",
                language=Language.BANGLISH,
                festival_or_market_day=True,
                shared_cash=ResourceSnapshot(resource_id="shared_cash", balance=180_000, safe_buffer=25_000, cash_in_5m=45_000, cash_out_5m=30_000),
                providers=[
                    ResourceSnapshot(resource_id="bkash", balance=7_000, safe_buffer=2_000, cash_in_5m=1_000, cash_out_5m=26_000, transaction_count_5m=30, repeated_amount_ratio=0.80, unique_customer_ratio=0.20),
                    ResourceSnapshot(resource_id="nagad", balance=120_000, safe_buffer=15_000, cash_in_5m=25_000, cash_out_5m=20_000),
                    ResourceSnapshot(resource_id="rocket", balance=90_000, safe_buffer=15_000, cash_in_5m=18_000, cash_out_5m=17_000),
                ],
            ),
        ),
        "data_conflict": (
            ScenarioSummary(
                scenario_id="data_conflict",
                title="Late provider feed and reconciliation conflict",
                purpose="Shows confidence reduction and data verification instead of unsafe escalation.",
            ),
            IntelligenceRequest(
                outlet_id="OUT-SYL-021",
                area_id="sylhet",
                language=Language.ENGLISH,
                festival_or_market_day=False,
                shared_cash=ResourceSnapshot(resource_id="shared_cash", balance=80_000, safe_buffer=20_000, cash_in_5m=12_000, cash_out_5m=11_000),
                providers=[
                    ResourceSnapshot(resource_id="nagad", balance=10_000, safe_buffer=8_000, cash_in_5m=1_000, cash_out_5m=14_000, feed_age_seconds=2_700, reconciliation_difference=6_000, completeness_ratio=0.45, source_quality_score=0.40),
                    ResourceSnapshot(resource_id="bkash", balance=95_000, safe_buffer=12_000, cash_in_5m=10_000, cash_out_5m=8_000),
                ],
            ),
        ),
        "shared_cash_pressure": (
            ScenarioSummary(
                scenario_id="shared_cash_pressure",
                title="Shared physical cash pressure",
                purpose="Shows outlet-level physical cash risk even when provider floats are available.",
            ),
            IntelligenceRequest(
                outlet_id="OUT-SYL-032",
                area_id="sylhet",
                language=Language.BANGLA,
                festival_or_market_day=True,
                shared_cash=ResourceSnapshot(resource_id="shared_cash", balance=18_000, safe_buffer=20_000, cash_in_5m=2_000, cash_out_5m=40_000, transaction_count_5m=45, repeated_amount_ratio=0.35, unique_customer_ratio=0.45),
                providers=[
                    ResourceSnapshot(resource_id="bkash", balance=110_000, safe_buffer=15_000, cash_in_5m=20_000, cash_out_5m=15_000),
                    ResourceSnapshot(resource_id="nagad", balance=100_000, safe_buffer=15_000, cash_in_5m=18_000, cash_out_5m=14_000),
                    ResourceSnapshot(resource_id="rocket", balance=70_000, safe_buffer=10_000, cash_in_5m=12_000, cash_out_5m=9_000),
                ],
            ),
        ),
    }


def list_scenarios() -> list[ScenarioSummary]:
    return [item[0] for item in _scenarios().values()]


def run_scenario(scenario_id: str) -> ScenarioRunResponse:
    scenarios = _scenarios()
    if scenario_id not in scenarios:
        available = ", ".join(sorted(scenarios))
        raise KeyError(f"Unknown scenario '{scenario_id}'. Available: {available}")
    summary, request = scenarios[scenario_id]
    analysis = analyze(request)
    return ScenarioRunResponse(
        scenario=summary,
        analysis=analysis,
        case=build_case_from_analysis(analysis),
    )

