# Final Demo Checklist

## Start

```powershell
powershell -ExecutionPolicy Bypass -File "E:\superagent-sentinel-v2\scripts\start-all.ps1"
```

Open:

```text
Frontend: http://127.0.0.1:5173
Backend docs: http://127.0.0.1:8000/docs
```

## Recommended demonstration order

1. Show that shared physical cash is separate from bKash, Nagad, and Rocket balances.
2. Run the trained-model demo.
3. Explain anomaly and 30/60/120-minute shortage probabilities.
4. Show affected resource, ETA, evidence, confidence, and stakeholder routing.
5. Emphasize that rush context and degraded data reduce unsafe over-claiming.
6. Show human review and case workflow.
7. Explain that OpenAI only rewrites an already-computed explanation.
8. State the safety boundary: no transfer, freeze, blocking, or final fraud verdict.

## Evidence to mention

- Phase 6B frozen-model training report
- Phase 6C blind-test evaluation report
- Phase 8 final readiness report
- Backend tests and frontend production build

## OpenAI behavior

`openai` mode means explanation polish was returned by the API.

`deterministic_fallback` is an intentional safe path when the API is disabled,
unavailable, rate-limited, or returns invalid content. The core model and routing
remain fully operational.