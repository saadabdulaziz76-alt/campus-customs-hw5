# AI Prompts — Homework 5

A log of what I typed to the AI assistant while building this assignment, in
order. One section per problem. Prompts are recorded as I actually sent them,
not cleaned up after the fact — the point of the log is what was really asked.

Tool: Claude (Anthropic), used through Claude Code with file access and a
terminal.

---

## Problem 1 — Vibe Coder Prompt

### Prompt

> Problem 1, title "Vibe Coder Prompt": Create "AI_prompts.md" and keep it
> update throughout this assignment, I want it to keep updating as I work. This
> file is the log of what I typed to you. Obviously, every problem will be
> described to you in my own words. Put one section for each problem, each
> sesion should include: 1) the problem number and title. 2) at least one prompt
> that I have typed. 3) one follow-up prompt if I needed to do that (one
> sentence on what was lacking the first prompt). Thanks, this problem 1

### Follow-up prompt

None needed.

### Notes

Before this, I asked for a joke file to confirm the assistant was writing into
the right folder (`Homework/HW 5/`). That check is why the rest of the
assignment landed in the correct place.

---

## Problem 2 — Study the Campus Customs Database

### Prompt

> Problem 2, title " Study the campus customs database", open the
> "data/campus_customs.db" and look through every table and its fields. I want.
> you to copy the original file to "data/campus_customs_new.db". Later problems
> update that working copy. Study the three open tickets so you see how they link
> to other tables. Start "output/harness.md". For each table, list the fields and
> one short line on why that table matters for the agents. You will keep growing
> this harness file in later problems. thanks and this is it for problem 2. FYI,
> I have added the data folder in the HW5 folder.

### Follow-up prompt

None needed.

### Notes

Nine tables, not the four from HW 4 — this is a back-office operations database
rather than a storefront one. The useful finding was that the three tickets are
not independent: they compete for a single $3,400 cash balance against $3,240 of
obligations.

---

## Problem 3 — Build the MCP Server

### Prompt

> Problem 3, title "Build the MCP server", write an MCP server in "mcp_server/"
> using FastMCP. it will talk to "data/campus_customs_new.db". no need to connect
> or run it in this problem. Every agent in this homework uses the tools in this
> MCP server. more tools will be added to it later. For now, write three tools you
> know you will need for the tickets in the database. Keep the names clear.
> Please, NEVER invent any data, only use information in the database. IN
> "output/harness.md", list each of your three MCP tools. For every tool, plese
> include: which tables it reads, which ticket it helps unlock (101,102 or 103),
> and one sentence on why that tool is the right one for that ticket. Vague line
> like "reads inventory" scores low, tie the tool to the ticket. I don't want you
> to score low. Also, please add a short "mcp_server/README.md" file that explains
> what the MCP server is for, which database file it uses, and the three tools it
> has. This is it for problem 3, don't mess up. Thanks

### Follow-up prompt

None needed.

### Notes

One tool per ticket, each named for the question it answers rather than the
table it touches. Although the problem said the server did not need to run, I
installed FastMCP and called all three tools against the real database to
confirm the numbers in the harness are measured rather than claimed.

---

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Prompt

> Problem 4, title " Add the MCP server to vibe coder and test each tool",
> please add my MCP server to this project so you can call the tools. Save the
> connection JSON text in ".mcp.json" at the project root (or however you save
> local MCP server lists). with you connected, please test each of my three MCP
> tools. Save the evidence in "output/mcp_smoke.json" For every tools, please
> include: 1) the prompt I asked you. 2) the tools name. 3) the tools output
> (must match values in "data/campus_sutoms_new.db". This is it for problem 4,
> please do it properly

### Follow-up prompt

None needed.

### Notes

Registered in both the project-root `.mcp.json` (so the tools are genuinely
available) and a copy at `HW 5/.mcp.json` (so the homework carries its own
connection JSON). Because MCP servers attach at session start, the test launches
the server over stdio using the exact command from the config and speaks real
MCP to it, rather than importing the module in-process. Each returned value is
compared against a fresh SQL query instead of a hard-coded expectation — 19
checks, all matching.

---

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Prompt

> Problem 5, title "Build the agent team and grow the MCP tools", Build the
> agentic team for campus customs using PydanticAI: Boss, Inventory, Accounting,
> Facilities and Customer Service. Inlcude prompts, models and agent loops so they
> can delegate work to each other with full connectivity and integration. Put the
> agent prompts in "backend/prompts/", one file per agent. Put data types in
> "backend/models.py" and the agent files under "backend/". My layout can vary as
> long as the five roles are claer. USe my PORTKEY_API_KEY and only gpt-6-luna for
> every agent. I want to prompts to be written in my own words of course with the
> shop rules that agent needs. More detailed prompt that cover all aspects of an
> agent's work and scope score higher than a short generic prompt. Add any tools
> the agent need to my MCP server so they can work on the open tickets. Shop facts
> come from the MCP server over "data/campus_customs_new.db". Do not invent a
> second shop-tools layer that bypasses MCP. Write the agent so they append to
> "output/audit_trail.json" as they run: foreach agent loop step, record enough to
> audit later please. Append this file (do not wipe it each run). In
> "output/harness.md", list each agent and each MCP tool (including ones added in
> this problem) along with which table the tool uses. Also, please add a short
> safet section: the guardrails a real business would want when the agents touch
> real customers and real money, plus limits that keep token use in check. Update
> "mcp_server/README.md" so the tool list matches what I have now. Please do it
> properly. thank you

### Follow-up prompt

None needed.

### Notes

Two real obstacles hit during this problem, both found by running rather than
assuming. gpt-6-luna **rejects function tools on `/v1/chat/completions`** and
needs the Responses API — the same constraint the Lecture 11 and 12 repos hit —
so `config.py` uses `OpenAIResponsesModel`. And my first audit call passed
`ticket_id` twice, which crashed the first ticket run; the agent work had
already succeeded, only the logging failed.

Seven MCP tools added (ten total). The agents have no database access of their
own: `backend/` never opens SQLite, and the only route to shop data is the
`MCPToolset` launched from the `.mcp.json` entry.

Across the live runs no money moved — all three tickets ended blocked pending
human approval, which is what the prompts and the write-tool guardrails are
supposed to produce.

---

## Problem 6 — Plan the Three Tickets

### Prompt

> Problem 6, title "Plan the three tickets", before writing the backend, write
> down what you expect the team to do on each open ticket. Build
> "output/desk_tickets.html", a page I can double-click with one tab per ticket
> (101,102 and 103). Also, add empty Cash and Reflection tabs for later problems
> (leave them empty or with a short "coming later" not for now). On each ticket
> tab, fill an Expected section only (leave room for an Actual section that will be
> filled after the agent is run). For each ticket's expected section, write: 1) who
> the Boss should call first and why. 2) All the agent delegations you expect - not
> "Boss calls everyone". 3) which MCP tools is expected to be run. Plans that send
> every specialist on every ticket score low, so please don't do that. A comparison
> must be done on this plan vs what actually happens when you (agent) resolve the
> ticket. I have personally no suggestion, use common practices to come up with the
> needed. Thanks and please do it properly

### Follow-up prompt

None needed.

### Notes

The problem says "before writing the backend", but the backend was already built
and run in Problem 5, so I could not write a blind prediction. The plans are
reasoned from the ticket data and standard practice; where they disagree with
the observed run, the disagreement is reported rather than the plan being edited
to match. Each ticket excludes at least one specialist with a stated reason.

---

## Problem 7 — Backend Routes

### Prompt

> Problem 7, title " Backend routes", the React frontend dashboard (the next
> problem) needs a backend it can call. In "backend/main.py", use FastAPI and add
> routed that do the following: 1) return the three tickets and whether each is
> open or resolved. 2) Take a ticket ID and run the agent team on that ticket. 3)
> return recent agent events, what each agent said an which tools they used, so the
> board can refresh. 4) Approve a payment or purchase after a human clicks approve
> (agents only prepare the pay; this route is what actually changes cash). 5)
> Return the current checking balance from "cash_accounts". 6) reset the database
> to the original values when tryin a fresh run is wanted. From the "backend/"
> folder, start the server with "uvicorn main:app --reload --port 8000". This turns
> on my backend at "http://localhost:8000" so the frontend dashboard can call those
> routes. In "output/harness.md", list each route in one line (what URL/ what it
> does). Thanks and pls don't mess it up.

### Follow-up prompt

None needed.

### Notes

The run route is asynchronous — it returns a `run_id` and works in the
background — because an agent run takes tens of seconds and a dashboard needs to
poll for progress rather than hang on one request.

Testing the approval route surfaced something the dashboard should show: the
Boss claimed in its `consulted` field to have asked three specialists, but the
events route proved it delegated to only one and did the other work itself. The
self-reported field and the audit trail disagree, and the audit trail is the one
to trust.

---

## Problem 8 — Agent Dashboard

### Prompt

> Problem 8, title " Agent dashboard", Build the frontend dashboard in
> "frontend/" with React + Vite + TypeScript. The page should call the routes
> built in Problem 7. At minimum, the board should: 1) List all three tickets. 2)
> Let me pick one ticket and start the agent team on it. 3) show each agent and
> what they are saying/doing while the ticket runs. 4) Mark a ticket resolved when
> the run finishes. 5) Show a short summary of what each agent did on that ticket.
> 6) Let a human approve a pay or purchase when asked. 7) Show the checking
> balance, it should drop after an approved pay. In terms of look and feel, please
> I want it to look good, I want it to be creative but no too much, use subtle
> colors. I want it to use thank you and some personal notes as people will use it
> and I want them to feel good. Tell the frontend to talk to the backend at
> "http://localhost:8000". On the backend, allow the Vite page origin (usually
> http://localhost:5173) so the browser allowed to call those routes. Start the
> board with "npm run dev". This open React desk in the browser so I can pick
> tickets and watch agents. Write "output/design.md" with what I chose for the look
> of the dashboard and why, including a creative choices that make it feel special
> and something humans would actually enjoy using!! pls do it properly

### Follow-up prompt

None needed.

### Notes

The agents were given names — Morgan, Priya, Dan, Rosa, Theo — rather than role
labels, and the board describes what they did in plain English ("checked the
books", "asked Theo") instead of tool names. Approvals are signed by name and
thanked by first name, because that is the moment a person takes responsibility
for real money.

Verified live in the browser rather than assumed: ran ticket 101, watched the
cards update, approved the $840 invoice, and confirmed the balance moved $3,400
to $2,560 with the ticket marked resolved.

---

## Problem 9 — Resolve the tickets

### Prompt sent

> Problem 9, title"Resolve the tickets". Before testing the agents on a full run
> over the three tickets, reset the working database "dat/campus_customs_new.db"
> agin so we can start clean. please note the starting checking balance. Then run
> all three tickets on the board (101,102 and 103) until each is resolved. Open
> "output/desk_tickets.html" from problem 6. on each ticket tab, fill the actual
> section from this run: which agents worked, what they delgated, and which tools
> they used. Keep your exepcted section so I can compare the two. On the Cash tab
> of the same "output/desk_tickets.html", itemize the money: 1) starting checking
> balance (after the reset). 2)for each ticket: how cash changes when that ticket
> got resovled, and why (which pay/purachse, dollar amount). 3) Ending checking
> balance, it must match "cah_accounts" in the working database. Wrong cash math
> loses points even if the board shows everyt ticket resolved (don't mess up).
> Also, save: 1) "output/resolved_tickets.json", for each ticket: ID, final
> status, short outcome, what each agent contributed, and any human approvals. 2)
> "output/resolved_board.html", a page I can double click with a screenshot of my
> React board for each resolved ticket (101,102 and 103). Append real runs to
> "output/audit_trial.json". Finish "output/harness.md" so it covers tables, MCP
> tool, the five agents, API routes, the dashboard and safety rules. Do it
> properly please, I need the full mark

### Follow-up prompt

None needed.

### Follow-up prompt — screenshot quality

> So I have one comment on the aulity of the photos on the website, can you make
> them better, I can't read

The board shots were compressed JPEGs captured at 1x and then displayed narrower
than they were captured — lossy, then shrunk. Re-captured with headless Chrome at
`--force-device-scale-factor=2` as PNG (2880px wide), the figures were given a
breakout width so they render at the full 1440px they were captured at, and each
one now opens full size on click. Effective ratio is exactly 2.00x.

### Follow-up prompt — the five reflection questions

> I am supposed to answer the following questions and have them written in
> "output/desk_tickets.html". 1) How would you evaluate the performance of the
> agents on each ticket and why? 2) for each ticket, how did Actual compare to the
> expected plan you wrote earlier? 3)What would have been simpler as one agent with
> tools, and why? 4) Describe three new problems Campus Customs might face that this
> agent team could solve with the tools built. 5)Describe three new problems Campus
> Customs might face that this agent team could not solve with the tolls you built
> and explain the tools and agents you would need to solve them. Tie every answer to
> this app and the three tickets you ran - use ticket tabs and cash tabs on the same
> page as your evidence. Generic AI essays without campus customs detials will score
> low.

### Follow-up prompt — more detail in the answers

> I don't like the answers, make them more detailed please

Rebuilt the Reflection tab from a call-by-call reconstruction of the audit trail
rather than from summaries: per-agent token accounting, timestamped traces, and
a five-criterion rubric for the performance question.

Re-counting turned up a figure that had been quoted wrongly. The `usage` object
on a run counts only the **Boss**, because that is the agent the API
orchestrates — the specialists are invoiced inside their own sub-runs. True
whole-team totals are **32 model calls and 100,943 input tokens**, not 16 and
57,091. The ticket Actual cards now label both numbers, and the gap between them
became the measurement behind question 3: delegation added **+77%** to the token
bill of this run, and **+124%** on ticket 102 alone.

Three other findings came out of the recount and are now load-bearing:
`consult_teammate` was called **zero** times, so the peer network exists only in
code; on ticket 102 the Boss emitted `ask_accounting` and
`review_cash_and_obligations` in the **same model response**, delegating a
question and answering it simultaneously; and Customer Service was handed
"$2,560 … $2,400 … leaving $160" in its brief and re-fetched the cash anyway.

Every numeric claim on the tab is checked by script against the audit trail and
the database — including the arithmetic in the prose. One error was caught that
way: total wall clock read 49.9s and is actually **29.9s**.

### Notes

Two things in the prompt had no existing route to satisfy them honestly, and
both were built rather than worked around.

**Resolving a ticket that costs nothing.** Tickets 101 and 102 resolve through
`POST /api/approvals`, which records a payment and closes the ticket together.
Ticket 103 involves no payment, so closing it that way would have meant writing
a transaction that never happened — and the cash math would then be wrong by
construction. `POST /api/tickets/{id}/resolve` was added instead: a named human
accepting the team's recommendation, logged as a `resolution` event, with no
cash tool touched.

**Screenshotting a resolved ticket.** The board only showed a run while it was
in memory, so the only way to screenshot ticket 101's detail view was to run it
again — which would have re-blocked a resolved ticket and corrupted the very
state being captured. The board now accepts `?ticket=101&run=ee15b0fe0c60` and
rehydrates a finished run from the API, so the record can be reopened and
photographed without re-running anything.

The cash figure was not asserted anywhere. It was read back from
`cash_accounts`, cross-checked against `SUM(amount)` on `payments`, against
`GET /api/cash`, and against what the dashboard header renders — five
independent views, all $160.00.

The "actual" sections record what the audit trail shows, not what the models
said about themselves. On ticket 101 those disagree: the Boss claimed three
consults, the trail records one. The disagreement is written up rather than
smoothed over, because it is the most useful thing the run produced.

---

## Problem 11 — Submit to GitHub

### Prompt sent

> Problem 11, title " Submit to Github", Push the code to a public github
> repository so graders can clone it. Share with me a repo URL so I can share it
> with the professor and TAs, and also put it in "output/github_url.txt". Do not
> push my real .env to the github repo. Do include both database files under
> "data/" (the original and my working copy) so graders can run my app easily.
> The expected layout is in the attached two pics. One last thing, README should
> explain: copy original DB tot he working copy when I need a clean run, start the
> MCP server, start FastAPI backend, start the React board, reset the DB before a
> full three-ticket run. I want a 100% in this HW, make me proud!

*(Two screenshots of the expected file layout were attached.)*

### Follow-up prompt

None needed.

### Notes

Preparing the repository exposed two things that were broken for anyone who is
not me.

`.mcp.json` stored absolute paths into `/Users/saadaziz/…`. Made relative, and
resolved at load time by both the backend and the smoke test. The first attempt
at resolving used `Path.resolve()`, which follows symlinks — and a virtualenv's
`bin/python` is a symlink to the base interpreter, so the MCP server would have
launched outside the environment holding `fastmcp`. Joining without resolving
fixes it, with a `sys.executable` fallback so a single shared environment also
works.

The smoke test asserted against the shop's opening position and therefore died
with an opaque `StopIteration` on a database that had already been worked. It now
checks `payments` first and prints the one command that fixes it.

Both databases are committed as asked. The working copy ships in the state the
graded run left it — $160.00, three tickets closed — so the database agrees with
`resolved_tickets.json` and the Cash tab rather than contradicting them. The
README says this explicitly and gives the copy command to start clean.

Every staged file was scanned for key-shaped strings before the first commit.

---

<!-- Later problems get appended here as the work happens. -->
