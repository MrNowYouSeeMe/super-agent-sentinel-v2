
# Final Local Demo Flow

Use this flow for the hackathon demo.

## 1. Start the app

```powershell
powershell -ExecutionPolicy Bypass -File "E:\superagent-sentinel-v2\scripts\start-all.ps1"
```

Open:

```text
Frontend: http://127.0.0.1:5173
Docs:     http://127.0.0.1:8000/docs
```

## 2. Show the problem

Explain that one outlet has:

- one shared physical-cash pool;
- separate bKash/Nagad/Rocket e-money balances;
- changing demand;
- delayed/conflicting provider feeds;
- human operators who need safe review support.

## 3. Run hidden provider shortage

Scenario: `hidden_provider_shortage`

Expected message:

- total/shared cash may look okay;
- one provider float is under pressure;
- provider-specific ETA/runway is shown;
- human review is required;
- no fraud verdict is made.

## 4. Run data conflict

Scenario: `data_conflict`

Expected message:

- feed/reconciliation problem is detected;
- confidence is reduced;
- recommended action is verification, not escalation.

## 5. Show scoped auth

Use `/api/v1/auth/demo-login` for:

- `area-manager-sylhet`
- `bkash-ops-sylhet`
- `nagad-ops-sylhet`

Then show `/api/v1/intelligence/analyze-scoped`.

Expected:

- area manager sees combined resources in assigned area;
- provider user only sees scoped provider evidence;
- competitor raw data is not exposed.

## 6. Show human-in-the-loop case transition

Use `/api/v1/cases/transition`:

```text
OPEN -> ASSIGNED -> ACKNOWLEDGED -> UNDER_REVIEW -> RESOLVED
```

Explain that the system recommends and records review actions, but never takes financial action.

## 7. Show validation evidence

Open:

```text
GET /api/v1/demo/validation-evidence
```

Show:

- scenario coverage;
- safety controls;
- current local verification;
- dataset-training limitations.

## 8. Finish with roadmap

Dataset training will replace the baseline artifact and add:

- anomaly precision/recall/FPR;
- shortage precision/recall/FPR;
- shortage lead time;
- rule-only vs ML-only vs hybrid comparison;
- calibration and uncertainty checks.
