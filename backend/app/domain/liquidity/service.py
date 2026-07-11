from math import exp

from app.domain.common.enums import DataHealth
from app.domain.liquidity.models import LiquidityInput, LiquidityProjection


def _shortage_probability(runway: float | None, balance: float, buffer: float) -> float:
    if balance <= buffer:
        return 0.99
    if runway is None:
        return 0.05
    return 1.0 / (1.0 + exp((runway - 60.0) / 12.0))


def project_liquidity(data: LiquidityInput) -> LiquidityProjection:
    net_burn = max((data.cash_out_5m - data.cash_in_5m) / 5.0, 0.0)
    usable_balance = max(data.balance - data.safe_buffer, 0.0)
    runway = None if net_burn <= 0 else usable_balance / net_burn
    probability = _shortage_probability(runway, data.balance, data.safe_buffer)

    low: int | None = None
    high: int | None = None
    if runway is not None:
        uncertainty_ratio = 0.15 + (1.0 - data.data_quality_score) * 0.50
        spread = max(5.0, runway * uncertainty_ratio)
        low = max(0, round(runway - spread))
        high = max(low, round(runway + spread))

    confidence = data.data_quality_score
    if data.data_health == DataHealth.UNRELIABLE:
        confidence = min(confidence, 0.40)

    evidence: list[str] = []
    if net_burn > 0:
        evidence.append(
            f"Net balance burn is approximately BDT {net_burn:,.0f} per minute."
        )
    else:
        evidence.append("Recent inflow is sufficient to cover recent outflow.")
    if data.balance <= data.safe_buffer:
        evidence.append("The balance is already at or below its safe operating buffer.")
    elif runway is not None:
        evidence.append(
            f"The current balance provides about {round(runway)} minutes of runway."
        )

    return LiquidityProjection(
        resource_id=data.resource_id,
        net_burn_per_minute=round(net_burn, 6),
        estimated_runway_minutes=None if runway is None else round(runway, 3),
        shortage_eta_low_minutes=low,
        shortage_eta_high_minutes=high,
        shortage_probability_60m=round(probability, 6),
        confidence=round(confidence, 6),
        evidence=evidence,
    )
