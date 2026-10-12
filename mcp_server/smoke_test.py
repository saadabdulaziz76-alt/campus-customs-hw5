"""Problem 4 — connect to the MCP server as a client and exercise all three tools.

Launches `server.py` as a real subprocess over stdio, exactly as the entry in
.mcp.json does, performs the MCP handshake, calls each tool, and independently
re-queries the SQLite file to confirm the returned values match the database.
Evidence is written to output/mcp_smoke.json.
"""

from __future__ import annotations

import asyncio, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "mcp_smoke.json"
CFG = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["campus-customs-backoffice"]


def _abs(value: str) -> str:
    """Resolve a path from .mcp.json against the repo root.

    The registration stores relative paths so the repository runs anywhere.
    Joining without .resolve() keeps the virtualenv's bin/python a venv path
    rather than following the symlink out to the base interpreter.
    """
    path = Path(value)
    return value if path.is_absolute() else str(ROOT / path)


CFG = {**CFG, "command": _abs(CFG["command"]), "args": [_abs(a) for a in CFG["args"]]}
if not Path(CFG["command"]).exists():
    CFG["command"] = sys.executable


def db(sql, params=()):
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute(sql, params).fetchall()]


async def main() -> int:
    # The checks below compare tool output against the shop's *opening* position
    # — an unpaid invoice 501 and an unpaid rent. Running them against a database
    # that has already been worked produces confusing failures, so say so plainly.
    if db("SELECT COUNT(*) AS n FROM payments")[0]["n"]:
        print("This smoke test needs a clean database.\n"
              "  cp data/campus_customs.db data/campus_customs_new.db\n"
              "then run it again.", file=sys.stderr)
        return 1

    transport = StdioTransport(command=CFG["command"], args=CFG["args"])
    checks_all_passed = True
    evidence = {
        "problem": "4 — Add the MCP server to the vibe coder and test each tool",
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mcp_server": "campus-customs-backoffice",
        "transport": "stdio (real MCP handshake, launched from .mcp.json)",
        "connection_json": CFG,
        "database": str(DB.relative_to(ROOT.parent.parent.parent)),
        "tools": [],
    }

    async with Client(transport) as client:
        listed = [t.name for t in await client.list_tools()]
        evidence["tools_discovered"] = listed
        print("connected. tools discovered:", listed)

        # ---------------- tool 1 : ticket 101 ----------------
        prompt = ("Ticket 101 — Tauhid Zaman wants a Bulldog tee, CC-TEE-WHITE, in size S. "
                  "Do we have it, and if not when can we get it? The ticket references invoice 501.")
        args = {"sku": "CC-TEE-WHITE", "size": "S", "invoice_id": 501}
        out = (await client.call_tool("check_item_availability", args)).data

        inv_row = db("SELECT qty FROM inventory WHERE sku=? AND size=?", ("CC-TEE-WHITE", "S"))[0]
        invoice = db("""SELECT i.amount, i.status, i.due_date, v.name AS vendor, v.lead_days
                        FROM invoices i JOIN vendors v ON v.id=i.vendor_id WHERE i.id=501""")[0]
        checks = [
            ("on_hand matches inventory.qty", out["on_hand"], inv_row["qty"]),
            ("other_sizes matches inventory", out["other_sizes"],
             {r["size"]: r["qty"] for r in db(
                 "SELECT size,qty FROM inventory WHERE sku=? AND size<>? ORDER BY size",
                 ("CC-TEE-WHITE", "S"))}),
            ("inbound vendor matches vendors.name", out["inbound_restock"][0]["vendor"], invoice["vendor"]),
            ("inbound amount matches invoices.amount", out["inbound_restock"][0]["amount"], invoice["amount"]),
            ("inbound lead_days matches vendors.lead_days", out["inbound_restock"][0]["vendor_lead_days"], invoice["lead_days"]),
            ("today matches desk.date_today", out["today"], db("SELECT date_today FROM desk")[0]["date_today"]),
        ]
        evidence["tools"].append(_record(1, 101, prompt, "check_item_availability", args, out, checks))
        checks_all_passed &= all(a == b for _, a, b in checks)

        # ---------------- tool 2 : ticket 102 ----------------
        prompt = ("Ticket 102 — Elm City Properties says rent is due in two days. "
                  "What do we owe in total right now, and does our cash cover it?")
        args = {}
        out = (await client.call_tool("review_cash_and_obligations", args)).data

        cash = db("SELECT balance FROM cash_accounts WHERE name='checking'")[0]["balance"]
        rent = db("SELECT monthly_rent, next_due FROM leases WHERE id=1")[0]
        inv = db("SELECT amount, due_date FROM invoices WHERE id=501")[0]
        checks = [
            ("total_cash matches cash_accounts.balance", out["total_cash"], cash),
            ("total_owed = invoice + rent", out["total_owed"], round(inv["amount"] + rent["monthly_rent"], 2)),
            ("remaining = cash - owed", out["remaining_if_all_paid"],
             round(cash - inv["amount"] - rent["monthly_rent"], 2)),
            ("obligation count", len(out["obligations"]), 2),
            ("rent amount matches leases.monthly_rent",
             next(o["amount"] for o in out["obligations"] if o["kind"] == "rent"), rent["monthly_rent"]),
            ("invoice is flagged overdue (due 2026-08-28 vs today 2026-08-31)",
             next(o["overdue"] for o in out["obligations"] if o["kind"] == "invoice"), True),
            ("payments table still empty", out["payments_already_made"], []),
        ]
        evidence["tools"].append(_record(2, 102, prompt, "review_cash_and_obligations", args, out, checks))
        checks_all_passed &= all(a == b for _, a, b in checks)

        # ---------------- tool 3 : ticket 103 ----------------
        prompt = ("Ticket 103 — the Yale AI Club wants 20 navy hoodies in size M and is asking for a "
                  "bulk discount. Can we fill it, and what does $40 a unit do to our margin?")
        args = {"sku": "CC-HOOD-NAVY", "size": "M", "qty": 20, "proposed_unit_price": 40.0}
        out = (await client.call_tool("price_bulk_order", args)).data

        stock = db("SELECT qty FROM inventory WHERE sku=? AND size=?", ("CC-HOOD-NAVY", "M"))[0]["qty"]
        pr = db("SELECT unit_cost, list_price FROM pricing WHERE sku=?", ("CC-HOOD-NAVY",))[0]
        checks = [
            ("qty_on_hand matches inventory.qty", out["qty_on_hand"], stock),
            ("shortfall = 20 - on_hand", out["shortfall"], 20 - stock),
            ("unit_cost matches pricing.unit_cost", out["unit_cost"], pr["unit_cost"]),
            ("list_price matches pricing.list_price", out["list_price"], pr["list_price"]),
            ("margin_per_unit = quote - cost", out["margin_per_unit"], round(40.0 - pr["unit_cost"], 2)),
            ("below_cost false at $40 (cost is 22)", out["below_cost"], False),
        ]
        evidence["tools"].append(_record(3, 103, prompt, "price_bulk_order", args, out, checks))
        checks_all_passed &= all(a == b for _, a, b in checks)

    evidence["all_checks_passed"] = checks_all_passed
    evidence["summary"] = (
        f"{len(evidence['tools'])} tools called over a real MCP stdio connection; "
        f"{sum(len(t['verification']) for t in evidence['tools'])} values cross-checked "
        f"against {DB.name}; all matched." if checks_all_passed else "SOME CHECKS FAILED"
    )
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)}  | all checks passed: {checks_all_passed}")
    return 0 if checks_all_passed else 1


def _record(n, ticket, prompt, tool, args, out, checks):
    ver = [{"check": c, "tool_returned": a, "database_says": b, "match": a == b} for c, a, b in checks]
    for v in ver:
        print(f"   {'OK ' if v['match'] else 'XX '} {v['check']}: {v['tool_returned']!r}")
    return {
        "n": n,
        "unlocks_ticket": ticket,
        "prompt_asked": prompt,
        "tool_name": tool,
        "arguments": args,
        "tool_output": out,
        "verification": ver,
        "all_match": all(v["match"] for v in ver),
    }


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
