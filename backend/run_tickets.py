"""Work the open tickets with the agent team.

    python run_tickets.py              # every open ticket
    python run_tickets.py --ticket 101 # just one

Every loop step is appended to output/audit_trail.json. The file is never
truncated, so runs accumulate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import audit
import config
from agents import TeamDeps, build_team, run_traced
from models import RunSummary

OUT = Path(__file__).resolve().parent.parent / "output"


async def work_ticket(team, deps: TeamDeps, ticket_id: int):
    deps.ticket_id = ticket_id
    deps.depth = 0
    deps.delegations = 0
    question = (
        f"Work ticket {ticket_id}. Call get_ticket({ticket_id}) first to see what it "
        "depends on, then bring in whichever specialists you need. Decide what the shop "
        "will do, and flag anything that needs my approval before it happens."
    )
    decision, usage = await run_traced(team["boss"], question, deps=deps, agent_name="boss")
    deps.note("boss", "decision",
              decision=audit.short(decision.decision, 300),
              needs_human=decision.needs_human_approval,
              consulted=decision.consulted, usage=usage)
    return decision


async def main() -> int:
    ap = argparse.ArgumentParser(description="Run the Campus Customs agent team")
    ap.add_argument("--ticket", type=int, help="work a single ticket id")
    args = ap.parse_args()

    run_id = audit.new_run_id()
    started = audit.now()
    toolset = config.build_mcp_toolset()
    team = build_team(toolset)
    deps = TeamDeps(run_id=run_id, toolset=toolset)

    audit.step(run_id, agent="system", kind="run_start", model=config.MODEL_NAME,
               limits={"requests_per_agent": config.MAX_REQUESTS_PER_AGENT,
                       "tool_calls_per_agent": config.MAX_TOOL_CALLS_PER_AGENT,
                       "delegation_depth": config.MAX_DELEGATION_DEPTH,
                       "delegations_per_run": config.MAX_DELEGATIONS_PER_RUN},
               single_ticket=args.ticket)

    decisions, errors = [], []
    async with toolset:
        if args.ticket:
            ids = [args.ticket]
        else:
            res = await toolset.client.call_tool("list_open_tickets", {"status": "open"})
            ids = [t["id"] for t in res.data["tickets"]]
        print(f"run {run_id} · model {config.MODEL_NAME} · tickets {ids}\n")

        for tid in ids:
            print(f"--- ticket {tid} ---")
            try:
                d = await work_ticket(team, deps, tid)
                decisions.append(d)
                print(f"  decision      : {d.decision[:150]}")
                print(f"  consulted     : {', '.join(d.consulted) or '(none)'}")
                print(f"  needs approval: {d.needs_human_approval}"
                      f"{' — ' + d.approval_reason[:90] if d.approval_reason else ''}")
            except Exception as exc:
                errors.append(f"ticket {tid}: {type(exc).__name__}: {exc}")
                audit.step(run_id, agent="system", kind="error", ticket_id=tid, error=str(exc))
                print(f"  ERROR: {exc}")
            print()

    summary = RunSummary(
        run_id=run_id, started_at=started, finished_at=audit.now(),
        model=config.MODEL_NAME, tickets_seen=len(ids), decisions=decisions,
        total_input_tokens=deps.usage_totals["input_tokens"],
        total_output_tokens=deps.usage_totals["output_tokens"],
        total_requests=deps.usage_totals["requests"], errors=errors,
    )
    audit.step(run_id, agent="system", kind="run_end",
               tickets=len(ids), decisions=len(decisions), errors=len(errors),
               usage=deps.usage_totals)
    OUT.mkdir(exist_ok=True)
    (OUT / f"run_{run_id}.json").write_text(summary.model_dump_json(indent=2) + "\n")

    print(f"tokens: {deps.usage_totals} | summary -> output/run_{run_id}.json")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
