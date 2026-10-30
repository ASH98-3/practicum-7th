import { useState } from 'react'
import { api } from '../api'

const DEMOS = [
  { email: 'company@nimbus.dev', password: 'Demo@1234', label: 'Company — Nimbus' },
  { email: 'candidate@demo.dev', password: 'Demo@1234', label: 'Candidate — Priya' },
]

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

  function fillDemo(d) {
    setMode('login')
    setEmail(d.email)
    setPassword(d.password)
    setMsg('')
    setErr(false)
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

        <div className="card demo-card">
          <h2>Quick demo logins</h2>
          <p className="muted">
            Run <code>python seed_demo.py</code> once first, then click a preset:
          </p>
          <div className="demo-list">
            {DEMOS.map((d) => (
              <button key={d.email} type="button" className="demo-btn" onClick={() => fillDemo(d)}>
                <strong>{d.label}</strong>
                <span>{d.email}</span>
              </button>
            ))}
          </div>
          <div className="feature-list">
            <div><span className="dot" /> PDF / DOCX resume upload</div>
            <div><span className="dot" /> Semantic JD retrieval</div>
            <div><span className="dot" /> ATS score + LLM rationale</div>
            <div><span className="dot" /> Company shortlist workflow</div>
          </div>
        </div>
      </div>
    </div>
  )
}
