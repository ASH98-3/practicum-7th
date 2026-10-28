"""
ATS rubric scoring — same weighted formula as the Phase 1 notebook, with the
education-fit bug fixed (compares degree LEVEL, not exact string) and now
pulling live JD data from the vector store instead of an in-memory mock list.
"""
from typing import Tuple

from app.config import ATS_WEIGHTS, DEGREE_RANK
from app.schemas.models import ResumeData, JDData
from app.parsing.llm_extractor import skill_equivalence_bonus


def _degree_rank(keywords: list) -> int:
    return max((DEGREE_RANK.get(k, 0) for k in keywords), default=0)


def rubric_score(resume: ResumeData, jd: JDData) -> Tuple[float, str]:
    resume_skills = set(resume.skills)
    jd_skills = set(jd.required_skills)
    overlap = len(resume_skills & jd_skills) / max(len(jd_skills), 1)

    exp_fit = 1.0 if resume.experience_years >= jd.min_experience_years else \
        max(resume.experience_years / max(jd.min_experience_years, 0.01), 0.0)
    exp_fit = min(exp_fit, 1.0)

    if jd.education_requirement == "Not specified":
        edu_fit = 1.0
    else:
        req_rank = _degree_rank([jd.education_requirement])
        resume_rank = _degree_rank(resume.education)
        if req_rank == 0 or resume_rank >= req_rank:
            edu_fit = 1.0
        elif resume_rank > 0:
            edu_fit = 0.5
        else:
            edu_fit = 0.0

    score = 100 * (
        ATS_WEIGHTS["skill_overlap"] * overlap
        + ATS_WEIGHTS["experience_fit"] * exp_fit
        + ATS_WEIGHTS["education_fit"] * edu_fit
    )
    missing = jd_skills - resume_skills
    rationale = (
        f"skill_overlap={overlap:.2f} (missing: {sorted(missing) or 'none'}), "
        f"experience_fit={exp_fit:.2f} ({resume.experience_years}y vs "
        f"{jd.min_experience_years}y required), education_fit={edu_fit:.2f}"
    )
    return round(score, 1), rationale


def score_with_llm_bonus(resume: ResumeData, jd: JDData) -> Tuple[float, str]:
    """Rubric score plus an LLM judgment call on skill equivalence the keyword
    rubric structurally can't see (e.g. 'Golang' phrased differently from 'Go')."""
    score, rationale = rubric_score(resume, jd)
    bonus, reason = skill_equivalence_bonus(resume.skills, jd.required_skills)
    if bonus > 0:
        score = min(score + bonus, 100.0)
        rationale += f", llm_equivalence_bonus={bonus:.1f} ({reason})"
    return round(score, 1), rationale
