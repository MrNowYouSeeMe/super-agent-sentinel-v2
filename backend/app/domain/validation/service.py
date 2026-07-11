
from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.validation.models import ValidationFinding, ValidationReport, ValidationSeverity

ALLOWED_PROVIDER_IDS = {"bkash", "nagad", "rocket"}
MAX_REASONABLE_5M_VALUE = 10_000_000
HIGH_VALUE_WARNING = 2_000_000


def _finding(
    severity: ValidationSeverity,
    code: str,
    message: str,
    resource_id: str | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        severity=severity,
        code=code,
        message=message,
        resource_id=resource_id,
    )


def _validate_resource_common(resource: ResourceSnapshot, findings: list[ValidationFinding]) -> None:
    if resource.safe_buffer > resource.balance * 1.5 and resource.balance > 0:
        findings.append(
            _finding(
                ValidationSeverity.WARNING,
                "safe_buffer_unusually_high",
                "Safe buffer is unusually high compared with current balance; confidence may be conservative.",
                resource.resource_id,
            )
        )
    if resource.cash_in_5m > MAX_REASONABLE_5M_VALUE or resource.cash_out_5m > MAX_REASONABLE_5M_VALUE:
        findings.append(
            _finding(
                ValidationSeverity.ERROR,
                "unreasonable_transaction_value",
                "Five-minute transaction value is outside the accepted local-demo range.",
                resource.resource_id,
            )
        )
    elif resource.cash_in_5m > HIGH_VALUE_WARNING or resource.cash_out_5m > HIGH_VALUE_WARNING:
        findings.append(
            _finding(
                ValidationSeverity.WARNING,
                "high_transaction_value",
                "Five-minute transaction value is high; verify whether this is a real demand spike.",
                resource.resource_id,
            )
        )
    if resource.feed_age_seconds > 1800:
        findings.append(
            _finding(
                ValidationSeverity.WARNING,
                "provider_feed_very_stale",
                "Feed is more than 30 minutes old; output should be treated as degraded.",
                resource.resource_id,
            )
        )
    elif resource.feed_age_seconds > 900:
        findings.append(
            _finding(
                ValidationSeverity.INFO,
                "provider_feed_stale",
                "Feed is older than 15 minutes; confidence should be reduced.",
                resource.resource_id,
            )
        )
    if resource.reconciliation_difference > max(25_000, resource.balance * 0.25):
        findings.append(
            _finding(
                ValidationSeverity.WARNING,
                "reconciliation_conflict",
                "Balance conflicts with reconciliation tolerance; verify source data before escalation.",
                resource.resource_id,
            )
        )
    if resource.completeness_ratio < 0.50:
        findings.append(
            _finding(
                ValidationSeverity.ERROR,
                "insufficient_data_completeness",
                "Too much input data is missing for a reliable decision-support result.",
                resource.resource_id,
            )
        )
    elif resource.completeness_ratio < 0.80:
        findings.append(
            _finding(
                ValidationSeverity.WARNING,
                "partial_data_completeness",
                "Input data is incomplete; confidence should be lowered.",
                resource.resource_id,
            )
        )


def validate_intelligence_request(payload: IntelligenceRequest) -> ValidationReport:
    findings: list[ValidationFinding] = []

    if payload.shared_cash.resource_id != "shared_cash":
        findings.append(
            _finding(
                ValidationSeverity.ERROR,
                "invalid_shared_cash_resource",
                "The physical-cash resource must use resource_id='shared_cash'.",
                payload.shared_cash.resource_id,
            )
        )

    seen: set[str] = set()
    for provider in payload.providers:
        resource_id = provider.resource_id.lower()
        if resource_id == "shared_cash":
            findings.append(
                _finding(
                    ValidationSeverity.ERROR,
                    "provider_cannot_be_shared_cash",
                    "Provider list cannot contain the shared physical cash resource.",
                    provider.resource_id,
                )
            )
        if resource_id not in ALLOWED_PROVIDER_IDS:
            findings.append(
                _finding(
                    ValidationSeverity.ERROR,
                    "unknown_provider_id",
                    "Provider must be one of: bkash, nagad, rocket.",
                    provider.resource_id,
                )
            )
        if resource_id in seen:
            findings.append(
                _finding(
                    ValidationSeverity.ERROR,
                    "duplicate_provider_resource",
                    "Each provider can appear only once in a request.",
                    provider.resource_id,
                )
            )
        seen.add(resource_id)

    _validate_resource_common(payload.shared_cash, findings)
    for provider in payload.providers:
        _validate_resource_common(provider, findings)

    errors = sum(1 for finding in findings if finding.severity == ValidationSeverity.ERROR)
    warnings = sum(1 for finding in findings if finding.severity == ValidationSeverity.WARNING)
    valid = errors == 0
    if not valid:
        required_action = "Reject request and fix input contract before analysis."
    elif warnings:
        required_action = "Analyze in degraded-confidence mode and require human verification for review-worthy outputs."
    else:
        required_action = "Input contract is healthy enough for normal local analysis."

    return ValidationReport(
        valid=valid,
        error_count=errors,
        warning_count=warnings,
        finding_count=len(findings),
        findings=findings,
        required_action=required_action,
    )
