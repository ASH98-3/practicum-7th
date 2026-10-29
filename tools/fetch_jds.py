"""
Standalone job-description collector (NOT part of the live demo UI).

Pulls public postings from Greenhouse / Lever job-board APIs and saves them
to a JSON file. You can review/edit the file, then import into the app later
with tools/import_collected_jds.py.

Usage:
    python tools/fetch_jds.py
    python tools/fetch_jds.py --per-board 10 --out data/collected_jds.json
    python tools/fetch_jds.py --only greenhouse

Notes:
  - Uses official public board APIs (not LinkedIn/Indeed — those block scrapers).
  - Board tokens are the slug in boards.greenhouse.io/<token> or jobs.lever.co/<token>.
  - Failed boards are skipped; one bad token does not stop the run.
  - Output is append-friendly by JD id (re-runs update/skip duplicates).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Prefer requests if installed; fall back to urllib (stdlib only).
try:
    import requests

    def _get_json(url: str) -> object:
        r = requests.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r.json()
except ImportError:
    import json as _json

    def _get_json(url: str) -> object:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=25) as resp:
            return _json.loads(resp.read().decode("utf-8", errors="replace"))

HEADERS = {"User-Agent": "TalentGraph-Collector/1.0 (student project; local research)"}

# (source, board_token) — public careers boards. Edit freely.
DEFAULT_BOARDS = [
    ("greenhouse", "stripe"),
    ("greenhouse", "airbnb"),
    ("greenhouse", "databricks"),
    ("greenhouse", "cloudflare"),
    ("greenhouse", "datadog"),
    ("greenhouse", "figma"),
    ("greenhouse", "discord"),
    ("greenhouse", "notion"),
    ("lever", "spotify"),
    ("lever", "netflix"),
    ("lever", "plaid"),
]


def _strip_html(raw: str) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def greenhouse_jobs(board: str, limit: int) -> Iterator[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    data = _get_json(url)
    company = board.replace("-", " ").title()
    for job in (data.get("jobs") or [])[:limit]:
        text = _strip_html(job.get("content") or "")
        if len(text) < 200:
            continue
        yield {
            "source": "greenhouse",
            "board": board,
            "company": company,
            "title": job.get("title") or "Untitled",
            "url": job.get("absolute_url") or "",
            "text": text,
            "external_id": f"greenhouse:{board}:{job.get('id')}",
        }


def lever_jobs(board: str, limit: int) -> Iterator[dict]:
    url = f"https://api.lever.co/v0/postings/{board}?mode=json"
    data = _get_json(url)
    company = board.replace("-", " ").title()
    for p in (data or [])[:limit]:
        text = p.get("descriptionPlain") or _strip_html(p.get("description") or "")
        for lst in p.get("lists") or []:
            text += f"\n{lst.get('text', '')}\n{_strip_html(lst.get('content', ''))}"
        text = text.strip()
        if len(text) < 200:
            continue
        yield {
            "source": "lever",
            "board": board,
            "company": company,
            "title": p.get("text") or "Untitled",
            "url": p.get("hostedUrl") or "",
            "text": text,
            "external_id": f"lever:{board}:{p.get('id')}",
        }


SOURCES = {
    "greenhouse": greenhouse_jobs,
    "lever": lever_jobs,
}


def load_existing(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for row in rows if isinstance(rows, list) else []:
        key = row.get("external_id") or f"{row.get('company')}|{row.get('title')}|{row.get('url')}"
        out[key] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect public JDs into a JSON file")
    ap.add_argument("--out", default="data/collected_jds.json", help="Output JSON path")
    ap.add_argument("--per-board", type=int, default=8, help="Max jobs per board")
    ap.add_argument("--only", choices=list(SOURCES), help="Only one source type")
    ap.add_argument("--delay", type=float, default=0.4, help="Seconds between boards")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_id = load_existing(out_path)

    ok, failed, added = [], [], 0
    for source, board in DEFAULT_BOARDS:
        if args.only and source != args.only:
            continue
        try:
            n = 0
            for job in SOURCES[source](board, args.per_board):
                key = job["external_id"]
                if key not in by_id:
                    added += 1
                by_id[key] = job
                n += 1
            print(f"  ok   {source}:{board}  {n} jobs")
            ok.append(f"{source}:{board}")
        except (HTTPError, URLError, Exception) as e:
            print(f"  skip {source}:{board}  ({type(e).__name__}: {str(e)[:80]})")
            failed.append(f"{source}:{board}")
        time.sleep(args.delay)

    rows: List[dict] = sorted(by_id.values(), key=lambda r: (r.get("company", ""), r.get("title", "")))
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSaved {len(rows)} jobs → {out_path}  (+{added} new this run)")
    if failed:
        print(f"Skipped boards: {', '.join(failed)}")
    print("Next: review the JSON, then run  python tools/import_collected_jds.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
