from __future__ import annotations

from app.services.phase9_governance import Phase9AnalysisResponse
from app.services.phase91_models import (
    ProviderAttribution,
    ProviderFeedAssessment,
    StructuredExplanation,
    StructuredValidation,
)
from app.services.phase91_security import contains_cross_provider_reference

UNSAFE_TERMS = (
    "fraud is confirmed",
    "freeze the account",
    "block the account",
    "transfer funds",
    "move funds",
    "send money",
)


def build_structured_explanation(
    *,
    analysis: Phase9AnalysisResponse,
    attribution: ProviderAttribution,
    feeds: list[ProviderFeedAssessment],
    language: str,
) -> StructuredExplanation:
    evidence_ids = [item.code for item in analysis.evidence[:6]]
    affected_feed = next(
        (item for item in feeds if item.provider == analysis.prediction.affected_resource),
        None,
    )

    uncertainty_parts: list[str] = []
    if analysis.context.normal_alternative_explanations:
        uncertainty_parts.append("Legitimate local demand may explain part of the pattern.")
    if attribution.requires_verification:
        uncertainty_parts.append("Provider attribution requires manual verification.")
    if affected_feed and affected_feed.status != "healthy":
        uncertainty_parts.append(
            f"{affected_feed.provider} feed status is {affected_feed.status}; exact timing is limited."
        )
    if not uncertainty_parts:
        uncertainty_parts.append("Model output remains advisory and may contain false positives.")

    normal_alternative = (
        analysis.context.normal_alternative_explanations[0]
        if analysis.context.normal_alternative_explanations
        else None
    )
    return StructuredExplanation(
        situation=(
            f"{analysis.prediction.classification} affects "
            f"{analysis.prediction.affected_resource} at "
            f"{analysis.prediction.severity} severity."
        ),
        evidence_ids=evidence_ids,
        uncertainty=" ".join(uncertainty_parts),
        normal_alternative=normal_alternative,
        safe_next_step=analysis.prediction.recommended_action,
        human_review_required=True,
        disclaimer=(
            "Decision support only. This is not a fraud verdict and does not authorize "
            "blocking, freezing, balance conversion, wallet refill, or fund movement."
        ),
        narrative=analysis.explanation,
        language=language,
    )


def validate_structured_explanation(
    *,
    explanation: StructuredExplanation,
    analysis: Phase9AnalysisResponse,
    attribution: ProviderAttribution,
) -> StructuredValidation:
    issues: list[str] = []
    available_ids = {item.code for item in analysis.evidence}
    supplied_ids = set(explanation.evidence_ids)
    missing = supplied_ids - available_ids
    if missing:
        issues.append("Unknown evidence IDs: " + ", ".join(sorted(missing)))
    if not supplied_ids:
        issues.append("No evidence IDs were supplied.")
    if not explanation.uncertainty.strip():
        issues.append("Uncertainty statement is required.")
    if explanation.human_review_required is not True:
        issues.append("Human review must remain mandatory.")
    lowered = " ".join(
        [
            explanation.situation,
            explanation.safe_next_step,
            explanation.narrative,
            explanation.disclaimer,
        ]
    ).lower()
    if any(term in lowered for term in UNSAFE_TERMS):
        issues.append("Unsafe verdict or autonomous financial action detected.")

    allowed_provider = (
        analysis.prediction.affected_resource
        if analysis.prediction.affected_resource in {"bkash", "nagad", "rocket"}
        else None
    )
    if contains_cross_provider_reference(explanation.narrative, allowed_provider):
        issues.append("Narrative references a provider outside the authorized evidence scope.")

    coverage = len(supplied_ids & available_ids) / max(len(available_ids), 1)
    if coverage < 0.50:
        issues.append("Structured explanation covers less than half of available evidence.")

    if attribution.requires_verification and "verify" not in explanation.uncertainty.lower():
        issues.append("Attribution uncertainty does not require verification.")

    return StructuredValidation(
        valid=not issues,
        evidence_coverage=round(coverage, 4),
        issues=issues,
        fallback_used=bool(issues),
    )


def deterministic_structured_fallback(
    *,
    analysis: Phase9AnalysisResponse,
    attribution: ProviderAttribution,
    language: str,
) -> StructuredExplanation:
    evidence_ids = [item.code for item in analysis.evidence[:4]]
    evidence_text = "; ".join(item.statement for item in analysis.evidence[:3])
    return StructuredExplanation(
        situation=(
            f"{analysis.prediction.affected_resource} requires review for "
            f"{analysis.prediction.classification}."
        ),
        evidence_ids=evidence_ids,
        uncertainty=(
            "Provider attribution or explanation validation was uncertain. "
            "Verify the latest provider feed and case evidence before action."
        ),
        normal_alternative=(
            analysis.context.normal_alternative_explanations[0]
            if analysis.context.normal_alternative_explanations
            else "A legitimate demand spike may explain part of the activity."
        ),
        safe_next_step=analysis.prediction.recommended_action,
        human_review_required=True,
        disclaimer=(
            "Decision support only. No fraud verdict or financial action is authorized."
        ),
        narrative=(
            f"Evidence: {evidence_text}. Operational confidence is "
            f"{analysis.confidence.final_operational_confidence:.0%}. "
            "Human verification is required."
        ),
        language=language,
    )
