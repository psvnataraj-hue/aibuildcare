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
  assigned_staff_id: number | null
  assigned_staff_name: string | null
  media_urls: string | null
  detected_language: string | null
  official_summaries: Record<string, string> | null
  estimated_completion_date: string | null
  // E1c/E2a escalation timestamps (null until each level fires)
  escalated_to_manager_at: string | null
  escalated_to_sr_manager_at: string | null
  escalated_to_secretary_at: string | null
  escalated_to_chairman_at: string | null
  // E2d major-incident flagging
  major_incident: number | null
  major_incident_flagged_at: string | null
  major_incident_reason: string | null
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
  average_rating?: number
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
  average_rating: number | null
  assigned_count: number
  resolved_count: number
  avg_response_time_hours: number | null
  avg_resolution_time_hours: number | null
  completion_rate: number
  last_activity: string | null
}

export interface ContractorAnalytics {
  contractor_id: number
  name: string
  rating: number | null
  workload: {
    pending_count: number
    in_progress_count: number
    completed_count: number
    total_assigned: number
  }
  response_time: {
    avg_hours: number | null
    min_hours: number | null
    max_hours: number | null
    trend: number[]
  }
  resolution_time: {
    avg_hours: number | null
    min_hours: number | null
    max_hours: number | null
    trend: number[]
  }
  rating_trend: { current: number | null; data_points: number[]; samples: number }
  category_specialization: Record<
    string,
    { completed: number; pct_of_total: number }
  >
  availability: { status: string; last_activity: string | null }
}
// E1c / E3e — escalation hierarchy CRUD
export interface HierarchyEntry {
  id: number
  society_id: number
  role_name: 'manager' | 'sr_manager' | 'secretary' | 'chairman' | string
  person_name: string
  phone: string | null
  whatsapp_enabled: boolean
  email: string | null
  escalation_level: number
  response_time_target_minutes: number
  active: boolean
  created_at?: string
}
export interface HierarchyCreatePayload {
  role_name: string
  person_name: string
  phone?: string | null
  whatsapp_enabled?: boolean
  email?: string | null
  escalation_level?: number
  response_time_target_minutes?: number
}
export interface HierarchyPatchPayload {
  role_name?: string
  person_name?: string
  phone?: string | null
  whatsapp_enabled?: boolean
  email?: string | null
  escalation_level?: number
  response_time_target_minutes?: number
  active?: boolean
}

// E3a / E3f — staff CRUD
export interface StaffCategory {
  category: string
  primary_category: boolean
  skill_level: 'junior' | 'senior' | 'expert' | string
}
export interface Staff {
  id: number
  society_id: number
  name: string
  phone_primary: string
  phone_secondary: string | null
  whatsapp_enabled: boolean
  sms_fallback: boolean
  email: string | null
  shift_pattern: string | null
  hire_date: string | null
  emergency_contact: string | null
  notes: string | null
  active: boolean
  categories: StaffCategory[]
  created_at: string
}
export interface StaffCreatePayload {
  name: string
  phone_primary: string
  phone_secondary?: string | null
  whatsapp_enabled?: boolean
  sms_fallback?: boolean
  email?: string | null
  shift_pattern?: string | null
  hire_date?: string | null
  emergency_contact?: string | null
  notes?: string | null
  categories?: StaffCategory[]
}
export interface StaffPatchPayload {
  name?: string
  phone_primary?: string
  phone_secondary?: string | null
  whatsapp_enabled?: boolean
  sms_fallback?: boolean
  email?: string | null
  shift_pattern?: string | null
  hire_date?: string | null
  emergency_contact?: string | null
  notes?: string | null
  active?: boolean
}

export interface AnalyticsSummary {
  total_contractors: number
  active_contractors: number
  avg_rating_across_all: number | null
  top_performers: { name: string; rating: number | null; completed: number }[]
  workload_distribution: {
    available: number
    at_capacity: number
    overloaded: number
  }
  category_performance: Record<
    string,
    { avg_response_time: number | null; avg_resolution_time: number | null }
  >
}

// E3h — identity + effective permissions
export interface CurrentUser {
  id: number
  email: string
  full_name: string | null
  role: string
  society_id: number | null
  permissions: string[]
}

// Permission keys mirror backend/app/services/rbac.py constants.
// Keep this list in sync; the source of truth is the backend.
export const PERMISSIONS = {
  FILE_COMPLAINT: 'file_complaint',
  VIEW_OWN: 'view_own',
  VIEW_ALL: 'view_all',
  ASSIGN: 'assign',
  RESOLVE: 'resolve',
  ESCALATE: 'escalate',
  AUTHORIZE_ENFORCEMENT: 'authorize_enforcement',
  MODIFY_STAFF: 'modify_staff',
  MODIFY_CONFIG: 'modify_config',
  APPROVE_REPORTS: 'approve_reports',
  VIEW_FINANCIAL: 'view_financial',
} as const

export const api = {
  login: (email: string, password: string) =>
    req<{ access_token: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => req<CurrentUser>('/api/v1/auth/me'),
  logout: () =>
    req<void>('/api/v1/auth/logout', { method: 'POST' }),
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
  contractorsByCategory: (category: string) =>
    req<Contractor[]>(
      `/api/v1/contractors/by-category?category=${encodeURIComponent(
        category || ''
      )}`
    ),
  contractorPerformance: () =>
    req<ContractorPerf[]>('/api/v1/contractors/performance'),
  rate: (id: number, rating: number, feedback: string) =>
    req<Rating>(`/api/v1/complaints/${id}/rate`, {
      method: 'POST',
      body: JSON.stringify({ rating, feedback }),
    }),
  contractorAnalytics: (id: number) =>
    req<ContractorAnalytics>(`/api/v1/contractors/${id}/analytics`),
  analyticsSummary: () =>
    req<AnalyticsSummary>('/api/v1/contractors/analytics/summary'),
  adminConfig: () => req<Record<string, string>>('/api/v1/admin/config'),
  setAdminConfig: (key: string, value: string) =>
    req<{ config_key: string; config_value: string }>(
      `/api/v1/admin/config/${key}`,
      { method: 'POST', body: JSON.stringify({ value }) }
    ),
  // E3a / E3f — staff CRUD
  listStaff: (includeInactive = false) =>
    req<Staff[]>(
      `/api/v1/staff${includeInactive ? '?include_inactive=true' : ''}`
    ),
  getStaff: (id: number) => req<Staff>(`/api/v1/staff/${id}`),
  createStaff: (body: StaffCreatePayload) =>
    req<Staff>('/api/v1/staff', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateStaff: (id: number, body: StaffPatchPayload) =>
    req<Staff>(`/api/v1/staff/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deactivateStaff: (id: number) =>
    req<Staff>(`/api/v1/staff/${id}`, { method: 'DELETE' }),
  addStaffCategory: (id: number, body: StaffCategory) =>
    req<Staff>(`/api/v1/staff/${id}/categories`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  removeStaffCategory: (id: number, category: string) =>
    req<Staff>(
      `/api/v1/staff/${id}/categories/${encodeURIComponent(category)}`,
      { method: 'DELETE' }
    ),
  // E1c / E3e — escalation hierarchy CRUD
  listHierarchy: () =>
    req<HierarchyEntry[]>('/api/v1/escalation/hierarchy'),
  addHierarchy: (body: HierarchyCreatePayload) =>
    req<HierarchyEntry>('/api/v1/escalation/hierarchy', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateHierarchy: (id: number, body: HierarchyPatchPayload) =>
    req<HierarchyEntry>(`/api/v1/escalation/hierarchy/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  deleteHierarchy: (id: number) =>
    req<{ deleted: number }>(`/api/v1/escalation/hierarchy/${id}`, {
      method: 'DELETE',
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
