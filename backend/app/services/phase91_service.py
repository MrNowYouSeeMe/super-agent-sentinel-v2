from __future__ import annotations

from uuid import uuid4

from app.services.phase6b_runtime import Phase6BPredictionRequest
from app.services.phase9_governance import analyze_phase9, phase9_status
from app.services.phase91_audit import append_chain_event
from app.services.phase91_guard import (
    check_rate_limit,
    get_idempotent_response,
    request_fingerprint,
    store_idempotent_response,
)
from app.services.phase91_models import (
    CoordinationCase,
    Phase91AnalysisRequest,
    Phase91AnalysisResponse,
    Phase91Status,
)
from app.services.phase91_security import (
    assess_provider_feeds,
    corroborate_provider_attribution,
    deterministic_pressure_scores,
    filter_historical_matches,
    provider_confidence_cap,
)
from app.services.phase91_structured import (
    build_structured_explanation,
    deterministic_structured_fallback,
    validate_structured_explanation,
)

PHASE91_VERSION = "phase9.1-1.0.0"


def _base_payload(payload: Phase91AnalysisRequest) -> Phase6BPredictionRequest:
    return Phase6BPredictionRequest.model_validate(
        payload.model_dump(exclude={"provider_feeds", "idempotency_key"})
    )


def _apply_attribution_safety(
    analysis,
    *,
    attribution,
    adjusted_confidence: float,
    feed_cap: float,
):
    prediction = analysis.prediction
    updates = {
        "confidence": min(prediction.confidence, adjusted_confidence, feed_cap),
        "human_review_required": True,
    }
    if attribution.requires_verification:
        updates["estimated_time_to_shortage_minutes"] = None
        updates["data_verification_required"] = True
        updates["recommended_action"] = (
            "Verify provider-specific balances, feed freshness, and deterministic pressure "
            "evidence before assigning operational responsibility."
        )
    prediction = prediction.model_copy(update=updates)

    confidence = analysis.confidence.model_copy(
        update={
            "final_operational_confidence": adjusted_confidence,
            "confidence_band": (
                "very_high"
                if adjusted_confidence >= 0.90
                else "high"
                if adjusted_confidence >= 0.75
                else "medium"
                if adjusted_confidence >= 0.55
                else "low"
            ),
            "reasons": analysis.confidence.reasons
            + [
                (
                    "Phase 9.1 provider-attribution adjustment: "
                    f"{attribution.confidence_adjustment:+.1%}."
                ),
                f"Provider-feed confidence cap: {feed_cap:.1%}.",
            ],
        }
    )
    filtered_matches = filter_historical_matches(
        model_resource=prediction.affected_resource,
        matches=analysis.historical_matches,
    )
    return analysis.model_copy(
        update={
            "prediction": prediction,
            "confidence": confidence,
            "historical_matches": filtered_matches,
            "human_review_required": True,
        }
    )


def analyze_phase91(
    payload: Phase91AnalysisRequest,
    *,
    actor_id: str,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    enforce_rate_limit: bool = True,
) -> Phase91AnalysisResponse:
    if enforce_rate_limit:
        check_rate_limit(actor_id)

    key = idempotency_key or payload.idempotency_key
    fingerprint = request_fingerprint(payload)
    cache_key = f"{actor_id}:{key}" if key else None
    if cache_key:
        cached = get_idempotent_response(cache_key, fingerprint=fingerprint)
        if cached is not None:
            return Phase91AnalysisResponse.model_validate(cached).model_copy(
                update={"idempotent_replay": True}
            )

    resolved_request_id = request_id or f"REQ91-{uuid4().hex[:16].upper()}"
    base = _base_payload(payload)
    analysis = analyze_phase9(base, actor_id=actor_id)

    feeds = assess_provider_feeds(base, payload.provider_feeds)
    scores = deterministic_pressure_scores(base)
    attribution = corroborate_provider_attribution(
        model_resource=analysis.prediction.affected_resource,
        scores=scores,
        feeds=feeds,
    )
    feed_cap = provider_confidence_cap(
        model_resource=analysis.prediction.affected_resource,
        feeds=feeds,
    )
    adjusted_confidence = max(
        0.05,
        min(
            feed_cap,
            analysis.confidence.final_operational_confidence
            + attribution.confidence_adjustment,
        ),
    )
    adjusted_confidence = round(adjusted_confidence, 4)

    analysis = _apply_attribution_safety(
        analysis,
        attribution=attribution,
        adjusted_confidence=adjusted_confidence,
        feed_cap=feed_cap,
    )

    structured = build_structured_explanation(
        analysis=analysis,
        attribution=attribution,
        feeds=feeds,
        language=payload.language,
    )
    validation = validate_structured_explanation(
        explanation=structured,
        analysis=analysis,
        attribution=attribution,
    )
    if not validation.valid:
        structured = deterministic_structured_fallback(
            analysis=analysis,
            attribution=attribution,
            language=payload.language,
        )
        second_validation = validate_structured_explanation(
            explanation=structured,
            analysis=analysis,
            attribution=attribution,
        )
        validation = second_validation.model_copy(update={"fallback_used": True})

    append_chain_event(
        analysis_id=analysis.analysis_id,
        event="phase91_analysis_hardened",
        actor_id=actor_id,
        details={
            "request_id": resolved_request_id,
            "model_resource": attribution.model_resource,
            "deterministic_resource": attribution.deterministic_resource,
            "agreement": attribution.agreement,
            "adjusted_operational_confidence": adjusted_confidence,
            "structured_output_valid": validation.valid,
            "evidence_coverage": validation.evidence_coverage,
        },
    )

    response = Phase91AnalysisResponse(
        phase91_version=PHASE91_VERSION,
        request_id=resolved_request_id,
        area_id=payload.area_id,
        outlet_id=payload.outlet_id,
        language=payload.language,
        analysis=analysis,
        provider_feeds=feeds,
        provider_attribution=attribution,
        adjusted_operational_confidence=adjusted_confidence,
        structured_explanation=structured,
        structured_validation=validation,
        case=None,
        idempotent_replay=False,
        safety_boundary=(
            "Advisory decision support only. Provider balances remain separate. "
            "No wallet interoperability, fund movement, automatic blocking, account freezing, "
            "or final fraud determination is performed."
        ),
    )

    if cache_key:
        store_idempotent_response(
            cache_key,
            fingerprint=fingerprint,
            response=response.model_dump(mode="json"),
        )
    return response


def attach_case(
    response: Phase91AnalysisResponse,
    case: CoordinationCase,
) -> Phase91AnalysisResponse:
    return response.model_copy(update={"case": case})



def redact_phase91_response(
    response: Phase91AnalysisResponse,
    *,
    allowed_providers: set[str],
) -> Phase91AnalysisResponse:
    known = {"bkash", "nagad", "rocket"}

    def redact_text(text: str) -> str:
        result = text
        for provider in known - allowed_providers:
            result = result.replace(provider, "another_provider")
            result = result.replace(provider.capitalize(), "Another provider")
        return result

    feeds = [
        item for item in response.provider_feeds if item.provider in allowed_providers
    ]
    attribution = response.provider_attribution
    scores = {
        key: value
        for key, value in attribution.deterministic_scores.items()
        if key == "shared_cash" or key in allowed_providers
    }
    deterministic_resource = attribution.deterministic_resource
    if deterministic_resource in known and deterministic_resource not in allowed_providers:
        deterministic_resource = "redacted_provider"
    effective_resource = attribution.effective_resource
    if effective_resource in known and effective_resource not in allowed_providers:
        effective_resource = "requires_verification"
    attribution = attribution.model_copy(
        update={
            "deterministic_resource": deterministic_resource,
            "effective_resource": effective_resource,
            "deterministic_scores": scores,
            "reasons": [redact_text(item) for item in attribution.reasons],
        }
    )

    matches = [
        item
        for item in response.analysis.historical_matches
        if item.affected_service in allowed_providers
        or item.affected_service in {"shared_cash", "none", "unknown"}
    ]
    analysis = response.analysis.model_copy(update={"historical_matches": matches})
    structured = response.structured_explanation.model_copy(
        update={
            "situation": redact_text(response.structured_explanation.situation),
            "uncertainty": redact_text(response.structured_explanation.uncertainty),
            "normal_alternative": (
                redact_text(response.structured_explanation.normal_alternative)
                if response.structured_explanation.normal_alternative
                else None
            ),
            "safe_next_step": redact_text(response.structured_explanation.safe_next_step),
            "narrative": redact_text(response.structured_explanation.narrative),
        }
    )
    return response.model_copy(
        update={
            "provider_feeds": feeds,
            "provider_attribution": attribution,
            "analysis": analysis,
            "structured_explanation": structured,
        }
    )

def phase91_status() -> Phase91Status:
    base = phase9_status()
    return Phase91Status(
        available=base.available and base.evidence_index_available,
        phase91_version=PHASE91_VERSION,
        capabilities=[
            "per-provider feed-health assessment",
            "provider-pressure corroboration",
            "provider-attribution disagreement handling",
            "provider-scoped historical evidence filtering",
            "structured evidence-ID explanation contract",
            "LLM narrative safety validation",
            "persistent idempotency and duplicate-case prevention",
            "per-actor analysis rate limiting",
            "linked acknowledgement, assignment, notes, escalation, resolution, and closure",
            "tamper-evident hash-chained audit",
            "judge-facing reliability metrics",
        ],
        safety_boundary=(
            "The prototype uses synthetic decision-support data only and never moves money, "
            "merges provider balances, blocks accounts, or declares fraud."
        ),
    )
