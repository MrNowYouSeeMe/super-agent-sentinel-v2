# SuperAgent Sentinel V2

> Safe, explainable, and human-reviewed decision-support prototype for multi-provider mobile financial-service agents.

SuperAgent Sentinel V2 helps a multi-provider agent/outlet understand **shared physical cash pressure**, **provider-specific e-money balance pressure**, **unusual transaction behavior**, and **case coordination** across providers such as **bKash**, **Nagad**, and **Rocket**.

The system is built for a hackathon prototype, but the backend is designed with production-oriented safety patterns: strict provider separation, uncertainty-aware prediction, evidence-grounded explanation, safe fallback, role-based access control, audit trail, and human-review workflow.

---

## Table of Contents

- [1. Problem](#1-problem)
- [2. What This Project Does](#2-what-this-project-does)
- [3. What This Project Does Not Do](#3-what-this-project-does-not-do)
- [4. Key Features](#4-key-features)
- [5. Tech Stack](#5-tech-stack)
- [6. Architecture](#6-architecture)
- [7. Repository Structure](#7-repository-structure)
- [8. Backend Overview](#8-backend-overview)
- [9. Frontend Overview](#9-frontend-overview)
- [10. Setup Guide](#10-setup-guide)
- [11. Environment Variables](#11-environment-variables)
- [12. Running the Project](#12-running-the-project)
- [13. Testing](#13-testing)
- [14. API Overview](#14-api-overview)
- [15. Demo Scenarios](#15-demo-scenarios)
- [16. Metrics and Validation Evidence](#16-metrics-and-validation-evidence)
- [17. Security and Responsible AI](#17-security-and-responsible-ai)
- [18. Frontend Redesign Rules](#18-frontend-redesign-rules)
- [19. Known Limitations](#19-known-limitations)
- [20. Troubleshooting](#20-troubleshooting)
- [21. Git and Artifact Notes](#21-git-and-artifact-notes)

---

## 1. Problem

Many mobile financial-service agents in Bangladesh serve customers from more than one provider from the same shop.

An outlet may have:

```text
Shared physical cash reserve
bKash e-money balance
Nagad e-money balance
Rocket e-money balance
```

The challenge is that these balances are **not interchangeable**.

An outlet may look healthy if all money is added together, but still fail to serve customers because:

- one provider’s e-money balance is nearly exhausted;
- shared physical cash is running low;
- cash-out demand suddenly spikes;
- repeated or unusual transactions appear;
- provider feeds are stale, missing, or conflicting;
- nobody knows who should acknowledge, own, escalate, or resolve the issue.

SuperAgent Sentinel turns this fragmented situation into a clear operational workflow.

---

## 2. What This Project Does

The system provides a safe decision-support flow:

```text
Synthetic provider data
        ↓
Input validation
        ↓
Frozen ML model inference
        ↓
Deterministic provider-pressure corroboration
        ↓
Evidence generation
        ↓
Confidence and uncertainty assessment
        ↓
LLM-assisted explanation with validation
        ↓
Safe fallback when needed
        ↓
Role-based alert routing
        ↓
Case acknowledgement, assignment, escalation, resolution
        ↓
Tamper-evident audit trail
```

It answers questions like:

- What is the current shared physical-cash position?
- What is each provider’s separate e-money balance?
- Which provider or shared resource is under pressure?
- Approximately when may service be disrupted?
- How confident is the system?
- Is the data fresh and complete?
- Why was unusual activity flagged?
- Could this be a normal Eid/salary/remittance demand spike?
- Who should receive the alert?
- Who owns the case?
- Was the alert acknowledged, escalated, resolved, and audited?

---

## 3. What This Project Does Not Do

This is a **decision-support prototype**, not a production financial-control system.

It does **not**:

- move money;
- transfer funds;
- refill wallets;
- convert one provider balance into another;
- merge bKash/Nagad/Rocket balances;
- block users;
- freeze funds;
- accuse agents or customers;
- declare final fraud;
- access real customer accounts;
- connect to production provider APIs;
- collect PINs, OTPs, passwords, private keys, or real credentials.

All outputs are advisory and require human review.

---

## 4. Key Features

### Multi-provider liquidity view

- Shared physical cash
- Separate bKash balance
- Separate Nagad balance
- Separate Rocket balance
- Provider-specific feed health
- Shared-cash pressure and provider-level pressure

### ML-based prediction

- Anomaly probability
- 30-minute shortage risk
- 60-minute shortage risk
- 120-minute shortage risk
- Estimated time to shortage
- Affected resource classification
- Severity and stakeholder routing

### Deterministic corroboration

The frozen ML output is checked against an independent deterministic pressure engine.

Possible attribution states:

```text
confirmed
close
disagreement
insufficient_data
```

If ML and deterministic signals disagree, confidence is reduced and manual verification is required.

### Evidence engine

The system generates evidence such as:

```text
VELOCITY_ABOVE_BASELINE
REPEATED_AMOUNT_CONCENTRATION
LOW_CUSTOMER_DIVERSITY
AFFECTED_RESOURCE_RUNWAY
SHORTAGE_60M_MODEL_SIGNAL
DATA_RELIABILITY_LIMIT
LEGITIMATE_RUSH_CONTEXT
TRAINING_PATTERN_SIMILARITY
```

### OpenAI-assisted explanation

OpenAI is used only for human-readable explanation. The backend validates the output and falls back to deterministic explanation if needed.

### Safe fallback

When data is stale, missing, incomplete, or conflicting:

- confidence is reduced;
- exact ETA may be hidden;
- manual verification is required;
- unsupported conclusions are disabled;
- case workflow remains available.

### Case workflow

A high-priority alert can become a case with:

```text
recipient
owner
acknowledgement
case notes
escalation history
resolution status
audit trail
```

Supported actions:

```text
acknowledge
assign
add_note
escalate
resolve
close
```

### Tamper-evident audit

Phase 9.1 audit events are hash-chained:

```text
previous_hash
event_hash
analysis_id
actor_id
timestamp
details
```

The audit verification endpoint can detect broken or modified audit chains.

---

## 5. Tech Stack

### Backend

- Python
- FastAPI
- Pydantic
- pytest
- Local trained ML model artifacts
- OpenAI API for explanation
- Local JSON/JSONL prototype runtime storage
- Role-based authorization
- Provider-scope authorization and redaction

### Frontend

- React
- TypeScript
- Vite
- CSS
- HTTP/fetch API integration

### Development

- Windows PowerShell
- Git
- Local virtual environment
- Local frontend build with Vite

---

## 6. Architecture

```text
React / TypeScript Frontend
        ↓
FastAPI Router
        ↓
Authentication and RBAC
        ↓
Provider / Area / Outlet Authorization
        ↓
Phase 9.1 Final Backend Orchestrator
        ↓
Phase 9 Governed Intelligence Layer
        ↓
Phase 6B Frozen ML Runtime
        ↓
Evidence and Historical Similarity Engine
        ↓
Deterministic Provider-Pressure Engine
        ↓
Confidence / Data Quality / Context Assessment
        ↓
OpenAI Explanation Service
        ↓
LLM Output Validator
        ↓
Deterministic Safe Fallback
        ↓
Case Workflow
        ↓
Tamper-Evident Audit
        ↓
Metrics and Reports
```

---

## 7. Repository Structure

```text
superagent-sentinel-v2/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── router.py
│   │   ├── core/
│   │   │   └── config.py
│   │   └── services/
│   │       ├── phase6b_runtime.py
│   │       ├── openai_explanation.py
│   │       ├── validation_evidence.py
│   │       ├── phase9_audit.py
│   │       ├── phase9_feedback.py
│   │       ├── phase9_evidence.py
│   │       ├── phase9_governance.py
│   │       ├── phase91_models.py
│   │       ├── phase91_audit.py
│   │       ├── phase91_security.py
│   │       ├── phase91_structured.py
│   │       ├── phase91_case_workflow.py
│   │       ├── phase91_guard.py
│   │       ├── phase91_service.py
│   │       └── phase91_metrics.py
│   └── tests/
│       ├── test_root_env_loading.py
│       ├── test_phase9_governance.py
│       └── test_phase91_final_hardening.py
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── scripts/
│   ├── build_phase9_evidence_index.py
│   ├── patch_phase9_router.py
│   ├── phase9_governance_smoke.py
│   ├── patch_phase91_router.py
│   ├── phase91_final_metrics.py
│   └── phase91_final_smoke.py
├── docs/
│   ├── PHASE9_GOVERNED_INTELLIGENCE.md
│   └── PHASE91_FINAL_BACKEND_HARDENING.md
├── reports/
│   └── final/
├── artifacts/
│   ├── evidence/
│   └── models/
├── data/
├── runtime/
├── .gitignore
└── README.md
```

---

## 8. Backend Overview

### `backend/app/main.py`

FastAPI application entry point.

Responsible for:

- creating the FastAPI app;
- registering API routes;
- exposing the app for tests and local server runs.

### `backend/app/api/v1/router.py`

Main API contract layer.

Responsible for:

- defining endpoints;
- applying authentication;
- applying authorization;
- mapping service errors to HTTP status codes;
- returning typed responses.

### `backend/app/core/config.py`

Configuration layer.

Responsible for:

- loading root `.env`;
- exposing OpenAI settings;
- exposing model/runtime configuration;
- keeping secrets out of frontend and logs.

### `backend/app/services/phase6b_runtime.py`

Frozen ML runtime.

Responsible for:

- loading trained model bundle;
- running anomaly and shortage prediction;
- estimating shortage ETA;
- identifying affected resource;
- producing base prediction output.

### `backend/app/services/openai_explanation.py`

OpenAI explanation wrapper.

Responsible for:

- generating operator-friendly explanations;
- handling empty/invalid OpenAI output;
- falling back to deterministic explanation.

### `backend/app/services/phase9_evidence.py`

Evidence and historical-pattern engine.

Responsible for:

- generating evidence items;
- matching compact training prototypes;
- supporting confidence and explanation.

### `backend/app/services/phase9_governance.py`

Governed intelligence layer.

Responsible for:

- combining prediction, evidence, context, confidence, and explanation;
- validating LLM output;
- applying safe fallback;
- preserving uncertainty.

### `backend/app/services/phase91_security.py`

Final provider-aware security and corroboration layer.

Responsible for:

- per-provider feed-health assessment;
- deterministic pressure scoring;
- model-vs-rule attribution comparison;
- provider-scope filtering and leakage prevention.

### `backend/app/services/phase91_service.py`

Final Phase 9.1 orchestration layer.

Responsible for:

- rate limit;
- idempotency;
- Phase 9 analysis call;
- provider-feed assessment;
- deterministic corroboration;
- confidence adjustment;
- structured explanation;
- audit event;
- response redaction.

### `backend/app/services/phase91_case_workflow.py`

Case workflow engine.

Responsible for:

- creating cases;
- preventing duplicate cases;
- managing acknowledgement, assignment, notes, escalation, resolution, and closure;
- writing audit events.

### `backend/app/services/phase91_audit.py`

Tamper-evident audit chain.

Responsible for:

- writing hash-chained audit events;
- verifying audit integrity.

### `backend/app/services/phase91_guard.py`

Request safety guard.

Responsible for:

- actor-scoped idempotency;
- duplicate prevention;
- rate limiting.

### `backend/app/services/phase91_metrics.py`

Metrics loader.

Responsible for:

- loading final reliability metrics report;
- exposing metrics through API.

---

## 9. Frontend Overview

The current frontend uses:

```text
React
TypeScript
Vite
CSS
```

Current production build command:

```powershell
cd E:\superagent-sentinel-v2\frontend
npm run build
```

The frontend should consume the Phase 9.1 APIs through an adapter layer.

Recommended frontend flow:

```text
Backend API response
        ↓
TypeScript type
        ↓
Adapter / mapper
        ↓
View model
        ↓
UI component
```

Do not change backend logic just because a new frontend design expects a different shape.

---

## 10. Setup Guide

These commands assume Windows PowerShell and project path:

```text
E:\superagent-sentinel-v2
```

### 10.1 Clone

```powershell
cd E:\
git clone https://github.com/<your-username>/<your-repo>.git superagent-sentinel-v2
cd E:\superagent-sentinel-v2
```

If the repository already exists:

```powershell
cd E:\superagent-sentinel-v2
git pull origin main
```

### 10.2 Backend virtual environment

```powershell
cd E:\superagent-sentinel-v2

py -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
```

Install backend dependencies using the project dependency file if available:

```powershell
pip install -r backend\requirements.txt
```

If the project uses a root requirements file instead:

```powershell
pip install -r requirements.txt
```

### 10.3 Frontend dependencies

```powershell
cd E:\superagent-sentinel-v2\frontend
npm install
```

---

## 11. Environment Variables

Create a local `.env` file in the project root:

```powershell
cd E:\superagent-sentinel-v2
New-Item -ItemType File -Path .env -Force
```

Example `.env`:

```env
OPENAI_ENABLED=false
OPENAI_MODEL=gpt-5-mini
OPENAI_API_KEY=
```

For live OpenAI explanation testing:

```env
OPENAI_ENABLED=true
OPENAI_MODEL=gpt-5-mini
OPENAI_API_KEY=your_key_here
```

Important:

- never commit `.env`;
- never expose OpenAI key in frontend;
- never paste secrets into README or logs.

---

## 12. Running the Project

### 12.1 Run backend

```powershell
cd E:\superagent-sentinel-v2

.\backend\.venv\Scripts\Activate.ps1

uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

If imports require running from the backend folder:

```powershell
cd E:\superagent-sentinel-v2\backend
.\.venv\Scripts\Activate.ps1

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend API base:

```text
http://127.0.0.1:8000/api/v1
```

### 12.2 Run frontend

```powershell
cd E:\superagent-sentinel-v2\frontend
npm run dev
```

Frontend usually runs at:

```text
http://127.0.0.1:5173
```

### 12.3 Build frontend

```powershell
cd E:\superagent-sentinel-v2\frontend
npm run build
```

---

## 13. Testing

### 13.1 Full backend tests

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe -m pytest -q
```

Expected recent result:

```text
51 passed
```

A non-blocking Starlette/httpx deprecation warning may appear.

### 13.2 Phase 9.1 final smoke

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe scripts\phase91_final_smoke.py
```

Expected:

```text
PHASE 9.1 FINAL HARDENING SMOKE PASSED
```

### 13.3 Phase 9.1 metrics

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe scripts\phase91_final_metrics.py
```

Expected:

```text
PHASE 9.1 FINAL METRICS PASSED
```

### 13.4 Frontend production build

```powershell
cd E:\superagent-sentinel-v2\frontend
npm run build
```

Expected:

```text
✓ built
```

---

## 14. API Overview

### Authentication

Demo login endpoint may be available:

```text
POST /api/v1/auth/demo-login
```

Use the returned token as:

```text
Authorization: Bearer <token>
```

### Phase 6B model runtime

```text
GET  /api/v1/ml/phase6b/status
POST /api/v1/ml/phase6b/predict
```

### Phase 9 governed intelligence

```text
GET  /api/v1/ml/phase9/status
POST /api/v1/ml/phase9/analyze
POST /api/v1/ml/phase9/feedback
```

### Phase 9.1 final backend

```text
GET  /api/v1/ml/phase91/status
POST /api/v1/ml/phase91/analyze
GET  /api/v1/ml/phase91/cases/{case_id}
POST /api/v1/ml/phase91/cases/{case_id}/transition
GET  /api/v1/ml/phase91/audit/verify
GET  /api/v1/ml/phase91/metrics
```

### Important headers for analysis

```text
X-Request-ID: <uuid>
X-Idempotency-Key: <stable request key>
```

Idempotency behavior:

```text
Same actor + same key + same request
→ replay previous response

Same actor + same key + different request
→ 409 conflict

Different actor + same key
→ allowed
```

---

## 15. Demo Scenarios

### Scenario A — Hidden provider shortage

Show:

- outlet looks healthy at first;
- one provider balance is near shortage;
- shortage ETA;
- confidence;
- evidence;
- safe next step.

### Scenario B — Liquidity pressure with unusual activity

Show:

- shared cash falling quickly;
- repeated or near-identical amounts;
- unusual velocity;
- possible Eid explanation;
- human review required.

### Scenario C — Stale or conflicting provider feed

Show:

- provider feed status;
- confidence reduction;
- exact ETA hidden;
- manual verification required;
- safe fallback message.

### Scenario D — Coordinated response and closure

Show:

```text
Alert
→ Acknowledge
→ Assign owner
→ Add note
→ Escalate
→ Resolve
→ Close
→ Audit verification
```

---

## 16. Metrics and Validation Evidence

### Frozen model blind-test metrics

Anomaly detection:

```text
Precision: 93.2%
Recall:    83.5%
F2:        85.2%
FPR:        3.2%
```

30-minute shortage:

```text
Precision: 75.9%
Recall:    84.6%
F2:        82.7%
FPR:        1.7%
```

60-minute shortage:

```text
Precision: 74.5%
Recall:    68.5%
F2:        69.6%
FPR:        2.5%
```

120-minute shortage:

```text
Precision: 71.1%
Recall:    51.9%
F2:        54.8%
FPR:        3.7%
```

Other:

```text
ETA MAE:                      14.462 minutes
Affected-service accuracy:   44.3%
Route accuracy:              around 74%
```

### Phase 9.1 reliability metrics

```text
Structured output validation:      100%
Degraded-feed fallback:             75%
Idempotency duplicate prevention:  100%
Audit-chain verification:          100%
Provider-scope guard tests:         100%
Model-only p50 latency:          43.834 ms
Model-only p95 latency:          93.587 ms
```

Important:

- operational confidence is not model accuracy;
- degraded-feed fallback is intentionally documented as 75%;
- synthetic metrics are for engineering evidence, not production certification.

---

## 17. Security and Responsible AI

### Provider boundary

The backend preserves provider separation through:

- provider-specific balance fields;
- provider-aware authorization;
- provider-feed health checks;
- provider-scoped historical evidence filtering;
- provider leakage validation;
- response redaction;
- case access authorization.

### Human review

Every important risk result remains advisory.

The system uses careful language:

```text
unusual
requires review
possible risk
confidence is limited
manual verification required
```

It avoids:

```text
fraud confirmed
guilty
malicious
freeze account
block user
transfer funds
```

### Secrets

Never commit:

```text
.env
OpenAI API key
PIN
OTP
password
private key
real provider credentials
```

---

## 18. Frontend Redesign Rules

If a new frontend design/template is used:

### Correct direction

```text
Existing backend API
        ↓
Frontend API client
        ↓
TypeScript types
        ↓
Adapter / mapper
        ↓
New UI components
```

### Wrong direction

```text
New UI template expects another shape
        ↓
Backend model changed
        ↓
ML/security/case logic becomes unstable
```

### Do not change backend logic for UI design

Do not change:

- model thresholds;
- provider-boundary logic;
- confidence calculation;
- safe fallback;
- idempotency;
- audit logic;
- case state machine;
- LLM validation.

### Allowed frontend changes

You may change:

- colors;
- layout;
- typography;
- cards;
- buttons;
- charts;
- icons;
- sidebar;
- responsive layout;
- modals;
- loading states;
- empty states.

---

## 19. Known Limitations

This prototype has honest limitations:

- data is synthetic;
- no real provider API is used;
- no real financial action is performed;
- local JSON/JSONL runtime storage is not production DB;
- affected-service model accuracy is limited;
- 120-minute shortage recall is weaker than short-term shortage detection;
- degraded-feed fallback strict metric is 75%;
- OpenAI explanation requires network/API availability when enabled;
- final fraud/compliance decisions are outside the prototype.

---

## 20. Troubleshooting

### Backend import error

Try running from project root:

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe -m pytest -q
```

Or from backend folder:

```powershell
cd E:\superagent-sentinel-v2\backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

### Missing `.env`

Create root `.env`:

```powershell
cd E:\superagent-sentinel-v2
New-Item -ItemType File -Path .env -Force
```

### OpenAI not working

Check:

```text
OPENAI_ENABLED=true
OPENAI_API_KEY is set
OPENAI_MODEL is available
network access works
```

The backend still works with deterministic fallback if OpenAI fails.

### Model artifact missing

The frozen model artifact is expected at:

```text
artifacts/models/phase6b/phase6b_model_bundle.joblib
```

If this file is not committed, restore it from the local artifact bundle or rerun the training/artifact-generation workflow used for the project.

### Evidence index missing

Build it with:

```powershell
cd E:\superagent-sentinel-v2
.\backend\.venv\Scripts\python.exe scripts\build_phase9_evidence_index.py
```

Expected output:

```text
artifacts/evidence/phase9_evidence_index.json
```

### Frontend build fails

Run:

```powershell
cd E:\superagent-sentinel-v2\frontend
npm install
npm run build
```

---

## 21. Git and Artifact Notes

Before pushing:

```powershell
cd E:\superagent-sentinel-v2
git status
git status --ignored
```

Should not be committed:

```text
.env
backend/.venv/
frontend/node_modules/
frontend/dist/
runtime/
data/private/
data/raw/blind_test/
OpenAI keys
```

Model and large data artifacts may be intentionally ignored depending on repository policy.

If artifacts are ignored, document how reviewers should restore/generate them.

Push local commits:

```powershell
git push origin main
```

Verify:

```powershell
git status
```

Expected:

```text
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

---

## Final Status

```text
Backend: complete and frozen after Phase 9.1
Frontend: React + TypeScript + Vite
Next major work: polished role-based frontend and final presentation
```

The project is designed to prove:

```text
multi-provider liquidity insight
+ unusual-activity evidence
+ uncertainty
+ provider separation
+ safe human review
+ complete coordination workflow
+ measurable reliability
```
