# Phase 9.1 — Final Backend Hardening

Phase 9.1 is the final backend intelligence/security phase before frontend work.

## Final pipeline

```text
Authenticated request
        ↓
Area/outlet RBAC
        ↓
Rate limit + actor-scoped idempotency
        ↓
Phase 9 validated model/evidence/LLM pipeline
        ↓
Per-provider feed-health assessment
        ↓
Deterministic provider-pressure corroboration
        ↓
Provider-specific authorization
        ↓
Structured evidence-ID explanation contract
        ↓
Cross-provider and unsafe-output validation
        ↓
Linked coordination case
        ↓
Acknowledgement → assignment → note → escalation → resolution → closure
        ↓
Tamper-evident hash-chained audit
        ↓
Judge-facing reliability report
```

## API

```text
GET  /api/v1/ml/phase91/status
POST /api/v1/ml/phase91/analyze
GET  /api/v1/ml/phase91/cases/{case_id}
POST /api/v1/ml/phase91/cases/{case_id}/transition
GET  /api/v1/ml/phase91/audit/verify
GET  /api/v1/ml/phase91/metrics
```

The analysis endpoint supports:

```text
X-Request-ID
X-Idempotency-Key
```

Idempotency keys are scoped to the authenticated actor and persisted locally for 24 hours.

## Per-provider feed contract

The request can send an optional `provider_feeds` array:

```json
[
  {
    "provider": "bkash",
    "status": "healthy",
    "feed_age_seconds": 30,
    "quality_score": 0.98,
    "missing_ratio": 0.0,
    "reported_balance": 45000,
    "reconciled_balance": 45000,
    "conflict_amount": 0
  }
]
```

Supported statuses:

```text
healthy
degraded
stale
missing
conflict
```

When the predicted provider feed is missing, severely stale, or conflicting:

- attribution becomes `insufficient_data`;
- operational confidence is capped;
- exact shortage ETA is hidden;
- human verification becomes mandatory;
- no automatic operational conclusion is issued.

## Provider attribution

The frozen model prediction is compared with deterministic pressure scores for:

```text
shared_cash
bkash
nagad
rocket
```

Possible agreement states:

```text
confirmed
close
disagreement
insufficient_data
```

Confidence increases only when independent signals agree. It decreases when signals disagree or data quality is weak.

## Structured explanation contract

The final response contains:

```text
situation
evidence_ids
uncertainty
normal_alternative
safe_next_step
human_review_required
disclaimer
narrative
language
```

Every evidence ID must exist in the generated evidence set. Cross-provider narrative references, unsupported autonomous actions, missing uncertainty, or missing human-review language trigger deterministic fallback.

## Provider boundary

After analysis identifies a provider, the API applies provider-aware authorization before returning the response or creating a case. Historical evidence is filtered to the affected/shared scope.

The system never:

- merges provider balances;
- exposes one provider as controlling another;
- moves or converts funds;
- refills wallets;
- blocks or freezes accounts;
- declares fraud;
- bypasses human review.

## Complete coordination case

Each important analysis creates one idempotent case containing:

```text
recipient
owner
acknowledgement status
recommended action
notes
escalation history
resolution status
created/updated timestamps
```

Allowed actions:

```text
acknowledge
assign
add_note
escalate
resolve
close
```

A case must be acknowledged before resolution and resolved before closure.

## Tamper-evident audit

Every Phase 9.1 event contains:

```text
event_hash
previous_hash
analysis_id
actor_id
timestamp
details
```

The verification endpoint detects:

- modified events;
- deleted/reordered links;
- broken previous hashes;
- malformed audit records.

## Reliability report

Generated files:

```text
reports/final/PHASE91_FINAL_BACKEND_REPORT.md
reports/final/PHASE91_FINAL_BACKEND_REPORT.json
```

Measured synthetic engineering evidence:

- structured output validation rate;
- degraded-feed fallback rate;
- idempotency duplicate prevention;
- audit-chain verification;
- provider-scope guard tests;
- model-only p50 latency;
- model-only p95 latency.

These are reliability measurements, not replacements for the frozen-model blind-test metrics.

## Frontend contract

The frontend should now use `/ml/phase91/analyze` and visualize:

- separate shared cash and provider balances;
- per-provider feed status;
- model/deterministic attribution agreement;
- adjusted operational confidence;
- structured evidence IDs;
- uncertainty and normal alternative;
- safe next step;
- case owner/acknowledgement/escalation/resolution;
- audit integrity;
- reliability metrics.

No further backend feature phase is planned before the frontend.
