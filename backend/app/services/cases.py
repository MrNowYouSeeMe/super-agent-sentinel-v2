from app.domain.cases.models import CaseEvent, CaseNote, CaseRecord
from app.domain.cases.workflow import CaseStatus
from app.domain.common.enums import Classification, Severity
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
            note="Review-worthy intelligence result created a human review case.",
        ),
        CaseEvent(
            sequence=2,
            status=CaseStatus.ASSIGNED,
            actor_role="system",
            event="case_assigned",
            note=f"Case assigned to {owner} based on severity and affected resource.",
        ),
    ]

    current_status = CaseStatus.ASSIGNED
    notes = [
        CaseNote(
            author_role="system",
            note="No automated fund movement, account freeze, or fraud verdict was produced.",
        )
    ]

    if analysis.decision.classification == Classification.DATA_QUALITY_ISSUE:
        current_status = CaseStatus.WAITING_FOR_DATA
        timeline.append(
            CaseEvent(
                sequence=3,
                status=CaseStatus.WAITING_FOR_DATA,
                actor_role=owner,
                event="data_verification_requested",
                note="Provider feed or reconciliation must be verified before escalation.",
            )
        )
    elif analysis.decision.severity == Severity.HIGH:
        current_status = CaseStatus.ACKNOWLEDGED
        timeline.append(
            CaseEvent(
                sequence=3,
                status=CaseStatus.ACKNOWLEDGED,
                actor_role=owner,
                event="case_acknowledged",
                note="High-priority case requires immediate human review.",
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
        notes=notes,
        audit_summary="Complete audit path: detection, assignment, acknowledgement/data request, and safe human-review boundary.",
    )

