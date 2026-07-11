
# SuperAgent Sentinel V2

Clean local-first rebuild for the multi-provider MFS liquidity and anomaly decision-support challenge.

This project is intentionally separate from the legacy/buggy repository. Legacy code is reference-only. The business logic comes from the challenge/problem statement, while reusable ideas from reference repositories are adapted carefully into a cleaner architecture.

## What this prototype solves locally

- Shared physical-cash pool is modeled separately from provider e-money balances.
- bKash, Nagad, and Rocket provider resources are evaluated separately.
- Provider-wise shortage probability and estimated runway are shown.
- Unusual activity signals are combined with liquidity pressure.
- Stale, missing, or conflicting data lowers confidence.
- Medium/high or degraded-confidence outputs create human-review cases.
- Case workflow supports assignment, acknowledgement, review, escalation, and resolution.
- Role, provider, area, and outlet scopes are enforced server-side.
- Output language remains advisory: the system does not declare fraud or perform financial action.

## Current local stack

- Backend: FastAPI + Pydantic
- Frontend: React + Vite
- Tests: Pytest + TypeScript build
- Local data/model prep: Python scripts
- AI: local baseline artifact now; dataset training pipeline scaffold included
- OpenAI: optional explanation polish only, never scoring or final decision

## Run locally

```powershell
powershell -ExecutionPolicy Bypass -File "E:\superagent-sentinel-v2\scripts\start-all.ps1"
```

Open:

```text
Frontend:     http://127.0.0.1:5173
Backend docs: http://127.0.0.1:8000/docs
```

## Verify locally

```powershell
cd E:\superagent-sentinel-v2\backend
.\.venv\Scripts\python.exe -m pytest -q

cd E:\superagent-sentinel-v2\frontend
npm run build
```

After the backend is running:

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe scripts\local_smoke_test.py
```

## Main demo endpoints

```text
GET  /api/v1/health
GET  /api/v1/demo/scenarios
POST /api/v1/demo/scenarios/{scenario_id}
GET  /api/v1/intelligence/model
POST /api/v1/intelligence/analyze
POST /api/v1/intelligence/analyze-scoped
POST /api/v1/validation/check
GET  /api/v1/demo/validation-evidence
POST /api/v1/auth/demo-login
POST /api/v1/cases/transition
```

## Demo users

Use `/api/v1/auth/demo-users` to list local demo profiles.

Important profiles:

```text
area-manager-sylhet
bkash-ops-sylhet
nagad-ops-sylhet
risk-reviewer
admin
```

## Dataset workflow

Put uploaded datasets in:

```text
data/raw/
```

Create a mapping/feature template:

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe scripts\prepare_dataset_template.py
```

Training scaffold:

```powershell
.\backend\.venv\Scripts\python.exe scripts\train_phase2_baseline.py data\processed\your_features.csv --output artifacts\models\mfs_phase2_trained.json
```

The current ML artifact is only a local baseline. Final metrics must come from the uploaded dataset.

## Safety boundary

The system never:

- moves money;
- transfers value between providers;
- freezes accounts;
- blocks customers;
- declares fraud;
- treats one provider as controlling another provider's balance.

It provides risk evidence, confidence, explanation, and human-review workflow only.
