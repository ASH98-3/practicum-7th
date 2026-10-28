"""Ways to get REAL job descriptions into the system:
  1. Greenhouse / Lever public job-board APIs (clean, bulk, many companies)
  2. Any job-page URL (reads schema.org JobPosting JSON-LD first, then page text)
  3. Paste text (handled by the API directly)
LinkedIn/Indeed/Workday pages are JS-rendered or block bots; use paste for those."""
import html
import json
import re
from typing import Iterator

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "TalentGraph/0.1 (student project)"}
TIMEOUT = 20


def html_to_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        t.decompose()
    for br in soup.find_all(["br", "li", "p", "div", "h1", "h2", "h3", "h4"]):
        br.append("\n")
    text = soup.get_text()
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def _jsonld_job(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        for item in (data if isinstance(data, list) else data.get("@graph", [data])):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                org = item.get("hiringOrganization") or {}
                return {"title": item.get("title", ""),
                        "company": org.get("name", "") if isinstance(org, dict) else "",
                        "text": html_to_text(html.unescape(item.get("description", "")))}
    return None


def fetch_url_jd(url: str) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    job = _jsonld_job(soup)
    if job and len(job["text"]) > 200:
        return {**job, "url": url}
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else (soup.title.string.strip() if soup.title else "")
    text = html_to_text(r.text)
    if len(text) < 300:
        raise ValueError("Page has almost no readable text (probably JavaScript-rendered, e.g. "
                         "LinkedIn/Indeed/Workday). Paste the JD text instead, or use the "
                         "Greenhouse/Lever import.")
    return {"title": title, "company": "", "text": text, "url": url}


def greenhouse_jobs(board: str, limit: int = 20) -> Iterator[dict]:
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true",
                     headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    for job in r.json().get("jobs", [])[:limit]:
        yield {"company": board.replace("-", " ").title(), "title": job["title"],
               "text": html_to_text(html.unescape(job.get("content", ""))),
               "url": job.get("absolute_url", "")}


def lever_jobs(site: str, limit: int = 20) -> Iterator[dict]:
    r = requests.get(f"https://api.lever.co/v0/postings/{site}?mode=json", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    for p in r.json()[:limit]:
        text = p.get("descriptionPlain") or html_to_text(p.get("description", ""))
        for lst in p.get("lists", []):
            text += f"\n{lst.get('text', '')}\n{html_to_text(lst.get('content', ''))}"
        yield {"company": site.replace("-", " ").title(), "title": p.get("text", ""),
               "text": text.strip(), "url": p.get("hostedUrl", "")}


SOURCES = {"greenhouse": greenhouse_jobs, "lever": lever_jobs}
