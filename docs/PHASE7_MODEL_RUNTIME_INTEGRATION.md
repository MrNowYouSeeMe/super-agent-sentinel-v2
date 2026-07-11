# Phase 7 Trained Model Runtime Integration

Phase 7 connects the frozen Phase 6B model bundle to the FastAPI backend and local React UI.

## New endpoints

```text
GET  /api/v1/ml/phase6b/status
POST /api/v1/ml/phase6b/predict
```

The prediction endpoint requires a valid local bearer token with `analysis.create` permission and matching area/outlet scope.

## Runtime flow

```text
Pydantic input validation
→ Phase 6B feature engineering
→ frozen preprocessing contract
→ calibrated anomaly + shortage models
→ deterministic rule fusion
→ output validation
→ stakeholder routing
→ optional OpenAI explanation polish
→ human review
```

## Stakeholder routing

- Provider liquidity pressure → area manager + affected provider operations
- Shared-cash pressure → area manager + outlet operator
- Unusual activity → risk reviewer
- Combined anomaly and shortage → area manager + risk reviewer
- Data-quality issue → data operations
- High severity → central operations visibility

## OpenAI boundary

OpenAI is optional and only rewrites already-validated evidence into clearer Bangla/Banglish/English. It does not calculate scores, choose the classification, change routing, move money, freeze/block, or declare fraud.

Use:

```powershell
powershell -ExecutionPolicy Bypass -File "E:\superagent-sentinel-v2\scripts\configure-openai.ps1"
```

Then restart the local app.