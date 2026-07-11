# MFS Dataset Audit Report

Generated: 2026-07-11T20:18:23.433702+00:00

## Blind-test policy

Private test label values were not inspected. Only header and key alignment were checked.

## Core inventory

- Full historical agent files: **64**
- Full historical rows: **841,984**
- Train agents: **64**
- Blind-test agents: **64**
- Blind-test unseen agents: **16 (25.0%)**
- Exact 5-minute stress train rows: **120,000**
- Exact 5-minute stress public-test rows: **48,000**

## Main label balance

- Full-history unusual positive rate: **0.6520%**
- Full-history shortage-within-60m rate: **0.0005%**
- Stress-train unusual positive rate: **25.6392%**
- Stress-train shortage-within-60m rate: **5.7917%**

The full historical anomaly target is extremely imbalanced, so accuracy is not an acceptable primary metric.

## Leakage controls

- Public model-ready test is a feature subset of train: **True**
- Future/target columns removed from public test: **True**
- Intervention columns excluded by policy: **approved_bkash_support_amount, approved_cash_support_amount, approved_nagad_support_amount, approved_rocket_support_amount**

## Important gaps and decisions

- **Extreme anomaly class imbalance in full historical windows** (high): Use class/sample weighting, episode-aware sampling, hard-negative batches, PR-AUC, and threshold tuning. Do not use accuracy as the main metric.
- **Human stakeholder routing is not a model target** (intentional): Keep routing deterministic from classification, affected service, severity, confidence, area, and authorization scope. AI must not choose final authority.
- **No confirmed-fraud target** (intentional): Use is_unusual as review-required, never as fraud confirmation. Preserve human review and safe language.
- **Provider-specific shortage booleans are not explicit for every provider** (medium): Derive provider-specific 30/60/120-minute targets from future provider balances and provider critical thresholds, while keeping affected_service as a separate evaluation label.
- **Approved support amounts are post-decision/intervention fields** (high): Exclude approved_*_support_amount from predictive features to avoid policy/intervention leakage; retain only for workflow/audit analysis.
- **Synthetic-to-real generalization is unproven** (high): State this limitation, evaluate unseen agents and distribution shifts, calibrate confidence, and never claim production fraud detection.

## Final modeling direction

- Separate fast models for anomaly, 30/60/120-minute shortage, and runway regression.
- Data-quality handling stays deterministic and reduces confidence.
- Provider-specific predictions are fused with transparent rules.
- Stakeholder routing remains deterministic and authorization-scoped.
- AI never declares fraud or performs financial action.

## Generated files

- `audit_summary.json`
- `agent_file_summary.csv`
- `full_history_missingness.csv`
- `model_training_plan.json`
- `training_feature_contract.json`
