from enum import StrEnum


class Language(StrEnum):
    ENGLISH = "en"
    BANGLA = "bn"
    BANGLISH = "banglish"


class ProviderId(StrEnum):
    BKASH = "bkash"
    NAGAD = "nagad"
    ROCKET = "rocket"


class DataHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRELIABLE = "unreliable"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Classification(StrEnum):
    NORMAL_OPERATION = "normal_operation"
    LIQUIDITY_PRESSURE = "liquidity_pressure"
    UNUSUAL_ACTIVITY = "unusual_activity"
    LIQUIDITY_PRESSURE_WITH_UNUSUAL_ACTIVITY = (
        "liquidity_pressure_with_unusual_activity"
    )
    DATA_QUALITY_ISSUE = "data_quality_issue"
