# Phase 6C Frozen Blind-Test Evaluation

- Evaluation time: `2026-07-11T21:22:39.950490+00:00`
- Rows: `48,000`
- Model/threshold retraining: `No`
- Threshold retuning: `No`
- Private labels opened only after frozen hashes were verified: `Yes`

## Core blind-test metrics

| Task | Precision | Recall | F1 | F2 | PR-AUC | FPR | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| anomaly | 0.932 | 0.835 | 0.880 | 0.852 | 0.934 | 0.032 | 0.076 |
| shortage_30m | 0.759 | 0.846 | 0.800 | 0.827 | 0.890 | 0.017 | 0.017 |
| shortage_60m | 0.745 | 0.685 | 0.714 | 0.696 | 0.766 | 0.025 | 0.041 |
| shortage_120m | 0.711 | 0.519 | 0.600 | 0.548 | 0.654 | 0.037 | 0.081 |
| data_quality_verification | 1.000 | 0.309 | 0.472 | 0.359 | 0.796 | 0.000 | 0.191 |

## ETA and affected service

- ETA MAE: `14.462` minutes
- ETA RMSE: `20.584` minutes
- ETA within 30 minutes: `0.841`
- Affected-service accuracy: `0.443`
- Anomaly-type accuracy on unusual rows: `0.000`

## Human review and stakeholder routing

- Human-review precision: `0.921`
- Human-review recall: `0.799`
- Primary stakeholder accuracy: `0.743`
- Secondary stakeholder accuracy: `0.853`
- Exact route accuracy: `0.740`

## Integrity and safety

- Frozen hash checks: `True`
- Key alignment: `48,000/48,000`
- Probability/ETA validation: `Passed`
- Shortage horizon monotonicity violations: `0`
- AI final decision maker: `No`
- Automatic money movement/freeze/block/fraud verdict: `Not implemented`

## Detailed files

- `phase6c_blind_test_metrics.json`
- `phase6c_context_metrics.csv`
- `phase6c_scenario_anomaly_metrics.csv`
- `phase6c_scenario_shortage60_metrics.csv`
- `phase6c_anomaly_type_metrics.csv`
- `phase6c_service_metrics.csv`
- `phase6c_primary_route_confusion.csv`

## Honest limitation

These results are measured on the supplied synthetic blind-test pack. They do not constitute production certification for real MFS operations.
