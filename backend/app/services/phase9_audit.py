from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = ROOT / "runtime" / "phase9"
AUDIT_PATH = AUDIT_DIR / "audit.jsonl"
_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_event(
    *,
    analysis_id: str,
    event: str,
    actor_id: str,
    details: dict[str, Any] | None = None,
) -> str:
    event_id = f"AUD-{uuid4().hex[:16].upper()}"
    record = {
        "event_id": event_id,
        "analysis_id": analysis_id,
        "event": event,
        "actor_id": actor_id,
        "created_at": utc_now(),
        "details": details or {},
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with _LOCK:
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return event_id
