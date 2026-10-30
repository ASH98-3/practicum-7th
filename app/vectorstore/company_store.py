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
        "company_id": jd.company_id, "company": jd.company, "title": jd.title, "url": jd.url or "",
        "required_skills": ",".join(jd.required_skills or []),
        "min_experience_years": int(jd.min_experience_years or 0),
        "education_requirement": jd.education_requirement or "",
        "parsed_summary": jd.parsed_summary or "",
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
    meta = meta or {}
    skills = meta.get("required_skills") or ""
    return JDData(
        jd_id=jd_id, company_id=meta.get("company_id", ""), company=meta.get("company", ""),
        title=meta.get("title", ""), url=meta.get("url", ""), raw_text=doc or "",
        required_skills=[s for s in str(skills).split(",") if s],
        min_experience_years=int(meta.get("min_experience_years") or 0),
        education_requirement=meta.get("education_requirement") or "",
        parsed_summary=meta.get("parsed_summary") or "")


def get_jd_by_id(jd_id: str) -> Optional[JDData]:
    r = _get_collection().get(ids=[jd_id], include=["documents", "metadatas"])
    if not r or not r.get("ids"):
        return None
    return _to_jd(jd_id, (r.get("metadatas") or [None])[0], (r.get("documents") or [""])[0])


def list_jds(company_id: Optional[str] = None) -> List[dict]:
    """List JD metadata. Safe on empty collections and partial metadata."""
    try:
        col = _get_collection()
        if col.count() == 0:
            return []
        kwargs = {"include": ["metadatas"]}
        if company_id:
            kwargs["where"] = {"company_id": company_id}
        r = col.get(**kwargs)
    except Exception as e:
        print(f"[company_store] list_jds failed: {type(e).__name__}: {e}")
        return []

    ids = r.get("ids") or []
    metas = r.get("metadatas") or []
    rows = []
    for i, m in zip(ids, metas):
        m = m or {}
        skills = m.get("required_skills") or ""
        rows.append({
            "jd_id": i,
            "company": m.get("company") or "",
            "title": m.get("title") or "",
            "url": m.get("url") or "",
            "required_skills": [s for s in str(skills).split(",") if s],
            "min_experience_years": int(m.get("min_experience_years") or 0),
        })
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
    ids = (r.get("ids") or [[]])[0]
    metas = (r.get("metadatas") or [[]])[0]
    dists = (r.get("distances") or [[]])[0]
    return [
        MatchScore(
            jd_id=i,
            company_id=(m or {}).get("company_id", ""),
            company=(m or {}).get("company", ""),
            title=(m or {}).get("title", ""),
            url=(m or {}).get("url", ""),
            similarity_score=round(1.0 - float(d), 4),
        )
        for i, m, d in zip(ids, metas, dists)
    ]


def collection_size() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0
