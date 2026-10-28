"""
Where the LLM actually earns its place in this pipeline: turning messy,
free-form resume/JD prose into the structured fields (skills, experience_years,
education) that the rest of the system operates on.

If GROQ_API_KEY isn't set, every function below falls back to the same offline
keyword/regex heuristics from the Phase 1 notebook — boundary-aware skill
matching (fixed false-positive bug from Phase 1) plus regex for years/degrees.
This means the pipeline is always runnable, even with zero API keys.
"""
import re
import json
from typing import List, Tuple

from app.config import GROQ_API_KEY, GROQ_MODEL, USE_LLM, SKILL_VOCAB

_client = None
if USE_LLM:
    from groq import Groq
    _client = Groq(api_key=GROQ_API_KEY)


# ── Offline fallback helpers (no API key needed) ────────────────────────────

def _extract_skills_keyword(text: str) -> List[str]:
    """Boundary-aware keyword match — avoids 'javascript' falsely matching 'java',
    'django' falsely matching 'go', etc. (the bug fixed in the Phase 1 notebook)."""
    text_l = text.lower()
    found = set()
    for skill in SKILL_VOCAB:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, text_l):
            found.add(skill)
    return sorted(found)


def _extract_experience_years(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?", text.lower())
    return float(match.group(1)) if match else 0.0


def _extract_education(text: str) -> List[str]:
    degrees = []
    for kw in ["b.tech", "b.s.", "b.a.", "bachelor", "m.tech", "m.s.", "m.a.", "master", "phd"]:
        if kw in text.lower():
            degrees.append(kw.upper())
    return degrees or ["Not specified"]


def _offline_extract(text: str) -> dict:
    return {
        "skills": _extract_skills_keyword(text),
        "experience_years": _extract_experience_years(text),
        "education": _extract_education(text),
        "summary": " ".join(text.split())[:200] + "...",
    }


# ── LLM path (Groq) ──────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """Extract the following from this {doc_type} as strict JSON \
with exactly these keys: skills (list[str], normalized/lowercase, e.g. "golang" -> \
"go"), experience_years (float — infer from context even if not stated as \
"X years"), education (list[str], e.g. ["B.Tech"]), summary (str, 1-2 sentences).
Return ONLY the JSON object, no other text.

{doc_type}:
{text}"""


def _llm_extract(text: str, doc_type: str) -> dict:
    prompt = _EXTRACTION_PROMPT.format(doc_type=doc_type, text=text)
    resp = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


# ── Public functions ─────────────────────────────────────────────────────

def extract_resume_fields(raw_text: str) -> dict:
    """Returns dict with keys: skills, experience_years, education, summary."""
    if USE_LLM:
        try:
            return _llm_extract(raw_text, "resume")
        except Exception:
            # Never let an LLM hiccup take down the pipeline — degrade gracefully.
            return _offline_extract(raw_text)
    return _offline_extract(raw_text)


def extract_jd_fields(raw_text: str) -> dict:
    if USE_LLM:
        try:
            return _llm_extract(raw_text, "job description")
        except Exception:
            return _offline_extract(raw_text)
    return _offline_extract(raw_text)


def skill_equivalence_bonus(resume_skills: List[str], jd_skills: List[str]) -> Tuple[float, str]:
    """LLM judgment call: how much unrecognized skill equivalence exists that a
    keyword/embedding match might still miss (e.g. 'Golang' vs 'Go', 'Postgres'
    vs 'PostgreSQL')? Returns (0-10 bonus, one-line reason). No-ops offline."""
    if not USE_LLM:
        return 0.0, "offline mode — no LLM equivalence check"
    prompt = f"""Resume skills: {resume_skills}
JD required skills: {jd_skills}
On a 0-10 scale, how much unrecognized skill equivalence exists (synonyms, closely
related tools/frameworks) that a keyword match would miss? Reply as strict JSON:
{{"bonus": <number 0-10>, "reason": "<one short sentence>"}}"""
    try:
        resp = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(resp.choices[0].message.content)
        return float(data.get("bonus", 0.0)), data.get("reason", "")
    except Exception:
        return 0.0, "LLM equivalence check failed — scored without bonus"
