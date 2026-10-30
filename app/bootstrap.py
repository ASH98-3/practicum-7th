"""One-time bootstrap: if Chroma has no JDs, import tools/data/collected_jds.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.vectorstore.company_store import collection_size

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATHS = [
    ROOT / "tools" / "data" / "collected_jds.json",
    ROOT / "data" / "collected_jds.json",
    Path.cwd() / "tools" / "data" / "collected_jds.json",
    Path.cwd() / "data" / "collected_jds.json",
]


def _find_json() -> Optional[Path]:
    for p in CANDIDATE_PATHS:
        try:
            if p.is_file() and p.stat().st_size > 50:
                return p
        except OSError:
            continue
    return None


def load_scraped_jds_if_empty(limit: int = 0) -> int:
    """Import scraped JDs when the store is empty. Returns number imported."""
    try:
        n = collection_size()
    except Exception as e:
        print(f"[bootstrap] could not read vector store: {e}")
        return 0

    if n > 0:
        print(f"[bootstrap] vector store already has {n} JDs — skip auto-load")
        return 0

    path = _find_json()
    if path is None:
        print("[bootstrap] no collected_jds.json found — skip auto-load")
        print("  looked in:")
        for p in CANDIDATE_PATHS:
            print(f"    {p}")
        return 0

    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[bootstrap] failed to read {path}: {e}")
        return 0

    if not isinstance(rows, list) or not rows:
        print(f"[bootstrap] {path} has no jobs")
        return 0

    from app.ingestion.service import ingest_jd

    print(f"[bootstrap] loading JDs from {path} ({len(rows)} rows)…")
    imported = 0
    for row in rows:
        text = (row.get("text") or "").strip()
        title = (row.get("title") or "Untitled").strip()
        company = (row.get("company") or row.get("board") or "Unknown").strip()
        url = row.get("url") or ""
        if len(text) < 200:
            continue
        try:
            ingest_jd(company, title, text, url)
            imported += 1
            if imported % 10 == 0:
                print(f"[bootstrap]   … {imported} imported")
        except Exception as e:
            print(f"[bootstrap] skip {company} / {title}: {e}")
        if limit and imported >= limit:
            break

    print(f"[bootstrap] done — imported {imported} JDs (store size={collection_size()})")
    return imported
