from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.phase91_models import AuditVerification

ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = ROOT / "runtime" / "phase91"
AUDIT_PATH = AUDIT_DIR / "audit_chain.jsonl"
_LOCK = threading.Lock()
GENESIS = "GENESIS"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_records() -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def append_chain_event(
    *,
    analysis_id: str,
    event: str,
    actor_id: str,
    details: dict[str, Any] | None = None,
) -> str:
    with _LOCK:
        records = _read_records()
        previous_hash = records[-1]["event_hash"] if records else GENESIS
        body = {
            "event_id": f"A91-{uuid4().hex[:16].upper()}",
            "analysis_id": analysis_id,
            "event": event,
            "actor_id": actor_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
            "previous_hash": previous_hash,
        }
        body["event_hash"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(body) + "\n")
        return body["event_id"]


def verify_audit_chain() -> AuditVerification:
    with _LOCK:
        try:
            records = _read_records()
        except (json.JSONDecodeError, OSError) as exc:
            return AuditVerification(
                valid=False,
                event_count=0,
                broken_index=0,
                latest_hash=None,
                message=f"Audit file could not be parsed: {exc}",
            )

        previous_hash = GENESIS
        for index, record in enumerate(records):
            claimed = str(record.get("event_hash", ""))
            if record.get("previous_hash") != previous_hash:
                return AuditVerification(
                    valid=False,
                    event_count=len(records),
                    broken_index=index,
                    latest_hash=records[index - 1].get("event_hash") if index else None,
                    message="Previous-hash link mismatch.",
                )
            unsigned = dict(record)
            unsigned.pop("event_hash", None)
            expected = hashlib.sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
            if claimed != expected:
                return AuditVerification(
                    valid=False,
                    event_count=len(records),
                    broken_index=index,
                    latest_hash=records[index - 1].get("event_hash") if index else None,
                    message="Event hash mismatch.",
                )
            previous_hash = claimed

        return AuditVerification(
            valid=True,
            event_count=len(records),
            broken_index=None,
            latest_hash=previous_hash if records else None,
            message="Audit hash chain is valid.",
        )
