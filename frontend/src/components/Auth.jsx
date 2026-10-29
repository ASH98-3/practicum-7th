import { useState } from 'react'
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

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setMsg('')
    setErr(false)
    try {
      const user =
        mode === 'login'
          ? await api.login({ email, password })
          : await api.register({
              name,
              email,
              password,
              role,
              company_name: companyName,
            })
      onAuth(user)
    } catch (e) {
      setErr(true)
      setMsg(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="hero" style={{ textAlign: 'center' }}>
        <h1>Match talent to the right roles</h1>
        <p>
          AI-powered resume parsing, semantic matching, and ATS scoring across company job descriptions.
        </p>
      </div>
      <div className="card">
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
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
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
            />
          </div>
          <button className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
          {msg && <div className={`msg ${err ? 'error' : 'ok'}`}>{msg}</div>}
        </form>
      </div>
    </div>
  )
}
