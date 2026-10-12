import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  approvePayment, fetchCash, fetchEvents, fetchHealth, fetchRun, fetchTickets,
  resetDatabase, startRun,
} from './api'
import { COLLEAGUES, TOOL_LABELS, byKey, describeEvent, greeting } from './agents'
import type { AgentEvent, Cash, EventsResponse, Run, Ticket } from './types'

const POLL_MS = 1500

const TICKET_BLURB: Record<number, string> = {
  101: 'A customer is waiting on a tee.',
  102: 'The landlord would like to be paid.',
  103: 'A student club wants twenty hoodies.',
}

function money(n: number | null | undefined) {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [today, setToday] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [events, setEvents] = useState<EventsResponse | null>(null)
  const [health, setHealth] = useState<{ ok: boolean; model: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [approver, setApprover] = useState('')
  const [cashFlash, setCashFlash] = useState(false)
  const prevCash = useRef<number | null>(null)
  const timer = useRef<number | null>(null)

  const refreshBoard = useCallback(async () => {
    const [t, c] = await Promise.all([fetchTickets(), fetchCash()])
    setTickets(t.tickets)
    setToday(t.today)
    if (prevCash.current !== null && c.checking_balance !== prevCash.current) {
      setCashFlash(true)
      window.setTimeout(() => setCashFlash(false), 1800)
    }
    prevCash.current = c.checking_balance
    setCash(c)
  }, [])

  useEffect(() => {
    fetchHealth().then((h) => setHealth({ ok: h.ok, model: h.model })).catch(() => setHealth(null))
    refreshBoard().catch(() => undefined)
  }, [refreshBoard])

  // While a run is in flight, keep pulling the agent events.
  useEffect(() => {
    if (!run || (run.status !== 'queued' && run.status !== 'running')) return
    const tick = async () => {
      try {
        const [r, e] = await Promise.all([fetchRun(run.run_id), fetchEvents(run.run_id)])
        setRun(r)
        setEvents(e)
        if (r.status === 'done' || r.status === 'error') {
          await refreshBoard()
          setToast(r.status === 'done'
            ? 'All done — the team has written it up below.'
            : 'That run hit a snag. The details are in the log.')
        }
      } catch { /* a dropped poll is not worth shouting about */ }
    }
    timer.current = window.setInterval(tick, POLL_MS)
    void tick()
    return () => { if (timer.current) window.clearInterval(timer.current) }
  }, [run, refreshBoard])

  // Reopen a finished run from the URL (?ticket=101&run=ee15b0fe0c60) so a
  // resolved ticket can be read back later without asking the team to redo it.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search)
    const runId = q.get('run')
    const ticketId = Number(q.get('ticket'))
    if (!runId) return
    if (ticketId) setSelected(ticketId)
    Promise.all([fetchRun(runId), fetchEvents(runId)])
      .then(([r, e]) => { setRun(r); setEvents(e) })
      .catch(() => setToast('That run is no longer in memory.'))
  }, [])

  useEffect(() => {
    if (!toast) return
    const id = window.setTimeout(() => setToast(null), 4200)
    return () => window.clearTimeout(id)
  }, [toast])

  async function onStart(id: number) {
    setBusy(true)
    setSelected(id)
    setEvents(null)
    try {
      const r = await startRun(id)
      setRun({ run_id: r.run_id, ticket_id: id, status: 'queued', started_at: new Date().toISOString() })
      setToast('The team is on it.')
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'Could not start the run.')
    } finally {
      setBusy(false)
    }
  }

  async function onApprove(kind: 'invoice' | 'rent', refId: number, amount: number) {
    const who = approver.trim()
    if (!who) { setToast('Please add your name first — approvals are signed.'); return }
    setBusy(true)
    try {
      const res = await approvePayment({ kind, ref_id: refId, amount, approved_by: who, ticket_id: selected ?? undefined })
      await refreshBoard()
      setToast(`Thank you, ${who.split(' ')[0]}. Paid — balance is now ${money(res.payment.balance_after)}.`)
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'That approval was refused.')
    } finally {
      setBusy(false)
    }
  }

  async function onReset() {
    setBusy(true)
    try {
      await resetDatabase()
      setRun(null); setEvents(null); setSelected(null)
      prevCash.current = null
      await refreshBoard()
      setToast('Fresh start. Everything is back where it began.')
    } finally { setBusy(false) }
  }

  const running = run?.status === 'queued' || run?.status === 'running'
  const decision = run?.status === 'done' ? run.decision : undefined

  // Which colleague is active right now, and what each has been doing.
  const activity = useMemo(() => {
    const map: Record<string, { lines: string[]; tools: string[]; last: string }> = {}
    for (const ev of events?.events ?? []) {
      if (ev.agent === 'system' || ev.agent === 'human') continue
      const a = (map[ev.agent] ??= { lines: [], tools: [], last: '' })
      a.last = describeEvent(ev.kind, ev.tool_calls)
      if (ev.kind === 'model_response' && ev.text) a.lines.push(ev.text)
      for (const [tool, label] of Object.entries(TOOL_LABELS)) {
        if ((ev.tool_calls ?? '').includes(tool) && !a.tools.includes(label)) a.tools.push(label)
      }
    }
    return map
  }, [events])

  const lastAgent = useMemo(() => {
    const evs = (events?.events ?? []).filter((e: AgentEvent) => e.agent !== 'system')
    return evs.length ? evs[evs.length - 1].agent : null
  }, [events])

  return (
    <div className="page">
      <header className="top">
        <div>
          <p className="eyebrow">Campus Customs · Chapel Street</p>
          <h1>The Desk</h1>
          <p className="hello">
            {greeting()}. {tickets.filter((t) => !t.resolved).length > 0
              ? `There ${tickets.filter((t) => !t.resolved).length === 1 ? 'is one ticket' : `are ${tickets.filter((t) => !t.resolved).length} tickets`} waiting.`
              : 'The queue is clear — nice work.'}
          </p>
        </div>
        <div className="top-right">
          <div className={`cash ${cashFlash ? 'flash' : ''}`}>
            <span>Checking</span>
            <b>{money(cash?.checking_balance)}</b>
            {cash && <em>{money(cash.total_owed)} still owed</em>}
          </div>
          <button className="ghost" onClick={onReset} disabled={busy || running}>Fresh start</button>
        </div>
      </header>

      <main className="grid">
        {/* ---------------- tickets ---------------- */}
        <section className="col">
          <h2>Today's tickets {today && <span className="muted">· {today}</span>}</h2>
          {tickets.map((t) => (
            <article
              key={t.id}
              className={`ticket ${t.resolved ? 'done' : ''} ${selected === t.id ? 'on' : ''}`}
            >
              <header>
                <span className="tnum">#{t.id}</span>
                <h3>{t.subject}</h3>
                <span className={`chip ${t.state}`}>{t.state}</span>
              </header>
              <p className="blurb">{TICKET_BLURB[t.id] ?? t.type.replace(/_/g, ' ')}</p>
              <p className="who">from {t.requester}</p>
              <button
                className="primary"
                disabled={busy || running}
                onClick={() => onStart(t.id)}
              >
                {running && selected === t.id ? 'The team is working…' : t.resolved ? 'Run it again' : 'Ask the team'}
              </button>
            </article>
          ))}
          {cash && cash.obligations.length > 0 && (
            <div className="owed">
              <h3>Still to settle</h3>
              {cash.obligations.map((o) => (
                <div key={`${o.kind}-${o.ref_id}`} className="owed-row">
                  <span>{o.payee}</span>
                  <b>{money(o.amount)}</b>
                  <em className={o.overdue ? 'late' : ''}>
                    {o.overdue ? `${Math.abs(o.days_until_due ?? 0)}d overdue` : `due in ${o.days_until_due}d`}
                  </em>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ---------------- the team ---------------- */}
        <section className="col wide">
          <h2>
            The team
            {running && <span className="pulse-label">· working on #{selected}</span>}
          </h2>
          <div className="team">
            {COLLEAGUES.map((c) => {
              const a = activity[c.key]
              const active = running && lastAgent === c.key
              const touched = Boolean(a)
              return (
                <article
                  key={c.key}
                  className={`mate ${active ? 'active' : ''} ${touched ? 'touched' : ''}`}
                  style={{ ['--accent' as string]: c.accent }}
                >
                  <div className="avatar">{c.initials}</div>
                  <div className="mate-body">
                    <h4>{c.name} <span>{c.role}</span></h4>
                    <p className="status">
                      {active ? <><i className="dot" /> {a?.last ?? c.working}…</>
                        : touched ? (a?.last ?? 'done')
                        : running ? 'not needed so far' : 'at the desk'}
                    </p>
                    {a?.tools.length ? (
                      <p className="tools">{a.tools.slice(0, 4).join(' · ')}</p>
                    ) : null}
                    {a?.lines.length ? (
                      <p className="said">“{a.lines[a.lines.length - 1].slice(0, 180)}”</p>
                    ) : null}
                  </div>
                </article>
              )
            })}
          </div>

          {running && (
            <p className="working-note">
              Give them a moment — they check the real numbers before answering.
            </p>
          )}

          {/* ---------------- outcome ---------------- */}
          {decision && (
            <div className="outcome">
              <h3>What the team decided</h3>
              <p className="decision">{decision.decision}</p>
              {decision.reasoning && <p className="reason">{decision.reasoning}</p>}

              {decision.customer_reply && (
                <div className="reply">
                  <span className="label">Draft reply to the customer</span>
                  <p>{decision.customer_reply}</p>
                </div>
              )}

              <div className="summary">
                <span className="label">Who did what</span>
                {Object.entries(activity).map(([k, a]) => {
                  const c = byKey(k)
                  return (
                    <div key={k} className="sum-row" style={{ ['--accent' as string]: c.accent }}>
                      <b>{c.name}</b>
                      <span>{a.tools.length ? a.tools.join(' · ') : 'took a look'}</span>
                    </div>
                  )
                })}
              </div>

              {decision.needs_human_approval && (
                <div className="approve">
                  <span className="label">Over to you</span>
                  <p>{decision.approval_reason || 'This one needs a person to sign it off.'}</p>
                  <div className="approve-row">
                    <input
                      placeholder="Your name"
                      value={approver}
                      onChange={(e) => setApprover(e.target.value)}
                      aria-label="Your name, for the approval record"
                    />
                    {(cash?.obligations ?? []).map((o) => (
                      <button
                        key={`${o.kind}-${o.ref_id}`}
                        className="approve-btn"
                        disabled={busy}
                        onClick={() => onApprove(o.kind as 'invoice' | 'rent', o.ref_id, o.amount)}
                      >
                        Approve {money(o.amount)} · {o.payee}
                      </button>
                    ))}
                  </div>
                  <p className="fineprint">
                    Your name goes on the record. The agents can prepare a payment, but only a
                    person can authorise one.
                  </p>
                </div>
              )}

              {run?.usage && (
                <p className="usage">
                  {run.usage.requests} model calls · {run.usage.input_tokens.toLocaleString()} in /
                  {' '}{run.usage.output_tokens.toLocaleString()} out tokens · {run.usage.seconds}s
                </p>
              )}
            </div>
          )}

          {run?.status === 'error' && (
            <div className="outcome err">
              <h3>That didn't go to plan</h3>
              <p>{run.error}</p>
            </div>
          )}
        </section>
      </main>

      <footer className="foot">
        <span>
          {health
            ? <>Backend up · {health.model} · thanks for keeping an eye on things.</>
            : <>Backend not answering — is <code>uvicorn</code> running on port 8000?</>}
        </span>
      </footer>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
