# Talent Graph — backend pipeline (real AI, real vector store)

Upgrade of the Phase 1 notebook demo into an actual backend: real embeddings,
a persistent vector store of company JDs, PDF/DOCX resume parsing, and Groq
for structured extraction + skill-equivalence judgment.

## Architecture

| Layer | What it does | Tech |
|---|---|---|
| `app/parsing/document_reader.py` | Resume file → raw text | pypdf, python-docx |
| `app/parsing/llm_extractor.py` | Raw text → structured fields (skills, experience, education) | Groq LLM (offline regex fallback if no API key) |
| `app/embeddings/embedder.py` | Text → semantic vector | sentence-transformers (local, not the LLM) |
| `app/vectorstore/company_store.py` | Persistent store of every company's JDs, semantic search across all of them | Chroma |
| `app/matching/ats_scorer.py` | Rubric fit score + LLM equivalence bonus | Groq LLM |
| `app/pipeline/graph.py` | Wires it all together, routes shortlist/manual_review/reject | LangGraph |

**Why two AI components, not one**: embeddings do ranking/similarity (a
specialized NLP model, not the LLM); the Groq LLM does understanding — turning
messy prose into structured fields, and judging skill equivalence the keyword
rubric can't see. See the chat explanation for more on this split.

## Setup & run

```bash
pip install -r requirements.txt
cp .env.example .env          # add GROQ_API_KEY (optional but strongly recommended)
uvicorn app.api:app --reload  # open http://localhost:8000
```

The header pills in the UI show whether the LLM and the real embedding model are active
(amber = running on a fallback; fix that before trusting match quality).

## Accounts and roles

- **Company account** (one per company name): manages only its own JDs, sees candidates whose
  resumes matched them (ATS 60+), and can shortlist (with an assessment date/time) or reject.
- **Candidate account**: uploads a resume, sees ranked matches, and sees each company's response
  and assessment schedule. A checkbox controls whether the profile is shared with companies.
- Passwords are scrypt-hashed; sessions are HttpOnly cookies stored hashed in SQLite (`data/app.db`).
- Seeded JDs (from `seed_real_jds.py`) belong to their company name. If someone registers a company
  account with the same name (e.g. "Stripe"), they take ownership of those JDs. Fine for a demo,
  not for production (needs email-domain verification).

## Loading real JDs

- **Before a demo:** `python seed_real_jds.py` bulk-loads real postings from Greenhouse/Lever boards.
- **As a company:** log in, then Paste text / From URL / Import your own job board.

## Layout

`app/api.py` (FastAPI) · `app/auth.py`, `app/db.py` (accounts, SQLite) · `static/index.html` (frontend) ·
`app/ingestion/` (JD sources) · `app/pipeline/graph.py` (LangGraph) · `app/vectorstore/` (Chroma) ·
`app/parsing/` · `app/matching/`

## Not built yet
Multiple employees per company (invites), email verification, password reset, rate limiting,
multi-candidate assignment (Hungarian), real email/calendar notifications, OCR, deployment.
