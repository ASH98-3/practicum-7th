# Talent Graph

AI-powered talent matching: parse resumes, embed profiles, retrieve company JDs from a vector store, and score with an ATS rubric + LLM skill equivalence.

**Stack**
- Backend: FastAPI, LangGraph, Chroma, sentence-transformers, Groq
- Frontend: React + Vite (`frontend/`)

## Architecture

| Layer | What it does | Tech |
|---|---|---|
| `app/parsing/document_reader.py` | Resume file → raw text | pypdf, python-docx |
| `app/parsing/llm_extractor.py` | Raw text → structured fields | Groq LLM (offline regex fallback) |
| `app/embeddings/embedder.py` | Text → semantic vector | sentence-transformers |
| `app/vectorstore/company_store.py` | Persistent JD store + search | Chroma |
| `app/matching/ats_scorer.py` | Rubric + LLM equivalence bonus | Groq |
| `app/pipeline/graph.py` | End-to-end routing | LangGraph |
| `frontend/` | Company & candidate UI | React + Vite |

## How to start the project

You need **two terminals** (backend + frontend).

### 1. Backend (API)

```bash
cd practicum-7th
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env and add GROQ_API_KEY
uvicorn app.api:app --reload       # http://127.0.0.1:8000
```

### 2. Frontend (React)

```bash
cd practicum-7th/frontend
npm install
npm run dev                        # http://localhost:5173
```

Open **http://localhost:5173** for the new UI.  
The old static UI remains at **http://127.0.0.1:8000** if needed.

Vite proxies `/api/*` to the FastAPI server, so cookie sessions work in local dev.

## Demo flow for the panel

1. Register a **company** account → paste 1–2 job descriptions → Add JD  
2. Log out → register a **candidate** → upload / paste a resume → Find matches  
3. Log back in as company → see applicant → shortlist + set assessment time  
4. Candidate history shows the company response  

Header pills show whether the LLM and embeddings are live (amber = fallback).

## What is required for it to function

| Requirement | Why |
|---|---|
| Python 3.10+ | Backend runtime |
| Node.js 18+ / npm | React frontend |
| `pip install -r requirements.txt` | Backend deps |
| `npm install` in `frontend/` | Frontend deps |
| `.env` with optional `GROQ_API_KEY` | Better extraction & ATS rationale; works offline without it |
| First download of embedding model | `all-MiniLM-L6-v2` downloads on first run (needs network once) |
| At least one company JD | Matching fails with a clear error if the vector store is empty |

**Not required for a basic demo:** production DB, email, Docker, Greenhouse/Lever imports.

## Accounts and roles

- **Company**: paste JD title + text, review applicants (ATS ≥ 60), shortlist/reject  
- **Candidate**: upload resume, see ranked matches and company responses  
- Auth: scrypt passwords, HttpOnly cookie sessions in SQLite (`data/app.db`)

## Layout

```
app/api.py              FastAPI routes + CORS
app/auth.py, app/db.py  sessions & SQLite
app/pipeline/graph.py   LangGraph matching pipeline
app/vectorstore/        Chroma JD store
frontend/               React (Vite) UI
static/                 legacy single-page UI
```

## Not built yet

Multi-employee company invites, email verification, password reset, rate limiting,
global multi-candidate assignment (Hungarian), real email/calendar notifications, OCR, deployment.
