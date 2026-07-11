import pytest

from app.domain.cases.workflow import (
    CaseAction,
    CaseStatus,
    WorkflowError,
    next_status,
)


def test_human_in_the_loop_case_path() -> None:
    status = next_status(CaseStatus.OPEN, CaseAction.ASSIGN)
    status = next_status(status, CaseAction.ACKNOWLEDGE)
    status = next_status(status, CaseAction.START_REVIEW)
    status = next_status(status, CaseAction.RESOLVE)
    assert status == CaseStatus.RESOLVED


def test_case_cannot_skip_review() -> None:
    with pytest.raises(WorkflowError):
        next_status(CaseStatus.OPEN, CaseAction.RESOLVE)
