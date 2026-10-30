"""
Load scraped JDs into Chroma (+ optional company accounts).

Run from the repo root:

    python tools/load_scraped_jds.py

Or with an explicit file:

    python tools/load_scraped_jds.py --file tools/data/collected_jds.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional

# tools/ -> repo root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_JSON = ROOT / "tools" / "data" / "collected_jds.json"
FALLBACK_JSON = ROOT / "data" / "collected_jds.json"
PASSWORD = "Demo@1234"


def find_json(user_path: Optional[str]) -> Path:
    candidates: List[Path] = []
    if user_path:
        p = Path(user_path)
        candidates.append(p if p.is_absolute() else (Path.cwd() / p))
        candidates.append(ROOT / user_path)
    candidates.extend([DEFAULT_JSON, FALLBACK_JSON])

    tried = []
    for p in candidates:
        p = p.resolve()
        tried.append(str(p))
        if p.is_file() and p.stat().st_size > 50:
            return p

    print("ERROR: could not find collected_jds.json")
    print("Tried:")
    for t in tried:
        print("  ", t)
    print()
    print("Expected file at:")
    print("  ", DEFAULT_JSON)
    print("Check with:  dir tools\\data\\collected_jds.json")
    sys.exit(1)


def ensure_company_account(company_name: str) -> None:
    from app.auth import hash_password
    from app.db import conn
    from app.ingestion.service import _slug

    company_name = (company_name or "").strip()
    if len(company_name) < 2:
        return
    cid = _slug(company_name)
    slug = re.sub(r"[^a-z0-9]+", "", company_name.lower()) or "company"
    email = f"company@{slug[:40]}.demo"

    with conn() as c:
        if c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            print(f"  skip account  {email}")
            return
        if c.execute("SELECT id FROM users WHERE company_id=?", (cid,)).fetchone():
            print(f"  skip account  company_id={cid}")
            return
        c.execute(
            "INSERT INTO users(email,password_hash,role,name,company_name,company_id) VALUES(?,?,?,?,?,?)",
            (email, hash_password(PASSWORD), "company", f"{company_name} Recruiter", company_name, cid),
        )
        print(f"  + account     {email}  ({company_name})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Import scraped JDs into Talent Graph")
    ap.add_argument("--file", default=None, help="Path to collected_jds.json")
    ap.add_argument("--limit", type=int, default=0, help="Max jobs to import (0=all)")
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--skip-accounts", action="store_true")
    args = ap.parse_args()

    print("Repo root:", ROOT)
    path = find_json(args.file)
    print("Using JSON:", path)
    print("File size:", path.stat().st_size, "bytes")

    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        print("ERROR: JSON is empty or not a list")
        return 1
    print("Jobs in file:", len(rows))

    from app.db import init_db
    from app.ingestion.service import ingest_jd
    from app.vectorstore.company_store import collection_size

    init_db()

    if not args.skip_accounts:
        print("\nCompany accounts:")
        companies = sorted(
            {(r.get("company") or r.get("board") or "Unknown").strip() for r in rows}
        )
        for name in companies:
            ensure_company_account(name)

    print("\nImporting job descriptions…")
    n = 0
    for row in rows:
        text = (row.get("text") or "").strip()
        title = (row.get("title") or "Untitled").strip()
        company = (row.get("company") or row.get("board") or "Unknown").strip()
        url = row.get("url") or ""
        if len(text) < args.min_chars:
            continue
        try:
            ingest_jd(company, title, text, url)
        except Exception as e:
            print(f"  ! fail {company} — {title[:50]}: {e}")
            continue
        n += 1
        print(f"  + [{n}] {company} — {title[:70]}")
        if args.limit and n >= args.limit:
            break

    print(f"\nDone. Imported {n} JDs.")
    print(f"Vector store size: {collection_size()}")
    print(f"Company password (if accounts created): {PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
