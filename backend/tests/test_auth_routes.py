from fastapi.testclient import TestClient

from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.common.enums import Language
from app.main import app

client = TestClient(app)


def _request(area_id: str = "sylhet", outlet_id: str = "OUT-1") -> dict:
    return IntelligenceRequest(
        outlet_id=outlet_id,
        area_id=area_id,
        language=Language.ENGLISH,
        festival_or_market_day=False,
        shared_cash=ResourceSnapshot(
            resource_id="shared_cash",
            balance=80_000,
            safe_buffer=20_000,
            cash_in_5m=10_000,
            cash_out_5m=15_000,
        ),
        providers=[
            ResourceSnapshot(
                resource_id="bkash",
                balance=8_000,
                safe_buffer=3_000,
                cash_in_5m=1_000,
                cash_out_5m=30_000,
                transaction_count_5m=28,
                repeated_amount_ratio=0.70,
                unique_customer_ratio=0.20,
            ),
            ResourceSnapshot(
                resource_id="nagad",
                balance=150_000,
                safe_buffer=15_000,
                cash_in_5m=30_000,
                cash_out_5m=10_000,
            ),
        ],
    ).model_dump(mode="json")


def _login(profile_id: str) -> str:
    response = client.post("/api/v1/auth/demo-login", json={"profile_id": profile_id})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_demo_login_and_me_round_trip() -> None:
    token = _login("area-manager-sylhet")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "area_manager"
    assert "analysis.create" in body["permissions"]
    assert body["area_scopes"] == ["sylhet"]


def test_scoped_analysis_allows_area_manager() -> None:
    token = _login("area-manager-sylhet")
    response = client.post(
        "/api/v1/intelligence/analyze-scoped",
        json=_request(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hidden_resource_count"] == 0
    assert set(body["visible_resource_ids"]) == {"shared_cash", "bkash", "nagad"}
    assert body["case"] is not None


def test_scoped_analysis_denies_wrong_area() -> None:
    token = _login("area-manager-sylhet")
    response = client.post(
        "/api/v1/intelligence/analyze-scoped",
        json=_request(area_id="dhaka"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_provider_viewer_cannot_create_analysis_but_can_authenticate() -> None:
    token = _login("bkash-ops-sylhet")
    response = client.post(
        "/api/v1/intelligence/analyze-scoped",
        json=_request(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

