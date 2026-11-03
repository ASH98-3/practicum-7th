const BASE = ''
const DEFAULT_TIMEOUT_MS = 8000

function formatDetail(detail) {
  if (!detail) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d)))
      .join('; ')
  }
  if (typeof detail === 'object' && detail.msg) return detail.msg
  return String(detail)
}

async function request(path, options = {}) {
  const { timeout = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const res = await fetch(`${BASE}${path}`, {
      credentials: 'include',
      signal: controller.signal,
      ...fetchOptions,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const err = new Error(formatDetail(data.detail) || res.statusText || 'Request failed')
      err.status = res.status
      throw err
    }
    return data
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error('Backend not responding. Is uvicorn running on port 8000?')
    }
    if (e instanceof TypeError) {
      throw new Error('Cannot reach API. Start backend: uvicorn app.api:app --host 127.0.0.1 --port 8000')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  status: () => request('/api/status', { timeout: 15000 }),
  me: () => request('/api/auth/me', { timeout: 5000 }),
  publicJobs: () => request('/api/jobs', { timeout: 10000 }),
  login: (body) =>
    request('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  register: (body) =>
    request('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),

  matchResume: (formData) =>
    request('/api/candidate/match', { method: 'POST', body: formData, timeout: 180000 }),
  apply: (matchId) =>
    request('/api/candidate/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ match_id: matchId }),
    }),
  myMatches: () => request('/api/candidate/matches'),

  companyJds: () => request('/api/company/jds'),
  addJd: (body) =>
    request('/api/company/jds', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      timeout: 120000,
    }),
  setOpenings: (jdId, openings) =>
    request(`/api/company/jds/${jdId}/openings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ openings }),
    }),
  finalizeJd: (jdId) =>
    request(`/api/company/jds/${jdId}/finalize`, { method: 'POST' }),
  deleteJd: (id) => request(`/api/company/jds/${id}`, { method: 'DELETE' }),
  applicants: () => request('/api/company/applicants'),
  setStatus: (id, body) =>
    request(`/api/company/applicants/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
