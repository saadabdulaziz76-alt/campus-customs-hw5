import type { Cash, EventsResponse, Run, Ticket } from './types'

export const API = 'http://localhost:8000'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const text = await res.text()
  if (!res.ok) {
    try {
      throw new Error(JSON.parse(text).detail ?? text)
    } catch {
      throw new Error(text || `HTTP ${res.status}`)
    }
  }
  return JSON.parse(text) as T
}

export const fetchHealth = () => get<{ ok: boolean; model: string; portkey_key_set: boolean }>('/api/health')
export const fetchTickets = () => get<{ today: string; tickets: Ticket[] }>('/api/tickets')
export const fetchCash = () => get<Cash>('/api/cash')
export const fetchRun = (id: string) => get<Run>(`/api/runs/${id}`)
export const fetchEvents = (runId: string) =>
  get<EventsResponse>(`/api/events?run_id=${encodeURIComponent(runId)}&limit=200`)

export const startRun = (ticketId: number) =>
  post<{ run_id: string; ticket_id: number }>(`/api/tickets/${ticketId}/run`, {})

export const approvePayment = (b: {
  kind: 'invoice' | 'rent'
  ref_id: number
  amount: number
  approved_by: string
  ticket_id?: number
  note?: string
}) => post<{ approval_id: string; payment: { balance_before: number; balance_after: number } }>(
  '/api/approvals', { account: 'checking', ...b },
)

export const resetDatabase = () => post<{ ok: boolean }>('/api/reset', { confirm: true })
