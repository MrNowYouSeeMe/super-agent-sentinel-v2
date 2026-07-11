# Phase 9 — Governed Intelligence and Evidence Matching

Phase 9 hardens the trained-model flow before frontend redesign.

## Implemented pipeline

```text
Validated synthetic inputs
        ↓
Frozen Phase 6B model
        ↓
Context assessment
        ↓
Deterministic evidence engine
        ↓
Training-prototype similarity matching
        ↓
Operational-confidence calculation
        ↓
Minimized LLM input
        ↓
LLM or deterministic explanation
        ↓
Output/evidence validation
        ↓
Safe fallback
        ↓
Human feedback and append-only audit
```

## API

```text
GET  /api/v1/ml/phase9/status
POST /api/v1/ml/phase9/analyze
POST /api/v1/ml/phase9/feedback
```

## Security and responsible-AI behavior

- Rejects credential-, OTP-, PIN-, private-key-, and API-key-like text.
- Sends no outlet ID, area ID, episode ID, customer identity, or raw credential to the LLM.
- Validates provider mentions, percentages, evidence coverage, human-review wording, and unsafe action language.
- Falls back to deterministic text when LLM input or output is invalid.
- Hides exact ETA when feeds are severely stale, missing, or conflicting.
- Captures reviewer feedback without automatically retraining the frozen model.
- Writes runtime audit and feedback to ignored local JSONL files.
- Does not merge balances, move money, refill wallets, freeze accounts, block customers, or declare fraud.

## Confidence interpretation

`final_operational_confidence` is not a replacement for blind-test accuracy. It combines:

- calibrated Phase 6B confidence;
- model probability certainty;
- validated evidence strength;
- data quality and freshness;
- similarity to training prototypes;
- legitimate rush-context penalty;
- input-validation penalty.

## Evidence index

The compact index is generated only from:

```text
data/raw/train/pressure_stress_train_5m.csv.gz
```

It does not read private blind-test labels and does not include customer or transaction identifiers.

## Frontend contract

The Phase 10 frontend should visualize:

- `input_validation`
- `context`
- `evidence`
- `historical_matches`
- `confidence`
- `explanation_validation`
- `safe_fallback_active`
- `prediction.primary_stakeholder`
- `prediction.secondary_stakeholder`
- `audit_event_ids`
- feedback controls
