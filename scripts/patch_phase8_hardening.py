from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "backend" / "app" / "api" / "v1" / "router.py"

text = ROUTER.read_text(encoding="utf-8-sig")

import_anchor = (
    "from app.services.scenarios import ScenarioRunResponse, ScenarioSummary, "
    "list_scenarios, run_scenario\n"
)
import_line = "from app.services.scope_redaction import redact_analysis_for_scope\n"

if import_line not in text:
    if import_anchor not in text:
        raise RuntimeError("Phase 8 router import anchor was not found.")
    text = text.replace(import_anchor, import_anchor + import_line, 1)

old_block = '''    analysis = analyze(payload)
    all_resources = [payload.shared_cash.resource_id, *(provider.resource_id for provider in payload.providers)]
    visible = visible_resource_ids(
        principal,
        resource_ids=all_resources,
        area_id=payload.area_id,
        outlet_id=payload.outlet_id,
    )
    hidden_count = len(all_resources) - len(visible)
    scope_policy = (
        "Provider, area, and outlet scopes were enforced server-side. "
        "Shared-cash coordination is visible only where the user's area/outlet scope allows it; "
        "provider raw data remains restricted to scoped users."
    )
    return ScopedAnalysisResponse(
        principal=principal_view(principal),
        visible_resource_ids=visible,
        hidden_resource_count=hidden_count,
        scope_policy=scope_policy,
        validation=validation,
        analysis=analysis,
        case=build_case_from_analysis(analysis),
    )
'''

new_block = '''    full_analysis = analyze(payload)
    all_resources = [payload.shared_cash.resource_id, *(provider.resource_id for provider in payload.providers)]
    visible = visible_resource_ids(
        principal,
        resource_ids=all_resources,
        area_id=payload.area_id,
        outlet_id=payload.outlet_id,
    )
    hidden_count = len(all_resources) - len(visible)
    scoped = redact_analysis_for_scope(
        full_analysis,
        visible_resource_ids=visible,
    )
    scope_policy = (
        "Provider, area, and outlet scopes are enforced server-side. "
        "Hidden resources, evidence, decisions, explanations, and cases are redacted "
        "before the response is serialized."
    )
    return ScopedAnalysisResponse(
        principal=principal_view(principal),
        visible_resource_ids=visible,
        hidden_resource_count=hidden_count,
        scope_policy=scope_policy,
        validation=validation,
        analysis=scoped.analysis,
        case=build_case_from_analysis(scoped.analysis) if scoped.case_allowed else None,
    )
'''

if old_block in text:
    text = text.replace(old_block, new_block, 1)
elif new_block not in text:
    raise RuntimeError(
        "Phase 8 router block did not match the expected Phase 7 code. "
        "No unsafe partial patch was applied."
    )

ROUTER.write_text(text, encoding="utf-8")
print("Phase 8 router redaction patch applied.")