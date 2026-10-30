"""
Load scraped JDs into Chroma and create company login accounts for each company.

Run from anywhere (repo root or tools/):

    python tools/load_scraped_jds.py
    python load_scraped_jds.py

Default password for every company account: Demo@1234
Email pattern: company@<slug>.demo  e.g. company@airbnb.demo
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import hash_password
from app.db import conn, init_db
from app.ingestion.service import ingest_jd, _slug
from app.vectorstore.company_store import collection_size

PASSWORD = "Demo@1234"
DEFAULT_FILES = [
    ROOT / "tools" / "data" / "collected_jds.json",
    ROOT / "data" / "collected_jds.json",
]


def _email_for(company: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "", (company or "company").lower()) or "company"
    return f"company@{slug[:40]}.demo"


def ensure_company_account(company_name: str) -> None:
    company_name = company_name.strip()
    if len(company_name) < 2:
        return
    cid = _slug(company_name)
    email = _email_for(company_name)
    with conn() as c:
        by_email = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        by_cid = c.execute("SELECT id FROM users WHERE company_id=?", (cid,)).fetchone()
        if by_email or by_cid:
            print(f"  skip account  {email} / {company_name}")
            return
        c.execute(
            "INSERT INTO users(email,password_hash,role,name,company_name,company_id) VALUES(?,?,?,?,?,?)",
            (email, hash_password(PASSWORD), "company", f"{company_name} Recruiter", company_name, cid),
        )
        print(f"  + account     {email}  ({company_name})")


def resolve_file(user_path: str | None) -> Path:
    if user_path:
        p = Path(user_path)
        if not p.is_file():
            p = (ROOT / user_path).resolve()
        if p.is_file():
            return p
        raise SystemExit(f"File not found: {user_path}")

    for candidate in DEFAULT_FILES:
        if candidate.is_file() and candidate.stat().st_size > 10:
            return candidate

    raise SystemExit(
        "No collected JDs file found. Expected one of:\n"
        + "\n".join(f"  - {p}" for p in DEFAULT_FILES)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None, help="Path to collected_jds.json")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--skip-accounts", action="store_true")
    args = ap.parse_args()

    path = resolve_file(args.file)
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        print(f"No jobs in {path}")
        return 1

    init_db()
    print(f"Loading {len(rows)} rows from {path} …\n")

    companies = sorted({(r.get("company") or r.get("board") or "Unknown").strip() for r in rows})
    if not args.skip_accounts:
        print("Company accounts:")
        for name in companies:
            ensure_company_account(name)

    print("\nJob descriptions:")
    n = 0
    for row in rows:
        text = (row.get("text") or "").strip()
        title = (row.get("title") or "Untitled").strip()
        company = (row.get("company") or row.get("board") or "Unknown").strip()
        url = row.get("url") or ""
        if len(text) < args.min_chars:
            continue
        ingest_jd(company, title, text, url)
        n += 1
        print(f"  + {company} — {title[:70]}")
        if args.limit and n >= args.limit:
            break

    print(f"\nDone. Imported {n} JDs. Vector store size: {collection_size()}")
    print(f"All company passwords: {PASSWORD}")
    print("Candidate demo: python seed_demo.py  (optional)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
