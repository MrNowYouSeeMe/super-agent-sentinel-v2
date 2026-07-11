from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.services.phase6b_runtime import Phase6BPredictionRequest, Phase6BPredictionResponse

ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = ROOT / "artifacts" / "evidence" / "phase9_evidence_index.json"


class EvidenceItem(BaseModel):
    code: str
    category: Literal[
        "liquidity",
        "behavior",
        "data_quality",
        "context",
        "historical",
        "routing",
    ]
    statement: str
    source: Literal["deterministic_rule", "trained_model", "training_similarity"]
    strength: float = Field(ge=0, le=1)
    observed_value: str
    expected_condition: str
    supports: list[str]


class HistoricalMatch(BaseModel):
    match_id: str
    similarity: float = Field(ge=0, le=1)
    scenario_family: str
    affected_service: str
    unusual: bool
    shortage_60m: bool
    summary: str


FEATURE_SCALES = {
    "velocity_vs_baseline": 5.0,
    "repeated_amount_ratio": 1.0,
    "unique_customer_ratio": 1.0,
    "failure_rate": 0.5,
    "data_quality_score": 1.0,
    "feed_age_seconds": 1800.0,
    "shared_cash_burn_ratio": 2.0,
    "bkash_burn_ratio": 2.0,
    "nagad_burn_ratio": 2.0,
    "rocket_burn_ratio": 2.0,
}


def _safe_ratio(numerator: float, denominator: float) -> float:
    return max(0.0, numerator) / max(abs(denominator), 1.0)


def feature_vector(payload: Phase6BPredictionRequest) -> dict[str, float]:
    return {
        "velocity_vs_baseline": float(payload.velocity_vs_baseline),
        "repeated_amount_ratio": float(payload.repeated_amount_ratio),
        "unique_customer_ratio": float(payload.unique_customer_ratio),
        "failure_rate": float(payload.failure_rate),
        "data_quality_score": float(payload.data_quality_score),
        "feed_age_seconds": float(payload.feed_age_seconds),
        "shared_cash_burn_ratio": _safe_ratio(
            payload.shared_cash_burn_60m,
            payload.shared_cash_balance,
        ),
        "bkash_burn_ratio": _safe_ratio(payload.bkash_burn_60m, payload.bkash_balance),
        "nagad_burn_ratio": _safe_ratio(payload.nagad_burn_60m, payload.nagad_balance),
        "rocket_burn_ratio": _safe_ratio(payload.rocket_burn_60m, payload.rocket_balance),
    }


@lru_cache(maxsize=1)
def load_evidence_index() -> list[dict[str, object]]:
    if not INDEX_PATH.exists():
        return []
    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    rows = payload.get("prototypes", [])
    return rows if isinstance(rows, list) else []


def match_historical_cases(
    payload: Phase6BPredictionRequest,
    *,
    limit: int = 5,
) -> list[HistoricalMatch]:
    current = feature_vector(payload)
    candidates: list[tuple[float, dict[str, object]]] = []
    for prototype in load_evidence_index():
        vector = prototype.get("features", {})
        if not isinstance(vector, dict):
            continue
        distances: list[float] = []
        for name, scale in FEATURE_SCALES.items():
            left = current.get(name, 0.0)
            right = float(vector.get(name, 0.0))
            distances.append(((left - right) / scale) ** 2)
        distance = math.sqrt(sum(distances) / max(len(distances), 1))
        similarity = math.exp(-distance)
        candidates.append((similarity, prototype))

    candidates.sort(key=lambda item: item[0], reverse=True)
    matches: list[HistoricalMatch] = []
    for similarity, prototype in candidates[:limit]:
        service = str(prototype.get("affected_service", "unknown"))
        scenario = str(prototype.get("scenario_family", "unknown"))
        unusual = bool(prototype.get("is_unusual", False))
        shortage = bool(prototype.get("shortage_within_60m", False))
        matches.append(
            HistoricalMatch(
                match_id=str(prototype.get("prototype_id", "unknown")),
                similarity=round(float(similarity), 4),
                scenario_family=scenario,
                affected_service=service,
                unusual=unusual,
                shortage_60m=shortage,
                summary=(
                    f"Training prototype {scenario} / {service}: "
                    f"unusual={unusual}, shortage_60m={shortage}."
                ),
            )
        )
    return matches


def build_evidence(
    payload: Phase6BPredictionRequest,
    prediction: Phase6BPredictionResponse,
    matches: list[HistoricalMatch],
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []

    if payload.velocity_vs_baseline >= 1.5:
        evidence.append(
            EvidenceItem(
                code="VELOCITY_ABOVE_BASELINE",
                category="behavior",
                statement=(
                    f"Transaction velocity is {payload.velocity_vs_baseline:.2f}x "
                    "the expected outlet baseline."
                ),
                source="deterministic_rule",
                strength=min(1.0, 0.45 + (payload.velocity_vs_baseline - 1.5) / 5.0),
                observed_value=f"{payload.velocity_vs_baseline:.2f}x",
                expected_condition="Near 1.00x during ordinary activity.",
                supports=["anomaly"],
            )
        )

    if payload.repeated_amount_ratio >= 0.35:
        evidence.append(
            EvidenceItem(
                code="REPEATED_AMOUNT_CONCENTRATION",
                category="behavior",
                statement=(
                    f"Repeated or near-identical amounts represent "
                    f"{payload.repeated_amount_ratio:.1%} of recent activity."
                ),
                source="deterministic_rule",
                strength=min(1.0, 0.35 + payload.repeated_amount_ratio),
                observed_value=f"{payload.repeated_amount_ratio:.1%}",
                expected_condition="Below 35% unless local demand creates repetition.",
                supports=["anomaly", "human_review"],
            )
        )

    if payload.unique_customer_ratio <= 0.45:
        evidence.append(
            EvidenceItem(
                code="LOW_CUSTOMER_DIVERSITY",
                category="behavior",
                statement=(
                    f"Unique-customer ratio is low at {payload.unique_customer_ratio:.1%}."
                ),
                source="deterministic_rule",
                strength=min(1.0, 0.4 + (0.45 - payload.unique_customer_ratio)),
                observed_value=f"{payload.unique_customer_ratio:.1%}",
                expected_condition="Above 45% for broadly distributed demand.",
                supports=["anomaly", "human_review"],
            )
        )

    resource_burn = {
        "shared_cash": _safe_ratio(payload.shared_cash_burn_60m, payload.shared_cash_balance),
        "bkash": _safe_ratio(payload.bkash_burn_60m, payload.bkash_balance),
        "nagad": _safe_ratio(payload.nagad_burn_60m, payload.nagad_balance),
        "rocket": _safe_ratio(payload.rocket_burn_60m, payload.rocket_balance),
    }
    affected = prediction.affected_resource
    if affected in resource_burn:
        ratio = resource_burn[affected]
        evidence.append(
            EvidenceItem(
                code="AFFECTED_RESOURCE_RUNWAY",
                category="liquidity",
                statement=(
                    f"{affected} has the strongest estimated pressure; its positive "
                    f"60-minute burn is {ratio:.2f}x the current balance."
                ),
                source="trained_model",
                strength=min(1.0, 0.45 + ratio / 2.0),
                observed_value=f"{ratio:.2f}x balance",
                expected_condition="Burn-to-balance ratio should remain comfortably below 1.00x.",
                supports=["shortage", "affected_resource"],
            )
        )

    if prediction.probabilities.shortage_60m >= 0.5:
        evidence.append(
            EvidenceItem(
                code="SHORTAGE_60M_MODEL_SIGNAL",
                category="liquidity",
                statement=(
                    "The frozen calibrated model estimates "
                    f"{prediction.probabilities.shortage_60m:.1%} probability of "
                    "shortage within 60 minutes."
                ),
                source="trained_model",
                strength=prediction.probabilities.shortage_60m,
                observed_value=f"{prediction.probabilities.shortage_60m:.1%}",
                expected_condition="Review threshold is model- and policy-controlled.",
                supports=["shortage", "routing"],
            )
        )

    if (
        payload.data_quality_score < 0.75
        or payload.feed_age_seconds > 300
        or payload.missing_ratio > 0.05
        or payload.reconciliation_difference > 10_000
    ):
        evidence.append(
            EvidenceItem(
                code="DATA_RELIABILITY_LIMIT",
                category="data_quality",
                statement=(
                    f"Data quality is {payload.data_quality_score:.1%}, feed age is "
                    f"{payload.feed_age_seconds:.0f}s, and reconciliation difference is "
                    f"BDT {payload.reconciliation_difference:,.0f}."
                ),
                source="deterministic_rule",
                strength=min(
                    1.0,
                    max(
                        1.0 - payload.data_quality_score,
                        payload.feed_age_seconds / 1800.0,
                        payload.missing_ratio,
                    ),
                ),
                observed_value=(
                    f"quality={payload.data_quality_score:.1%}, "
                    f"age={payload.feed_age_seconds:.0f}s"
                ),
                expected_condition="Fresh, complete, reconciled provider feeds.",
                supports=["data_quality", "safe_fallback"],
            )
        )

    active_contexts = sum(
        [
            payload.festival_flag,
            payload.salary_flag,
            payload.remittance_flag,
            payload.market_day_flag,
            payload.network_recovery_flag,
        ]
    )
    if active_contexts:
        evidence.append(
            EvidenceItem(
                code="LEGITIMATE_RUSH_CONTEXT",
                category="context",
                statement=(
                    f"{active_contexts} demand context signal(s) are active, so a "
                    "legitimate rush remains a possible explanation."
                ),
                source="deterministic_rule",
                strength=min(1.0, 0.35 + 0.12 * active_contexts),
                observed_value=f"{active_contexts} active context flags",
                expected_condition="Context must reduce overconfident anomaly claims.",
                supports=["uncertainty", "false_positive_control"],
            )
        )

    strong_matches = [match for match in matches if match.similarity >= 0.60]
    if strong_matches:
        aligned = sum(
            1
            for match in strong_matches
            if (
                (match.unusual and prediction.probabilities.anomaly >= 0.5)
                or (match.shortage_60m and prediction.probabilities.shortage_60m >= 0.5)
            )
        )
        evidence.append(
            EvidenceItem(
                code="TRAINING_PATTERN_SIMILARITY",
                category="historical",
                statement=(
                    f"{len(strong_matches)} similar training prototypes were found; "
                    f"{aligned} align with the current anomaly or shortage direction."
                ),
                source="training_similarity",
                strength=sum(item.similarity for item in strong_matches)
                / len(strong_matches),
                observed_value=f"{len(strong_matches)} matches",
                expected_condition="Similarity supports review but never proves the cause.",
                supports=["confidence", "evidence_matching"],
            )
        )

    return sorted(evidence, key=lambda item: item.strength, reverse=True)[:10]
