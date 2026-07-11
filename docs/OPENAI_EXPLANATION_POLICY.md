
# OpenAI Explanation Policy

OpenAI is optional in this project.

## Allowed use

OpenAI may transform already-computed structured decisions into clearer Bangla, Banglish, or English explanations.

Allowed input:

- classification;
- severity;
- affected resource;
- confidence;
- evidence;
- uncertainty/data-health notes;
- recommended human action.

## Not allowed

OpenAI must not:

- calculate the risk score;
- choose the final classification;
- invent new evidence;
- accuse fraud;
- suggest moving money;
- suggest freezing/blocking;
- expose one provider's confidential raw data to another provider user.

## Fallback

If OpenAI is disabled, missing, slow, or unavailable, the deterministic explanation must be returned.
