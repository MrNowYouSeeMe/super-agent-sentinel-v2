# Problem coverage matrix

| Requirement | V2 status |
|---|---|
| Shared physical cash separated from provider balances | implemented in intelligence contract |
| Provider-specific shortage risk | implemented with provider projections |
| Approximate shortage time/range | implemented as deterministic runway baseline |
| Unusual activity with contextual evidence | implemented as transparent rule baseline |
| Missing/stale/conflicting data lowers confidence | implemented |
| Safe language; no fraud verdict | implemented |
| Human review recommendation | implemented |
| Provider/area/outlet scoped authorization | policy implemented; login persistence pending |
| Alert ownership and case lifecycle | state machine implemented; persistence/UI pending |
| Trained anomaly/liquidity models | pending dataset ingestion and benchmark |
| SHAP and calibrated model evidence | pending trained model selection |
| OpenAI multilingual explanation | interface/config prepared; adapter pending |
| PostgreSQL/Redis persistence | pending clean infrastructure checkpoint |
