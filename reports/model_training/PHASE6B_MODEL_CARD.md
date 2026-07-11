# Phase 6B Model Card

- Model version: `phase6b-1.0.0`
- Exact 5-minute training rows: `120,000`
- Episode-separated train/calibration/validation: `84,360` / `17,424` / `18,216`
- Blind public rows predicted: `48,000`
- Private ground-truth values opened: `No`

## Validation summary

| Task | Precision | Recall | F2 | PR-AUC | FPR | Hard-negative FPR |
|---|---:|---:|---:|---:|---:|---:|
| anomaly | 0.899 | 0.753 | 0.778 | 0.881 | 0.029 | 0.094 |
| shortage_30m | 0.742 | 0.843 | 0.821 | 0.878 | 0.011 | 0.037 |
| shortage_60m | 0.743 | 0.680 | 0.692 | 0.752 | 0.015 | 0.043 |
| shortage_120m | 0.675 | 0.521 | 0.546 | 0.632 | 0.024 | 0.070 |

## Design

- CPU-friendly histogram gradient boosting for anomaly and shortage horizons.
- Episode-level split prevents adjacent-window leakage.
- Separate calibration split chooses thresholds without touching validation.
- Hard-negative rush windows receive extra training weight.
- Hybrid score combines calibrated ML with deterministic operational rules.
- Data-quality issues use deterministic verification rules.
- Stakeholder routing is deterministic and human-controlled.

## Safety

AI is not the final decision maker. The system cannot move funds, freeze/block, or issue a fraud verdict.
