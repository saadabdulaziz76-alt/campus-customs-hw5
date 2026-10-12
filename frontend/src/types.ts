export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  status: string
  notes: string | null
  state: 'open' | 'blocked' | 'resolved'
  resolved: boolean
  last_run: string | null
}

export interface Obligation {
  kind: string
  ref_id: number
  payee: string
  amount: number
  due_date: string
  days_until_due: number | null
  overdue: boolean
}

export interface Cash {
  today: string
  checking_balance: number
  total_owed: number
  remaining_if_all_paid: number
  covers_everything: boolean
  obligations: Obligation[]
  payments_made: unknown[]
}

export interface Decision {
  ticket_id: number
  decision: string
  reasoning: string
  customer_reply: string
  actions_taken: string[]
  needs_human_approval: boolean
  approval_reason: string
  consulted: string[]
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'queued' | 'running' | 'done' | 'error'
  started_at: string
  finished_at?: string
  decision?: Decision
  usage?: { requests: number; input_tokens: number; output_tokens: number; seconds: number }
  error?: string
}

export interface AgentEvent {
  ts: string
  run_id: string
  agent: string
  kind: string
  ticket_id: number | null
  depth: number
  text?: string
  tool_calls?: string
  question?: string
  output?: string
  step?: number
  usage?: unknown
}

export interface EventsResponse {
  count: number
  total_in_log: number
  events: AgentEvent[]
  agents: Record<string, { said: string[]; tools: string[]; steps: number }>
}
