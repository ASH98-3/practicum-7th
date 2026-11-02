"""One place that turns raw JD text into a registered JD (used by the API)."""
import hashlib
import re

from app.parsing.llm_extractor import extract_jd_fields
from app.schemas.models import JDData
from app.vectorstore.company_store import register_jd


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "unknown"


def ingest_jd(company: str, title: str, text: str, url: str = "", *, skip_chroma: bool = False) -> JDData:
    fields = extract_jd_fields(text)
    jd_id = hashlib.sha1(f"{company}|{title}|{url or text[:200]}".encode()).hexdigest()[:12]
    edu = fields["education"][0] if fields["education"] else "Not specified"
    jd = JDData(
        jd_id=jd_id,
        company_id=_slug(company),
        company=company,
        title=title,
        url=url,
        raw_text=text,
        required_skills=fields["skills"],
        min_experience_years=fields["experience_years"],
        education_requirement=edu,
        parsed_summary=fields["summary"],
    )
    register_jd(jd, skip_chroma=skip_chroma)
    return jd
