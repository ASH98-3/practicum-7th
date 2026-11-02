"""JD metadata + text in SQLite; optional vectors in Chroma.

On Windows, chromadb native code often access-violates during upsert/query.
We always persist to SQLite first so load/list/match can work without Chroma.
"""
import threading
from typing import List, Optional

from app.config import CHROMA_PERSIST_DIR, JD_COLLECTION_NAME
from app.db import conn
from app.embeddings.embedder import embed_text, embed_batch, build_embedding_text
from app.schemas.models import JDData, MatchScore

_collection = None
_lock = threading.RLock()
_chroma_disabled = False


def _get_collection():
    global _collection, _chroma_disabled
    if _chroma_disabled:
        return None
    if _collection is None:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
            _collection = client.get_or_create_collection(
                name=JD_COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        except Exception as e:
            print(f"[company_store] chroma unavailable: {e}")
            _chroma_disabled = True
            return None
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
            "INSERT INTO jd_meta(jd_id,company_id,company,title,url,required_skills,"
            "min_experience_years,education_requirement,parsed_summary,raw_text) "
            "VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(jd_id) DO UPDATE SET "
            "company_id=excluded.company_id, company=excluded.company, title=excluded.title, "
            "url=excluded.url, required_skills=excluded.required_skills, "
            "min_experience_years=excluded.min_experience_years, "
            "education_requirement=excluded.education_requirement, "
            "parsed_summary=excluded.parsed_summary, raw_text=excluded.raw_text",
            (
                jd.jd_id, jd.company_id, jd.company, jd.title, jd.url or "", skills,
                int(jd.min_experience_years or 0),
                jd.education_requirement or "",
                jd.parsed_summary or "",
                jd.raw_text or "",
            ),
        )


def register_jd(jd: JDData, *, skip_chroma: bool = False) -> None:
    """Always write SQLite. Chroma upsert is optional and best-effort."""
    _upsert_sqlite(jd)
    if skip_chroma or _chroma_disabled:
        return
    try:
        with _lock:
            col = _get_collection()
            if col is None:
                return
            col.upsert(
                ids=[jd.jd_id],
                embeddings=[embed_text(_text(jd))],
                documents=[jd.raw_text],
                metadatas=[_meta(jd)],
            )
    except Exception as e:
        print(f"[company_store] chroma upsert skipped: {e}")


def register_jds_bulk(jds: List[JDData], *, skip_chroma: bool = False) -> None:
    if not jds:
        return
    for jd in jds:
        _upsert_sqlite(jd)
    if skip_chroma or _chroma_disabled:
        return
    try:
        with _lock:
            col = _get_collection()
            if col is None:
                return
            col.upsert(
                ids=[j.jd_id for j in jds],
                embeddings=embed_batch([_text(j) for j in jds]),
                documents=[j.raw_text for j in jds],
                metadatas=[_meta(j) for j in jds],
            )
    except Exception as e:
        print(f"[company_store] chroma bulk upsert skipped: {e}")


def get_jd_by_id(jd_id: str) -> Optional[JDData]:
    # Prefer SQLite (always available after load)
    with conn() as c:
        r = c.execute("SELECT * FROM jd_meta WHERE jd_id=?", (jd_id,)).fetchone()
    if r:
        skills = r["required_skills"] or ""
        return JDData(
            jd_id=r["jd_id"],
            company_id=r["company_id"],
            company=r["company"],
            title=r["title"],
            url=r["url"] or "",
            raw_text=r["raw_text"] or "",
            required_skills=[s for s in str(skills).split(",") if s],
            min_experience_years=int(r["min_experience_years"] or 0),
            education_requirement=r["education_requirement"] or "",
            parsed_summary=r["parsed_summary"] or "",
        )
    return None


def list_jds(company_id: Optional[str] = None) -> List[dict]:
    with conn() as c:
        if company_id:
            rows = c.execute(
                "SELECT jd_id, company_id, company, title, url, required_skills, min_experience_years "
                "FROM jd_meta WHERE company_id=? ORDER BY company, title",
                (company_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT jd_id, company_id, company, title, url, required_skills, min_experience_years "
                "FROM jd_meta ORDER BY company, title"
            ).fetchall()
    out = []
    for r in rows:
        skills = r["required_skills"] or ""
        out.append({
            "jd_id": r["jd_id"],
            "company_id": r["company_id"],
            "company": r["company"] or "",
            "title": r["title"] or "",
            "url": r["url"] or "",
            "required_skills": [s for s in str(skills).split(",") if s],
            "min_experience_years": int(r["min_experience_years"] or 0),
        })
    return out


def delete_jd(jd_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM jd_meta WHERE jd_id=?", (jd_id,))
    try:
        with _lock:
            col = _get_collection()
            if col is not None:
                col.delete(ids=[jd_id])
    except Exception as e:
        print(f"[company_store] chroma delete skipped: {e}")


def _fallback_matches(top_k: int) -> List[MatchScore]:
    rows = list_jds()[: max(top_k, 15)]
    return [
        MatchScore(
            jd_id=r["jd_id"],
            company_id=r.get("company_id") or "",
            company=r["company"],
            title=r["title"],
            url=r.get("url") or "",
            similarity_score=0.55,
        )
        for r in rows[:top_k]
    ]


def query_top_jds(resume_embedding: List[float], top_k: int) -> List[MatchScore]:
    if _chroma_disabled:
        return _fallback_matches(top_k)
    try:
        with _lock:
            c = _get_collection()
            if c is None:
                return _fallback_matches(top_k)
            n = c.count()
            if n == 0:
                return _fallback_matches(top_k)
            r = c.query(
                query_embeddings=[resume_embedding],
                n_results=min(top_k, n),
                include=["metadatas", "distances"],
            )
            ids = (r.get("ids") or [[]])[0]
            metas = (r.get("metadatas") or [[]])[0]
            dists = (r.get("distances") or [[]])[0]
            if not ids:
                return _fallback_matches(top_k)
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
    except Exception as e:
        print(f"[company_store] chroma query failed, SQLite fallback: {e}")
        return _fallback_matches(top_k)


def collection_size() -> int:
    try:
        with conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM jd_meta").fetchone()
            return int(row["n"] if row else 0)
    except Exception as e:
        print(f"[company_store] sqlite count failed: {e}")
        return 0
