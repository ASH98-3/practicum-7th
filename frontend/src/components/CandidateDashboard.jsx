import { useEffect, useState } from 'react'
import { api } from '../api'

const STATUS_LABEL = {
  new: 'Awaiting company review',
  shortlisted: 'Shortlisted',
  rejected: 'Not selected',
  not_sent: 'Not sent (low fit or not shared)',
}

export default function CandidateDashboard({ onMatched }) {
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [share, setShare] = useState(true)
  const [loading, setLoading] = useState(false)
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
      fd.append('share', share)
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

  const decisionLabel = {
    shortlist: 'Strong fit found',
    manual_review: 'Partial fit',
    reject: 'No strong fit',
  }

  return (
    <>
      <div className="hero">
        <h1>Find your best-fit companies</h1>
        <p>Upload a resume. We extract skills, embed your profile, and rank live company JDs with ATS-style scoring.</p>
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
            <label className="check">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
              <span>Share my profile with companies I match well (score 60+)</span>
            </label>
            <button className="btn btn-primary" disabled={loading}>
              {loading ? 'Matching…' : 'Find best-fit companies'}
            </button>
            {msg && <div className={`msg ${err ? 'error' : ''}`}>{msg}</div>}
          </form>
        </div>

        <div className="card">
          <h2>How it works</h2>
          <p className="muted">1. Parse resume into skills, experience, education</p>
          <p className="muted">2. Embed profile with a local sentence-transformers model</p>
          <p className="muted">3. Retrieve similar JDs from the vector store</p>
          <p className="muted">4. Re-score with ATS rubric + LLM skill equivalence</p>
          <p className="muted">5. Route: shortlist · manual review · reject</p>
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
            {result.shared
              ? 'Your profile was sent to companies scoring 60+. Track their response below.'
              : 'Sharing is off: nothing was sent to companies.'}
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
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h2>Match history & status</h2>
        {history.length === 0 ? (
          <div className="empty">No matches yet — upload a resume above.</div>
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
              {history.map((r) => (
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
