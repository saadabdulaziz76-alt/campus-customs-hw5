# Campus Customs — Back-Office MCP Server

An MCP server, built with **FastMCP**, that gives the homework's agents read
access to the Campus Customs back office. Every agent in this assignment reaches
the shop's data through these tools rather than from memory, so no answer is
ever based on an invented price, stock level or due date.

## What it is for

The shop's inbox holds three open tickets, and none of them can be answered from
the ticket alone — each needs facts spread across several tables. These tools do
that joining, so an agent gets a complete picture in one call instead of
guessing at the gaps.

The tools are **read-only**. Nothing here writes to the database, and nothing
here spends money. Where a record does not exist, a tool returns an explicit
error naming what was missing rather than filling it in.

## Database

```
data/campus_customs_new.db
```

The working copy, resolved relative to this folder as `../data/campus_customs_new.db`.
The original `campus_customs.db` is left untouched. Connections are opened in
SQLite read-only mode (`mode=ro`).

"Today" always comes from the `desk` table, never from the system clock, so
due-date arithmetic matches the scenario rather than the day the code is run.

## The tools

Ten tools. Seven read; three write. The write tools are the only way the shop's
state can change, which is why the controls live in them rather than in a prompt.

### Read

| Tool | Answers | Tables |
|---|---|---|
| `check_item_availability(sku, size, invoice_id=None)` | Can we fill this order in this size, and if not, when? | `inventory`, `pricing`, `invoices`, `vendors`, `desk` |
| `review_cash_and_obligations()` | What do we owe, when, and does the cash cover all of it? | `cash_accounts`, `invoices`, `vendors`, `leases`, `payments`, `desk` |
| `price_bulk_order(sku, size, qty, proposed_unit_price=None)` | Can we fill this bulk request, and does the price clear cost? | `inventory`, `pricing` |
| `list_open_tickets(status="open")` | What is in the queue? | `tickets`, `desk` |
| `get_ticket(ticket_id)` | One ticket with its linked inventory, pricing, invoice, vendor and lease already resolved. | `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`, `desk` |
| `list_vendors()` | Who supplies what, and how many days they take. | `vendors`, `desk` |
| `get_lease(lease_id)` | The space, the landlord, the rent, when it is next due, and whether it has been paid. | `leases`, `payments`, `desk` |

### Write — these change real state

| Tool | Does | Refuses when |
|---|---|---|
| `record_payment(kind, ref_id, amount, account, approved_by, note="")` | Pays an invoice or rent: writes `payments`, decrements `cash_accounts`, marks the invoice paid — in one transaction. | No named approver · amount does not match what is owed · account does not exist · already paid · insufficient funds |
| `adjust_inventory(sku, size, delta, reason)` | Moves stock for one size. Negative fulfils an order. | The change would take a size below zero |
| `close_ticket(ticket_id, status, resolution)` | Sets ticket status and appends the reasoning to its notes. | Status is not `open`, `closed` or `blocked` |

`record_payment` deliberately requires a human name in `approved_by`. An agent
must not put its own name there — that field is the record of who is
accountable.

## Running it

Not required for Problem 3, but it works:

```bash
python -m venv .venv
./.venv/bin/pip install -r requirements.txt

./.venv/bin/python server.py           # stdio (how an MCP client connects)
./.venv/bin/python server.py --http    # Streamable HTTP on port 8013
```

The agent team in `backend/` reaches these tools through `MCPToolset`, launched from the `.mcp.json` entry. There is no other path from the agents to the database.
