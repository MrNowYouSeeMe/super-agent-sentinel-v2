from app.domain.common.enums import DataHealth
from app.domain.data_quality.models import DataQualityInput, DataQualityResult


def _freshness_factor(age_seconds: int) -> float:
    if age_seconds <= 300:
        return 1.0
    if age_seconds <= 900:
        return 0.85
    if age_seconds <= 1800:
        return 0.60
    return 0.35


def _reconciliation_factor(balance: float, difference: float) -> float:
    base = max(balance, 1.0)
    ratio = difference / base
    if ratio <= 0.01:
        return 1.0
    if ratio <= 0.05:
        return 0.75
    return 0.40


def evaluate_data_quality(data: DataQualityInput) -> DataQualityResult:
    freshness = _freshness_factor(data.feed_age_seconds)
    reconciliation = _reconciliation_factor(
        data.balance, data.reconciliation_difference
    )
    completeness = data.completeness_ratio
    score = round(
        0.35 * freshness
        + 0.30 * reconciliation
        + 0.20 * completeness
        + 0.15 * data.source_quality_score,
        6,
    )

    if score >= 0.80:
        state = DataHealth.HEALTHY
    elif score >= 0.50:
        state = DataHealth.DEGRADED
    else:
        state = DataHealth.UNRELIABLE

    evidence: list[str] = []
    if freshness < 1:
        evidence.append(
            f"Provider feed is {round(data.feed_age_seconds / 60)} minutes old."
        )
    if reconciliation < 1:
        evidence.append(
            "The reported balance conflicts with reconciliation records."
        )
    if completeness < 1:
        evidence.append(
            f"Only {round(completeness * 100)}% of required fields are available."
        )
    if not evidence:
        evidence.append("Provider data is fresh, complete, and reconciled.")

    return DataQualityResult(
        state=state,
        score=score,
        freshness_factor=freshness,
        reconciliation_factor=reconciliation,
        completeness_factor=completeness,
        evidence=evidence,
    )
