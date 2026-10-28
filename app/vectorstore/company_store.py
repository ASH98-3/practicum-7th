"""Persistent Chroma store of every company's JDs. We embed with our own embedder
and pass vectors in explicitly, so resume and JD vectors always come from the
same model. Resumes are NOT stored (one-at-a-time flow)."""
import chromadb
from typing import List, Optional

from app.config import CHROMA_PERSIST_DIR, JD_COLLECTION_NAME
from app.embeddings.embedder import embed_text, embed_batch, build_embedding_text
from app.schemas.models import JDData, MatchScore

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = client.get_or_create_collection(
            name=JD_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    return _collection


def _text(jd: JDData) -> str:
    return build_embedding_text(jd.title, jd.required_skills, jd.raw_text)


def _meta(jd: JDData) -> dict:
    return {
        "company_id": jd.company_id, "company": jd.company, "title": jd.title, "url": jd.url,
        "required_skills": ",".join(jd.required_skills),
        "min_experience_years": jd.min_experience_years,
        "education_requirement": jd.education_requirement,
        "parsed_summary": jd.parsed_summary,
    }


def register_jd(jd: JDData) -> None:
    _get_collection().upsert(ids=[jd.jd_id], embeddings=[embed_text(_text(jd))],
                             documents=[jd.raw_text], metadatas=[_meta(jd)])


def register_jds_bulk(jds: List[JDData]) -> None:
    if not jds:
        return
    _get_collection().upsert(ids=[j.jd_id for j in jds], embeddings=embed_batch([_text(j) for j in jds]),
                             documents=[j.raw_text for j in jds], metadatas=[_meta(j) for j in jds])


def _to_jd(jd_id: str, meta: dict, doc: str) -> JDData:
    return JDData(
        jd_id=jd_id, company_id=meta["company_id"], company=meta["company"],
        title=meta.get("title", ""), url=meta.get("url", ""), raw_text=doc,
        required_skills=[s for s in meta["required_skills"].split(",") if s],
        min_experience_years=meta["min_experience_years"],
        education_requirement=meta["education_requirement"],
        parsed_summary=meta["parsed_summary"])


def get_jd_by_id(jd_id: str) -> Optional[JDData]:
    r = _get_collection().get(ids=[jd_id], include=["documents", "metadatas"])
    return _to_jd(jd_id, r["metadatas"][0], r["documents"][0]) if r["ids"] else None


def list_jds(company_id: Optional[str] = None) -> List[dict]:
    kw = {"where": {"company_id": company_id}} if company_id else {}
    r = _get_collection().get(include=["metadatas"], **kw)
    rows = [{"jd_id": i, "company": m["company"], "title": m.get("title", ""), "url": m.get("url", ""),
             "required_skills": [s for s in m["required_skills"].split(",") if s],
             "min_experience_years": m["min_experience_years"]}
            for i, m in zip(r["ids"], r["metadatas"])]
    return sorted(rows, key=lambda x: (x["company"], x["title"]))


def delete_jd(jd_id: str) -> None:
    _get_collection().delete(ids=[jd_id])


def query_top_jds(resume_embedding: List[float], top_k: int) -> List[MatchScore]:
    c = _get_collection()
    n = c.count()
    if n == 0:
        return []
    r = c.query(query_embeddings=[resume_embedding], n_results=min(top_k, n),
                include=["metadatas", "distances"])
    return [MatchScore(jd_id=i, company_id=m["company_id"], company=m["company"], title=m.get("title", ""), url=m.get("url", ""),
                       similarity_score=round(1.0 - d, 4))
            for i, m, d in zip(r["ids"][0], r["metadatas"][0], r["distances"][0])]


def collection_size() -> int:
    return _get_collection().count()
