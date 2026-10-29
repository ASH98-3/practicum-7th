"""
Standalone job-description collector (NOT part of the live demo UI).

Pulls public postings from Greenhouse / Lever job-board APIs, keeps only
tech-relevant roles, and saves FULL job description text into JSON.

Each saved object looks like:
  {
    "company": "Stripe",
    "title": "Backend Engineer",
    "url": "https://...",
    "text": "<full plain-text job description — this is the actual JD>",
    "text_chars": 4821,
    ...
  }

The importer (tools/import_collected_jds.py) uses the "text" field as the JD body.

Usage:
    python tools/fetch_jds.py
    python tools/fetch_jds.py --per-board 10 --out data/collected_jds.json
    python tools/fetch_jds.py --only greenhouse
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterator, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HEADERS = {"User-Agent": "TalentGraph-Collector/1.0 (student project; local research)"}

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

DEFAULT_BOARDS = [
    ("greenhouse", "stripe"),
    ("greenhouse", "airbnb"),
    ("greenhouse", "databricks"),
    ("greenhouse", "cloudflare"),
    ("greenhouse", "datadog"),
    ("greenhouse", "figma"),
    ("greenhouse", "discord"),
    ("greenhouse", "notion"),
    ("greenhouse", "roblox"),
    ("lever", "spotify"),
    ("lever", "netflix"),
    ("lever", "plaid"),
]

TECH_TITLE_KEYWORDS = [
    r"software", r"developer", r"engineer", r"engineering",
    r"full\s*stack", r"fullstack", r"front\s*end", r"frontend", r"back\s*end", r"backend",
    r"web\s*dev", r"web\s*engineer", r"application\s*dev", r"app\s*dev", r"mobile",
    r"android", r"ios", r"react", r"node", r"python", r"java", r"golang", r"\bgo\b",
    r"data\s*scien", r"data\s*engin", r"data\s*analy", r"analytics\s*engineer",
    r"machine\s*learning", r"\bml\b", r"\bai\b", r"artificial\s*intelligence",
    r"deep\s*learning", r"nlp", r"computer\s*vision", r"llm", r"gen\s*ai", r"generative",
    r"devops", r"sre", r"site\s*reliability", r"platform\s*engineer", r"cloud\s*engineer",
    r"infrastructure", r"security\s*engineer", r"cyber", r"qa\s*engineer", r"sdet",
    r"test\s*engineer", r"automation\s*engineer", r"systems?\s*engineer",
    r"database", r"\bsql\b", r"etl", r"analytics", r"bi\s*engineer",
    r"research\s*engineer", r"applied\s*scientist", r"research\s*scientist",
    r"intern.*(software|engineer|developer|data|ml|ai)",
    r"(software|engineer|developer|data|ml|ai).*intern",
]

EXCLUDE_TITLE_KEYWORDS = [
    r"sales", r"account\s*executive", r"account\s*manager", r"business\s*development",
    r"recruiter", r"talent\s*acquisition", r"people\s*partner", r"hr\b", r"human\s*resources",
    r"marketing", r"brand", r"content\s*writer", r"copywriter", r"social\s*media",
    r"legal", r"counsel", r"attorney", r"compliance\s*officer",
    r"finance", r"accountant", r"controller", r"bookkeep",
    r"customer\s*success", r"customer\s*support", r"customer\s*service",
    r"office\s*manager", r"executive\s*assistant", r"receptionist",
    r"nurse", r"physician", r"therapist", r"retail", r"store\s*manager",
    r"abuse\s*investigator", r"trust\s*and\s*safety",
]

_TECH_RE = re.compile("|".join(TECH_TITLE_KEYWORDS), re.I)
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_TITLE_KEYWORDS), re.I)
MIN_JD_CHARS = 300


def is_tech_role(title: str, text: str = "") -> bool:
    t = title or ""
    if _EXCLUDE_RE.search(t):
        return False
    if _TECH_RE.search(t):
        return True
    head = (text or "")[:1200]
    body_hits = re.search(
        r"python|javascript|typescript|react|node\.js|java\b|kotlin|swift|"
        r"machine learning|deep learning|tensorflow|pytorch|sql|kubernetes|docker|aws|gcp|azure",
        head,
        re.I,
    )
    return bool(body_hits and re.search(r"engineer|developer|scientist|analyst", t, re.I))


def _strip_html(raw: str) -> str:
    """Turn API HTML (sometimes double-escaped) into plain JD text."""
    text = raw or ""
    # Greenhouse often returns <p>...</p> — unescape until stable.
    for _ in range(3):
        un = html.unescape(text)
        if un == text:
            break
        text = un
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|h[1-6]|li|tr)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _pack(company: str, title: str, url: str, text: str, source: str, board: str, external_id: str) -> Optional[dict]:
    text = (text or "").strip()
    if len(text) < MIN_JD_CHARS:
        return None
    return {
        "source": source,
        "board": board,
        "company": company,
        "title": title or "Untitled",
        "url": url or "",
        "text": text,  # FULL job description body used by the app
        "text_chars": len(text),
        "external_id": external_id,
    }


def _greenhouse_job_content(board: str, job_id: object) -> str:
    """Fallback: fetch a single job when the list payload has empty content."""
    try:
        data = _get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?questions=false"
        )
        if isinstance(data, dict):
            return _strip_html(data.get("content") or "")
    except Exception:
        return ""
    return ""


def greenhouse_jobs(board: str, fetch_n: int) -> Iterator[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    data = _get_json(url)
    company_fallback = board.replace("-", " ").title()
    for job in (data.get("jobs") or [])[:fetch_n]:
        if not isinstance(job, dict):
            continue
        company = (job.get("company_name") or company_fallback).strip()
        title = job.get("title") or "Untitled"
        text = _strip_html(job.get("content") or "")
        if len(text) < MIN_JD_CHARS and job.get("id") is not None:
            text = _greenhouse_job_content(board, job["id"]) or text
        packed = _pack(
            company=company,
            title=title,
            url=job.get("absolute_url") or "",
            text=text,
            source="greenhouse",
            board=board,
            external_id=f"greenhouse:{board}:{job.get('id')}",
        )
        if packed:
            yield packed


def lever_jobs(board: str, fetch_n: int) -> Iterator[dict]:
    url = f"https://api.lever.co/v0/postings/{board}?mode=json"
    data = _get_json(url)
    company = board.replace("-", " ").title()
    for p in (data or [])[:fetch_n]:
        if not isinstance(p, dict):
            continue
        text = p.get("descriptionPlain") or _strip_html(p.get("description") or "")
        for lst in p.get("lists") or []:
            if not isinstance(lst, dict):
                continue
            text += f"\n{lst.get('text', '')}\n{_strip_html(lst.get('content', ''))}"
        # Lever categories sometimes hold extra structured sections
        for cat in p.get("categories") or []:
            if isinstance(cat, str):
                text += f"\n{cat}"
        packed = _pack(
            company=company,
            title=p.get("text") or "Untitled",
            url=p.get("hostedUrl") or "",
            text=text,
            source="lever",
            board=board,
            external_id=f"lever:{board}:{p.get('id')}",
        )
        if packed:
            yield packed


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
    ap = argparse.ArgumentParser(description="Collect tech JDs (full text) into a JSON file")
    ap.add_argument("--out", default="data/collected_jds.json", help="Output JSON path")
    ap.add_argument("--per-board", type=int, default=12, help="Max tech jobs to keep per board")
    ap.add_argument("--fetch-pool", type=int, default=60,
                    help="How many raw postings to pull per board before filtering")
    ap.add_argument("--only", choices=list(SOURCES), help="Only one source type")
    ap.add_argument("--delay", type=float, default=0.4, help="Seconds between boards")
    ap.add_argument("--no-filter", action="store_true", help="Disable tech-role filter")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_id = load_existing(out_path)

    ok, failed, added = [], [], 0
    for source, board in DEFAULT_BOARDS:
        if args.only and source != args.only:
            continue
        try:
            kept = 0
            scanned = 0
            for job in SOURCES[source](board, args.fetch_pool):
                scanned += 1
                if not args.no_filter and not is_tech_role(job["title"], job["text"]):
                    continue
                key = job["external_id"]
                if key not in by_id:
                    added += 1
                by_id[key] = job
                kept += 1
                if kept >= args.per_board:
                    break
            print(f"  ok   {source}:{board}  kept {kept}/{scanned} tech roles with full JD text")
            ok.append(f"{source}:{board}")
        except (HTTPError, URLError, Exception) as e:
            print(f"  skip {source}:{board}  ({type(e).__name__}: {str(e)[:80]})")
            failed.append(f"{source}:{board}")
        time.sleep(args.delay)

    rows: List[dict] = sorted(by_id.values(), key=lambda r: (r.get("company", ""), r.get("title", "")))
    if not args.no_filter:
        before = len(rows)
        rows = [
            r for r in rows
            if is_tech_role(r.get("title", ""), r.get("text", ""))
            and len((r.get("text") or "").strip()) >= MIN_JD_CHARS
        ]
        dropped = before - len(rows)
        if dropped:
            print(f"  cleaned {dropped} non-tech / empty-body rows from existing file")

    # Ensure text_chars is present for quick inspection in editors
    for r in rows:
        r["text_chars"] = len((r.get("text") or "").strip())

    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if rows:
        avg = sum(r["text_chars"] for r in rows) // len(rows)
        sample = rows[0]
        print(f"\nSaved {len(rows)} jobs → {out_path}  (+{added} new)")
        print(f"Average JD length: {avg} characters")
        print(f"Sample: {sample.get('company')} — {sample.get('title')} ({sample.get('text_chars')} chars)")
        print(f"  text starts: {str(sample.get('text', ''))[:160]!r}...")
    else:
        print(f"\nSaved 0 jobs → {out_path}")

    if failed:
        print(f"Skipped boards: {', '.join(failed)}")
    print("\nRemember: the full JD is in each object's \"text\" field (not only title/url).")
    print("Import with:  python tools/import_collected_jds.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
