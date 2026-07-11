# V2 Architecture

```text
React UI
   |
FastAPI API
   |-- authentication + RBAC + provider/area/outlet scopes
   |-- input contract and request context
   |
Data-quality gate
   |-- completeness
   |-- freshness
   |-- reconciliation consistency
   |
Feature layer
   |-- shared-cash features
   |-- provider-specific features
   |-- velocity and concentration features
   |
   +---------------------------+
   |                           |
Liquidity engine          Anomaly engine
   |                           |
   +------------+--------------+
                |
        Decision fusion
                |
     Evidence + uncertainty
                |
      Human-in-the-loop case
                |
        Explanation service
```

## Module boundaries

- `domain`: pure business logic with no database or framework dependency.
- `api`: HTTP schemas and routes.
- `infrastructure`: database, Redis, model artifact, and external API adapters.
- `services`: orchestration and explanation interfaces.
- `ml`: offline training, evaluation, calibration, robustness, and versioning.

This prevents the monolithic coupling found in the legacy implementation.
