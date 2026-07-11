# Phase 6C Frozen Blind-Test Evaluation Policy

Phase 6C evaluates the already-frozen Phase 6B prediction file against the private blind-test labels.

## Hard rules

- No model retraining.
- No feature changes.
- No threshold retuning.
- No rule-weight changes.
- No prediction regeneration.
- Frozen model, metrics, feature contract, and prediction hashes must match the Phase 6B freeze manifest before private labels are opened.

## Evaluation coverage

- anomaly precision, recall, F1, F2, PR-AUC, ROC-AUC, FPR, Brier score, and calibration;
- shortage-within-30/60/120-minute metrics;
- shortage ETA MAE/RMSE;
- affected-service accuracy;
- anomaly-type accuracy;
- festival/salary/remittance/market-day hard-negative performance;
- scenario-family and service-level performance;
- data-quality verification performance;
- human-review performance;
- primary/secondary stakeholder routing accuracy;
- key alignment, probability range, ETA range, monotonic horizon, and frozen-hash validation.

## Safety

The evaluation measures decision-support quality only. AI remains non-authoritative and cannot move funds, freeze/block accounts, or issue a fraud verdict.

## Honest limitation

The supplied blind test is synthetic. Passing it does not certify production readiness for real MFS operations.