# Stakeholder Routing Policy

AI/ML models produce risk scores, evidence, uncertainty, and the affected resource. They do not decide the final operational action.

Routing is deterministic and scope-aware after model/rule fusion.

| Situation | Primary recipient | Secondary/visibility | Required human action |
|---|---|---|---|
| Provider-specific liquidity pressure | Area manager + affected provider operations team | Outlet operator; central operations for high severity | Verify balance/demand and coordinate approved support |
| Shared physical-cash pressure | Area manager | Outlet operator; central operations for high severity | Verify cash position and coordinate operational support |
| Unusual activity without immediate shortage | Risk/compliance reviewer | Affected provider operations team | Review evidence and possible legitimate context |
| Liquidity pressure + unusual activity | Area manager + risk reviewer | Affected provider operations; central operations if high severity | Joint human review before escalation |
| Stale/missing/conflicting provider data | Data/provider operations | Area manager | Verify feed/reconciliation before relying on the alert |
| Cross-area recurring pressure/hotspot | Central operations/management | Relevant area managers | Prioritize area-level support and monitor recurrence |

## Routing inputs

- affected resource/provider;
- area and outlet;
- classification;
- severity;
- confidence/data health;
- current owner and workflow status;
- provider/area/outlet authorization scopes.

## Safety boundary

The system may notify, assign, recommend, escalate, and record. It never moves money, transfers value, freezes accounts, blocks users, or declares fraud.