const BASE = import.meta.env.VITE_API_BASE || ''

let token = localStorage.getItem('token') || ''

export function setToken(t: string) {
  token = t
  localStorage.setItem('token', t)
}
export function clearToken() {
  token = ''
  localStorage.removeItem('token')
}
export function hasToken() {
  return !!token
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + path, { ...opts, headers })
  if (res.status === 401) {
    clearToken()
    throw new Error('unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(
      typeof body.detail === 'string' ? body.detail : 'request failed'
    )
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export interface Complaint {
  id: number
  ticket_number: string
  unit_number: string | null
  category: string | null
  priority: string
  status: string
  channel: string
  raw_text: string
  acknowledgement: string | null
  contractor_id: number | null
  media_urls: string | null
  detected_language: string | null
  created_at: string
  updated_at: string
  messages?: Message[]
  rating?: Rating | null
}
export interface Message {
  id: number
  sender: string
  body: string
  created_at: string
}
export interface Contractor {
  id: number
  name: string
  specialty: string
  phone: string
}
export interface Rating {
  rating: number
  feedback: string | null
  rated_at: string
}
export interface ContractorPerf {
  contractor_id: number
  name: string
  phone: string
  specialty: string
  assigned_count: number
  resolved_count: number
  avg_response_time_hours: number | null
  avg_resolution_time_hours: number | null
  completion_rate: number
  last_activity: string | null
}

export const api = {
  login: (email: string, password: string) =>
    req<{ access_token: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  analytics: () =>
    req<{
      total: number
      open: number
      urgent_open: number
      by_status: Record<string, number>
    }>('/api/v1/analytics'),
  listComplaints: (q = '', status = '', sort = 'created_at') =>
    req<Complaint[]>(
      `/api/v1/complaints?q=${encodeURIComponent(q)}&status=${status}&sort=${sort}`
    ),
  getComplaint: (id: number) => req<Complaint>(`/api/v1/complaints/${id}`),
  createComplaint: (raw_text: string) =>
    req<Complaint>('/api/v1/complaints', {
      method: 'POST',
      body: JSON.stringify({ raw_text }),
    }),
  assign: (id: number, contractor_id: number) =>
    req<Complaint>(`/api/v1/complaints/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({ contractor_id }),
    }),
  setStatus: (id: number, status: string) =>
    req<Complaint>(`/api/v1/complaints/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
  addMessage: (id: number, body: string) =>
    req<Message>(`/api/v1/complaints/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ sender: 'staff', body }),
    }),
  contractors: () => req<Contractor[]>('/api/v1/contractors'),
  contractorPerformance: () =>
    req<ContractorPerf[]>('/api/v1/contractors/performance'),
  rate: (id: number, rating: number, feedback: string) =>
    req<Rating>(`/api/v1/complaints/${id}/rate`, {
      method: 'POST',
      body: JSON.stringify({ rating, feedback }),
    }),
}

export function openWS(onEvent: (e: { event: string; payload: any }) => void) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const host = BASE ? BASE.replace(/^https?:\/\//, '') : location.host
  const ws = new WebSocket(`${proto}://${host}/api/v1/ws`)
  ws.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data))
    } catch {
      /* ignore malformed frames */
    }
  }
  return ws
}
