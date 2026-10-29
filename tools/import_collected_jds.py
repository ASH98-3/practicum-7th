"""
Import JDs previously collected by tools/fetch_jds.py into the app store.

    python tools/import_collected_jds.py
    python tools/import_collected_jds.py --file data/collected_jds.json --limit 20

Uses the same ingest_jd() path as the company UI (parse → embed → Chroma).
Company names in the JSON become company_id slugs; if you later register a
company account with the same name, those JDs show under that account.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as `python tools/import_collected_jds.py` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ingestion.service import ingest_jd
from app.vectorstore.company_store import collection_size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/collected_jds.json")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--min-chars", type=int, default=200)
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        print("Run: python tools/fetch_jds.py")
        return 1

    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("Expected a JSON list of jobs")
        return 1

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
        print(f"  + {company} — {title}")
        if args.limit and n >= args.limit:
            break

    print(f"\nImported {n} JDs. Store now holds {collection_size()} total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
