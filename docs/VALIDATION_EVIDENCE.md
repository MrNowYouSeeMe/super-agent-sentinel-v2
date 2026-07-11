
# Local Validation Evidence

This document tracks local validation expectations for the V2 prototype.

## Covered scenarios

- Normal operation
- Hidden provider shortage
- Shared-cash pressure
- Data conflict / stale feed
- Scoped authorization
- Human-in-the-loop case transitions

## Current verification commands

```powershell
cd E:\superagent-sentinel-v2\backend
.\.venv\Scripts\python.exe -m pytest -q

cd E:\superagent-sentinel-v2\frontend
npm run build
```

## Metrics to replace after dataset training

- Anomaly precision/recall/FPR
- Shortage precision/recall/FPR
- Shortage lead-time
- Rule-only vs ML-only vs hybrid comparison
- Calibration/uncertainty evidence
- API p95 latency
