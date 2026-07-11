
from enum import StrEnum

from pydantic import BaseModel, Field


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationFinding(BaseModel):
    severity: ValidationSeverity
    code: str
    message: str
    resource_id: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    findings: list[ValidationFinding]
    required_action: str
    safety_mode: str = (
        "Invalid input is rejected. Degraded data is analyzed with lower confidence. "
        "The system never moves money, freezes accounts, or declares fraud."
    )
