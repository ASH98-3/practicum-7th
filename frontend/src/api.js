const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || res.statusText || 'Request failed')
    err.status = res.status
    throw err
  }
  return data
}

export const api = {
  status: () => request('/api/status'),
  me: () => request('/api/auth/me'),
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
    request('/api/candidate/match', { method: 'POST', body: formData }),
  myMatches: () => request('/api/candidate/matches'),

  companyJds: () => request('/api/company/jds'),
  addJd: (body) =>
    request('/api/company/jds', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  deleteJd: (id) => request(`/api/company/jds/${id}`, { method: 'DELETE' }),
  applicants: () => request('/api/company/applicants'),
  setStatus: (id, body) =>
    request(`/api/company/applicants/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
