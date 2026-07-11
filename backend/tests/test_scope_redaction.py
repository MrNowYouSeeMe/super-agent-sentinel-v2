from fastapi.testclient import TestClient

from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.auth.models import Permission, Principal, Role
from app.domain.common.enums import Language
from app.main import app
from app.services.auth import current_principal
from app.services.intelligence import analyze
from app.services.scope_redaction import redact_analysis_for_scope

client = TestClient(app)


def _request() -> IntelligenceRequest:
    return IntelligenceRequest(
        outlet_id="OUT-1",
        area_id="sylhet",
        language=Language.ENGLISH,
        festival_or_market_day=True,
        shared_cash=ResourceSnapshot(
            resource_id="shared_cash",
            balance=180_000,
            safe_buffer=25_000,
            cash_in_5m=45_000,
            cash_out_5m=30_000,
        ),
        providers=[
            ResourceSnapshot(
                resource_id="bkash",
                balance=7_000,
                safe_buffer=2_000,
                cash_in_5m=1_000,
                cash_out_5m=26_000,
                transaction_count_5m=30,
                repeated_amount_ratio=0.80,
                unique_customer_ratio=0.20,
            ),
            ResourceSnapshot(
                resource_id="nagad",
                balance=120_000,
                safe_buffer=15_000,
                cash_in_5m=25_000,
                cash_out_5m=20_000,
            ),
        ],
    )


def _nagad_scoped_principal() -> Principal:
    return Principal(
        user_id="TEST-NAGAD-OPS",
        role=Role.CENTRAL_OPERATIONS,
        permissions={Permission.ANALYSIS_CREATE, Permission.ALERT_READ},
        provider_scopes={"nagad"},
        area_scopes={"sylhet"},
        outlet_scopes={"*"},
    )


def test_hidden_affected_provider_is_fully_redacted() -> None:
    full = analyze(_request())
    assert full.decision.affected_resource == "bkash"

    result = redact_analysis_for_scope(
        full,
        visible_resource_ids=["shared_cash", "nagad"],
    )

    assert result.redacted is True
    assert result.case_allowed is False
    assert result.analysis.decision.affected_resource == "redacted"
    assert {item.resource_id for item in result.analysis.resources} == {
        "shared_cash",
        "nagad",
    }
    serialized = result.analysis.model_dump_json().lower()
    assert '"bkash"' not in serialized
    assert "7000" not in serialized


def test_visible_affected_provider_keeps_decision_but_filters_others() -> None:
    full = analyze(_request())
    result = redact_analysis_for_scope(
        full,
        visible_resource_ids=["shared_cash", "bkash"],
    )

    assert result.redacted is False
    assert result.case_allowed is True
    assert result.analysis.decision.affected_resource == "bkash"
    assert {item.resource_id for item in result.analysis.resources} == {
        "shared_cash",
        "bkash",
    }


def test_scoped_endpoint_does_not_leak_hidden_provider() -> None:
    app.dependency_overrides[current_principal] = _nagad_scoped_principal
    try:
        response = client.post(
            "/api/v1/intelligence/analyze-scoped",
            json=_request().model_dump(mode="json"),
        )
    finally:
        app.dependency_overrides.pop(current_principal, None)

    assert response.status_code == 200
    body = response.json()
    assert body["hidden_resource_count"] == 1
    assert set(body["visible_resource_ids"]) == {"shared_cash", "nagad"}
    assert body["analysis"]["decision"]["affected_resource"] == "redacted"
    assert body["case"] is None

    serialized = response.text.lower()
    assert '"bkash"' not in serialized
    assert "7000" not in serialized