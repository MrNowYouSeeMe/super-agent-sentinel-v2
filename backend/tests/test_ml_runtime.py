from app.api.v1.schemas import ResourceSnapshot
from app.domain.data_quality.models import DataQualityInput
from app.domain.data_quality.service import evaluate_data_quality
from app.domain.liquidity.models import LiquidityInput
from app.domain.liquidity.service import project_liquidity
from app.domain.ml.features import build_resource_features
from app.services.ml_runtime import model_metadata, predict_resource


def test_phase2_model_metadata_is_dataset_ready() -> None:
    metadata = model_metadata()
    assert metadata["model_version"].startswith("2.1")
    assert metadata["feature_count"] >= 10
    assert metadata["training_status"] == "baseline_ready_dataset_pending"


def test_ml_runtime_scores_risky_resource_higher_than_safe_resource() -> None:
    risky = ResourceSnapshot(
        resource_id="bkash",
        balance=7_000,
        safe_buffer=2_000,
        cash_in_5m=1_000,
        cash_out_5m=26_000,
        transaction_count_5m=30,
        repeated_amount_ratio=0.80,
        unique_customer_ratio=0.20,
    )
    healthy = ResourceSnapshot(
        resource_id="nagad",
        balance=120_000,
        safe_buffer=15_000,
        cash_in_5m=25_000,
        cash_out_5m=20_000,
    )

    def score(resource: ResourceSnapshot):
        quality = evaluate_data_quality(DataQualityInput(balance=resource.balance, feed_age_seconds=0, reconciliation_difference=0))
        liquidity = project_liquidity(
            LiquidityInput(
                resource_id=resource.resource_id,
                balance=resource.balance,
                safe_buffer=resource.safe_buffer,
                cash_in_5m=resource.cash_in_5m,
                cash_out_5m=resource.cash_out_5m,
                data_quality_score=quality.score,
                data_health=quality.state,
            )
        )
        features = build_resource_features(resource, data_quality=quality, liquidity=liquidity, festival_or_market_day=True)
        return predict_resource(features)

    risky_score = score(risky)
    healthy_score = score(healthy)
    assert risky_score.shortage_probability_60m > healthy_score.shortage_probability_60m
    assert risky_score.anomaly_probability > healthy_score.anomaly_probability
    assert risky_score.notable_signals

