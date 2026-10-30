import { useEffect, useState } from 'react'
import { api } from './api'
import Auth from './components/Auth'
import CandidateDashboard from './components/CandidateDashboard'
import CompanyDashboard from './components/CompanyDashboard'

export default function App() {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(null)
  const [booting, setBooting] = useState(true)
  const [bootError, setBootError] = useState('')

  async function refreshStatus() {
    try {
      setStatus(await api.status())
    } catch {
      /* backend may still be loading the embedding model */
    }
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // Session check only — do NOT wait on /api/status (it can load torch/embeddings).
      try {
        const me = await api.me()
        if (!cancelled) setUser(me)
      } catch {
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setBooting(false)
      }
      // Status pills refresh in the background
      refreshStatus()
    })()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleLogout() {
    try {
      await api.logout()
    } catch {
      /* ignore */
    }
    setUser(null)
  }

  if (booting) {
    return (
      <div className="main">
        <div className="empty">Loading Talent Graph…</div>
        {bootError && <div className="msg error">{bootError}</div>}
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">TG</div>
          <span>Talent Graph</span>
        </div>
        <div className="pills">
          <span className={`pill ${status?.llm === 'groq' ? 'ok' : 'warn'}`}>
            LLM: {status?.llm || '—'}
          </span>
          <span className={`pill ${status?.embedder && status.embedder !== 'fallback' ? 'ok' : 'warn'}`}>
            Embeddings: {status?.embedder || 'loading…'}
          </span>
          <span className="pill">{status?.jd_count ?? '—'} JDs</span>
        </div>
        {user && (
          <div className="topbar-right">
            <span className="user-chip">
              {user.name} · {user.role === 'company' ? user.company_name : 'candidate'}
            </span>
            <button className="btn btn-ghost" onClick={handleLogout}>Log out</button>
          </div>
        )}
      </header>

      <main className="main">
        {!user && <Auth onAuth={setUser} />}
        {user?.role === 'candidate' && (
          <CandidateDashboard user={user} onMatched={refreshStatus} />
        )}
        {user?.role === 'company' && (
          <CompanyDashboard user={user} onChanged={refreshStatus} />
        )}
      </main>
    </div>
  )
}
