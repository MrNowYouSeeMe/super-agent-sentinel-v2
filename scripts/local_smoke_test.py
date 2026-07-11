
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8000/api/v1"


def request(method: str, path: str, *, body: dict[str, Any] | None = None, token: str | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def assert_ok(name: str, status: int, expected: int = 200) -> None:
    if status != expected:
        raise AssertionError(f"{name} expected {expected}, got {status}")


def main() -> int:
    checks: list[str] = []

    status, health = request("GET", "/health")
    assert_ok("health", status)
    checks.append(f"health={health['status']}")

    status, scenarios = request("GET", "/demo/scenarios")
    assert_ok("scenarios", status)
    scenario_ids = {item["scenario_id"] for item in scenarios}
    assert "hidden_provider_shortage" in scenario_ids
    checks.append(f"scenarios={len(scenarios)}")

    status, hidden = request("POST", "/demo/scenarios/hidden_provider_shortage")
    assert_ok("hidden_provider_shortage", status)
    assert hidden["analysis"]["decision"]["human_review_required"] is True
    checks.append(f"hidden_case={hidden['case']['case_id']}")

    status, evidence = request("GET", "/demo/validation-evidence")
    assert_ok("validation_evidence", status)
    assert len(evidence["metrics"]) >= 3
    checks.append("validation_evidence=ok")

    status, login = request("POST", "/auth/demo-login", body={"profile_id": "area-manager-sylhet"})
    assert_ok("demo_login", status)
    token = login["access_token"]
    checks.append(f"login={login['profile']['profile_id']}")

    payload = {
        "outlet_id": "OUT-1",
        "area_id": "sylhet",
        "language": "en",
        "festival_or_market_day": True,
        "shared_cash": {
            "resource_id": "shared_cash",
            "balance": 90000,
            "safe_buffer": 20000,
            "cash_in_5m": 8000,
            "cash_out_5m": 16000
        },
        "providers": [
            {
                "resource_id": "bkash",
                "balance": 7000,
                "safe_buffer": 3000,
                "cash_in_5m": 1000,
                "cash_out_5m": 30000,
                "transaction_count_5m": 32,
                "repeated_amount_ratio": 0.75,
                "unique_customer_ratio": 0.18
            },
            {
                "resource_id": "nagad",
                "balance": 120000,
                "safe_buffer": 15000,
                "cash_in_5m": 20000,
                "cash_out_5m": 10000
            }
        ]
    }

    status, scoped = request("POST", "/intelligence/analyze-scoped", body=payload, token=token)
    assert_ok("analyze_scoped", status)
    assert scoped["case"] is not None
    checks.append(f"scoped_hidden={scoped['hidden_resource_count']}")

    status, transitioned = request(
        "POST",
        "/cases/transition",
        body={"case": scoped["case"], "action": "assign", "note": "Smoke test assignment."},
        token=token,
    )
    assert_ok("case_transition", status)
    assert transitioned["case"]["current_status"] == "ASSIGNED"
    checks.append("case_transition=ASSIGNED")

    bad_payload = dict(payload)
    bad_payload["providers"] = [dict(payload["providers"][0])]
    bad_payload["providers"][0]["resource_id"] = "unknownpay"
    status, validation = request("POST", "/validation/check", body=bad_payload)
    assert_ok("validation_bad_provider", status)
    assert validation["valid"] is False
    checks.append("bad_provider_validation=rejected")

    print("LOCAL SMOKE TEST PASSED")
    for item in checks:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"LOCAL SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise
