from app.domain.common.enums import DataHealth
from app.domain.data_quality.models import DataQualityInput
from app.domain.data_quality.service import evaluate_data_quality


def test_stale_conflicting_data_becomes_unreliable() -> None:
    result = evaluate_data_quality(
        DataQualityInput(
            balance=10_000,
            feed_age_seconds=2_400,
            reconciliation_difference=4_000,
            completeness_ratio=0.50,
            source_quality_score=0.40,
        )
    )
    assert result.state == DataHealth.UNRELIABLE
    assert result.score < 0.50
    assert len(result.evidence) >= 3
