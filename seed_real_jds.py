"""
Bulk-load real job postings before a demo.

    python seed_real_jds.py                 # default company list, 12 jobs each
    python seed_real_jds.py --per-company 25
    python seed_real_jds.py --only greenhouse

Pulls from Greenhouse / Lever public job-board APIs. Boards that don't exist
(or have changed) are skipped and reported, so one bad token never stops the run.
Safe to re-run: JDs are upserted by a stable id, so nothing is duplicated.
Add or remove tokens in BOARDS below; the token is the part of the company's
careers URL after boards.greenhouse.io/ or jobs.lever.co/.
"""
import argparse
import time

from app.config import USE_LLM
from app.ingestion.jd_sources import SOURCES
from app.ingestion.service import ingest_jd
from app.vectorstore.company_store import collection_size

BOARDS = [
    # (source, board token) -- tokens are guesses at well-known boards; failures are skipped
    ("greenhouse", "stripe"), ("greenhouse", "airbnb"), ("greenhouse", "coinbase"),
    ("greenhouse", "databricks"), ("greenhouse", "cloudflare"), ("greenhouse", "datadog"),
    ("greenhouse", "discord"), ("greenhouse", "figma"), ("greenhouse", "reddit"),
    ("greenhouse", "instacart"), ("greenhouse", "lyft"), ("greenhouse", "twilio"),
    ("lever", "spotify"), ("lever", "palantir"), ("lever", "plaid"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-company", type=int, default=12)
    ap.add_argument("--only", choices=list(SOURCES))
    ap.add_argument("--delay", type=float, default=2.0 if USE_LLM else 0.0,
                    help="seconds between JDs (avoids Groq rate limits when the LLM is on)")
    a = ap.parse_args()

    ok, failed, total = [], [], 0
    for source, board in BOARDS:
        if a.only and source != a.only:
            continue
        try:
            n = 0
            for job in SOURCES[source](board, a.per_company):
                if len(job["text"]) < 200:
                    continue
                ingest_jd(job["company"], job["title"], job["text"], job["url"])
                n += 1
                time.sleep(a.delay)
            print(f"  ok   {source}:{board}  {n} jobs")
            ok.append(board); total += n
        except Exception as e:
            print(f"  skip {source}:{board}  ({type(e).__name__}: {str(e)[:70]})")
            failed.append(board)

    print(f"\nImported {total} jobs from {len(ok)} companies. Store now holds {collection_size()} JDs.")
    if failed:
        print(f"Skipped: {', '.join(failed)}")


if __name__ == "__main__":
    main()
