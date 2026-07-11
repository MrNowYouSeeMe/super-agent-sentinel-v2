from app.api.v1.schemas import ResourceSnapshot
from app.domain.data_quality.models import DataQualityResult
from app.domain.liquidity.models import LiquidityProjection
from app.domain.ml.models import MLFeatureSet


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / max(denominator, 1.0)


def build_resource_features(
    resource: ResourceSnapshot,
    *,
    data_quality: DataQualityResult,
    liquidity: LiquidityProjection,
    festival_or_market_day: bool,
) -> MLFeatureSet:
    runway = liquidity.estimated_runway_minutes
    runway_capped = 300.0 if runway is None else min(runway, 300.0)
    balance_to_buffer_ratio = _safe_ratio(resource.balance, resource.safe_buffer)
    reconciliation_ratio = _safe_ratio(
        resource.reconciliation_difference, max(resource.balance, resource.safe_buffer, 1.0)
    )
    features = {
        "balance_to_buffer_ratio": balance_to_buffer_ratio,
        "net_burn_per_minute": liquidity.net_burn_per_minute,
        "runway_minutes_capped": runway_capped,
        "cashout_to_in_ratio": _safe_ratio(resource.cash_out_5m, resource.cash_in_5m),
        "transaction_count_5m": float(resource.transaction_count_5m),
        "repeated_amount_ratio": resource.repeated_amount_ratio,
        "unique_customer_ratio": resource.unique_customer_ratio,
        "failure_rate": resource.failure_rate,
        "feed_age_minutes": resource.feed_age_seconds / 60.0,
        "reconciliation_ratio": reconciliation_ratio,
        "completeness_ratio": resource.completeness_ratio,
        "source_quality_score": resource.source_quality_score,
        "data_quality_score": data_quality.score,
        "festival_or_market_day": 1.0 if festival_or_market_day else 0.0,
        "is_shared_cash": 1.0 if resource.resource_id == "shared_cash" else 0.0,
    }
    return MLFeatureSet(resource_id=resource.resource_id, features=features)

