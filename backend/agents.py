"""The Campus Customs agent team.

Five PydanticAI agents — Boss, Inventory, Accounting, Facilities, Customer
Service — all on gpt-6-luna, all reading shop data through the same MCP
toolset. There is no second tools layer: `backend/` never opens the database.

Connectivity
------------
The Boss can delegate to any of the four specialists. Each specialist can in
turn consult any peer through `consult_teammate`, so the team is fully
connected without every agent owning four near-identical tools. Depth and
delegation count are capped in config, so a loop cannot run away.

Auditing
--------
`run_traced` drives `agent.iter()` node by node and appends an event to
`output/audit_trail.json` for every step — prompt in, model request, model
response with its tool calls and token usage, tool returns, and the end of the
loop — plus one event per delegation. Nothing is overwritten.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    RetryPromptPart, TextPart, ThinkingPart, ToolCallPart, ToolReturnPart,
)
from pydantic_ai.usage import UsageLimits

import audit
import config
from models import ROLE_TITLES, SpecialistReport, TicketDecision

PROMPTS = Path(__file__).resolve().parent / "prompts"
SHOP_RULES = (PROMPTS / "_shop_rules.md").read_text(encoding="utf-8")


def _prompt(name: str) -> str:
    """A role prompt with the house rules appended — same rules for everyone."""
    return f"{(PROMPTS / f'{name}.md').read_text(encoding='utf-8')}\n\n---\n\n{SHOP_RULES}"


@dataclass
class TeamDeps:
    """Shared state for one pass over the tickets."""
    run_id: str
    toolset: MCPToolset
    ticket_id: int | None = None
    depth: int = 0
    delegations: int = 0
    trail: list[dict] = field(default_factory=list)
    usage_totals: dict = field(default_factory=lambda: {"requests": 0, "input_tokens": 0, "output_tokens": 0})

    def note(self, agent: str, kind: str, **data: Any) -> None:
        audit.step(self.run_id, agent=agent, kind=kind, ticket_id=self.ticket_id,
                   depth=self.depth, **data)
        self.trail.append({"agent": agent, "kind": kind, **data})

    def add_usage(self, usage: dict) -> None:
        for k in self.usage_totals:
            self.usage_totals[k] += usage.get(k, 0)


LIMITS = UsageLimits(
    request_limit=config.MAX_REQUESTS_PER_AGENT,
    tool_calls_limit=config.MAX_TOOL_CALLS_PER_AGENT,
)


# --------------------------------------------------------------- audit tracing

def _usage_dict(usage: Any) -> dict:
    return {
        "requests": getattr(usage, "requests", 0) or 0,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }


def _describe(node: Any) -> tuple[str, dict] | None:
    """Turn one agent-loop node into an auditable event."""
    if Agent.is_user_prompt_node(node):
        return "model_request", {"prompt": audit.short(node.user_prompt)}
    if Agent.is_model_request_node(node):
        parts = node.request.parts
        return "tool_result", {
            "returns": [{"tool": p.tool_name, "content": audit.short(p.model_response_str(), 300)}
                        for p in parts if isinstance(p, ToolReturnPart)],
            "retries": [audit.short(p.model_response(), 200) for p in parts
                        if isinstance(p, RetryPromptPart)],
        }
    if Agent.is_call_tools_node(node):
        resp = node.model_response
        return "model_response", {
            "text": audit.short("".join(p.content for p in resp.parts if isinstance(p, TextPart))),
            "thinking": audit.short("".join(p.content for p in resp.parts if isinstance(p, ThinkingPart)), 250),
            "tool_calls": [{"tool": p.tool_name, "args": audit.short(p.args_as_dict(), 200)}
                           for p in resp.parts if isinstance(p, ToolCallPart)],
            "usage": _usage_dict(resp.usage),
            "finish_reason": getattr(resp, "finish_reason", None),
        }
    if Agent.is_end_node(node):
        return "agent_end", {"output": audit.short(node.data.output)}
    return None


async def run_traced(agent: Agent, prompt: str, *, deps: TeamDeps, agent_name: str) -> tuple[Any, dict]:
    """Run an agent, writing one audit event per loop step."""
    started = time.perf_counter()
    deps.note(agent_name, "agent_start", question=audit.short(prompt, 300),
              model=config.MODEL_NAME)
    async with agent.iter(prompt, deps=deps, usage_limits=LIMITS) as run:
        step_n = 0
        async for node in run:
            described = _describe(node)
            if described is None:
                continue
            step_n += 1
            kind, data = described
            deps.note(agent_name, kind, step=step_n, **data)
        raw = run.usage() if callable(run.usage) else run.usage
        usage = _usage_dict(raw)
        usage["seconds"] = round(time.perf_counter() - started, 2)
        deps.add_usage(usage)
        deps.note(agent_name, "agent_done", steps=step_n, usage=usage)
        return run.result.output, usage


# ------------------------------------------------------------------- the agents

def _build(role: str, output_type: Any, toolset: MCPToolset) -> Agent:
    return Agent(
        config.build_model(),
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=_prompt(role),
        toolsets=[toolset],
        name=role,
        retries=2,
    )


def build_team(toolset: MCPToolset) -> dict[str, Agent]:
    """The five agents, wired so everyone can reach everyone."""
    team: dict[str, Agent] = {
        "inventory": _build("inventory", SpecialistReport, toolset),
        "accounting": _build("accounting", SpecialistReport, toolset),
        "facilities": _build("facilities", SpecialistReport, toolset),
        "customer_service": _build("customer_service", SpecialistReport, toolset),
        "boss": _build("boss", TicketDecision, toolset),
    }

    async def _delegate(ctx: RunContext[TeamDeps], role: str, question: str) -> dict:
        d = ctx.deps
        if d.depth >= config.MAX_DELEGATION_DEPTH:
            return {"error": f"Delegation depth limit ({config.MAX_DELEGATION_DEPTH}) reached. "
                             "Answer from what you already have."}
        if d.delegations >= config.MAX_DELEGATIONS_PER_RUN:
            return {"error": f"Delegation limit ({config.MAX_DELEGATIONS_PER_RUN}) reached for this ticket."}
        d.delegations += 1
        caller_depth = d.depth
        d.note(role, "delegation", asked_by_depth=caller_depth, question=audit.short(question, 300))
        d.depth = caller_depth + 1
        try:
            report, _ = await run_traced(team[role], question, deps=d, agent_name=role)
        except Exception as exc:  # a specialist failing must not kill the ticket
            d.note(role, "error", error=audit.short(exc, 300))
            return {"error": f"{ROLE_TITLES[role]} could not answer: {exc}"}
        finally:
            d.depth = caller_depth
        return report.model_dump() if hasattr(report, "model_dump") else {"summary": str(report)}

    # --- Boss -> each specialist -------------------------------------------
    @team["boss"].tool
    async def ask_inventory(ctx: RunContext[TeamDeps], question: str) -> dict:
        """Ask the Inventory Lead about stock, sizes, reorders or vendor lead times.

        Args:
            question: a specific question naming the SKU and size where relevant.
        """
        return await _delegate(ctx, "inventory", question)

    @team["boss"].tool
    async def ask_accounting(ctx: RunContext[TeamDeps], question: str) -> dict:
        """Ask the Bookkeeper about cash, invoices, rent or whether we can afford something.

        Args:
            question: a specific question. Say which bill or ticket you mean.
        """
        return await _delegate(ctx, "accounting", question)

    @team["boss"].tool
    async def ask_facilities(ctx: RunContext[TeamDeps], question: str) -> dict:
        """Ask the Facilities Coordinator about the lease, the landlord or the premises.

        Args:
            question: a specific question, naming the lease id where relevant.
        """
        return await _delegate(ctx, "facilities", question)

    @team["boss"].tool
    async def ask_customer_service(ctx: RunContext[TeamDeps], question: str) -> dict:
        """Ask Customer Service to draft the reply to the requester.

        Give them the decision and the facts behind it; they turn it into a message.

        Args:
            question: the decision and the facts the reply must contain.
        """
        return await _delegate(ctx, "customer_service", question)

    # --- specialist -> peer (full connectivity) ----------------------------
    for role in ("inventory", "accounting", "facilities", "customer_service"):
        @team[role].tool
        async def consult_teammate(ctx: RunContext[TeamDeps], teammate: str, question: str) -> dict:
            """Ask another specialist something outside your own area.

            Use this when answering properly needs someone else's facts — for
            example Inventory asking Accounting whether a reprint invoice has
            been paid before quoting a restock date.

            Args:
                teammate: one of "inventory", "accounting", "facilities", "customer_service".
                question: what you need from them, specifically.
            """
            name = (teammate or "").strip().lower()
            if name not in ("inventory", "accounting", "facilities", "customer_service"):
                return {"error": "teammate must be inventory, accounting, facilities or customer_service."}
            return await _delegate(ctx, name, question)

    return team
