from enum import StrEnum


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_REVIEW = "UNDER_REVIEW"
    WAITING_FOR_DATA = "WAITING_FOR_DATA"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"


class CaseAction(StrEnum):
    ASSIGN = "assign"
    ACKNOWLEDGE = "acknowledge"
    START_REVIEW = "start_review"
    REQUEST_DATA = "request_data"
    RESUME_REVIEW = "resume_review"
    ESCALATE = "escalate"
    RESOLVE = "resolve"


class WorkflowError(ValueError):
    pass


TRANSITIONS: dict[tuple[CaseStatus, CaseAction], CaseStatus] = {
    (CaseStatus.OPEN, CaseAction.ASSIGN): CaseStatus.ASSIGNED,
    (CaseStatus.ASSIGNED, CaseAction.ACKNOWLEDGE): CaseStatus.ACKNOWLEDGED,
    (CaseStatus.ACKNOWLEDGED, CaseAction.START_REVIEW): CaseStatus.UNDER_REVIEW,
    (CaseStatus.UNDER_REVIEW, CaseAction.REQUEST_DATA): CaseStatus.WAITING_FOR_DATA,
    (CaseStatus.WAITING_FOR_DATA, CaseAction.RESUME_REVIEW): CaseStatus.UNDER_REVIEW,
    (CaseStatus.ACKNOWLEDGED, CaseAction.ESCALATE): CaseStatus.ESCALATED,
    (CaseStatus.UNDER_REVIEW, CaseAction.ESCALATE): CaseStatus.ESCALATED,
    (CaseStatus.UNDER_REVIEW, CaseAction.RESOLVE): CaseStatus.RESOLVED,
    (CaseStatus.ESCALATED, CaseAction.RESOLVE): CaseStatus.RESOLVED,
}


def next_status(current: CaseStatus, action: CaseAction) -> CaseStatus:
    target = TRANSITIONS.get((current, action))
    if target is None:
        raise WorkflowError(f"{action.value} is not allowed from {current.value}")
    return target
