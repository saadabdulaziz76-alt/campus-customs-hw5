"""Shared types for the Campus Customs agent team.

Structured outputs rather than free text, so a hand-off between agents carries
the same fields every time and the audit trail records something checkable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

ROLES: list[Role] = ["boss", "inventory", "accounting", "facilities", "customer_service"]

ROLE_TITLES: dict[str, str] = {
    "boss": "Shop Manager",
    "inventory": "Inventory Lead",
    "accounting": "Bookkeeper",
    "facilities": "Facilities Coordinator",
    "customer_service": "Customer Service",
}


class SpecialistReport(BaseModel):
    """What a specialist hands back when asked to look at something.

    `facts` is the part that must trace to an MCP tool result; `recommendation`
    is the specialist's judgement, which the Boss may override.
    """

    agent: str = Field(description="Which role produced this.")
    summary: str = Field(description="Two or three sentences answering what was asked.")
    facts: list[str] = Field(
        default_factory=list,
        description="Concrete values pulled from MCP tools — numbers, dates, ids. "
                    "Anything stated here must have come from a tool result.",
    )
    recommendation: str = Field(default="", description="What this specialist thinks should happen.")
    needs_human: bool = Field(
        default=False,
        description="True when the decision spends money, sets a price below the "
                    "usual floor, or otherwise exceeds what an agent should settle alone.",
    )
    blocked_on: str = Field(default="", description="What is missing, if anything.")


class TicketDecision(BaseModel):
    """The Boss's answer for one ticket."""

    ticket_id: int
    decision: str = Field(description="What the shop will actually do.")
    reasoning: str = Field(description="Why, referring to the facts the specialists returned.")
    customer_reply: str = Field(
        default="", description="The message to send the requester, if one is needed."
    )
    actions_taken: list[str] = Field(
        default_factory=list, description="Writes actually performed, with their tool results."
    )
    needs_human_approval: bool = Field(
        default=False, description="True when a person must sign off before anything is executed."
    )
    approval_reason: str = Field(default="", description="Why a human is needed.")
    consulted: list[str] = Field(default_factory=list, description="Which specialists were asked.")


class RunSummary(BaseModel):
    """One pass over the open tickets."""

    run_id: str
    started_at: str
    finished_at: str
    model: str
    tickets_seen: int
    decisions: list[TicketDecision] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    errors: list[str] = Field(default_factory=list)
