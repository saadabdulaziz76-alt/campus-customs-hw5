"""FastAPI backend for the Campus Customs desk dashboard.

Run from this folder:
    uvicorn main:app --reload --port 8000

Everything that touches shop data goes through the MCP server — this file never
opens SQLite for shop records. The one exception is `/api/reset`, which copies
the pristine database file back over the working copy; that is a file operation,
not a query.

The division that matters: **agents prepare, humans approve.** The agent team
can analyse a payment and recommend it, but only `POST /api/approvals` actually
moves cash, and it requires a named human.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import audit
import config
from agents import TeamDeps, build_team, run_traced

HERE = Path(__file__).resolve().parent
HW_ROOT = HERE.parent
DATA = HW_ROOT / "data"
PRISTINE_DB = DATA / "campus_customs.db"
WORKING_DB = DATA / "campus_customs_new.db"
AUDIT = HW_ROOT / "output" / "audit_trail.json"

app = FastAPI(title="Campus Customs — Desk API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[                # the Vite dev server, explicitly
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Run state lives in memory — fine for one desk, not for production.
RUNS: dict[str, dict] = {}


# ----------------------------------------------------------------- MCP helper

async def mcp_call(tool: str, args: dict | None = None) -> Any:
    """One-shot MCP call. The only route from this API to shop data."""
    toolset = config.build_mcp_toolset()
    async with toolset:
        result = await toolset.client.call_tool(tool, args or {})
        return result.data


# -------------------------------------------------------------------- schemas

class RunRequest(BaseModel):
    wait: bool = Field(default=False, description="Block until the run finishes instead of returning a run_id.")


class ApprovalRequest(BaseModel):
    kind: Literal["invoice", "rent"]
    ref_id: int = Field(description="Invoice id, or lease id for rent.")
    amount: float = Field(gt=0)
    account: str = Field(default="checking")
    approved_by: str = Field(min_length=1, description="The human authorising this. Required.")
    note: str = ""
    ticket_id: int | None = Field(default=None, description="Ticket to close once paid.")


class ResetRequest(BaseModel):
    confirm: bool = Field(default=False, description="Must be true. Guards against an accidental wipe.")


# ========================================================== 0 · health

@app.get("/api/health")
async def health():
    """Is the API up, is the key set, and can it reach the MCP server?"""
    try:
        tickets = await mcp_call("list_open_tickets", {"status": "all"})
        mcp_ok, detail = True, f"{tickets['count']} tickets visible"
    except Exception as exc:
        mcp_ok, detail = False, str(exc)
    return {
        "ok": mcp_ok,
        "model": config.MODEL_NAME,
        "portkey_key_set": bool(config.api_key_present()),
        "mcp": {"reachable": mcp_ok, "detail": detail},
        "database": WORKING_DB.name,
    }


# ========================================================== 1 · tickets

@app.get("/api/tickets")
async def list_tickets():
    """The three tickets, each marked open or resolved."""
    data = await mcp_call("list_open_tickets", {"status": "all"})
    out = []
    for t in data["tickets"]:
        status = t.get("status", "")
        out.append({
            **t,
            "resolved": status in ("closed", "blocked"),
            "state": "open" if status == "open" else ("blocked" if status == "blocked" else "resolved"),
            "last_run": RUNS_BY_TICKET.get(t["id"]),
        })
    return {"today": data["today"], "count": len(out), "tickets": out}


RUNS_BY_TICKET: dict[int, str] = {}


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket with its linked inventory, pricing, invoice, vendor and lease."""
    data = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(404, data.get("error", f"No ticket {ticket_id}"))
    return data


# ========================================================== 2 · run the team

async def _do_run(run_id: str, ticket_id: int) -> None:
    RUNS[run_id].update(status="running")
    toolset = config.build_mcp_toolset()
    team = build_team(toolset)
    deps = TeamDeps(run_id=run_id, toolset=toolset, ticket_id=ticket_id)
    audit.step(run_id, agent="system", kind="run_start", ticket_id=ticket_id,
               model=config.MODEL_NAME, source="api")
    try:
        async with toolset:
            question = (
                f"Work ticket {ticket_id}. Call get_ticket({ticket_id}) first to see what it "
                "depends on, then bring in whichever specialists you need. Decide what the shop "
                "will do, and flag anything that needs my approval before it happens."
            )
            decision, usage = await run_traced(team["boss"], question, deps=deps, agent_name="boss")
        RUNS[run_id].update(status="done", decision=decision.model_dump(), usage=usage,
                            finished_at=audit.now())
        audit.step(run_id, agent="boss", kind="decision", ticket_id=ticket_id,
                   decision=audit.short(decision.decision, 300),
                   needs_human=decision.needs_human_approval, usage=usage)
    except Exception as exc:
        RUNS[run_id].update(status="error", error=f"{type(exc).__name__}: {exc}",
                            finished_at=audit.now())
        audit.step(run_id, agent="system", kind="error", ticket_id=ticket_id, error=str(exc))
    finally:
        audit.step(run_id, agent="system", kind="run_end", ticket_id=ticket_id,
                   usage=deps.usage_totals)


@app.post("/api/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int, body: RunRequest, background: BackgroundTasks):
    """Run the agent team on one ticket.

    Returns a `run_id` immediately and works in the background, so the board can
    poll `/api/events` while the team thinks. Pass `{"wait": true}` to block.
    """
    found = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if not found.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}")

    run_id = audit.new_run_id()
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "queued",
                    "started_at": audit.now()}
    RUNS_BY_TICKET[ticket_id] = run_id

    if body.wait:
        await _do_run(run_id, ticket_id)
        return RUNS[run_id]
    background.add_task(_do_run, run_id, ticket_id)
    return {"run_id": run_id, "ticket_id": ticket_id, "status": "queued",
            "poll": f"/api/runs/{run_id}"}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """Status and result of one run."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id}")
    return RUNS[run_id]


@app.get("/api/runs")
def list_runs():
    """Every run this server has started, newest first."""
    return {"runs": sorted(RUNS.values(), key=lambda r: r["started_at"], reverse=True)}


# ========================================================== 3 · agent events

@app.get("/api/events")
def recent_events(limit: int = 80, run_id: str | None = None, ticket_id: int | None = None):
    """Recent agent-loop events: who spoke, what they said, which tools they used.

    Reads the append-only audit trail, newest last. The board polls this to
    refresh while a run is in flight.
    """
    if not AUDIT.exists():
        return {"count": 0, "events": [], "agents": {}}
    rows: list[dict] = []
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if run_id:
        rows = [r for r in rows if r.get("run_id") == run_id]
    if ticket_id is not None:
        rows = [r for r in rows if r.get("ticket_id") == ticket_id]

    tail = rows[-limit:]
    # what each agent said, and which tools it reached for
    per_agent: dict[str, dict] = {}
    for r in tail:
        a = per_agent.setdefault(r.get("agent", "?"), {"said": [], "tools": [], "steps": 0})
        a["steps"] += 1
        if r.get("kind") == "model_response":
            if r.get("text"):
                a["said"].append(r["text"])
            tc = r.get("tool_calls")
            if tc:
                text = tc if isinstance(tc, str) else json.dumps(tc)
                for name in {w for w in (
                    "get_ticket", "list_open_tickets", "check_item_availability",
                    "review_cash_and_obligations", "price_bulk_order", "list_vendors",
                    "get_lease", "record_payment", "adjust_inventory", "close_ticket",
                    "ask_inventory", "ask_accounting", "ask_facilities",
                    "ask_customer_service", "consult_teammate") if w in text}:
                    if name not in a["tools"]:
                        a["tools"].append(name)
    return {"count": len(tail), "total_in_log": len(rows), "events": tail, "agents": per_agent}


# ========================================================== 4 · approvals

@app.post("/api/approvals")
async def approve_payment(body: ApprovalRequest):
    """**The only route that moves money.**

    Agents prepare a payment; this is where a human signs it off. Calls the MCP
    `record_payment` tool, which independently re-checks the amount against what
    is owed, confirms the account holds it, and refuses a duplicate.
    """
    result = await mcp_call("record_payment", {
        "kind": body.kind, "ref_id": body.ref_id, "amount": body.amount,
        "account": body.account, "approved_by": body.approved_by, "note": body.note,
    })
    approval_id = uuid.uuid4().hex[:10]
    audit.step(approval_id, agent="human", kind="approval",
               ticket_id=body.ticket_id, approved_by=body.approved_by,
               kind_of_payment=body.kind, ref_id=body.ref_id, amount=body.amount,
               accepted=bool(result.get("ok")), result=audit.short(result, 400))
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Payment refused."))

    if body.ticket_id:
        await mcp_call("close_ticket", {
            "ticket_id": body.ticket_id, "status": "closed",
            "resolution": f"Paid {body.kind} {body.ref_id} (${body.amount:,.2f}), "
                          f"approved by {body.approved_by}.",
        })
    return {"approval_id": approval_id, "approved_by": body.approved_by, "payment": result}


class ResolveRequest(BaseModel):
    resolved_by: str = Field(min_length=1, description="The human accepting the recommendation.")
    resolution: str = Field(min_length=1, description="What was decided.")


@app.post("/api/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ResolveRequest):
    """Close a ticket that needs no payment — a human accepting the team's advice.

    Tickets that move money close through /api/approvals instead. This exists so
    a decision like "offer what we have at list price" can be signed off and
    closed without inventing a payment that never happened.
    """
    result = await mcp_call("close_ticket", {
        "ticket_id": ticket_id, "status": "closed",
        "resolution": f"{body.resolution} (accepted by {body.resolved_by})",
    })
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Could not close the ticket."))
    audit.step(uuid.uuid4().hex[:10], agent="human", kind="resolution",
               ticket_id=ticket_id, resolved_by=body.resolved_by,
               resolution=audit.short(body.resolution, 300))
    return {"ok": True, "ticket_id": ticket_id, "resolved_by": body.resolved_by, "result": result}


@app.get("/api/approvals/pending")
def pending_approvals():
    """Decisions from completed runs that are waiting on a human."""
    pending = []
    for r in RUNS.values():
        d = r.get("decision")
        if r.get("status") == "done" and d and d.get("needs_human_approval"):
            pending.append({"run_id": r["run_id"], "ticket_id": r["ticket_id"],
                            "decision": d["decision"], "reason": d.get("approval_reason", "")})
    return {"count": len(pending), "pending": pending}


# ========================================================== 5 · cash

@app.get("/api/cash")
async def cash():
    """Current checking balance, with what is still owed against it."""
    data = await mcp_call("review_cash_and_obligations")
    checking = next((a for a in data["accounts"] if a["name"] == "checking"), None)
    return {
        "today": data["today"],
        "checking_balance": checking["balance"] if checking else None,
        "as_of": checking["date"] if checking else None,
        "accounts": data["accounts"],
        "total_owed": data["total_owed"],
        "remaining_if_all_paid": data["remaining_if_all_paid"],
        "covers_everything": data["covers_everything"],
        "obligations": data["obligations"],
        "payments_made": data["payments_already_made"],
    }


# ========================================================== 6 · reset

@app.post("/api/reset")
def reset(body: ResetRequest):
    """Copy the pristine database back over the working copy for a fresh run.

    Needs `{"confirm": true}`. Clears in-memory run state too. The audit trail is
    deliberately left alone — it is append-only history, and wiping it would
    destroy the record of what the agents did before the reset.
    """
    if not body.confirm:
        raise HTTPException(400, 'Send {"confirm": true} to reset the database.')
    if not PRISTINE_DB.exists():
        raise HTTPException(500, f"Original database missing at {PRISTINE_DB}")
    shutil.copyfile(PRISTINE_DB, WORKING_DB)
    RUNS.clear()
    RUNS_BY_TICKET.clear()
    reset_id = uuid.uuid4().hex[:10]
    audit.step(reset_id, agent="system", kind="database_reset",
               restored_from=PRISTINE_DB.name, restored_to=WORKING_DB.name)
    return {"ok": True, "restored_from": PRISTINE_DB.name, "restored_to": WORKING_DB.name,
            "runs_cleared": True, "audit_trail": "left intact (append-only history)",
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
