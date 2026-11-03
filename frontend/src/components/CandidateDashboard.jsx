import { useEffect, useState } from 'react'
import { api } from '../api'

const STATUS_LABEL = {
  new: 'Applied — awaiting review',
  shortlisted: 'Shortlisted',
  rejected: 'Not selected',
  not_sent: 'Matched (not applied)',
}

export default function CandidateDashboard({ onMatched }) {
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState(false)
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])

  async function loadHistory() {
    try {
      setHistory(await api.myMatches())
    } catch {
      setHistory([])
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  async function matchResume(e) {
    e.preventDefault()
    setLoading(true)
    setMsg('Parsing, embedding, and matching…')
    setErr(false)
    try {
      const fd = new FormData()
      if (file) fd.append('file', file)
      fd.append('text', text)
      const data = await api.matchResume(fd)
      setResult(data)
      setMsg('')
      await loadHistory()
      onMatched?.()
    } catch (e) {
      setErr(true)
      setMsg(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function applyTo(matchId) {
    setApplying(matchId)
    setMsg('')
    setErr(false)
    try {
      await api.apply(matchId)
      setResult((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          matches: (prev.matches || []).map((m) =>
            m.match_id === matchId ? { ...m, status: 'new', applied: true } : m,
          ),
        }
      })
      await loadHistory()
      setMsg('Application submitted — the company can now review you.')
    } catch (e) {
      setErr(true)
      setMsg(e.message)
    } finally {
      setApplying(null)
    }
  }

  const decisionLabel = {
    shortlist: 'Strong fit found',
    manual_review: 'Partial fit',
    reject: 'No strong fit',
  }

  const applications = history.filter((r) => r.status !== 'not_sent')

  return (
    <>
      <div className="hero">
        <h1>Find your best-fit companies</h1>
        <p>
          Upload a resume to rank live JDs. Then <strong>Apply</strong> to roles you want —
          multiple candidates can apply to the same post; companies keep the top matches by openings.
        </p>
      </div>

      <div className="grid-2">
        <div className="card">
          <h2>Match your resume</h2>
          <form onSubmit={matchResume}>
            <div className="field">
              <label>Resume file (PDF, DOCX, or TXT)</label>
              <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            </div>
            <div className="field">
              <label>Or paste resume text</label>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Optional if you uploaded a file"
              />
            </div>
            <button className="btn btn-primary" disabled={loading}>
              {loading ? 'Matching…' : 'Find best-fit roles'}
            </button>
            {msg && <div className={`msg ${err ? 'error' : ''}`}>{msg}</div>}
          </form>
        </div>

        <div className="card">
          <h2>How it works</h2>
          <p className="muted">1. Parse resume → skills, experience, education</p>
          <p className="muted">2. Embed profile (sentence-transformers)</p>
          <p className="muted">3. Retrieve similar JDs (vector search)</p>
          <p className="muted">4. ATS score + optional LLM rationale</p>
          <p className="muted">5. You choose which roles to <strong>Apply</strong> to</p>
          <p className="muted">6. Company ranks applicants; top N = openings</p>
        </div>
      </div>

      {result && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className={`badge ${result.decision}`}>{decisionLabel[result.decision] || result.decision}</span>
            <span className="muted">
              {result.profile.experience_years} yrs · {result.profile.education?.join(', ') || 'Education n/a'}
            </span>
          </div>
          <div className="chips">{(result.profile.skills || []).map((s) => <span className="chip" key={s}>{s}</span>)}</div>
          <p className="muted" style={{ marginTop: 12 }}>
            Matching does not notify companies. Click <strong>Apply</strong> on each role you want.
          </p>

          {(result.matches || []).map((m, i) => (
            <div className="match-card" key={m.match_id || i}>
              <div>
                <strong>#{i + 1} {m.company}</strong>
                <div className="muted">{m.title}</div>
                <div className="muted" style={{ marginTop: 8 }}>{m.rationale}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="score">{m.ats_score}</div>
                <div className="score-sub">ATS · sim {(m.similarity_score ?? 0).toFixed(2)}</div>
                {m.applied || m.status === 'new' || m.status === 'shortlisted' || m.status === 'rejected' ? (
                  <span className={`badge ${m.status || 'new'}`} style={{ marginTop: 8 }}>
                    {STATUS_LABEL[m.status] || 'Applied'}
                  </span>
                ) : (
                  <button
                    className="btn btn-primary"
                    style={{ marginTop: 10 }}
                    disabled={applying === m.match_id}
                    onClick={() => applyTo(m.match_id)}
                    type="button"
                  >
                    {applying === m.match_id ? 'Applying…' : 'Apply'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h2>My applications</h2>
        {applications.length === 0 ? (
          <div className="empty">No applications yet — match a resume and click Apply.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Company / role</th>
                <th>ATS</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {applications.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.company}</strong>
                    <div className="muted">{r.jd_title}</div>
                  </td>
                  <td>{r.ats_score}</td>
                  <td>
                    <span className={`badge ${r.status}`}>{STATUS_LABEL[r.status] || r.status}</span>
                    {r.status === 'shortlisted' && r.assessment_at && (
                      <div className="muted">Assessment: {new Date(r.assessment_at).toLocaleString()}</div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
