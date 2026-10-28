"""
The LangGraph pipeline for a SINGLE resume (batch/multi-candidate assignment
across many resumes is a separate module, Phase 3 scope — see notes at bottom).

Flow:
  parse_resume -> embed_resume -> retrieve_top_jds (Chroma, across ALL companies)
  -> score_ats (rubric + LLM equivalence, live JD data pulled from the store)
  -> decide_route -> [shortlist | manual_review | reject] -> END

This replaces the notebook's in-memory MOCK_JDS list entirely: JDs now come
from whatever companies have registered via app.vectorstore.company_store.
"""
from langgraph.graph import StateGraph, END

from app.config import TOP_K_MATCHES, RETRIEVE_K, SHORTLIST_THRESHOLD, MANUAL_REVIEW_THRESHOLD
from app.schemas.models import GraphState
from app.parsing.llm_extractor import extract_resume_fields
from app.embeddings.embedder import embed_text, build_embedding_text
from app.vectorstore.company_store import query_top_jds, get_jd_by_id
from app.matching.ats_scorer import score_with_llm_bonus


def parse_resume_node(state: GraphState) -> dict:
    fields = extract_resume_fields(state.resume.raw_text)
    updated = state.resume.model_copy(update={
        "skills": fields["skills"],
        "experience_years": fields["experience_years"],
        "education": fields["education"],
        "parsed_summary": fields["summary"],
    })
    return {"resume": updated}


def embed_resume_node(state: GraphState) -> dict:
    r = state.resume
    text = build_embedding_text("", r.skills, r.raw_text)
    return {"resume_embedding": embed_text(text)}


def retrieve_top_jds_node(state: GraphState) -> dict:
    """Semantic search across every registered company's JDs at once — this is
    the 'send to best-fit company' step."""
    matches = query_top_jds(state.resume_embedding, top_k=RETRIEVE_K)
    if not matches:
        return {"errors": state.errors + ["No JDs registered in vector store yet."]}
    return {"match_scores": matches}


def score_ats_node(state: GraphState) -> dict:
    if not state.match_scores:
        return {"decision": "reject"}

    updated_matches = []
    for match in state.match_scores:
        jd = get_jd_by_id(match.jd_id)
        if jd is None:
            continue
        score, rationale = score_with_llm_bonus(state.resume, jd)
        updated_matches.append(match.model_copy(update={
            "ats_score": score, "rationale": rationale,
        }))

    updated_matches.sort(key=lambda m: m.ats_score, reverse=True)
    top_matches = updated_matches[:TOP_K_MATCHES]

    best_score = updated_matches[0].ats_score if updated_matches else 0.0
    if best_score >= SHORTLIST_THRESHOLD:
        decision = "shortlist"
    elif best_score >= MANUAL_REVIEW_THRESHOLD:
        decision = "manual_review"
    else:
        decision = "reject"

    return {"match_scores": updated_matches, "top_matches": top_matches, "decision": decision}


def decide_route(state: GraphState) -> str:
    return state.decision


def shortlist_node(state: GraphState) -> dict:
    # Phase 5 will replace this with a real notification/scheduling call.
    return {"notification_status": "shortlisted_pending_notification"}


def manual_review_node(state: GraphState) -> dict:
    return {"notification_status": "manual_review_pending"}


def reject_node(state: GraphState) -> dict:
    return {"notification_status": "rejected_notice_pending"}


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("parse_resume", parse_resume_node)
    builder.add_node("embed_resume", embed_resume_node)
    builder.add_node("retrieve_top_jds", retrieve_top_jds_node)
    builder.add_node("score_ats", score_ats_node)
    builder.add_node("shortlist", shortlist_node)
    builder.add_node("manual_review", manual_review_node)
    builder.add_node("reject", reject_node)

    builder.set_entry_point("parse_resume")
    builder.add_edge("parse_resume", "embed_resume")
    builder.add_edge("embed_resume", "retrieve_top_jds")
    builder.add_edge("retrieve_top_jds", "score_ats")

    builder.add_conditional_edges(
        "score_ats",
        decide_route,
        {"shortlist": "shortlist", "manual_review": "manual_review", "reject": "reject"},
    )
    builder.add_edge("shortlist", END)
    builder.add_edge("manual_review", END)
    builder.add_edge("reject", END)

    return builder.compile()


# ── Note on multi-candidate matching (your Phase 3 spec) ────────────────────
# This graph processes ONE resume against MANY companies' JDs — that's what you
# asked for right now. "Best candidate matched with best company" when there
# are MULTIPLE candidates for the SAME jd is a different, harder problem: it's
# a global assignment problem (candidates x JDs score matrix -> optimal
# pairing), not a per-resume pipeline. That needs:
#   1. A fan-in step collecting ATS scores for every (candidate, JD) pair
#   2. scipy.optimize.linear_sum_assignment (Hungarian algorithm) for the
#      globally optimal assignment, or a simpler greedy per-JD top-candidate
#      pick as a first pass
#   3. A decision on trigger cadence (real-time per upload vs. nightly batch)
# This is intentionally out of scope for this module — build it as
# app/pipeline/assignment.py once you're ready for Phase 3, reusing
# ats_scorer.score_with_llm_bonus for the pairwise scores.
