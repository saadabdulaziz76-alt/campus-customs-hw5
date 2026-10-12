# Campus Customs — an agentic back office

**MGT 409 · AI Foundations for Managers · Homework 5**
Saad Alarifi · Yale School of Management

Campus Customs is a small Yale apparel shop on Chapel Street. Three tickets are
open on the desk, there is **$3,400.00** in checking, and **$3,240.00** is owed.
Both bills can be paid — but only just, and only if nothing else is spent. The
third ticket asks for a bulk discount at exactly the moment there is no room to
give one.

Five agents work the desk. They read and write the shop's data **only** through
an MCP server, they are allowed to prepare a payment but never to make one, and
every step they take is appended to an audit trail.

---

## Quick start

Five commands, assuming Python 3.11+ and Node 18+.

```bash
git clone https://github.com/saadabdulaziz76-alt/campus-customs-hw5.git
cd campus-customs-hw5
cp .env.example .env            # then put your PORTKEY_API_KEY in it
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Then follow **Running it** below, in order.

---

## Running it

### 1 · Copy the original database over the working copy

Everything the agents do writes to `data/campus_customs_new.db`. The pristine
copy, `data/campus_customs.db`, is never touched and is the thing you restore
from.

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

> **Both files are committed to this repository on purpose**, so you can clone
> and run without building a database first.
>
> The working copy ships in the state the graded run left it: checking at
> **$160.00**, all three tickets `closed`, two payments on file. That is
> deliberate — it matches `output/resolved_tickets.json` and the Cash tab of
> `output/desk_tickets.html`, so the evidence and the database agree. **Run the
> copy command above before trying the app yourself**, or the board will open
> with nothing left to do.

### 2 · Start the MCP server

The MCP server is the agents' only route to shop data. It is launched over
**stdio**, so in normal use you do **not** start it by hand — the backend spawns
it from the entry in `.mcp.json`. To check it independently:

```bash
python mcp_server/smoke_test.py
```

That exercises all ten tools and writes `output/mcp_smoke.json`. If you would
rather give the server its own environment (which is what `.mcp.json` points at
by default), create it once:

```bash
python3 -m venv mcp_server/.venv
mcp_server/.venv/bin/pip install -r mcp_server/requirements.txt
```

If that virtualenv is absent, the backend falls back to whichever interpreter is
running it, so a single environment works fine.

### 3 · Start the FastAPI backend

```bash
cd backend
uvicorn main:app --port 8000
```

Check it came up — this also confirms the MCP server launches and the key is
loaded:

```bash
curl -s http://localhost:8000/api/health
```

```json
{"ok": true, "model": "gpt-6-luna", "portkey_key_set": true,
 "mcp": {"reachable": true, "detail": "3 tickets visible"},
 "database": "campus_customs_new.db"}
```

> Run `uvicorn` **without** `--reload`. The reloader spawns a second process
> that also tries to own the MCP subprocess.

### 4 · Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. The board talks to the backend at
`http://localhost:8000` by absolute URL, and the backend's CORS allow-list names
that origin explicitly rather than using a wildcard — so the ports matter.

You can also reopen a finished run without re-running the agents:
`http://localhost:5173/?ticket=101&run=<run_id>`.

### 5 · Reset the database before a full three-ticket run

Before running all three tickets end to end, **always start from a clean
database** — otherwise the cash figures will not reconcile, because an invoice
already paid cannot be paid again.

Either click **Fresh start** on the board, or:

```bash
curl -s -X POST http://localhost:8000/api/reset \
  -H 'Content-Type: application/json' -d '{"confirm":true}'
```

Both restore `data/campus_customs_new.db` from the pristine copy and clear the
in-memory run list. **Neither erases `output/audit_trail.json`** — a reset is an
event in the shop's history, not a reason to delete it, so the reset itself is
logged.

Confirm you are starting clean:

```bash
curl -s http://localhost:8000/api/cash      # checking should read 3400.0
```

Then run the three tickets in order — 101, 102, 103 — approving each payment as
a named human when the board asks. Cash should land on **$160.00**:

| Ticket | Change | Why | Balance |
|---|---|---|---|
| — | — | starting balance | $3,400.00 |
| 101 | −$840.00 | invoice 501, Bulldog Print Co | $2,560.00 |
| 102 | −$2,400.00 | September rent, Elm City Properties | $160.00 |
| 103 | $0.00 | no payment — discount declined | **$160.00** |

---

## Layout

```
.
├── AI_prompts.md          every prompt given to the AI, with notes
├── README.md
├── requirements.txt       backend + MCP server dependencies
├── .env.example           template; the real .env is never committed
├── .gitignore
├── .mcp.json              MCP server registration (relative paths, portable)
├── data/
│   ├── campus_customs.db      pristine — restore from this
│   └── campus_customs_new.db  working copy — the agents write here
├── mcp_server/
│   ├── server.py          the ten tools
│   ├── smoke_test.py      exercises all ten, writes output/mcp_smoke.json
│   └── README.md
├── backend/
│   ├── main.py            FastAPI routes
│   ├── agents.py          the five agents, delegation, traced runs
│   ├── config.py          model, MCP toolset, limits
│   ├── audit.py           append-only JSON Lines trail
│   ├── models.py          request/response shapes
│   ├── run_tickets.py     run the team from the command line
│   └── prompts/           one prompt per agent + shared _shop_rules.md
├── frontend/              React 19 + Vite 7 + TypeScript board
└── output/
    ├── harness.md             tables, tools, agents, routes, dashboard, safety
    ├── desk_tickets.html      plan vs actual per ticket, cash, reflection
    ├── resolved_tickets.json  machine-readable results of the graded run
    ├── resolved_board.html    board screenshots for each resolved ticket
    ├── board_shots/           the PNGs that page uses
    ├── audit_trail.json       every event from every run, append-only
    ├── mcp_smoke.json         tool-by-tool smoke test output
    ├── design.md              dashboard design rationale
    └── github_url.txt         this repository's URL
```

---

## The shop

Nine tables in SQLite. `desk.date_today` is **2026-08-31** — no code anywhere
calls the wall clock, so "overdue" always means overdue relative to the shop's
own date. `inventory` is keyed on `(sku, size)`, because a size is a different
product rather than a variant of one.

| Ticket | What it is | The catch |
|---|---|---|
| **101** | A customer wants one `CC-TEE-WHITE` in S | Stock is 0. The reprint that fixes it sits behind invoice 501, three days overdue. |
| **102** | Rent notice from the landlord | $2,400 on lease 1, due 2026-09-02. Arrived as an email. |
| **103** | Yale AI Club wants 20 `CC-HOOD-NAVY` in M, discounted | Only 8 on hand, and by then only $160 left. |

## The five agents

All five run on **gpt-6-luna** through Portkey — no agent picks its own model —
and all five reach shop data only through MCP. Nothing under `backend/` opens
the database.

| Agent | Role | Owns |
|---|---|---|
| **Morgan** | Shop Manager (Boss) | Reads the queue, delegates, decides, closes tickets |
| **Priya** | Inventory Lead | Stock by size, vendors, lead times |
| **Dan** | Bookkeeper | Cash, invoices, rent. Prepares payments, never authorises them |
| **Rosa** | Facilities | The lease, the landlord, the premises |
| **Theo** | Customer Service | The message the requester actually reads |

Every prompt has `backend/prompts/_shop_rules.md` appended, so the house rules
are identical for all five.

## The ten MCP tools

Seven read, three write.

**Read** — `check_item_availability`, `review_cash_and_obligations`,
`price_bulk_order`, `list_open_tickets`, `get_ticket`, `list_vendors`,
`get_lease`. These open SQLite in `mode=ro`, so they cannot write even by
accident.

**Write** — `record_payment`, `adjust_inventory`, `close_ticket`.

## API routes

| Route | Purpose |
|---|---|
| `GET /api/health` | Up? Key set? MCP reachable? |
| `GET /api/tickets` · `GET /api/tickets/{id}` | The queue, and one ticket with its linked records |
| `POST /api/tickets/{id}/run` | Run the team. Returns a `run_id`; add `{"wait":true}` to block |
| `POST /api/tickets/{id}/resolve` | Close a ticket that needs no payment |
| `GET /api/runs` · `GET /api/runs/{id}` | Run status and results |
| `GET /api/events` | Audit events, filterable by run or ticket — the board polls this |
| `POST /api/approvals` | **The only route that moves money** |
| `GET /api/approvals/pending` | Decisions waiting on a human |
| `GET /api/cash` | Checking balance and what is owed against it |
| `POST /api/reset` | Restore the working database. Requires `{"confirm":true}` |

## Safety

- **No agent can move money.** `record_payment` is reachable only through
  `POST /api/approvals`. No agent holds it. Across the graded run: 2 payments,
  both human-approved, **0 by an agent**.
- **Every payment carries a name.** `approved_by` must be non-blank, checked at
  the API and again inside the tool, and stored on the `payments` row.
- **Amounts must match.** Paying $9,999 against an $840 invoice is refused, as
  is a second payment on an invoice already marked paid.
- **Cash and stock cannot go negative.** Both write tools refuse rather than
  overdraw or oversell.
- **No invented shop facts.** Every number an agent states comes from a tool
  result.
- **Runs are bounded.** 8 model requests and 12 tool calls per agent,
  delegation depth 2, 8 delegations per run.
- **Nothing happens unlogged.** Every loop step, approval and reset is appended
  to `output/audit_trail.json`. It is JSON Lines and append-only.
- **The log outranks the prose.** Where a model's own summary disagrees with the
  audit trail, the trail is the evidence. On ticket 101 it caught the Boss
  reporting three consultations when it had made one.

Full write-up in [`output/harness.md`](output/harness.md); the run itself, with
plan-versus-actual and the cash ledger, is in
[`output/desk_tickets.html`](output/desk_tickets.html).
