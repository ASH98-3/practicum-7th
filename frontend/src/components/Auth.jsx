import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

export default function Auth({ onAuth }) {
  const [mode, setMode] = useState('login')
  const [role, setRole] = useState('candidate')
  const [name, setName] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState(false)
  const [loading, setLoading] = useState(false)
  const [jobs, setJobs] = useState([])
  const [jobsError, setJobsError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await api.publicJobs()
        if (!cancelled) {
          setJobs(Array.isArray(data) ? data : [])
          setJobsError('')
        }
      } catch (e) {
        if (!cancelled) {
          setJobs([])
          setJobsError(e.message || 'Could not load jobs — is the backend running?')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const companies = useMemo(() => {
    const map = new Map()
    for (const j of jobs) {
      const name = j.company || 'Unknown'
      if (!map.has(name)) map.set(name, [])
      map.get(name).push(j)
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [jobs])

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setMsg(mode === 'login' ? 'Signing in…' : 'Creating account…')
    setErr(false)
    try {
      const user =
        mode === 'login'
          ? await api.login({ email: email.trim(), password })
          : await api.register({
              name: name.trim(),
              email: email.trim(),
              password,
              role,
              company_name: companyName.trim(),
            })
      setMsg('')
      onAuth(user)
    } catch (e) {
      setErr(true)
      setMsg(e.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="hero" style={{ textAlign: 'center' }}>
        <div className="hero-badge">AI Talent Matching</div>
        <h1>Match talent to the right roles</h1>
        <p>
          Parse resumes, embed profiles, retrieve live job descriptions, and score fits with
          ATS + LLM skill equivalence.
        </p>
      </div>

      <div className="auth-grid">
        <div className="card auth-card">
          <div className="tabs">
            <button className={`tab ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')} type="button">
              Log in
            </button>
            <button className={`tab ${mode === 'register' ? 'active' : ''}`} onClick={() => setMode('register')} type="button">
              Create account
            </button>
          </div>

          <form onSubmit={submit}>
            {mode === 'register' && (
              <>
                <div className="field">
                  <label>I am a</label>
                  <select value={role} onChange={(e) => setRole(e.target.value)}>
                    <option value="candidate">Candidate</option>
                    <option value="company">Company (hiring)</option>
                  </select>
                </div>
                <div className="field">
                  <label>Full name</label>
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" required />
                </div>
                {role === 'company' && (
                  <div className="field">
                    <label>Company name</label>
                    <input
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="e.g. Acme Labs"
                      required
                    />
                  </div>
                )}
              </>
            )}
            <div className="field">
              <label>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
                minLength={8}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>
            <button className="btn btn-primary btn-block" disabled={loading}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
            </button>
            {msg && <div className={`msg ${err ? 'error' : ''}`}>{msg}</div>}
          </form>
        </div>

        <div className="card demo-card companies-panel">
          <h2>Companies hiring</h2>
          <p className="muted">
            Scraped / registered roles available for matching ({jobs.length} jobs
            {companies.length ? ` · ${companies.length} companies` : ''}).
          </p>

          {jobsError && <div className="msg error">{jobsError}</div>}

          {!jobsError && jobs.length === 0 && (
            <div className="empty">
              No jobs loaded yet. With the backend running, execute:
              <br />
              <code>python tools/load_scraped_jds.py</code>
            </div>
          )}

          <div className="company-list">
            {companies.map(([company, roles]) => (
              <details key={company} className="company-block">
                <summary>
                  <strong>{company}</strong>
                  <span className="muted">{roles.length} role{roles.length === 1 ? '' : 's'}</span>
                </summary>
                <ul className="role-list">
                  {roles.map((r) => (
                    <li key={r.jd_id || `${company}-${r.title}`}>
                      <span>{r.title}</span>
                      {(r.required_skills || []).length > 0 && (
                        <div className="chips">
                          {(r.required_skills || []).slice(0, 5).map((s) => (
                            <span className="chip" key={s}>{s}</span>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
