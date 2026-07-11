
from app.domain.cases.models import CaseEvent, CaseNote, CaseRecord
from app.domain.cases.workflow import CaseAction, CaseStatus, next_status
from app.domain.common.enums import Classification
from app.services.intelligence import IntelligenceResponse


def _owner_role(classification: Classification, affected_resource: str) -> str:
    if classification == Classification.DATA_QUALITY_ISSUE:
        return "data_operations"
    if classification == Classification.UNUSUAL_ACTIVITY:
        return "risk_reviewer"
    if affected_resource == "shared_cash":
        return "area_manager"
    return "area_manager"


def build_case_from_analysis(analysis: IntelligenceResponse) -> CaseRecord | None:
    if not analysis.decision.human_review_required:
        return None

    owner = _owner_role(analysis.decision.classification, analysis.decision.affected_resource)
    case_id = f"CASE-{analysis.area_id.upper()}-{analysis.outlet_id.upper()}-{analysis.decision.affected_resource.upper()}"
    timeline = [
        CaseEvent(
            sequence=1,
            status=CaseStatus.OPEN,
            actor_role="system",
            event="case_opened",
            note="Review-worthy intelligence result created a human-in-the-loop case.",
        )
    ]
    current_status = CaseStatus.OPEN
    if analysis.decision.classification == Classification.DATA_QUALITY_ISSUE:
        current_status = CaseStatus.WAITING_FOR_DATA
        timeline.append(
            CaseEvent(
                sequence=2,
                status=CaseStatus.WAITING_FOR_DATA,
                actor_role="system",
                event="data_verification_required",
                note="Case is waiting for provider feed/reconciliation verification before escalation.",
            )
        )

    return CaseRecord(
        case_id=case_id,
        outlet_id=analysis.outlet_id,
        area_id=analysis.area_id,
        affected_resource=analysis.decision.affected_resource,
        severity=analysis.decision.severity,
        current_status=current_status,
        owner_role=owner,
        recommended_action=analysis.decision.recommended_action,
        timeline=timeline,
        notes=[
            CaseNote(
                author_role="system",
                note=analysis.explanation,
            )
        ],
        audit_summary=(
            "The case stores the original decision, evidence, current owner, "
            "and timeline so a reviewer can audit why the alert was raised."
        ),
    )


def apply_case_action(
    case: CaseRecord,
    action: CaseAction,
    *,
    actor_role: str,
    note: str,
) -> CaseRecord:
    target = next_status(case.current_status, action)
    next_sequence = max((event.sequence for event in case.timeline), default=0) + 1
    case.current_status = target
    case.timeline.append(
        CaseEvent(
            sequence=next_sequence,
            status=target,
            actor_role=actor_role,
            event=f"case_{action.value}",
            note=note,
        )
    )
    if note:
        case.notes.append(CaseNote(author_role=actor_role, note=note))
    return case
