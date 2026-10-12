/** The five desk colleagues, with the muted colour each one signs its work in. */
export interface Colleague {
  key: string
  name: string
  role: string
  initials: string
  accent: string
  /** What the board says while this one is working — written to sound like a person. */
  working: string
}

export const COLLEAGUES: Colleague[] = [
  { key: 'boss', name: 'Morgan', role: 'Shop Manager', initials: 'M',
    accent: '#c9a227', working: 'reading the ticket' },
  { key: 'inventory', name: 'Priya', role: 'Inventory Lead', initials: 'P',
    accent: '#7a9e7e', working: 'counting the shelves' },
  { key: 'accounting', name: 'Dan', role: 'Bookkeeper', initials: 'D',
    accent: '#6d8bb0', working: 'checking the books' },
  { key: 'facilities', name: 'Rosa', role: 'Facilities', initials: 'R',
    accent: '#c08457', working: 'looking at the lease' },
  { key: 'customer_service', name: 'Theo', role: 'Customer Service', initials: 'T',
    accent: '#9b8bb4', working: 'drafting a reply' },
]

export const byKey = (k: string) =>
  COLLEAGUES.find((c) => c.key === k) ??
  { key: k, name: k, role: '', initials: k.slice(0, 1).toUpperCase(), accent: '#7d8590', working: 'working' }

/** Plain-English label for an audit event kind. */
export function describeEvent(kind: string, toolCalls?: string): string {
  if (kind === 'delegation') return 'was asked to help'
  if (kind === 'agent_start') return 'picked this up'
  if (kind === 'agent_done') return 'finished up'
  if (kind === 'agent_end') return 'wrote up an answer'
  if (kind === 'tool_result') return 'read what came back'
  if (kind === 'decision') return 'made the call'
  if (kind === 'error') return 'hit a problem'
  if (kind === 'model_response') {
    const t = toolCalls ?? ''
    if (t.includes('ask_') || t.includes('consult_teammate')) return 'asked a colleague'
    if (t.includes('close_ticket')) return 'closed the ticket'
    if (t.includes('record_payment')) return 'prepared a payment'
    if (t.includes('check_item_availability')) return 'checked the shelves'
    if (t.includes('review_cash_and_obligations')) return 'checked the books'
    if (t.includes('price_bulk_order')) return 'worked out the margin'
    if (t.includes('get_ticket') || t.includes('list_open_tickets')) return 'looked up the ticket'
    if (t.includes('get_lease')) return 'looked up the lease'
    if (t.includes('list_vendors')) return 'checked vendor lead times'
    if (t.includes('final_result')) return 'wrote up an answer'
    return 'thought it through'
  }
  return kind.replace(/_/g, ' ')
}

/** Tool name -> something a human would say. */
export const TOOL_LABELS: Record<string, string> = {
  get_ticket: 'read the ticket',
  list_open_tickets: 'checked the queue',
  check_item_availability: 'checked stock',
  review_cash_and_obligations: 'checked the books',
  price_bulk_order: 'priced the order',
  list_vendors: 'checked vendors',
  get_lease: 'checked the lease',
  record_payment: 'prepared a payment',
  adjust_inventory: 'moved stock',
  close_ticket: 'closed the ticket',
  ask_inventory: 'asked Priya',
  ask_accounting: 'asked Dan',
  ask_facilities: 'asked Rosa',
  ask_customer_service: 'asked Theo',
  consult_teammate: 'asked a colleague',
}

/** A warm line for the top of the page, by time of day. */
export function greeting(): string {
  const h = new Date().getHours()
  if (h < 5) return 'Still up?'
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  if (h < 21) return 'Good evening'
  return 'Working late'
}
