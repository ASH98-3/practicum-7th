"""FastAPI backend for Talent Graph."""
import json
import os
import sqlite3
import tempfile
import traceback
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import (current_user, end_session, hash_password, require_role, start_session, verify_password)
from app.config import USE_LLM
from app.db import conn, init_db
from app.embeddings.embedder import embedder_status
from app.ingestion.service import _slug, ingest_jd
from app.parsing.document_reader import EmptyDocumentError, UnsupportedFileType, read_resume_file
from app.pipeline.graph import build_graph
from app.schemas.models import GraphState, ResumeData
from app.vectorstore.company_store import (
    collection_size,
    delete_jd,
    get_jd_by_id,
    get_openings,
    list_jds,
    set_openings,
)

init_db()
app = FastAPI(title="Talent Graph")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = build_graph()
company_only = require_role("company")
candidate_only = require_role("candidate")


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    role: Literal["candidate", "company"]
    company_name: Optional[str] = ""


class LoginIn(BaseModel):
    email: str
    password: str


def _public(u: dict) -> dict:
    return {k: u[k] for k in ("id", "email", "name", "role", "company_name", "company_id")}


@app.post("/api/auth/register")
def register(body: RegisterIn, response: Response):
    email = body.email.strip().lower()
    if "@" not in email or len(body.name.strip()) < 2:
        raise HTTPException(400, "Enter a valid name and email.")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    cname = (body.company_name or "").strip()
    if body.role == "company" and len(cname) < 2:
        raise HTTPException(400, "Company accounts need a company name.")
    cid = _slug(cname) if body.role == "company" else None
    try:
        with conn() as c:
            uid = c.execute(
                "INSERT INTO users(email,password_hash,role,name,company_name,company_id) VALUES(?,?,?,?,?,?)",
                (email, hash_password(body.password), body.role, body.name.strip(),
                 cname or None, cid)).lastrowid
    except sqlite3.IntegrityError as e:
        if "company_id" in str(e):
            raise HTTPException(409, f"'{cname}' already has an account. Log in with it instead.")
        raise HTTPException(409, "An account with that email already exists.")
    start_session(response, uid)
    with conn() as c:
        return _public(dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()))


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response):
    with conn() as c:
        row = c.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong email or password.")
    start_session(response, row["id"])
    return _public(dict(row))


@app.post("/api/auth/logout")
def logout(response: Response, session: Optional[str] = Cookie(None)):
    try:
        end_session(response, session)
    except Exception:
        response.delete_cookie("session", path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return _public(user)


@app.get("/api/status")
def status():
    try:
        n = int(collection_size() or 0)
    except Exception:
        n = -1
    try:
        emb = embedder_status()
    except Exception:
        emb = "unknown"
    return {"llm": "groq" if USE_LLM else "offline-regex", "embedder": emb, "jd_count": n, "ok": True}


@app.get("/api/jobs")
def public_jobs():
    try:
        return list_jds() or []
    except Exception as e:
        print(f"[jobs] {e}")
        traceback.print_exc()
        return []


class JDIn(BaseModel):
    title: str
    text: str
    openings: int = Field(default=1, ge=1, le=50)


@app.get("/api/company/jds")
def company_jds(user: dict = Depends(company_only)):
    return list_jds(user["company_id"]) or []


@app.post("/api/company/jds")
def add_jd(body: JDIn, user: dict = Depends(company_only)):
    if len(body.text.strip()) < 100:
        raise HTTPException(400, "JD text is too short (need at least ~100 characters).")
    jd = ingest_jd(
        user["company_name"],
        body.title.strip() or "Untitled role",
        body.text,
        openings=body.openings,
    )
    return {"jd_id": jd.jd_id, "skills": jd.required_skills, "openings": body.openings}


class OpeningsIn(BaseModel):
    openings: int = Field(ge=1, le=50)


@app.patch("/api/company/jds/{jd_id}/openings")
def patch_openings(jd_id: str, body: OpeningsIn, user: dict = Depends(company_only)):
    jd = get_jd_by_id(jd_id)
    if jd is None or jd.company_id != user["company_id"]:
        raise HTTPException(404, "JD not found for your company.")
    set_openings(jd_id, body.openings)
    return {"jd_id": jd_id, "openings": body.openings}


@app.delete("/api/company/jds/{jd_id}")
def remove_jd(jd_id: str, user: dict = Depends(company_only)):
    jd = get_jd_by_id(jd_id)
    if jd is None or jd.company_id != user["company_id"]:
        raise HTTPException(404, "JD not found for your company.")
    delete_jd(jd_id)
    return {"deleted": jd_id}


class StatusIn(BaseModel):
    status: Literal["new", "shortlisted", "rejected"]
    assessment_at: Optional[str] = None


@app.get("/api/company/applicants")
def applicants(user: dict = Depends(company_only)):
    """All applicants who Applied. Ranked per JD; top `openings` marked within_openings."""
    with conn() as c:
        rows = c.execute(
            "SELECT m.*, r.profile_json, r.text, u.name AS cname, u.email AS cemail "
            "FROM matches m JOIN resumes r ON r.id=m.resume_id JOIN users u ON u.id=m.candidate_id "
            "WHERE m.company_id=? AND m.status!='not_sent' "
            "ORDER BY m.jd_id, m.ats_score DESC, m.id ASC",
            (user["company_id"],),
        ).fetchall()

    by_jd = defaultdict(list)
    for r in rows:
        by_jd[r["jd_id"]].append(r)

    out = []
    for jd_id, group in by_jd.items():
        openings = get_openings(jd_id)
        for rank, r in enumerate(group, start=1):
            out.append({
                "id": r["id"],
                "jd_id": r["jd_id"],
                "candidate_name": r["cname"],
                "candidate_email": r["cemail"],
                "jd_title": r["jd_title"],
                "ats_score": r["ats_score"],
                "similarity": r["similarity"],
                "rationale": r["rationale"],
                "status": r["status"],
                "assessment_at": r["assessment_at"],
                "profile": json.loads(r["profile_json"]),
                "resume_excerpt": r["text"][:1500],
                "rank": rank,
                "openings": openings,
                "within_openings": rank <= openings,
            })
    # overall list: still useful sorted by score for company overview
    out.sort(key=lambda a: (-(a["ats_score"] or 0), a["jd_title"] or "", a["rank"]))
    return out


@app.patch("/api/company/applicants/{match_id}")
def set_status(match_id: int, body: StatusIn, user: dict = Depends(company_only)):
    at = None
    if body.status == "shortlisted" and body.assessment_at:
        try:
            at = datetime.fromisoformat(body.assessment_at).isoformat(timespec="minutes")
        except ValueError:
            raise HTTPException(400, "Invalid assessment date/time.")
    with conn() as c:
        cur = c.execute(
            "UPDATE matches SET status=?, assessment_at=? WHERE id=? AND company_id=? AND status!='not_sent'",
            (body.status, at, match_id, user["company_id"]),
        )
    if cur.rowcount == 0:
        raise HTTPException(404, "Applicant not found for your company.")
    return {"id": match_id, "status": body.status, "assessment_at": at}


@app.post("/api/company/jds/{jd_id}/finalize")
def finalize_by_openings(jd_id: str, user: dict = Depends(company_only)):
    """Keep top `openings` applicants shortlisted; mark the rest rejected."""
    jd = get_jd_by_id(jd_id)
    if jd is None or jd.company_id != user["company_id"]:
        raise HTTPException(404, "JD not found for your company.")
    openings = get_openings(jd_id)
    with conn() as c:
        rows = c.execute(
            "SELECT id FROM matches WHERE company_id=? AND jd_id=? AND status!='not_sent' "
            "ORDER BY ats_score DESC, id ASC",
            (user["company_id"], jd_id),
        ).fetchall()
        shortlisted, rejected = [], []
        for i, r in enumerate(rows):
            if i < openings:
                c.execute("UPDATE matches SET status='shortlisted' WHERE id=?", (r["id"],))
                shortlisted.append(r["id"])
            else:
                c.execute("UPDATE matches SET status='rejected', assessment_at=NULL WHERE id=?", (r["id"],))
                rejected.append(r["id"])
    return {
        "jd_id": jd_id,
        "openings": openings,
        "shortlisted_ids": shortlisted,
        "rejected_ids": rejected,
        "message": f"Top {openings} shortlisted; {len(rejected)} rejected.",
    }


@app.post("/api/candidate/match")
def match(
    file: Optional[UploadFile] = File(None),
    text: str = Form(""),
    user: dict = Depends(candidate_only),
):
    """Match only — does not auto-apply. Candidate must call /apply."""
    try:
        n = collection_size()
    except Exception:
        n = 0
    if n == 0:
        raise HTTPException(400, "No jobs are registered yet. Run: python tools/load_scraped_jds.py")

    source = "pasted text"
    if file is not None and file.filename:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix.lower()) as tmp:
            tmp.write(file.file.read())
            path = tmp.name
        try:
            raw = read_resume_file(path)
        except (UnsupportedFileType, EmptyDocumentError) as e:
            raise HTTPException(400, str(e))
        finally:
            os.unlink(path)
        source = file.filename
    elif text.strip():
        raw = text.strip()
    else:
        raise HTTPException(400, "Upload a resume file or paste its text.")

    resume = ResumeData(
        candidate_id=f"cand_{user['id']}_{uuid.uuid4().hex[:6]}",
        raw_text=raw,
        source_file=source,
    )
    state = GraphState.model_validate(_graph.invoke(GraphState(resume=resume)))
    r = state.resume
    profile = {"skills": r.skills, "experience_years": r.experience_years, "education": r.education}

    out = []
    with conn() as c:
        rid = c.execute(
            "INSERT INTO resumes(user_id,filename,text,profile_json,share) VALUES(?,?,?,?,?)",
            (user["id"], source, raw, json.dumps(profile), 0),
        ).lastrowid
        for m in state.top_matches:
            # Always not_sent until candidate Applies
            mid = c.execute(
                "INSERT INTO matches(resume_id,candidate_id,jd_id,jd_title,jd_url,company_id,company,"
                "ats_score,similarity,rationale,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid, user["id"], m.jd_id, m.title, m.url, m.company_id, m.company,
                    m.ats_score, m.similarity_score, m.rationale, "not_sent",
                ),
            ).lastrowid
            out.append({**m.model_dump(), "match_id": mid, "status": "not_sent", "applied": False})
    return {"decision": state.decision, "profile": profile, "matches": out}


class ApplyIn(BaseModel):
    match_id: int


@app.post("/api/candidate/apply")
def apply(body: ApplyIn, user: dict = Depends(candidate_only)):
    """Explicit apply — multiple candidates may apply to the same JD."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM matches WHERE id=? AND candidate_id=?",
            (body.match_id, user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Match not found.")
        if row["status"] != "not_sent":
            return {
                "match_id": body.match_id,
                "status": row["status"],
                "message": "Already applied.",
                "applied": True,
            }
        # prevent duplicate active applications to same JD from same candidate
        other = c.execute(
            "SELECT id FROM matches WHERE candidate_id=? AND jd_id=? AND status!='not_sent' AND id!=?",
            (user["id"], row["jd_id"], body.match_id),
        ).fetchone()
        if other:
            raise HTTPException(409, "You already applied to this role.")
        c.execute("UPDATE matches SET status='new' WHERE id=?", (body.match_id,))
    return {"match_id": body.match_id, "status": "new", "message": "Application submitted.", "applied": True}


@app.get("/api/candidate/matches")
def my_matches(user: dict = Depends(candidate_only)):
    with conn() as c:
        rows = c.execute(
            "SELECT m.*, r.filename FROM matches m JOIN resumes r ON r.id=m.resume_id "
            "WHERE m.candidate_id=? ORDER BY m.id DESC LIMIT 80",
            (user["id"],),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["applied"] = d.get("status") != "not_sent"
        out.append(d)
    return out


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="static")
