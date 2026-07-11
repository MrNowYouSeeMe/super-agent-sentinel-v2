# Reference repositories

These repositories are references, not blindly merged dependencies.

| Repository | V2 use | Code policy |
|---|---|---|
| `saidulIslam1602/Transaction-Anomaly-Detection` | feature engineering, model comparison, SHAP, anomaly rules, monitoring ideas | MIT; selected logic may be adapted with attribution after tests |
| `Shahzod-CBU/BCC_liquidity` | forecasting-model comparison and interval ideas | no clear license found during initial review; concepts only unless permission/license is confirmed |
| `Filidetan597/finomaly` | small rule/ML utility ideas | MIT; use only after source-quality review |
| `jube-home/aml-fraud-transaction-monitoring` | rule suppression, audit and case-workflow design | AGPL; architecture concepts only unless the whole licensing strategy is intentionally changed |
| `00-Python/FastAPI-Role-and-Permissions` | JWT/RBAC entities and endpoint-authorization patterns | reported as open/MIT in README; verify license file before copying any source |
| `Paulinhx/aegisflow` | Semgrep/Trivy/SBOM ideas | intentionally vulnerable application; never copy the demo application code |
| SHAP / Great Expectations / IBM ART | explainability, data validation, adversarial evaluation | official libraries; add only when justified by dataset/model checkpoint |

Every reused source fragment must be recorded in `THIRD_PARTY_NOTICES.md`.
