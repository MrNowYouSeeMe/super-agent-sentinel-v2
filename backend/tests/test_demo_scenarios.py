from app.domain.common.enums import Classification
from app.services.scenarios import list_scenarios, run_scenario


def test_demo_scenarios_are_available() -> None:
    ids = {scenario.scenario_id for scenario in list_scenarios()}
    assert {"normal", "hidden_provider_shortage", "data_conflict", "shared_cash_pressure"}.issubset(ids)


def test_hidden_provider_shortage_creates_case() -> None:
    response = run_scenario("hidden_provider_shortage")
    assert response.analysis.decision.affected_resource == "bkash"
    assert response.analysis.decision.human_review_required is True
    assert response.case is not None
    assert response.case.owner_role == "area_manager"


def test_data_conflict_prioritizes_verification() -> None:
    response = run_scenario("data_conflict")
    assert response.analysis.decision.classification == Classification.DATA_QUALITY_ISSUE
    assert response.case is not None
    assert response.case.current_status == "WAITING_FOR_DATA"

