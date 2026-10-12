"""Campus Customs back-office MCP server.

Every agent in this homework reads the shop's data through these tools, so that
nothing is answered from memory. The tools are strictly read-only and return
only values that exist in `data/campus_customs_new.db`. Where a record is
missing, the tool says so explicitly rather than guessing — an agent cannot
invent a price or a stock level it was never given.

Run (stdio):  python server.py
Run (HTTP) :  python server.py --http      # port 8013
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
DB_PATH = HERE.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs-backoffice")


# --------------------------------------------------------------------------- db

def _rows(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query and return plain dicts."""
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _write(sql: str, params: tuple = ()) -> int:
    """Run a statement that changes data. Used only by the three write tools."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


def _today() -> str:
    """The shop's current date, taken from the `desk` table — never the wall clock."""
    rows = _rows("SELECT date_today FROM desk LIMIT 1")
    return rows[0]["date_today"] if rows else ""


def _days_until(due: str, today: str) -> int | None:
    """Whole days from `today` to `due`. Negative means already overdue."""
    try:
        return (date.fromisoformat(due[:10]) - date.fromisoformat(today[:10])).days
    except (ValueError, IndexError):
        return None


# ------------------------------------------------------------------ ticket 101

@mcp.tool
def check_item_availability(sku: str, size: str, invoice_id: int | None = None) -> dict:
    """Can we fill an order for this item in this size, and if not, when?

    Stock is held per (sku, size), so a shirt can be well stocked overall and
    still unavailable in the size a customer asked for. When the item is short,
    this also reports any open supplier invoice covering a reprint of it, with
    that vendor's lead time, so the answer can be a date rather than a promise.

    Args:
        sku: catalogue code, e.g. "CC-TEE-WHITE".
        size: the exact size requested, e.g. "S". Sizes are not interchangeable.
        invoice_id: optional. If the ticket names an invoice, pass it to tie the
            restock to that exact record instead of matching on description text.

    Returns:
        on_hand for the requested size, the other sizes that are stocked, and
        any inbound reprint with its vendor and expected lead time.
    """
    today = _today()
    item = _rows(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
        (sku, size),
    )
    if not item:
        known = _rows("SELECT DISTINCT sku FROM inventory ORDER BY sku")
        return {
            "found": False,
            "sku": sku,
            "size": size,
            "error": f"No inventory record for {sku} in size {size}.",
            "known_skus": [r["sku"] for r in known],
        }

    row = item[0]
    others = _rows(
        "SELECT size, qty FROM inventory WHERE sku = ? AND size <> ? ORDER BY size",
        (sku, size),
    )
    price = _rows("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))

    # Inbound restock: the ticket's invoice if given, otherwise open invoices
    # whose description names this SKU.
    if invoice_id is not None:
        inv = _rows(
            """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                      v.name AS vendor, v.lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.id = ?""",
            (invoice_id,),
        )
    else:
        inv = _rows(
            """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                      v.name AS vendor, v.lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status <> 'paid' AND i.description LIKE ?""",
            (f"%{sku}%",),
        )

    inbound = []
    for r in inv:
        days = _days_until(r["due_date"], today)
        inbound.append({
            "invoice_id": r["id"],
            "vendor": r["vendor"],
            "amount": r["amount"],
            "status": r["status"],
            "due_date": r["due_date"],
            "days_until_due": days,
            "overdue": days is not None and days < 0,
            "description": r["description"],
            "vendor_lead_days": r["lead_days"],
            "earliest_arrival_if_started_today": (
                (date.fromisoformat(today[:10]) + timedelta(days=r["lead_days"])).isoformat()
                if today else None
            ),
            "note": "Lead time runs from when the vendor starts. This invoice is "
                    "not yet paid." if r["status"] != "paid" else "",
        })

    return {
        "found": True,
        "today": today,
        "sku": sku,
        "name": row["name"],
        "size": size,
        "on_hand": row["qty"],
        "in_stock": row["qty"] > 0,
        "location": row["location"],
        "other_sizes": {r["size"]: r["qty"] for r in others},
        "unit_cost": price[0]["unit_cost"] if price else None,
        "list_price": price[0]["list_price"] if price else None,
        "inbound_restock": inbound,
    }


# ------------------------------------------------------------------ ticket 102

@mcp.tool
def review_cash_and_obligations() -> dict:
    """What the shop owes, when, and whether the cash on hand covers all of it.

    Rent and supplier invoices are separate tickets but they draw on one
    balance, so they have to be judged together. This returns every unpaid
    obligation with its due date measured against the shop's current date, the
    combined total, and what would be left afterwards.

    Returns:
        Account balances, each obligation with days until due, the combined
        total, and the shortfall or remainder against available cash.
    """
    today = _today()
    accounts = _rows("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    total_cash = sum(a["balance"] for a in accounts)

    obligations = []
    for r in _rows(
        """SELECT i.id, i.amount, i.due_date, i.status, i.description, v.name AS vendor
           FROM invoices i JOIN vendors v ON v.id = i.vendor_id
           WHERE i.status <> 'paid' ORDER BY i.due_date"""
    ):
        days = _days_until(r["due_date"], today)
        obligations.append({
            "kind": "invoice", "ref_id": r["id"], "payee": r["vendor"],
            "amount": r["amount"], "due_date": r["due_date"],
            "days_until_due": days, "overdue": days is not None and days < 0,
            "status": r["status"], "description": r["description"],
        })

    for r in _rows("SELECT id, space_name, landlord, monthly_rent, next_due FROM leases"):
        paid = _rows(
            "SELECT 1 FROM payments WHERE kind = 'rent' AND ref_id = ? LIMIT 1", (r["id"],)
        )
        if paid:
            continue
        days = _days_until(r["next_due"], today)
        obligations.append({
            "kind": "rent", "ref_id": r["id"], "payee": r["landlord"],
            "amount": r["monthly_rent"], "due_date": r["next_due"],
            "days_until_due": days, "overdue": days is not None and days < 0,
            "status": "unpaid", "description": f"Rent for {r['space_name']}",
        })

    obligations.sort(key=lambda o: (o["days_until_due"] is None, o["days_until_due"]))
    total_owed = sum(o["amount"] for o in obligations)
    paid_rows = _rows("SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments")

    return {
        "today": today,
        "accounts": accounts,
        "total_cash": round(total_cash, 2),
        "obligations": obligations,
        "total_owed": round(total_owed, 2),
        "remaining_if_all_paid": round(total_cash - total_owed, 2),
        "covers_everything": total_cash >= total_owed,
        "payments_already_made": paid_rows,
        "note": "Nothing here has been paid. Writing a payment is a separate, "
                "irreversible action that records who approved it.",
    }


# ------------------------------------------------------------------ ticket 103

@mcp.tool
def price_bulk_order(sku: str, size: str, qty: int, proposed_unit_price: float | None = None) -> dict:
    """Price a bulk request and check whether we can actually fill it.

    A discount request has two separate problems: whether the quantity exists in
    that size, and whether the price clears cost. This returns the stock
    shortfall and the real margin, using `pricing.unit_cost` as a hard floor, so
    a discount can be judged instead of guessed.

    Args:
        sku: catalogue code, e.g. "CC-HOOD-NAVY".
        size: the size requested, e.g. "M".
        qty: how many units the customer wants.
        proposed_unit_price: optional. A price to evaluate. Omit to price at list.

    Returns:
        On-hand versus requested, the cost floor, and the margin at both list
        price and the proposed price.
    """
    price = _rows("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not price:
        return {"found": False, "sku": sku,
                "error": f"No pricing record for {sku}; cannot quote a price for it."}

    stock = _rows("SELECT name, qty FROM inventory WHERE sku = ? AND size = ?", (sku, size))
    if not stock:
        return {"found": False, "sku": sku, "size": size,
                "error": f"No inventory record for {sku} in size {size}."}

    unit_cost, list_price = price[0]["unit_cost"], price[0]["list_price"]
    on_hand = stock[0]["qty"]
    quoted = list_price if proposed_unit_price is None else float(proposed_unit_price)
    fillable = min(on_hand, qty)

    return {
        "found": True,
        "sku": sku,
        "name": stock[0]["name"],
        "size": size,
        "qty_requested": qty,
        "qty_on_hand": on_hand,
        "qty_fillable_now": fillable,
        "shortfall": max(qty - on_hand, 0),
        "can_fill_in_full": on_hand >= qty,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "quoted_unit_price": quoted,
        "discount_vs_list_pct": round((1 - quoted / list_price) * 100, 2) if list_price else None,
        "margin_per_unit": round(quoted - unit_cost, 2),
        "margin_pct": round((quoted - unit_cost) / quoted * 100, 2) if quoted else None,
        "below_cost": quoted < unit_cost,
        "revenue_if_filled_now": round(quoted * fillable, 2),
        "margin_if_filled_now": round((quoted - unit_cost) * fillable, 2),
        "floor_note": f"unit_cost is {unit_cost}; any price at or below this loses money on every unit.",
    }



# ===========================================================================
# Added in Problem 5 — the tools the agent team needs to work the tickets.
# Reads first, then the three tools that change data.
# ===========================================================================


@mcp.tool
def list_open_tickets(status: str = "open") -> dict:
    """The shop's inbox: every ticket at this status, newest last.

    Start here. Each ticket names the SKU, lease or invoice it depends on, which
    tells you which other tool to call next.

    Args:
        status: "open", "closed", or "all". Defaults to open work.
    """
    if status == "all":
        rows = _rows("SELECT * FROM tickets ORDER BY created_at")
    else:
        rows = _rows("SELECT * FROM tickets WHERE status = ? ORDER BY created_at", (status,))
    return {"today": _today(), "count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket with the records it points at already looked up.

    Saves a round trip: the linked inventory row, pricing, invoice, vendor and
    lease come back with the ticket instead of needing separate calls.

    Args:
        ticket_id: the ticket number, e.g. 101.
    """
    rows = _rows("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if not rows:
        return {"found": False, "ticket_id": ticket_id,
                "error": f"No ticket with id {ticket_id}."}
    t = rows[0]
    linked: dict = {}
    if t.get("sku"):
        if t.get("size"):
            inv = _rows("SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
                        (t["sku"], t["size"]))
            linked["inventory"] = inv[0] if inv else None
        pr = _rows("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (t["sku"],))
        linked["pricing"] = pr[0] if pr else None
    if t.get("invoice_id"):
        inv = _rows("""SELECT i.*, v.name AS vendor, v.lead_days, v.specialty
                       FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?""",
                    (t["invoice_id"],))
        linked["invoice"] = inv[0] if inv else None
    if t.get("lease_id"):
        ls = _rows("SELECT * FROM leases WHERE id = ?", (t["lease_id"],))
        linked["lease"] = ls[0] if ls else None
    return {"found": True, "today": _today(), "ticket": t, "linked": linked}


@mcp.tool
def list_vendors() -> dict:
    """Every supplier with what they make and how many days they take.

    Use `lead_days` to turn "we will reorder" into an actual date.
    """
    return {"today": _today(), "vendors": _rows("SELECT * FROM vendors ORDER BY id")}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """One lease: the space, the landlord, the rent and when it is next due."""
    rows = _rows("SELECT * FROM leases WHERE id = ?", (lease_id,))
    if not rows:
        return {"found": False, "lease_id": lease_id, "error": f"No lease with id {lease_id}."}
    lease = rows[0]
    paid = _rows("SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ?", (lease_id,))
    days = _days_until(lease["next_due"], _today())
    return {"found": True, "today": _today(), "lease": lease,
            "days_until_due": days, "overdue": days is not None and days < 0,
            "payments_against_this_lease": paid, "already_paid": bool(paid)}


# --------------------------------------------------------------- write tools

@mcp.tool
def record_payment(kind: str, ref_id: int, amount: float, account: str, approved_by: str,
                   note: str = "") -> dict:
    """Pay an invoice or the rent. **This spends real money and cannot be undone.**

    Refuses rather than overdraws: the payment is rejected if the account does
    not hold the full amount, if no approver is named, or if this invoice or
    lease has already been paid. On success it writes the payment, moves the
    cash and marks the invoice paid, as one transaction.

    Args:
        kind: "invoice" or "rent".
        ref_id: the invoice id, or the lease id for rent.
        amount: dollars to pay. Must match what is actually owed.
        account: which cash account to draw on, e.g. "checking".
        approved_by: the human who authorised this. Never leave blank or put an
            agent's name here — this is the audit record of who is accountable.
        note: optional free text for the audit trail.
    """
    kind = (kind or "").strip().lower()
    if kind not in ("invoice", "rent"):
        return {"ok": False, "error": "kind must be 'invoice' or 'rent'."}
    if not (approved_by or "").strip():
        return {"ok": False, "error": "approved_by is required. A person must authorise a payment."}

    acct = _rows("SELECT name, balance FROM cash_accounts WHERE name = ?", (account,))
    if not acct:
        return {"ok": False, "error": f"No cash account named {account!r}."}
    balance = acct[0]["balance"]

    if kind == "invoice":
        rec = _rows("SELECT id, amount, status FROM invoices WHERE id = ?", (ref_id,))
        if not rec:
            return {"ok": False, "error": f"No invoice with id {ref_id}."}
        if rec[0]["status"] == "paid":
            return {"ok": False, "error": f"Invoice {ref_id} is already marked paid."}
        owed = rec[0]["amount"]
    else:
        rec = _rows("SELECT id, monthly_rent FROM leases WHERE id = ?", (ref_id,))
        if not rec:
            return {"ok": False, "error": f"No lease with id {ref_id}."}
        owed = rec[0]["monthly_rent"]

    dup = _rows("SELECT id FROM payments WHERE kind = ? AND ref_id = ?", (kind, ref_id))
    if dup:
        return {"ok": False, "error": f"Already paid: {kind} {ref_id} has payment {dup[0]['id']}."}
    if abs(amount - owed) > 0.005:
        return {"ok": False, "error": f"Amount {amount} does not match the {owed} owed on {kind} {ref_id}."}
    if amount > balance:
        return {"ok": False, "error": f"Insufficient funds: {account} holds {balance}, payment is {amount}.",
                "balance": balance, "shortfall": round(amount - balance, 2)}

    paid_at = _today()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by)
               VALUES (?,?,?,?,?,?)""", (kind, ref_id, amount, account, paid_at, approved_by))
        payment_id = cur.lastrowid
        conn.execute("UPDATE cash_accounts SET balance = balance - ? WHERE name = ?", (amount, account))
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
        conn.commit()

    new_balance = _rows("SELECT balance FROM cash_accounts WHERE name = ?", (account,))[0]["balance"]
    return {"ok": True, "payment_id": payment_id, "kind": kind, "ref_id": ref_id,
            "amount": amount, "account": account, "approved_by": approved_by,
            "paid_at": paid_at, "note": note,
            "balance_before": balance, "balance_after": round(new_balance, 2)}


@mcp.tool
def adjust_inventory(sku: str, size: str, delta: int, reason: str) -> dict:
    """Move stock up or down for one size. Negative `delta` fulfils an order.

    Refuses to take a size below zero — the shop cannot ship what it does not
    have, and a negative row would hide that from everyone downstream.

    Args:
        sku: catalogue code.
        size: the exact size being moved.
        delta: units to add (positive) or remove (negative).
        reason: why, in a few words. Goes in the response for the audit trail.
    """
    rows = _rows("SELECT qty, name FROM inventory WHERE sku = ? AND size = ?", (sku, size))
    if not rows:
        return {"ok": False, "error": f"No inventory record for {sku} size {size}."}
    before = rows[0]["qty"]
    after = before + int(delta)
    if after < 0:
        return {"ok": False, "error": f"Refused: {sku} size {size} holds {before}; "
                                      f"a change of {delta} would leave {after}.",
                "qty_on_hand": before, "requested_delta": delta}
    _write("UPDATE inventory SET qty = ? WHERE sku = ? AND size = ?", (after, sku, size))
    return {"ok": True, "sku": sku, "name": rows[0]["name"], "size": size,
            "qty_before": before, "delta": int(delta), "qty_after": after, "reason": reason}


@mcp.tool
def close_ticket(ticket_id: int, status: str, resolution: str) -> dict:
    """Mark a ticket resolved and record what was decided.

    The resolution is appended to the ticket's notes so the reasoning survives
    after the chat is gone.

    Args:
        ticket_id: which ticket.
        status: "closed", "open", or "blocked" if it needs a human.
        resolution: what was decided and why, in a sentence or two.
    """
    allowed = {"open", "closed", "blocked"}
    if status not in allowed:
        return {"ok": False, "error": f"status must be one of {sorted(allowed)}."}
    rows = _rows("SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,))
    if not rows:
        return {"ok": False, "error": f"No ticket with id {ticket_id}."}
    notes = (rows[0]["notes"] or "").strip()
    merged = f"{notes}\n[{_today()}] {status.upper()}: {resolution}".strip()
    _write("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, merged, ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "status_before": rows[0]["status"],
            "status_after": status, "resolution": resolution}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Campus Customs back-office MCP server")
    ap.add_argument("--http", action="store_true", help="serve Streamable HTTP on port 8013")
    args = ap.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8013)
    else:
        mcp.run()
