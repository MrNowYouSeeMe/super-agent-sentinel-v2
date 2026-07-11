from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.openai_explanation import (
    ExplanationInput,
    deterministic_operator_explanation,
    explain_with_optional_openai,
)
from app.services.phase6b_runtime import (
    Phase6BPredictionRequest,
    Phase6BPredictionResponse,
    Phase6BStatus,
    phase6b_status,
    predict_phase6b,
)
from app.services.phase9_audit import append_audit_event
from app.services.phase9_evidence import (
    EvidenceItem,
    HistoricalMatch,
    build_evidence,
    match_historical_cases,
)

PHASE9_VERSION = "phase9-1.0.0"
ALLOWED_RESOURCES = {"none", "shared_cash", "bkash", "nagad", "rocket"}
SECRET_OR_CREDENTIAL = re.compile(
    r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{8,}|password|api[_ -]?key|private[_ -]?key|"
    r"\botp\b|\bpin\b\s*[:=])",
    re.IGNORECASE,
)
UNSAFE_ACTION = re.compile(
    r"(?:fraud\s+(?:is\s+)?confirmed|"
    r"(?:should|must|immediately|recommend(?:ed)?\s+to)\s+"
    r"(?:freeze|block|suspend|transfer|move|send)\b)",
    re.IGNORECASE,
)
PROVIDER_PATTERN = re.compile(r"\b(bkash|nagad|rocket)\b", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%")


class ValidationIssue(BaseModel):
    code: str
    level: Literal["warning", "error"]
    field: str
    message: str


class InputValidationReport(BaseModel):
    valid: bool
    data_health: Literal["healthy", "degraded", "unreliable"]
    safe_mode_required: bool
    confidence_cap: float = Field(ge=0, le=1)
    issues: list[ValidationIssue]
    prohibited_content_removed: bool = False


class ContextAssessment(BaseModel):
    active_contexts: list[str]
    normal_alternative_explanations: list[str]
    ambiguity_penalty: float = Field(ge=0, le=0.30)
    summary: str


class ConfidenceBreakdown(BaseModel):
    model_confidence: float = Field(ge=0, le=1)
    model_certainty: float = Field(ge=0, le=1)
    evidence_strength: float = Field(ge=0, le=1)
    data_quality_component: float = Field(ge=0, le=1)
    historical_similarity: float = Field(ge=0, le=1)
    context_ambiguity_penalty: float = Field(ge=0, le=0.30)
    validation_penalty: float = Field(ge=0, le=0.40)
    final_operational_confidence: float = Field(ge=0, le=1)
    confidence_band: Literal["low", "medium", "high", "very_high"]
    reasons: list[str]
    note: str = (
        "Operational confidence combines calibrated model output with evidence, "
        "data quality, context, and historical similarity. It is not a new accuracy metric."
    )


class LLMInputValidation(BaseModel):
    valid: bool
    approved_evidence_count: int = Field(ge=0)
    redacted_fields: list[str]
    issues: list[str]


class ExplanationValidation(BaseModel):
    valid: bool
    evidence_coverage: float = Field(ge=0, le=1)
    issues: list[str]
    fallback_used: bool
    validated_mode: str


class Phase9AnalysisResponse(BaseModel):
    phase9_version: str
    analysis_id: str
    created_at: datetime
    input_validation: InputValidationReport
    context: ContextAssessment
    prediction: Phase6BPredictionResponse
    evidence: list[EvidenceItem]
    historical_matches: list[HistoricalMatch]
    confidence: ConfidenceBreakdown
    llm_input_validation: LLMInputValidation
    explanation: str
    explanation_mode: str
    explanation_validation: ExplanationValidation
    safe_fallback_active: bool
    human_review_required: bool
    audit_event_ids: list[str]
    safety_boundary: str


class Phase9Status(BaseModel):
    available: bool
    phase9_version: str
    phase6b: Phase6BStatus
    evidence_index_available: bool
    evidence_prototype_count: int
    capabilities: list[str]
    safety_boundary: str


class Phase9InputError(ValueError):
    def __init__(self, report: InputValidationReport):
        super().__init__("Phase 9 input validation failed.")
        self.report = report


def _issue(
    code: str,
    level: Literal["warning", "error"],
    field: str,
    message: str,
) -> ValidationIssue:
    return ValidationIssue(code=code, level=level, field=field, message=message)


def validate_phase9_input(payload: Phase6BPredictionRequest) -> InputValidationReport:
    issues: list[ValidationIssue] = []

    text_fields = {
        "episode_id": payload.episode_id,
        "window_id": payload.window_id,
        "area_id": payload.area_id,
        "outlet_id": payload.outlet_id,
        "agent_profile": payload.agent_profile,
        "location_type": payload.location_type,
        "provider_mix_shift": payload.provider_mix_shift,
    }
    for field, value in text_fields.items():
        if SECRET_OR_CREDENTIAL.search(value):
            issues.append(
                _issue(
                    "PROHIBITED_CREDENTIAL_CONTENT",
                    "error",
                    field,
                    "Credentials, secrets, PINs, or OTP-like content are not accepted.",
                )
            )

    money_fields = {
        "shared_cash_balance": payload.shared_cash_balance,
        "bkash_balance": payload.bkash_balance,
        "nagad_balance": payload.nagad_balance,
        "rocket_balance": payload.rocket_balance,
        "cash_in_amount_5m": payload.cash_in_amount_5m,
        "cash_out_amount_5m": payload.cash_out_amount_5m,
    }
    for field, value in money_fields.items():
        if not math.isfinite(float(value)):
            issues.append(_issue("NON_FINITE_VALUE", "error", field, "Value must be finite."))
        elif value > 10_000_000_000:
            issues.append(
                _issue(
                    "OUT_OF_DEMO_RANGE",
                    "error",
                    field,
                    "Value exceeds the documented synthetic prototype range.",
                )
            )

    expected_net = payload.cash_in_amount_5m - payload.cash_out_amount_5m
    mismatch = abs(payload.net_cash_flow_5m - expected_net)
    tolerance = max(
        100.0,
        0.02 * max(payload.cash_in_amount_5m, payload.cash_out_amount_5m, 1.0),
    )
    if mismatch > tolerance:
        issues.append(
            _issue(
                "NET_FLOW_MISMATCH",
                "warning",
                "net_cash_flow_5m",
                "Net flow does not reconcile with cash-in minus cash-out.",
            )
        )

    if payload.tx_count_5m == 0 and (
        payload.cash_in_amount_5m > 0 or payload.cash_out_amount_5m > 0
    ):
        issues.append(
            _issue(
                "ZERO_COUNT_WITH_AMOUNT",
                "warning",
                "tx_count_5m",
                "Transaction amount exists while transaction count is zero.",
            )
        )

    if payload.feed_age_seconds > 300:
        issues.append(
            _issue(
                "STALE_FEED",
                "warning",
                "feed_age_seconds",
                "Provider feed is stale and exact timing must be treated cautiously.",
            )
        )
    if payload.data_quality_score < 0.75:
        issues.append(
            _issue(
                "LOW_DATA_QUALITY",
                "warning",
                "data_quality_score",
                "Input data quality is below the preferred decision-support level.",
            )
        )
    if payload.missing_ratio >= 0.10:
        issues.append(
            _issue(
                "MISSING_DATA",
                "warning",
                "missing_ratio",
                "Missing-data ratio requires confidence reduction.",
            )
        )
    if payload.reconciliation_difference > 10_000:
        issues.append(
            _issue(
                "RECONCILIATION_CONFLICT",
                "warning",
                "reconciliation_difference",
                "Balance reconciliation conflict requires manual verification.",
            )
        )

    error_count = sum(item.level == "error" for item in issues)
    warning_count = sum(item.level == "warning" for item in issues)
    severe_quality = (
        payload.feed_age_seconds > 900
        or payload.data_quality_score < 0.50
        or payload.missing_ratio >= 0.25
        or payload.reconciliation_difference > 25_000
    )
    safe_mode = severe_quality or warning_count >= 3
    if severe_quality:
        health: Literal["healthy", "degraded", "unreliable"] = "unreliable"
        cap = 0.55
    elif warning_count:
        health = "degraded"
        cap = 0.75
    else:
        health = "healthy"
        cap = 0.98

    return InputValidationReport(
        valid=error_count == 0,
        data_health=health,
        safe_mode_required=safe_mode,
        confidence_cap=cap,
        issues=issues,
    )


def assess_context(payload: Phase6BPredictionRequest) -> ContextAssessment:
    mapping = [
        ("festival_or_eid", payload.festival_flag, "Festival or Eid demand may create a legitimate rush."),
        ("salary_day", payload.salary_flag, "Salary-day withdrawals may increase normal cash-out demand."),
        ("remittance_period", payload.remittance_flag, "Remittance activity may create a legitimate volume increase."),
        ("market_day", payload.market_day_flag, "Market-day commerce may explain part of the spike."),
        ("network_recovery", payload.network_recovery_flag, "Recovered queued transactions may create a temporary burst."),
    ]
    active = [name for name, flag, _ in mapping if flag]
    alternatives = [text for _, flag, text in mapping if flag]
    penalty = min(0.18, 0.04 * len(active))
    summary = (
        "No special demand context is active."
        if not active
        else (
            f"{len(active)} contextual demand signal(s) are active. They reduce "
            "overconfident anomaly interpretation but do not cancel liquidity evidence."
        )
    )
    return ContextAssessment(
        active_contexts=active,
        normal_alternative_explanations=alternatives,
        ambiguity_penalty=penalty,
        summary=summary,
    )


def _mean(values: list[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default


def calculate_operational_confidence(
    payload: Phase6BPredictionRequest,
    prediction: Phase6BPredictionResponse,
    validation: InputValidationReport,
    context: ContextAssessment,
    evidence: list[EvidenceItem],
    matches: list[HistoricalMatch],
) -> ConfidenceBreakdown:
    probabilities = [
        prediction.probabilities.anomaly,
        prediction.probabilities.shortage_30m,
        prediction.probabilities.shortage_60m,
        prediction.probabilities.shortage_120m,
    ]
    model_certainty = _mean([abs(value - 0.5) * 2.0 for value in probabilities], 0.5)
    evidence_strength = _mean([item.strength for item in evidence[:6]], 0.35)
    historical_similarity = _mean([item.similarity for item in matches[:3]], 0.0)

    freshness = max(0.0, 1.0 - payload.feed_age_seconds / 1800.0)
    reconciliation = max(
        0.0,
        1.0 - payload.reconciliation_difference / max(payload.shared_cash_balance, 1.0),
    )
    data_quality_component = max(
        0.0,
        min(
            1.0,
            0.60 * payload.data_quality_score
            + 0.20 * freshness
            + 0.10 * (1.0 - payload.missing_ratio)
            + 0.10 * reconciliation,
        ),
    )

    warning_count = sum(item.level == "warning" for item in validation.issues)
    validation_penalty = min(0.30, 0.04 * warning_count)
    raw = (
        0.45 * prediction.confidence
        + 0.20 * model_certainty
        + 0.15 * evidence_strength
        + 0.10 * data_quality_component
        + 0.10 * historical_similarity
        - context.ambiguity_penalty
        - validation_penalty
    )
    final = max(0.05, min(validation.confidence_cap, raw))
    if final >= 0.90:
        band: Literal["low", "medium", "high", "very_high"] = "very_high"
    elif final >= 0.75:
        band = "high"
    elif final >= 0.55:
        band = "medium"
    else:
        band = "low"

    reasons = [
        f"Base calibrated model confidence contributes {prediction.confidence:.1%}.",
        f"Model probability certainty contributes {model_certainty:.1%}.",
        f"Validated evidence strength is {evidence_strength:.1%}.",
        f"Data-quality component is {data_quality_component:.1%}.",
        f"Historical similarity component is {historical_similarity:.1%}.",
    ]
    if context.ambiguity_penalty:
        reasons.append(
            f"Legitimate demand context applies a {context.ambiguity_penalty:.1%} ambiguity penalty."
        )
    if validation_penalty:
        reasons.append(
            f"Input warnings apply a {validation_penalty:.1%} validation penalty."
        )
    if final >= validation.confidence_cap - 1e-9:
        reasons.append(
            f"Final confidence is capped at {validation.confidence_cap:.1%} by data-health policy."
        )

    return ConfidenceBreakdown(
        model_confidence=prediction.confidence,
        model_certainty=round(model_certainty, 4),
        evidence_strength=round(evidence_strength, 4),
        data_quality_component=round(data_quality_component, 4),
        historical_similarity=round(historical_similarity, 4),
        context_ambiguity_penalty=context.ambiguity_penalty,
        validation_penalty=validation_penalty,
        final_operational_confidence=round(final, 4),
        confidence_band=band,
        reasons=reasons,
    )


def validate_llm_input(
    *,
    prediction: Phase6BPredictionResponse,
    confidence: ConfidenceBreakdown,
    evidence: list[EvidenceItem],
) -> LLMInputValidation:
    issues: list[str] = []
    approved: list[EvidenceItem] = []
    for item in evidence:
        if SECRET_OR_CREDENTIAL.search(item.statement):
            issues.append(f"Evidence {item.code} contained prohibited secret-like text.")
            continue
        approved.append(item)

    if prediction.affected_resource not in ALLOWED_RESOURCES:
        issues.append("Affected resource is outside the provider-boundary allowlist.")
    if not approved:
        issues.append("No validated evidence is available for LLM explanation.")
    if not 0 <= confidence.final_operational_confidence <= 1:
        issues.append("Operational confidence is outside the allowed range.")

    return LLMInputValidation(
        valid=not issues,
        approved_evidence_count=len(approved),
        redacted_fields=[
            "episode_id",
            "window_id",
            "area_id",
            "outlet_id",
            "raw_balances",
            "credentials",
            "customer_identifiers",
        ],
        issues=issues,
    )


def _evidence_keywords(evidence: list[EvidenceItem]) -> list[set[str]]:
    stop = {
        "the", "and", "with", "that", "this", "from", "within", "current",
        "recent", "expected", "provider", "model", "activity", "review",
    }
    result: list[set[str]] = []
    for item in evidence:
        tokens = {
            token
            for token in re.findall(r"[a-zA-Z]{4,}", item.statement.lower())
            if token not in stop
        }
        result.append(tokens)
    return result


def validate_llm_output(
    text: str,
    *,
    prediction: Phase6BPredictionResponse,
    confidence: ConfidenceBreakdown,
    evidence: list[EvidenceItem],
) -> ExplanationValidation:
    issues: list[str] = []
    clean = text.strip()
    lowered = clean.lower()

    if len(clean) < 30 or len(clean) > 1500:
        issues.append("Explanation length is outside the approved range.")
    if SECRET_OR_CREDENTIAL.search(clean):
        issues.append("Explanation contains prohibited credential-like content.")
    if UNSAFE_ACTION.search(clean):
        issues.append("Explanation contains an unsafe verdict or autonomous action.")

    mentioned = {item.lower() for item in PROVIDER_PATTERN.findall(clean)}
    allowed = {
        prediction.affected_resource
        if prediction.affected_resource in {"bkash", "nagad", "rocket"}
        else ""
    }
    unexpected = mentioned - allowed
    if unexpected:
        issues.append(
            "Explanation mentioned provider(s) outside the affected-resource evidence: "
            + ", ".join(sorted(unexpected))
        )

    allowed_percentages = {
        round(confidence.final_operational_confidence * 100),
        round(prediction.confidence * 100),
        round(prediction.probabilities.anomaly * 100),
        round(prediction.probabilities.shortage_30m * 100),
        round(prediction.probabilities.shortage_60m * 100),
        round(prediction.probabilities.shortage_120m * 100),
    }
    for item in evidence:
        for value in PERCENT_PATTERN.findall(item.statement):
            allowed_percentages.add(round(float(value)))
    for value in PERCENT_PATTERN.findall(clean):
        rounded = round(float(value))
        if rounded not in allowed_percentages:
            issues.append(f"Explanation introduced unsupported percentage: {value}%.")
            break

    evidence_sets = _evidence_keywords(evidence[:6])
    covered = 0
    for tokens in evidence_sets:
        if tokens and any(token in lowered for token in tokens):
            covered += 1
    coverage = covered / len(evidence_sets) if evidence_sets else 0.0
    if evidence_sets and coverage < 0.25:
        issues.append("Explanation is insufficiently grounded in validated evidence.")

    if prediction.human_review_required and not any(
        token in lowered
        for token in ("review", "verify", "human", "manager", "reviewer")
    ):
        issues.append("Explanation omitted the required human-review boundary.")

    return ExplanationValidation(
        valid=not issues,
        evidence_coverage=round(coverage, 4),
        issues=issues,
        fallback_used=bool(issues),
        validated_mode="validated" if not issues else "rejected",
    )


def _safe_fallback_text(
    *,
    prediction: Phase6BPredictionResponse,
    confidence: ConfidenceBreakdown,
    evidence: list[EvidenceItem],
    context: ContextAssessment,
    validation: InputValidationReport,
) -> str:
    evidence_text = "; ".join(item.statement for item in evidence[:3])
    uncertainty = (
        " Data is degraded, so verify the latest provider feed before relying on exact timing."
        if validation.safe_mode_required
        else ""
    )
    normal_context = (
        " Possible normal context: " + " ".join(context.normal_alternative_explanations[:2])
        if context.normal_alternative_explanations
        else ""
    )
    return (
        f"{prediction.affected_resource} requires human review for "
        f"{prediction.classification}. Operational confidence is "
        f"{confidence.final_operational_confidence:.0%}. Evidence: {evidence_text}."
        f"{normal_context}{uncertainty} Safe next step: {prediction.recommended_action} "
        "This is not a fraud verdict and no financial action is authorized."
    )


def _apply_safe_mode(
    prediction: Phase6BPredictionResponse,
    validation: InputValidationReport,
) -> Phase6BPredictionResponse:
    if not validation.safe_mode_required:
        return prediction
    return prediction.model_copy(
        update={
            "estimated_time_to_shortage_minutes": None,
            "confidence": min(prediction.confidence, validation.confidence_cap),
            "data_health": "unreliable",
            "data_verification_required": True,
            "human_review_required": True,
            "recommended_action": (
                "Verify the latest provider balances and feed timestamps manually "
                "before operational escalation."
            ),
            "explanation_mode": "phase9_safe_fallback",
        }
    )


def analyze_phase9(
    payload: Phase6BPredictionRequest,
    *,
    actor_id: str = "system",
) -> Phase9AnalysisResponse:
    analysis_id = f"P9-{uuid4().hex[:16].upper()}"
    audit_events: list[str] = []

    validation = validate_phase9_input(payload)
    audit_events.append(
        append_audit_event(
            analysis_id=analysis_id,
            event="input_validated",
            actor_id=actor_id,
            details={
                "valid": validation.valid,
                "data_health": validation.data_health,
                "safe_mode_required": validation.safe_mode_required,
                "issue_codes": [item.code for item in validation.issues],
            },
        )
    )
    if not validation.valid:
        raise Phase9InputError(validation)

    prediction = predict_phase6b(
        payload.model_copy(update={"use_openai_explanation": False})
    )
    prediction = _apply_safe_mode(prediction, validation)
    audit_events.append(
        append_audit_event(
            analysis_id=analysis_id,
            event="frozen_model_scored",
            actor_id=actor_id,
            details={
                "model_version": prediction.model_version,
                "classification": prediction.classification,
                "affected_resource": prediction.affected_resource,
                "human_review_required": prediction.human_review_required,
            },
        )
    )

    context = assess_context(payload)
    matches = match_historical_cases(payload)
    evidence = build_evidence(payload, prediction, matches)
    confidence = calculate_operational_confidence(
        payload,
        prediction,
        validation,
        context,
        evidence,
        matches,
    )
    audit_events.append(
        append_audit_event(
            analysis_id=analysis_id,
            event="evidence_and_confidence_built",
            actor_id=actor_id,
            details={
                "evidence_codes": [item.code for item in evidence],
                "historical_match_count": len(matches),
                "operational_confidence": confidence.final_operational_confidence,
            },
        )
    )

    llm_input = validate_llm_input(
        prediction=prediction,
        confidence=confidence,
        evidence=evidence,
    )

    if llm_input.valid and not validation.safe_mode_required:
        candidate = explain_with_optional_openai(
            ExplanationInput(
                classification=prediction.classification,
                severity=prediction.severity,
                affected_resource=prediction.affected_resource,
                confidence=confidence.final_operational_confidence,
                evidence=[item.statement for item in evidence[:6]],
                recommended_action=prediction.recommended_action,
                language=payload.language,
            ),
            allow_openai=payload.use_openai_explanation,
        )
        candidate_text = candidate.text
        candidate_mode = candidate.mode
    else:
        base = deterministic_operator_explanation(
            ExplanationInput(
                classification=prediction.classification,
                severity=prediction.severity,
                affected_resource=prediction.affected_resource,
                confidence=confidence.final_operational_confidence,
                evidence=[item.statement for item in evidence[:6]],
                recommended_action=prediction.recommended_action,
                language=payload.language,
            )
        )
        candidate_text = base.text
        candidate_mode = "input_validation_fallback"

    explanation_validation = validate_llm_output(
        candidate_text,
        prediction=prediction,
        confidence=confidence,
        evidence=evidence,
    )
    if explanation_validation.valid and not validation.safe_mode_required:
        final_text = candidate_text
        final_mode = (
            "openai_validated"
            if candidate_mode == "openai"
            else "deterministic_validated"
        )
    else:
        final_text = _safe_fallback_text(
            prediction=prediction,
            confidence=confidence,
            evidence=evidence,
            context=context,
            validation=validation,
        )
        final_mode = "phase9_validated_fallback"
        explanation_validation = explanation_validation.model_copy(
            update={
                "fallback_used": True,
                "validated_mode": final_mode,
            }
        )

    audit_events.append(
        append_audit_event(
            analysis_id=analysis_id,
            event="explanation_validated",
            actor_id=actor_id,
            details={
                "candidate_mode": candidate_mode,
                "final_mode": final_mode,
                "valid": explanation_validation.valid,
                "issues": explanation_validation.issues,
                "evidence_coverage": explanation_validation.evidence_coverage,
            },
        )
    )
    audit_events.append(
        append_audit_event(
            analysis_id=analysis_id,
            event="analysis_completed",
            actor_id=actor_id,
            details={
                "safe_fallback_active": validation.safe_mode_required
                or explanation_validation.fallback_used,
                "human_review_required": prediction.human_review_required,
            },
        )
    )

    return Phase9AnalysisResponse(
        phase9_version=PHASE9_VERSION,
        analysis_id=analysis_id,
        created_at=datetime.now(timezone.utc),
        input_validation=validation,
        context=context,
        prediction=prediction,
        evidence=evidence,
        historical_matches=matches,
        confidence=confidence,
        llm_input_validation=llm_input,
        explanation=final_text,
        explanation_mode=final_mode,
        explanation_validation=explanation_validation,
        safe_fallback_active=(
            validation.safe_mode_required or explanation_validation.fallback_used
        ),
        human_review_required=True,
        audit_event_ids=audit_events,
        safety_boundary=(
            "Decision support only. The system does not merge provider balances, move "
            "funds, refill wallets, freeze or block accounts, or issue a final fraud verdict."
        ),
    )


def phase9_status() -> Phase9Status:
    from app.services.phase9_evidence import INDEX_PATH, load_evidence_index

    phase6b = phase6b_status()
    prototypes = load_evidence_index()
    return Phase9Status(
        available=phase6b.available,
        phase9_version=PHASE9_VERSION,
        phase6b=phase6b,
        evidence_index_available=INDEX_PATH.exists(),
        evidence_prototype_count=len(prototypes),
        capabilities=[
            "semantic and credential-aware input validation",
            "data-quality confidence caps and safe fallback",
            "context-aware false-positive control",
            "training-prototype similarity matching",
            "evidence-grounded operational confidence",
            "LLM input minimization and output validation",
            "human feedback capture without automatic retraining",
            "append-only local audit events",
        ],
        safety_boundary=(
            "All outputs remain advisory and require human review. No provider balance "
            "conversion, financial action, account blocking, or fraud verdict is performed."
        ),
    )
