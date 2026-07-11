from app.domain.anomaly.models import AnomalyInput, AnomalyResult


def evaluate_anomaly(data: AnomalyInput) -> AnomalyResult:
    score = 0.0
    evidence: list[str] = []
    context: list[str] = []

    if data.transaction_count_5m >= 10 and data.repeated_amount_ratio >= 0.60:
        score += 0.35
        evidence.append("A high share of recent transactions have repeated amounts.")

    if data.transaction_count_5m >= 10 and data.unique_customer_ratio <= 0.25:
        score += 0.25
        evidence.append("Recent activity is concentrated among a small customer group.")

    inflow_base = max(data.cash_in_5m, 1.0)
    if data.transaction_count_5m >= 10 and data.cash_out_5m / inflow_base >= 3.0:
        score += 0.25
        evidence.append("Recent cash-out demand is substantially higher than cash-in.")

    if data.failure_rate >= 0.15:
        score += 0.20
        evidence.append("The recent transaction failure rate is unusually high.")

    if data.festival_or_market_day:
        context.append(
            "Festival, salary, remittance, or market-day demand may explain part of the spike."
        )
        score = max(0.0, score - 0.10)

    if not evidence:
        evidence.append("No material unusual-activity rule was triggered.")

    return AnomalyResult(
        score=round(min(score, 1.0), 6),
        evidence=evidence,
        possible_normal_context=context,
    )
