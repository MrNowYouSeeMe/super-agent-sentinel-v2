# Phase 6A Dataset Audit Policy

This phase audits the imported MFS datasets before any model training.

## Strict blind-test discipline

The private blind-test label values must not be used for:

- feature engineering;
- model fitting;
- model selection;
- threshold tuning;
- risk-fusion tuning;
- calibration;
- synthetic augmentation design.

Phase 6A reads only the private file header and alignment keys (`episode_id`, `window_id`, `timestamp`) to verify structural integrity. Target values remain untouched until the full model, thresholds, rules, and output policy are frozen.

## Audit coverage

- full two-year per-agent historical pickles;
- model-ready training/public-test schema parity;
- exact 5-minute stress benchmark;
- transaction-event samples;
- agent/provider/context coverage;
- class imbalance;
- duplicate and missing-data checks;
- target/future/intervention leakage controls;
- provider separation;
- unseen-agent coverage;
- stakeholder-routing policy;
- fast model-training plan;
- synthetic augmentation guardrails.

## AI safety

AI models may produce scores, evidence, affected-resource estimates, and uncertainty. Final stakeholder routing and operational authority remain deterministic and human-controlled.