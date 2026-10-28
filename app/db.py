"""SQLite for accounts, sessions, resumes and matches. (JD vectors live in Chroma.)"""
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
  status TEXT NOT NULL DEFAULT 'new',   -- new | shortlisted | rejected | not_sent
  assessment_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_match_company ON matches(company_id);
CREATE INDEX IF NOT EXISTS ix_match_candidate ON matches(candidate_id);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
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
