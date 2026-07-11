from __future__ import annotations

from dataclasses import dataclass

from app.services.intelligence import IntelligenceResponse


@dataclass(frozen=True)
class ScopedAnalysisResult:
    analysis: IntelligenceResponse
    case_allowed: bool
    redacted: bool


def redact_analysis_for_scope(
    analysis: IntelligenceResponse,
    *,
    visible_resource_ids: list[str],
) -> ScopedAnalysisResult:
    visible = set(visible_resource_ids)
    scoped_resources = [
        resource
        for resource in analysis.resources
        if resource.resource_id in visible
    ]

    affected_visible = analysis.decision.affected_resource in visible
    if affected_visible:
        return ScopedAnalysisResult(
            analysis=analysis.model_copy(update={"resources": scoped_resources}),
            case_allowed=True,
            redacted=False,
        )

    redacted_decision = analysis.decision.model_copy(
        update={
            "affected_resource": "redacted",
            "recommended_action": (
                "Request an authorized reviewer for the hidden provider-level details."
            ),
        }
    )
    redacted_analysis = analysis.model_copy(
        update={
            "resources": scoped_resources,
            "decision": redacted_decision,
            "evidence": [
                "Provider-level evidence was redacted by server-side scope policy."
            ],
            "possible_normal_context": [],
            "explanation": (
                "The underlying decision involves a resource outside this user's "
                "authorized provider scope. No hidden provider values are returned."
            ),
        }
    )
    return ScopedAnalysisResult(
        analysis=redacted_analysis,
        case_allowed=False,
        redacted=True,
    )