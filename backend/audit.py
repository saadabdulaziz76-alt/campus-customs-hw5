"""Append-only audit trail for the agent team.

`output/audit_trail.json` is opened in append mode and never rewritten, so a run
cannot erase what earlier runs recorded. The format is JSON Lines — one complete
JSON object per line — because that is what makes the append safe: a single JSON
array would have to be read, re-serialised and written back on every event, and
that rewrite is the operation that loses a file when a process dies mid-write.

Read it back with:

    events = [json.loads(line) for line in open("output/audit_trail.json")]
"""

from __future__ import annotations

import json
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE.parent / "output" / "audit_trail.json"
MAX_FIELD_CHARS = 400

_LOCK = threading.Lock()


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def short(value: Any, limit: int = MAX_FIELD_CHARS) -> Any:
    """Trim a value to something readable and bounded, without losing its type."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        text = value
    elif hasattr(value, "model_dump_json"):
        try:
            text = value.model_dump_json()
        except Exception:  # noqa: BLE001 — auditing must never break a run
            text = str(value)
    else:
        try:
            text = json.dumps(value, default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append(event: dict) -> None:
    """Write one event. Never raises — a broken log must not break the shop."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, default=str, ensure_ascii=False) + "\n"
        with _LOCK:
            with AUDIT_PATH.open("a", encoding="utf-8") as fh:   # "a" — never truncates
                fh.write(line)
    except Exception as exc:  # noqa: BLE001
        print(f"[audit] could not write event: {exc}", file=sys.stderr)


def step(run_id: str, *, agent: str, kind: str, ticket_id: int | None = None,
         depth: int = 0, **data: Any) -> None:
    """Record one step of an agent loop.

    `kind` is one of: run_start, agent_start, model_request, model_response,
    tool_call, tool_result, delegation, agent_end, decision, run_end, error.
    """
    append({
        "ts": now(), "run_id": run_id, "agent": agent, "kind": kind,
        "ticket_id": ticket_id, "depth": depth,
        **{k: short(v) for k, v in data.items()},
    })
