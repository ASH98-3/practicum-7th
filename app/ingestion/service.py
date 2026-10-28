"""One place that turns raw JD text into a registered JD (used by API + CLI)."""
import hashlib
import re

from app.parsing.llm_extractor import extract_jd_fields
from app.schemas.models import JDData
from app.vectorstore.company_store import register_jd
from app.ingestion.jd_sources import SOURCES


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "unknown"


def ingest_jd(company: str, title: str, text: str, url: str = "") -> JDData:
    fields = extract_jd_fields(text)
    jd_id = hashlib.sha1(f"{company}|{title}|{url or text[:200]}".encode()).hexdigest()[:12]
    edu = fields["education"][0] if fields["education"] else "Not specified"
    jd = JDData(jd_id=jd_id, company_id=_slug(company), company=company, title=title, url=url,
                raw_text=text, required_skills=fields["skills"],
                min_experience_years=fields["experience_years"],
                education_requirement=edu, parsed_summary=fields["summary"])
    register_jd(jd)
    return jd


def import_board(source: str, board: str, limit: int = 20, company: str = None) -> list:
    if source not in SOURCES:
        raise ValueError(f"source must be one of {list(SOURCES)}")
    done = []
    for job in SOURCES[source](board, limit):
        if len(job["text"]) < 100:
            continue
        done.append(ingest_jd(company or job["company"], job["title"], job["text"], job["url"]))
    return done


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Bulk import real JDs from a public job board")
    ap.add_argument("source", choices=list(SOURCES))
    ap.add_argument("board", help="e.g. a Greenhouse board token or Lever site name")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()
    jds = import_board(a.source, a.board, a.limit)
    print(f"Imported {len(jds)} JDs from {a.source}:{a.board}")
