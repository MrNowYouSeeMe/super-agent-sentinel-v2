from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    OUTLET_OPERATOR = "outlet_operator"
    AREA_MANAGER = "area_manager"
    CENTRAL_OPERATIONS = "central_operations"
    RISK_REVIEWER = "risk_reviewer"
    ADMIN = "admin"


class Permission(StrEnum):
    ANALYSIS_CREATE = "analysis.create"
    ALERT_READ = "alert.read"
    ALERT_ASSIGN = "alert.assign"
    CASE_REVIEW = "case.review"
    CASE_ESCALATE = "case.escalate"
    SYSTEM_ADMIN = "system.admin"


class Principal(BaseModel):
    user_id: str = Field(min_length=1)
    role: Role
    permissions: set[Permission] = Field(default_factory=set)
    provider_scopes: set[str] = Field(default_factory=set)
    area_scopes: set[str] = Field(default_factory=set)
    outlet_scopes: set[str] = Field(default_factory=set)
