
# Dataset Mapping Template

Put raw uploaded datasets under:

```text
data/raw/
```

Use this document to map your dataset columns into the V2 feature contract.

## Required identity columns

| V2 field | Meaning | Example |
|---|---|---|
| `timestamp` | event/window timestamp | `2026-07-12T10:05:00` |
| `outlet_id` | MFS outlet/agent ID | `OUT-1` |
| `area_id` | area/region | `sylhet` |
| `resource_id` | `shared_cash`, `bkash`, `nagad`, or `rocket` | `bkash` |

## Required liquidity columns

| V2 field | Meaning |
|---|---|
| `balance` | current physical cash or provider e-money balance |
| `safe_buffer` | minimum operating buffer |
| `cash_in_5m` | cash-in amount over latest 5-minute window |
| `cash_out_5m` | cash-out amount over latest 5-minute window |

## Optional anomaly/context columns

| V2 field | Meaning |
|---|---|
| `transaction_count_5m` | number of transactions in latest 5-minute window |
| `repeated_amount_ratio` | ratio of repeated/near-identical amounts |
| `unique_customer_ratio` | customer diversity ratio |
| `failure_rate` | failed transaction ratio |
| `festival_or_market_day` | contextual demand flag |

## Data-quality columns

| V2 field | Meaning |
|---|---|
| `feed_age_seconds` | age of latest provider/feed snapshot |
| `reconciliation_difference` | absolute reconciliation mismatch |
| `completeness_ratio` | input completeness score |
| `source_quality_score` | source quality score |

## Target labels for training

| Target | Meaning |
|---|---|
| `is_unusual` | unusual activity within the window |
| `shortage_within_60m` | shortage/unsafe buffer crossing within 60 minutes |
| `shortage_runway_minutes` | optional regression target for estimated runway |

## Leakage rule

Do not train with future-only columns such as:

```text
future_balance
future_cash_out
future_shortage_time
manual_final_decision
reviewer_notes
```

These can be labels or evaluation fields, but not input features.

## First training goal

Create a processed CSV:

```text
data/processed/mfs_training_features.csv
```

Then run:

```powershell
.\backend\.venv\Scripts\python.exe scripts\train_phase2_baseline.py data\processed\mfs_training_features.csv --output artifacts\models\mfs_phase2_trained.json
```
