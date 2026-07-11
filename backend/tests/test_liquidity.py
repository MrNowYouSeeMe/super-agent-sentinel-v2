from app.domain.common.enums import DataHealth
from app.domain.liquidity.models import LiquidityInput
from app.domain.liquidity.service import project_liquidity


def test_provider_shortage_is_detected_even_when_other_resources_can_be_healthy() -> None:
    result = project_liquidity(
        LiquidityInput(
            resource_id="bkash",
            balance=5_000,
            safe_buffer=2_000,
            cash_in_5m=1_000,
            cash_out_5m=31_000,
            data_quality_score=0.95,
            data_health=DataHealth.HEALTHY,
        )
    )
    assert result.estimated_runway_minutes == 0.5
    assert result.shortage_probability_60m > 0.98
    assert result.shortage_eta_high_minutes is not None
