from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_DIR = ROOT / "runtime" / "phase91"
IDEMPOTENCY_PATH = RUNTIME_DIR / "idempotency.json"
_LOCK = threading.Lock()
_RATE: dict[str, list[float]] = {}


class Phase91RateLimitError(RuntimeError):
    pass


class Phase91IdempotencyConflict(ValueError):
    pass


def request_fingerprint(payload: BaseModel) -> str:
    data = payload.model_dump(mode="json")
    data.pop("idempotency_key", None)
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def check_rate_limit(
    actor_id: str,
    *,
    limit: int = 30,
    window_seconds: int = 60,
) -> None:
    now = time.time()
    with _LOCK:
        active = [
            stamp
            for stamp in _RATE.get(actor_id, [])
            if now - stamp < window_seconds
        ]
        if len(active) >= limit:
            raise Phase91RateLimitError(
                f"Rate limit exceeded: {limit} analyses per {window_seconds} seconds."
            )
        active.append(now)
        _RATE[actor_id] = active


def _load_idempotency() -> dict[str, dict[str, Any]]:
    if not IDEMPOTENCY_PATH.exists():
        return {}
    return json.loads(IDEMPOTENCY_PATH.read_text(encoding="utf-8"))


def _save_idempotency(records: dict[str, dict[str, Any]]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temporary = IDEMPOTENCY_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(IDEMPOTENCY_PATH)


def get_idempotent_response(
    key: str,
    *,
    fingerprint: str,
    ttl_seconds: int = 86_400,
) -> dict[str, Any] | None:
    now = time.time()
    with _LOCK:
        records = _load_idempotency()
        expired = [
            stored_key
            for stored_key, record in records.items()
            if now - float(record.get("created_at_epoch", 0)) > ttl_seconds
        ]
        for stored_key in expired:
            records.pop(stored_key, None)
        if expired:
            _save_idempotency(records)

        record = records.get(key)
        if record is None:
            return None
        if record.get("fingerprint") != fingerprint:
            raise Phase91IdempotencyConflict(
                "The idempotency key was already used with a different request."
            )
        response = record.get("response")
        return response if isinstance(response, dict) else None


def store_idempotent_response(
    key: str,
    *,
    fingerprint: str,
    response: dict[str, Any],
) -> None:
    with _LOCK:
        records = _load_idempotency()
        records[key] = {
            "fingerprint": fingerprint,
            "created_at_epoch": time.time(),
            "response": response,
        }
        _save_idempotency(records)
