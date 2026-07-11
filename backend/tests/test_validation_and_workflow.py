
from fastapi.testclient import TestClient

from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.common.enums import Language
from app.main import app

client = TestClient(app)


def _login(profile_id: str) -> str:
    response = client.post("/api/v1/auth/demo-login", json={"profile_id": profile_id})
    assert response.status_code == 200
    return response.json()["access_token"]


def _valid_request() -> dict:
    return IntelligenceRequest(
        outlet_id="OUT-1",
        area_id="sylhet",
        language=Language.ENGLISH,
        festival_or_market_day=False,
        shared_cash=ResourceSnapshot(
            resource_id="shared_cash",
            balance=90_000,
            safe_buffer=20_000,
            cash_in_5m=8_000,
            cash_out_5m=18_000,
        ),
        providers=[
            ResourceSnapshot(
                resource_id="bkash",
                balance=8_000,
                safe_buffer=3_000,
                cash_in_5m=1_000,
                cash_out_5m=30_000,
                transaction_count_5m=32,
                repeated_amount_ratio=0.75,
                unique_customer_ratio=0.18,
            ),
            ResourceSnapshot(
                resource_id="nagad",
                balance=120_000,
                safe_buffer=15_000,
                cash_in_5m=20_000,
                cash_out_5m=10_000,
            ),
        ],
    ).model_dump(mode="json")


def test_validation_rejects_unknown_provider() -> None:
    payload = _valid_request()
    payload["providers"][0]["resource_id"] = "unknownpay"
    response = client.post("/api/v1/validation/check", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert any(item["code"] == "unknown_provider_id" for item in body["findings"])

    rejected = client.post("/api/v1/intelligence/analyze", json=payload)
    assert rejected.status_code == 422


def test_validation_evidence_report_lists_safety_controls() -> None:
    response = client.get("/api/v1/demo/validation-evidence")
    assert response.status_code == 200
    body = response.json()
    assert any("No endpoint moves money" in item for item in body["safety_controls"])
    assert len(body["metrics"]) >= 3


def test_case_transition_moves_assigned_case_to_acknowledged() -> None:
    token = _login("area-manager-sylhet")
    analysis_response = client.post(
        "/api/v1/intelligence/analyze-scoped",
        json=_valid_request(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert analysis_response.status_code == 200
    case = analysis_response.json()["case"]
    assert case is not None

    assigned = client.post(
        "/api/v1/cases/transition",
        json={"case": case, "action": "assign", "note": "Assigning to Sylhet area manager."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert assigned.status_code == 200
    assigned_case = assigned.json()["case"]
    assert assigned_case["current_status"] == "ASSIGNED"

    acknowledged = client.post(
        "/api/v1/cases/transition",
        json={"case": assigned_case, "action": "acknowledge", "note": "Manager has started verification."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["case"]["current_status"] == "ACKNOWLEDGED"


def test_wrong_provider_user_cannot_transition_bkash_case() -> None:
    area_token = _login("area-manager-sylhet")
    nagad_token = _login("nagad-ops-sylhet")
    analysis_response = client.post(
        "/api/v1/intelligence/analyze-scoped",
        json=_valid_request(),
        headers={"Authorization": f"Bearer {area_token}"},
    )
    assert analysis_response.status_code == 200
    case = analysis_response.json()["case"]
    assert case["affected_resource"] == "bkash"

    denied = client.post(
        "/api/v1/cases/transition",
        json={"case": case, "action": "assign", "note": "Trying to access wrong provider."},
        headers={"Authorization": f"Bearer {nagad_token}"},
    )
    assert denied.status_code == 403
