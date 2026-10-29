import { useEffect, useState } from 'react'
import { api } from './api'
import Auth from './components/Auth'
import CandidateDashboard from './components/CandidateDashboard'
import CompanyDashboard from './components/CompanyDashboard'

export default function App() {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(null)
  const [booting, setBooting] = useState(true)

  async function refreshStatus() {
    try {
      setStatus(await api.status())
    } catch {
      /* backend may not be up yet */
    }
  }

  useEffect(() => {
    ;(async () => {
      await refreshStatus()
      try {
        setUser(await api.me())
      } catch {
        setUser(null)
      } finally {
        setBooting(false)
      }
    })()
  }, [])

  async function handleLogout() {
    await api.logout()
    setUser(null)
  }

  if (booting) {
    return (
      <div className="main">
        <div className="empty">Loading Talent Graph…</div>
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
            Embeddings: {status?.embedder || '—'}
          </span>
          <span className="pill">{status?.jd_count ?? 0} JDs</span>
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
