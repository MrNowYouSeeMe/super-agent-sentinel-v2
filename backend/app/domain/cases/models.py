from pydantic import BaseModel, Field

from app.domain.cases.workflow import CaseStatus
from app.domain.common.enums import Severity


class CaseEvent(BaseModel):
    sequence: int = Field(ge=1)
    status: CaseStatus
    actor_role: str
    event: str
    note: str


class CaseNote(BaseModel):
    author_role: str
    note: str


class CaseRecord(BaseModel):
    case_id: str
    outlet_id: str
    area_id: str
    affected_resource: str
    severity: Severity
    current_status: CaseStatus
    owner_role: str
    recommended_action: str
    timeline: list[CaseEvent]
    notes: list[CaseNote]
    audit_summary: str

