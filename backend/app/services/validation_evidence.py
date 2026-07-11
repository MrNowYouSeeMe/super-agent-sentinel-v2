
from pydantic import BaseModel


class ValidationMetric(BaseModel):
    name: str
    value: str
    why_it_matters: str


class ValidationEvidenceReport(BaseModel):
    local_scope: str
    scenario_coverage: list[str]
    safety_controls: list[str]
    metrics: list[ValidationMetric]
    repository_policy: list[str]
    known_limits_before_dataset: list[str]
    next_dataset_work: list[str]


def build_validation_evidence_report() -> ValidationEvidenceReport:
    return ValidationEvidenceReport(
        local_scope=(
            "Local hackathon-grade validation evidence for SuperAgent Sentinel V2. "
            "This is not a real financial production certification."
        ),
        scenario_coverage=[
            "Normal operation: confirms low-risk monitoring path.",
            "Hidden provider shortage: detects a provider float issue even when shared cash looks healthy.",
            "Shared-cash pressure: separates physical-cash pressure from provider e-money balances.",
            "Data conflict: reduces confidence and routes the case to data verification.",
            "Scoped authorization: provider/area/outlet checks are enforced server-side.",
            "Human-in-the-loop case workflow: case transition rules prevent unsafe automatic action.",
        ],
        safety_controls=[
            "No endpoint moves money or transfers value between providers.",
            "No endpoint freezes, blocks, or accuses an outlet or customer of fraud.",
            "LLM/explanation layer is advisory only and must use supplied evidence.",
            "Provider scopes prevent one provider user from reading another provider's raw data.",
            "Data-quality warnings lower confidence instead of producing overconfident conclusions.",
        ],
        metrics=[
            ValidationMetric(
                name="Automated backend checks",
                value="15+ tests after Phase 3; Phase 4 adds validation/workflow checks.",
                why_it_matters="Prevents regressions in business logic, authorization, data quality, and case flow.",
            ),
            ValidationMetric(
                name="Frontend build",
                value="Passing local Vite/TypeScript build.",
                why_it_matters="Keeps the demo UI runnable without deployment dependency.",
            ),
            ValidationMetric(
                name="Decision coverage",
                value="Liquidity, unusual activity, data-quality issue, and normal operation scenarios covered.",
                why_it_matters="Matches the challenge's core operational decision-support sections.",
            ),
            ValidationMetric(
                name="Scope enforcement",
                value="Provider, area, and outlet scope tests are enforced at API level.",
                why_it_matters="Protects bKash/Nagad/Rocket boundaries while still supporting a combined operational view.",
            ),
        ],
        repository_policy=[
            "Legacy buggy code remains reference-only.",
            "New work is built in the clean V2 project structure.",
            "Local commits are created after successful tests/builds.",
            "GitHub push is intentionally delayed until local validation is accepted.",
        ],
        known_limits_before_dataset=[
            "The current ML artifact is a local baseline, not trained on the final uploaded dataset yet.",
            "Case persistence is in-memory/request-driven for local demo; database persistence is a later hardening step.",
            "OpenAI is not used for scoring; it will only be used for optional Bangla/Banglish explanation polish.",
        ],
        next_dataset_work=[
            "Map uploaded dataset columns to resource snapshots and engineered model features.",
            "Train anomaly and shortage models, compare against rule-only and hybrid baselines.",
            "Record precision, recall, false-positive rate, shortage lead time, and calibration evidence.",
            "Replace baseline artifact with dataset-trained artifact and rerun all scenarios.",
        ],
    )
