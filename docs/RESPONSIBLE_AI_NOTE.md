
# Responsible AI and Safety Note

SuperAgent Sentinel V2 is a local decision-support prototype for multi-provider MFS liquidity and anomaly review.

## Hard safety boundaries

- The system does not move money.
- The system does not transfer value between providers.
- The system does not freeze accounts.
- The system does not block customers.
- The system does not declare fraud.
- Medium/high or degraded-confidence outputs route to human review.

## LLM usage policy

OpenAI may be used later for Bangla/Banglish/English explanation polish only. It must not calculate risk, choose the final classification, or invent evidence.

## Provider boundary

bKash, Nagad, and Rocket data are separate provider resources. The combined operations view is scoped by role, provider, area, and outlet. A provider-specific user must not receive competitor raw data.

## Data-quality policy

Missing, stale, or conflicting feeds lower confidence and can route the case to verification instead of escalation.
