"""
Entry point: process ONE resume file (PDF/DOCX/TXT) against every registered
company's JDs in the vector store, and print the routing decision.

Usage:
    python run_demo.py path/to/resume.pdf
    python run_demo.py path/to/resume.txt

First run (or whenever companies post new JDs):
    python -m app.pipeline.seed_companies
"""
import sys
import json
import uuid

from app.parsing.document_reader import read_resume_file
from app.schemas.models import ResumeData, GraphState
from app.pipeline.graph import build_graph
from app.vectorstore.company_store import collection_size


def run(resume_path: str):
    if collection_size() == 0:
        print("No companies registered yet — run `python -m app.pipeline.seed_companies` first.\n")
        sys.exit(1)

    raw_text = read_resume_file(resume_path)
    resume = ResumeData(
        candidate_id=f"cand_{uuid.uuid4().hex[:8]}",
        raw_text=raw_text,
        source_file=resume_path,
    )

    graph = build_graph()
    # LangGraph returns a plain dict, but nested Pydantic objects (resume,
    # match_scores, top_matches) come back un-converted — re-validate through
    # GraphState so we get a clean, fully-serializable structure back out.
    final_state = GraphState.model_validate(graph.invoke(GraphState(resume=resume)))

    print("=" * 60)
    print("FINAL STATE")
    print("=" * 60)
    print(final_state.model_dump_json(indent=2))

    print("\n" + "=" * 60)
    print(f"DECISION: {final_state.decision.upper()}")
    print("Top matches:")
    for m in final_state.top_matches:
        print(f"  {m.company:<20} similarity={m.similarity_score:.3f}  "
              f"ats_score={m.ats_score:.1f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_demo.py path/to/resume.pdf")
        sys.exit(1)
    run(sys.argv[1])
