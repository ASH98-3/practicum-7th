import { useEffect, useState } from 'react'
import { api } from '../api'

const STATUS_LABEL = {
  new: 'Awaiting review',
  shortlisted: 'Shortlisted',
  rejected: 'Rejected',
}

export default function CompanyDashboard({ user, onChanged }) {
  const [tab, setTab] = useState('apps')
  const [applicants, setApplicants] = useState([])
  const [jds, setJds] = useState([])
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState(false)
  const [loading, setLoading] = useState(false)
  const [assessment, setAssessment] = useState({})

  async function loadApps() {
    try {
      setApplicants(await api.applicants())
    } catch {
      setApplicants([])
    }
  }

  async function loadJds() {
    try {
      setJds(await api.companyJds())
      onChanged?.()
    } catch {
      setJds([])
    }
  }

  useEffect(() => {
    if (tab === 'apps') loadApps()
    else loadJds()
  }, [tab])

  async function addJd(e) {
    e.preventDefault()
    setLoading(true)
    setMsg('')
    setErr(false)
    try {
      const d = await api.addJd({ title, text })
      setMsg(`Added. Skills detected: ${(d.skills || []).join(', ') || 'none'}.`)
      setTitle('')
      setText('')
      await loadJds()
    } catch (e) {
      setErr(true)
      setMsg(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function removeJd(id) {
    try {
      await api.deleteJd(id)
      await loadJds()
    } catch (e) {
      alert(e.message)
    }
  }

  async function setStatus(id, status) {
    try {
      await api.setStatus(id, {
        status,
        assessment_at: status === 'shortlisted' ? assessment[id] || null : null,
      })
      await loadApps()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <>
      <div className="hero">
        <h1>{user.company_name}</h1>
        <p>Post roles, review AI-matched applicants, and shortlist candidates with an assessment slot.</p>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'apps' ? 'active' : ''}`} onClick={() => setTab('apps')} type="button">
          Applicants
        </button>
        <button className={`tab ${tab === 'jds' ? 'active' : ''}`} onClick={() => setTab('jds')} type="button">
          My job descriptions
        </button>
      </div>

      {tab === 'apps' && (
        <div>
          {applicants.length === 0 ? (
            <div className="card empty">
              No applicants yet. Candidates appear here when their resume matches one of your JDs with a score of 60+.
            </div>
          ) : (
            applicants.map((a) => (
              <div className="applicant" key={a.id}>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <strong>{a.candidate_name}</strong>
                    <span className="muted"> · {a.candidate_email}</span>
                    <div className="muted">Matched for {a.jd_title}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div className="score">{a.ats_score}</div>
                    <div className="score-sub">ATS · sim {(a.similarity ?? 0).toFixed(2)}</div>
                  </div>
                </div>
                <div className="chips">
                  {(a.profile?.skills || []).map((s) => (
                    <span className="chip" key={s}>{s}</span>
                  ))}
                </div>
                <div className="muted" style={{ marginTop: 8 }}>
                  {a.profile?.experience_years} yrs · {(a.profile?.education || []).join(', ')}
                </div>
                <div className="muted" style={{ marginTop: 6 }}>{a.rationale}</div>
                <details style={{ marginTop: 10 }}>
                  <summary className="muted">Resume excerpt</summary>
                  <pre className="excerpt">{a.resume_excerpt}</pre>
                </details>
                <div className="row" style={{ marginTop: 12 }}>
                  <span className={`badge ${a.status}`}>{STATUS_LABEL[a.status] || a.status}</span>
                  <input
                    type="datetime-local"
                    value={assessment[a.id] || a.assessment_at || ''}
                    onChange={(e) => setAssessment((s) => ({ ...s, [a.id]: e.target.value }))}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 10,
                      border: '1px solid var(--border)',
                      background: 'var(--bg-elevated)',
                    }}
                  />
                  <button className="btn btn-ok" onClick={() => setStatus(a.id, 'shortlisted')} type="button">
                    Shortlist & schedule
                  </button>
                  <button className="btn btn-danger" onClick={() => setStatus(a.id, 'rejected')} type="button">
                    Reject
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'jds' && (
        <div className="grid-2">
          <div className="card">
            <h2>Post a job</h2>
            <form onSubmit={addJd}>
              <div className="field">
                <label>Job title</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend Engineer" required />
              </div>
              <div className="field">
                <label>Full job description</label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste the full JD (skills, experience, education…)"
                  required
                />
              </div>
              <button className="btn btn-primary" disabled={loading}>
                {loading ? 'Adding…' : 'Add JD'}
              </button>
              {msg && <div className={`msg ${err ? 'error' : 'ok'}`}>{msg}</div>}
            </form>
          </div>

          <div className="card">
            <h2>Your registered JDs</h2>
            {jds.length === 0 ? (
              <div className="empty">No JDs yet — add one on the left.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Role</th>
                    <th>Skills</th>
                    <th>Exp</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {jds.map((r) => (
                    <tr key={r.jd_id}>
                      <td>{r.title}</td>
                      <td>
                        <div className="chips">
                          {(r.required_skills || []).slice(0, 6).map((s) => (
                            <span className="chip" key={s}>{s}</span>
                          ))}
                        </div>
                      </td>
                      <td>{r.min_experience_years}y</td>
                      <td>
                        <button className="btn btn-danger" onClick={() => removeJd(r.jd_id)} type="button">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </>
  )
}
