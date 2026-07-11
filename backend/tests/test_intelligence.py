from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.common.enums import Classification, Language
from app.services.intelligence import analyze


def test_full_flow_selects_provider_and_uses_safe_language() -> None:
    response = analyze(
        IntelligenceRequest(
            outlet_id="OUT-1",
            area_id="sylhet",
            language=Language.ENGLISH,
            festival_or_market_day=True,
            shared_cash=ResourceSnapshot(
                resource_id="shared_cash",
                balance=100_000,
                safe_buffer=20_000,
                cash_in_5m=40_000,
                cash_out_5m=25_000,
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
    )
    assert response.decision.affected_resource == "bkash"
    assert response.decision.classification in {
        Classification.LIQUIDITY_PRESSURE,
        Classification.LIQUIDITY_PRESSURE_WITH_UNUSUAL_ACTIVITY,
    }
    assert response.decision.human_review_required is True
    assert "not a fraud verdict" in response.explanation.lower()
