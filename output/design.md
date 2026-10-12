# The Desk — design notes

What I chose for the Campus Customs dashboard, and why. The brief was "creative
but not too much, subtle colours, and it should feel good to use" — so most of
these decisions are about restraint and warmth rather than decoration.

---

## The starting thought

This is a back-office board. Somebody sits in front of it while three tickets
and a few thousand dollars are on the line, and they look at it for a long time.
That ruled out two obvious directions straight away: a bright SaaS dashboard
(tiring at length, and it treats money decisions as cheerful) and a dense
operations console (accurate, but it makes the person feel like a data-entry
clerk).

What I went for instead is **a quiet desk**. Calm enough to sit with, warm
enough that you do not feel like you are operating machinery.

## Colour

**Charcoal base, warm not blue.** The background is `#15171a` with a faint
amber glow at the top-left and a cold blue one at the top-right, both at about
6% opacity. Almost nobody will notice them, but they stop the page reading as a
flat grey rectangle. Body text is `#eceae5` — a warm off-white, never pure
`#fff`, which is harsh on a dark field.

**One accent per colleague, all muted.** Five people, five colours, none of them
saturated:

| | | |
|---|---|---|
| Morgan, Shop Manager | brass `#c9a227` | the only warm "authority" colour on the page |
| Priya, Inventory | sage `#7a9e7e` | |
| Dan, Bookkeeper | slate blue `#6d8bb0` | |
| Rosa, Facilities | clay `#c08457` | |
| Theo, Customer Service | lilac `#9b8bb4` | |

These are desaturated on purpose. Five bright colours on one screen is a
carnival; five muted ones read as a team. Each colleague's avatar, status line,
quote bar and summary row all use their own colour, so you learn who is who
without reading names after the first run.

**Status colours stay in that family** — sage for resolved, clay for blocked,
brass for open. No red-amber-green traffic light, because that is the visual
language of alarms and most of what happens here is not an alarm.

**One deliberate break: the draft customer reply sits on paper.** It is the only
light element on the page — cream `#f3efe7` with dark ink and a brass left edge.
That is not decoration. It is the one piece of text that leaves the building and
gets read by a customer, so it is shown the way they will see it: on paper, not
on a console. It is the single most "designed" moment and it earns its place by
meaning something.

## Motion

Almost none, and all of it functional.

- The active colleague's card **lifts 2px and gains a soft glow in their colour**, so your eye finds who is working without hunting.
- A small dot **breathes** next to their status — slow, 1.4s, not a spinner. Spinners say "wait"; breathing says "thinking".
- The outcome panel **rises in** over 0.45s, so a long answer does not just appear and jar you.
- The cash figure **nudges upward and warms to brass for 1.8 seconds** when it changes. This is the most important animation on the page: money moving should be felt, not just displayed.
- Everything is disabled under `prefers-reduced-motion`.

Colleagues who were not involved stay at **62% opacity** rather than disappearing. You can still see the whole team, and the dimming tells you honestly that Priya and Dan were not asked — which, as it turns out, is a real finding about how the Boss delegates.

## Making it feel like people

This is the part the brief asked for most directly, so it got the most thought.

**The agents have names.** Morgan, Priya, Dan, Rosa, Theo — not "Inventory
Agent" and "Accounting Agent". You ask a colleague for help; you invoke a
service. The whole emotional register of the page changes with that one choice,
and it costs nothing.

**They do human things, described in human words.** The board never says
`check_item_availability`. It says *"checked stock"*, *"checked the books"*,
*"asked Theo"*, *"looked at the lease"*. The tool names are in the audit trail
for anyone who wants them; the board is for the person.

**The greeting knows the time of day.** "Good morning", "Good evening", and
after 9pm, "Working late" — because somebody will be, and being noticed is a
small kindness.

**The header counts the queue in plain English** — "There are 2 tickets
waiting", and when it empties, *"The queue is clear — nice work."* Finishing
should feel like finishing.

**Approvals are signed, and thanked.** You type your name before you can approve
a payment, and afterwards the board says *"Thank you, Saad. Paid — balance is
now $2,560.00."* Using the first name is deliberate: it is the moment a person
takes responsibility for real money, and it should feel like a handshake rather
than a form submission. The fine print underneath — *"Your name goes on the
record. The agents can prepare a payment, but only a person can authorise one"* —
is reassurance as much as rule.

**The waiting message is honest.** *"Give them a moment — they check the real
numbers before answering."* It explains the delay instead of apologising for it,
and it tells you something true about why this system is slower than a chatbot.

**The footer thanks you for keeping an eye on things.** And when the backend is
down it says so plainly, with the command to fix it, rather than failing in
silence.

**"Fresh start"** rather than "Reset database". Same action, no dread.

## Layout

Two columns. **Tickets on the left** in a narrow fixed rail — they are the
agenda and do not change much. **The team and the outcome on the right**, wide,
because that is where everything happens. Below the tickets sits a small "Still
to settle" list, so what you owe is visible at the same time as what you are
deciding — the squeeze between $3,400 of cash and $3,240 of obligations is the
whole drama of this scenario, and the layout should not hide it.

On narrow screens it stacks to one column, tickets first.

## What I deliberately did not do

- **No charts.** Three tickets and one bank balance do not need visualisation.
- **No live-streaming token counter.** It is in the footer of the result where it belongs, not competing with the decision.
- **No raw event log on the main board.** The audit trail is complete and available through `/api/events`; putting it on screen would bury the five sentences that actually matter.
- **No confetti, no celebration on approval.** Paying an $840 overdue invoice is a relief, not a party.

## Verified in the browser

| Requirement | |
|---|---|
| 1 · Lists all three tickets | ✅ with state chips and a plain-English line each |
| 2 · Pick one and start the team | ✅ "Ask the team" → background run |
| 3 · Shows each agent live | ✅ active card lifts, breathing dot, plain-English status |
| 4 · Marks resolved when done | ✅ 101 went `open` → `blocked` → `resolved` after approval |
| 5 · Summary of what each agent did | ✅ "Who did what", colour-coded per colleague |
| 6 · Human approves a payment | ✅ name required, then thanked by name |
| 7 · Balance drops after approval | ✅ **$3,400.00 → $2,560.00**, with the brass flash |

`tsc -b` passes clean.
