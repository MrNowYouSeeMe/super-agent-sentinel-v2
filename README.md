# SuperAgent Sentinel V2

A clean rebuild of the multi-provider MFS liquidity and unusual-activity decision-support platform.

## Non-negotiable design rules

- The uploaded legacy project is **reference-only**. New implementation must not be added to that codebase.
- Business rules come from the challenge/problem statement.
- External repositories are used only after code, license, security, and relevance review.
- The system never moves money, freezes accounts, or declares fraud.
- Medium/high-risk or unreliable-data cases require human review.
- Shared physical cash and provider-specific e-money balances are modeled separately.

## Current V2 milestone

This repository starts with a working, dependency-light intelligence core:

- provider-specific and shared-cash runway estimation;
- shortage probability and time range;
- anomaly rules for repeated amounts, customer concentration, cash-out pressure, and failures;
- stale/conflicting-data confidence reduction;
- safe decision fusion and human-review recommendation;
- provider/area/outlet scoped authorization policy;
- case workflow state machine;
- FastAPI endpoint and a small React demo;
- unit tests for the challenge-critical behavior.

Persistence, full login/refresh-token flows, Redis jobs, trained models, SHAP, and dataset training are intentionally added in later verified checkpoints.

## Project layout

```text
backend/                 FastAPI and domain logic
frontend/                React/Vite local demo
ml/                      training/evaluation modules (dataset added later)
data/                    local datasets; raw data is git-ignored
docs/                    architecture, coverage and source policy
scripts/                 Windows local-run helpers
legacy-reference/        manifest only; no legacy source imported
```

## Run locally on Windows

### Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

API docs: `http://127.0.0.1:8000/docs`

### Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend: `http://127.0.0.1:5173`

## GitHub repository name

Recommended remote name: `superagent-sentinel-v2`

After extracting into `E:\superagent-sentinel-v2`:

```powershell
cd E:\superagent-sentinel-v2
gh repo create superagent-sentinel-v2 --private --source . --remote origin --push
```

Use `--public` instead of `--private` only when you are ready to publish.
