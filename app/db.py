"""SQLite for accounts, sessions, resumes, matches, and JD metadata."""
import os
import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('candidate','company')),
  name TEXT NOT NULL, company_name TEXT, company_id TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE UNIQUE INDEX IF NOT EXISTS ux_company ON users(company_id) WHERE company_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS resumes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
  filename TEXT, text TEXT NOT NULL, profile_json TEXT NOT NULL, share INTEGER NOT NULL DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS matches(
  id INTEGER PRIMARY KEY AUTOINCREMENT, resume_id INTEGER NOT NULL REFERENCES resumes(id),
  candidate_id INTEGER NOT NULL REFERENCES users(id),
  jd_id TEXT NOT NULL, jd_title TEXT, jd_url TEXT, company_id TEXT NOT NULL, company TEXT NOT NULL,
  ats_score REAL, similarity REAL, rationale TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  assessment_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_match_company ON matches(company_id);
CREATE INDEX IF NOT EXISTS ix_match_candidate ON matches(candidate_id);
CREATE TABLE IF NOT EXISTS jd_meta(
  jd_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT DEFAULT '',
  required_skills TEXT DEFAULT '',
  min_experience_years INTEGER DEFAULT 0,
  education_requirement TEXT DEFAULT '',
  parsed_summary TEXT DEFAULT '',
  raw_text TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_jd_company ON jd_meta(company_id);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with conn() as c:
        c.executescript(SCHEMA)
        # migrate older jd_meta without raw_text / extra columns
        cols = {r[1] for r in c.execute("PRAGMA table_info(jd_meta)").fetchall()}
        for col, decl in [
            ("education_requirement", "TEXT DEFAULT ''"),
            ("parsed_summary", "TEXT DEFAULT ''"),
            ("raw_text", "TEXT DEFAULT ''"),
        ]:
            if col not in cols:
                c.execute(f"ALTER TABLE jd_meta ADD COLUMN {col} {decl}")
