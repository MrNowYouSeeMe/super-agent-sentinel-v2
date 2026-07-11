from __future__ import annotations

import math
from typing import Iterable

from app.services.phase6b_runtime import Phase6BPredictionRequest
from app.services.phase91_models import (
    ProviderAttribution,
    ProviderFeedAssessment,
    ProviderFeedInput,
)

PROVIDERS = ("bkash", "nagad", "rocket")


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _safe_ratio(numerator: float, denominator: float) -> float:
    return max(0.0, float(numerator)) / max(abs(float(denominator)), 1.0)


def _derived_feed(
    provider: str,
    payload: Phase6BPredictionRequest,
) -> ProviderFeedInput:
    balances = {
        "bkash": payload.bkash_balance,
        "nagad": payload.nagad_balance,
        "rocket": payload.rocket_balance,
    }
    severe_conflict = payload.reconciliation_difference > 25_000
    stale = payload.feed_age_seconds > 300
    missing = payload.missing_ratio >= 0.10
    degraded = payload.data_quality_score < 0.75

    if severe_conflict:
        status = "conflict"
    elif missing:
        status = "missing"
    elif stale:
        status = "stale"
    elif degraded:
        status = "degraded"
    else:
        status = "healthy"

    return ProviderFeedInput(
        provider=provider,
        status=status,
        feed_age_seconds=payload.feed_age_seconds,
        quality_score=payload.data_quality_score,
        missing_ratio=payload.missing_ratio,
        reported_balance=balances[provider],
        reconciled_balance=(
            max(0.0, balances[provider] - payload.reconciliation_difference)
            if severe_conflict
            else balances[provider]
        ),
        conflict_amount=payload.reconciliation_difference if severe_conflict else 0.0,
    )


def assess_provider_feeds(
    payload: Phase6BPredictionRequest,
    explicit: Iterable[ProviderFeedInput],
) -> list[ProviderFeedAssessment]:
    by_provider = {item.provider: item for item in explicit}
    assessments: list[ProviderFeedAssessment] = []

    for provider in PROVIDERS:
        item = by_provider.get(provider) or _derived_feed(provider, payload)
        reasons: list[str] = []

        status = item.status
        if item.feed_age_seconds > 900:
            status = "stale"
            reasons.append("Feed is older than 15 minutes.")
        elif item.feed_age_seconds > 300:
            status = "stale"
            reasons.append("Feed is older than 5 minutes.")

        balance_gap = 0.0
        if item.reported_balance is not None and item.reconciled_balance is not None:
            balance_gap = abs(item.reported_balance - item.reconciled_balance)
        conflict_amount = max(item.conflict_amount, balance_gap)

        if conflict_amount > 25_000:
            status = "conflict"
            reasons.append("Reported and reconciled balances materially conflict.")
        elif conflict_amount > 10_000 and status == "healthy":
            status = "degraded"
            reasons.append("Balance reconciliation difference needs review.")

        if item.missing_ratio >= 0.25:
            status = "missing"
            reasons.append("At least 25% of provider data is missing.")
        elif item.missing_ratio >= 0.10 and status == "healthy":
            status = "degraded"
            reasons.append("Provider data has a material missing-data ratio.")

        if item.quality_score < 0.50:
            status = "missing"
            reasons.append("Provider data quality is below 50%.")
        elif item.quality_score < 0.75 and status == "healthy":
            status = "degraded"
            reasons.append("Provider data quality is below 75%.")

        if status == "healthy":
            cap = 0.98
            supported = True
            reasons.append("Feed is fresh, reconciled, and sufficiently complete.")
        elif status == "degraded":
            cap = 0.75
            supported = True
        elif status == "stale":
            cap = 0.60
            supported = item.feed_age_seconds <= 900
        elif status == "conflict":
            cap = 0.50
            supported = False
        else:
            cap = 0.45
            supported = False

        assessments.append(
            ProviderFeedAssessment(
                provider=provider,
                status=status,
                supported_for_decision=supported,
                confidence_cap=cap,
                reasons=reasons,
                feed_age_seconds=item.feed_age_seconds,
                quality_score=item.quality_score,
                missing_ratio=item.missing_ratio,
                conflict_amount=conflict_amount,
            )
        )

    return assessments


def deterministic_pressure_scores(
    payload: Phase6BPredictionRequest,
) -> dict[str, float]:
    provider_balances = {
        "bkash": payload.bkash_balance,
        "nagad": payload.nagad_balance,
        "rocket": payload.rocket_balance,
    }
    provider_burn = {
        "bkash": payload.bkash_burn_60m,
        "nagad": payload.nagad_burn_60m,
        "rocket": payload.rocket_burn_60m,
    }

    scores: dict[str, float] = {}
    shared_ratio = _safe_ratio(payload.shared_cash_burn_60m, payload.shared_cash_balance)
    scores["shared_cash"] = _clamp(
        0.60 * min(shared_ratio / 1.25, 1.0)
        + 0.25 * min(max(payload.velocity_vs_baseline - 1.0, 0.0) / 4.0, 1.0)
        + 0.15 * min(max(-payload.net_cash_flow_5m, 0.0) / max(payload.shared_cash_balance, 1.0), 1.0)
    )

    for provider in PROVIDERS:
        ratio = _safe_ratio(provider_burn[provider], provider_balances[provider])
        low_balance = 1.0 - min(provider_balances[provider] / 100_000.0, 1.0)
        scores[provider] = _clamp(
            0.70 * min(ratio / 1.25, 1.0)
            + 0.20 * low_balance
            + 0.10 * min(max(payload.velocity_vs_baseline - 1.0, 0.0) / 4.0, 1.0)
        )

    return {name: round(score, 4) for name, score in scores.items()}


def corroborate_provider_attribution(
    *,
    model_resource: str,
    scores: dict[str, float],
    feeds: list[ProviderFeedAssessment],
) -> ProviderAttribution:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    deterministic_resource, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    feed_map = {item.provider: item for item in feeds}
    reasons: list[str] = []
    adjustment = 0.0
    requires_verification = False

    if model_resource in feed_map and not feed_map[model_resource].supported_for_decision:
        agreement = "insufficient_data"
        effective = "requires_verification"
        adjustment = -0.25
        requires_verification = True
        reasons.extend(feed_map[model_resource].reasons)
        reasons.append("The predicted provider does not have decision-grade feed data.")
    elif model_resource == deterministic_resource:
        agreement = "confirmed"
        effective = model_resource
        adjustment = 0.08 if top_score >= 0.70 else 0.04
        reasons.append("Frozen model and deterministic pressure engine agree.")
    elif abs(top_score - scores.get(model_resource, 0.0)) <= 0.12:
        agreement = "close"
        effective = model_resource
        adjustment = -0.03
        requires_verification = True
        reasons.append("Model and deterministic scores are close but not identical.")
    else:
        agreement = "disagreement"
        effective = "requires_verification"
        adjustment = -0.18
        requires_verification = True
        reasons.append(
            f"Model indicates {model_resource}, while deterministic pressure is highest for "
            f"{deterministic_resource}."
        )

    if top_score - second_score < 0.08:
        requires_verification = True
        adjustment = min(adjustment, -0.05)
        reasons.append("Top two deterministic pressure scores are too close for confident attribution.")

    return ProviderAttribution(
        model_resource=model_resource,
        deterministic_resource=deterministic_resource,
        effective_resource=effective,
        agreement=agreement,
        deterministic_scores=scores,
        confidence_adjustment=round(adjustment, 4),
        requires_verification=requires_verification,
        reasons=reasons,
    )


def provider_confidence_cap(
    *,
    model_resource: str,
    feeds: list[ProviderFeedAssessment],
) -> float:
    if model_resource not in PROVIDERS:
        return 0.98
    feed = next(item for item in feeds if item.provider == model_resource)
    return feed.confidence_cap


def filter_historical_matches(
    *,
    model_resource: str,
    matches: list,
) -> list:
    allowed = {model_resource, "shared_cash", "none", "unknown"}
    return [
        match
        for match in matches
        if str(getattr(match, "affected_service", "unknown")).lower() in allowed
    ]


def contains_cross_provider_reference(
    text: str,
    allowed_provider: str | None,
) -> bool:
    lowered = text.lower()
    mentioned = {provider for provider in PROVIDERS if provider in lowered}
    if not mentioned:
        return False
    if allowed_provider is None:
        return bool(mentioned)
    return bool(mentioned - {allowed_provider})
