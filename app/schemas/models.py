"""
Shared data contracts. Pydantic (not TypedDict, unlike the Phase 1 notebook) —
now that this runs as a real service, we want actual runtime validation:
malformed data from a PDF parser or an LLM extraction should fail loudly here,
not silently propagate into a vector store.
"""
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field


class ResumeData(BaseModel):
    candidate_id: str
    raw_text: str
    source_file: Optional[str] = None       # original filename, e.g. "priya_resume.pdf"
    skills: List[str] = Field(default_factory=list)
    experience_years: float = 0.0
    education: List[str] = Field(default_factory=list)
    parsed_summary: str = ""


class JDData(BaseModel):
    jd_id: str
    company_id: str
    company: str
    title: str = ""
    url: str = ""
    raw_text: str
    required_skills: List[str] = Field(default_factory=list)
    min_experience_years: float = 0.0
    education_requirement: str = "Not specified"
    parsed_summary: str = ""


class MatchScore(BaseModel):
    jd_id: str
    company_id: str = ""
    company: str
    title: str = ""
    url: str = ""
    similarity_score: float
    ats_score: float = 0.0
    rationale: str = ""


class GraphState(BaseModel):
    """The state object that flows through the LangGraph pipeline for ONE resume
    at a time (batch/multi-candidate assignment is Phase 3 — separate module)."""
    resume: ResumeData
    resume_embedding: Optional[List[float]] = None
    match_scores: List[MatchScore] = Field(default_factory=list)
    top_matches: List[MatchScore] = Field(default_factory=list)
    decision: Literal["shortlist", "manual_review", "reject", "pending"] = "pending"
    notification_status: str = "not_sent"
    errors: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
