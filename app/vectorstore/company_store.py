"""JD vectors in Chroma; JD listing/counting in SQLite (Windows-safe).

chromadb's Rust bindings crash under concurrent uvicorn threads on Windows
(access violation in _count). Listing and status therefore use SQLite jd_meta.
Chroma is only used for upsert + similarity query, under a lock.
"""
import threading
from typing import List, Optional

import chromadb

from app.config import CHROMA_PERSIST_DIR, JD_COLLECTION_NAME
from app.db import conn
from app.embeddings.embedder import embed_text, embed_batch, build_embedding_text
from app.schemas.models import JDData, MatchScore

_collection = None
_lock = threading.RLock()


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
        "company_id": jd.company_id,
        "company": jd.company,
        "title": jd.title,
        "url": jd.url or "",
        "required_skills": ",".join(jd.required_skills or []),
        "min_experience_years": int(jd.min_experience_years or 0),
        "education_requirement": jd.education_requirement or "",
        "parsed_summary": jd.parsed_summary or "",
    }


def _upsert_sqlite(jd: JDData) -> None:
    skills = ",".join(jd.required_skills or [])
    with conn() as c:
        c.execute(
            "INSERT INTO jd_meta(jd_id,company_id,company,title,url,required_skills,min_experience_years) "
            "VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(jd_id) DO UPDATE SET "
            "company_id=excluded.company_id, company=excluded.company, title=excluded.title, "
            "url=excluded.url, required_skills=excluded.required_skills, "
            "min_experience_years=excluded.min_experience_years",
            (
                jd.jd_id,
                jd.company_id,
                jd.company,
                jd.title,
                jd.url or "",
                skills,
                int(jd.min_experience_years or 0),
            ),
        )


def _delete_sqlite(jd_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM jd_meta WHERE jd_id=?", (jd_id,))


def register_jd(jd: JDData) -> None:
    _upsert_sqlite(jd)
    with _lock:
        _get_collection().upsert(
            ids=[jd.jd_id],
            embeddings=[embed_text(_text(jd))],
            documents=[jd.raw_text],
            metadatas=[_meta(jd)],
        )


def register_jds_bulk(jds: List[JDData]) -> None:
    if not jds:
        return
    for jd in jds:
        _upsert_sqlite(jd)
    with _lock:
        _get_collection().upsert(
            ids=[j.jd_id for j in jds],
            embeddings=embed_batch([_text(j) for j in jds]),
            documents=[j.raw_text for j in jds],
            metadatas=[_meta(j) for j in jds],
        )


def _to_jd(jd_id: str, meta: dict, doc: str) -> JDData:
    meta = meta or {}
    skills = meta.get("required_skills") or ""
    return JDData(
        jd_id=jd_id,
        company_id=meta.get("company_id", ""),
        company=meta.get("company", ""),
        title=meta.get("title", ""),
        url=meta.get("url", ""),
        raw_text=doc or "",
        required_skills=[s for s in str(skills).split(",") if s],
        min_experience_years=int(meta.get("min_experience_years") or 0),
        education_requirement=meta.get("education_requirement") or "",
        parsed_summary=meta.get("parsed_summary") or "",
    )


def get_jd_by_id(jd_id: str) -> Optional[JDData]:
    with _lock:
        r = _get_collection().get(ids=[jd_id], include=["documents", "metadatas"])
        if not r or not r.get("ids"):
            return None
        return _to_jd(jd_id, (r.get("metadatas") or [None])[0], (r.get("documents") or [""])[0])


def list_jds(company_id: Optional[str] = None) -> List[dict]:
    """List from SQLite — never touches Chroma (safe for concurrent UI polls)."""
    with conn() as c:
        if company_id:
            rows = c.execute(
                "SELECT jd_id, company, title, url, required_skills, min_experience_years "
                "FROM jd_meta WHERE company_id=? ORDER BY company, title",
                (company_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT jd_id, company, title, url, required_skills, min_experience_years "
                "FROM jd_meta ORDER BY company, title"
            ).fetchall()
    out = []
    for r in rows:
        skills = r["required_skills"] or ""
        out.append({
            "jd_id": r["jd_id"],
            "company": r["company"] or "",
            "title": r["title"] or "",
            "url": r["url"] or "",
            "required_skills": [s for s in str(skills).split(",") if s],
            "min_experience_years": int(r["min_experience_years"] or 0),
        })
    return out


def delete_jd(jd_id: str) -> None:
    _delete_sqlite(jd_id)
    with _lock:
        try:
            _get_collection().delete(ids=[jd_id])
        except Exception as e:
            print(f"[company_store] chroma delete failed: {e}")


def query_top_jds(resume_embedding: List[float], top_k: int) -> List[MatchScore]:
    with _lock:
        c = _get_collection()
        n = c.count()
        if n == 0:
            return []
        r = c.query(
            query_embeddings=[resume_embedding],
            n_results=min(top_k, n),
            include=["metadatas", "distances"],
        )
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
    """Count from SQLite — no chromadb._count (that crashed Windows)."""
    try:
        with conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM jd_meta").fetchone()
            return int(row["n"] if row else 0)
    except Exception as e:
        print(f"[company_store] sqlite count failed: {e}")
        return 0
