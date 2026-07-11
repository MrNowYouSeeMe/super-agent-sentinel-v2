# Phase 6B Model Training Policy

Phase 6B trains and freezes the local hybrid model bundle before any blind-test ground-truth evaluation.

## Dataset usage

- Primary exact model benchmark: `data/raw/train/pressure_stress_train_5m.csv.gz`
- Blind prediction input: `data/raw/blind_test/public/pressure_stress_test_5m.csv.gz`
- Private ground truth: not opened, read, joined, or used during Phase 6B
- The full 841,984-row historical dataset remains useful for profiling and context validation, but the exact 5-minute benchmark is used for rigorous 30/60/120-minute shortage modeling.

## Models

- Anomaly/review-risk classifier
- Shortage-within-30-minute classifier
- Shortage-within-60-minute classifier
- Shortage-within-120-minute classifier
- Shortage ETA regressor
- Affected-service helper for shared cash, bKash, Nagad, or Rocket

Data-quality handling and stakeholder routing remain deterministic.

## Fast strategy

- One shared preprocessing contract
- CPU-friendly histogram gradient boosting
- Episode-level train/calibration/validation split
- Hard-negative rush windows receive extra training weight
- Deterministic operational rules are fused with calibrated ML scores
- Compact permutation importance is calculated only for anomaly and 60-minute shortage

## Leakage controls

Forbidden model inputs include:

- future balances;
- shortage labels;
- unusual/anomaly labels;
- affected-service labels;
- approved support/intervention amounts;
- reviewer decisions;
- private blind-test targets.

## Input and output validation

Input validation checks required schema, timestamps, public/train feature parity, and target absence from blind-public data.

Output validation enforces:

- every probability stays within 0–1;
- `P(shortage 30m) <= P(shortage 60m) <= P(shortage 120m)`;
- ETA remains within 0–120 minutes;
- stale/conflicting data creates a verification route;
- risk outputs require human review;
- no automatic financial action or fraud verdict.

## Stakeholder routing

Routing is deterministic after validated scoring:

- provider shortage → area manager + affected provider operations;
- shared-cash shortage → area manager + outlet operator;
- anomaly → risk reviewer;
- anomaly + shortage → area manager + risk reviewer;
- data issue → data operations;
- high severity → central operations visibility.

AI is never the final decision maker.