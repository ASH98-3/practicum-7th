"""JD metadata in SQLite; vectors on disk as NumPy (Windows-friendly RAG)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.config import CHROMA_PERSIST_DIR
from app.db import conn
from app.embeddings.embedder import embed_text, embed_batch, build_embedding_text
from app.schemas.models import JDData, MatchScore

_lock = threading.RLock()
_VEC_DIR = Path(CHROMA_PERSIST_DIR).parent / "np_vectors"
_IDS_PATH = _VEC_DIR / "ids.json"
_MAT_PATH = _VEC_DIR / "matrix.npy"

_ids: List[str] = []
_matrix: Optional[np.ndarray] = None
_loaded = False


def _ensure_dir() -> None:
    _VEC_DIR.mkdir(parents=True, exist_ok=True)


def _load_vectors() -> None:
    global _ids, _matrix, _loaded
    if _loaded:
        return
    _ensure_dir()
    if _IDS_PATH.is_file() and _MAT_PATH.is_file():
        try:
            _ids = json.loads(_IDS_PATH.read_text(encoding="utf-8"))
            _matrix = np.load(_MAT_PATH)
            if len(_ids) != int(_matrix.shape[0]):
                _ids, _matrix = [], None
        except Exception as e:
            print(f"[vectorstore] could not load vectors: {e}")
            _ids, _matrix = [], None
    else:
        _ids, _matrix = [], None
    _loaded = True


def _save_vectors() -> None:
    _ensure_dir()
    _IDS_PATH.write_text(json.dumps(_ids), encoding="utf-8")
    if _matrix is not None and len(_ids):
        np.save(_MAT_PATH, _matrix)
    elif _MAT_PATH.is_file():
        _MAT_PATH.unlink()


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    if v.ndim == 1:
        n = float(np.linalg.norm(v)) or 1.0
        return v / n
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return v / norms


def _text(jd: JDData) -> str:
    return build_embedding_text(jd.title, jd.required_skills, jd.raw_text)


def _upsert_sqlite(jd: JDData, openings: int = 1) -> None:
    skills = ",".join(jd.required_skills or [])
    openings = max(1, int(openings or 1))
    with conn() as c:
        c.execute(
            "INSERT INTO jd_meta(jd_id,company_id,company,title,url,required_skills,"
            "min_experience_years,education_requirement,parsed_summary,raw_text,openings) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(jd_id) DO UPDATE SET "
            "company_id=excluded.company_id, company=excluded.company, title=excluded.title, "
            "url=excluded.url, required_skills=excluded.required_skills, "
            "min_experience_years=excluded.min_experience_years, "
            "education_requirement=excluded.education_requirement, "
            "parsed_summary=excluded.parsed_summary, raw_text=excluded.raw_text, "
            "openings=excluded.openings",
            (
                jd.jd_id, jd.company_id, jd.company, jd.title, jd.url or "", skills,
                int(jd.min_experience_years or 0),
                jd.education_requirement or "",
                jd.parsed_summary or "",
                jd.raw_text or "",
                openings,
            ),
        )


def _upsert_vector(jd_id: str, embedding: List[float]) -> None:
    global _ids, _matrix
    _load_vectors()
    vec = _normalize(np.asarray(embedding, dtype=np.float32))
    if jd_id in _ids:
        idx = _ids.index(jd_id)
        _matrix[idx] = vec
    else:
        _ids.append(jd_id)
        if _matrix is None or _matrix.size == 0:
            _matrix = vec.reshape(1, -1)
        else:
            if _matrix.shape[1] != vec.shape[0]:
                raise ValueError(
                    f"embedding dim mismatch: store={_matrix.shape[1]} new={vec.shape[0]}"
                )
            _matrix = np.vstack([_matrix, vec.reshape(1, -1)])
    _save_vectors()


def register_jd(jd: JDData, *, skip_chroma: bool = False, openings: int = 1) -> None:
    _upsert_sqlite(jd, openings=openings)
    if skip_chroma:
        return
    with _lock:
        emb = embed_text(_text(jd))
        _upsert_vector(jd.jd_id, emb)


def register_jds_bulk(jds: List[JDData], *, skip_chroma: bool = False, openings: int = 1) -> None:
    if not jds:
        return
    for jd in jds:
        _upsert_sqlite(jd, openings=openings)
    if skip_chroma:
        return
    with _lock:
        embs = embed_batch([_text(j) for j in jds])
        for jd, emb in zip(jds, embs):
            _upsert_vector(jd.jd_id, emb)


def set_openings(jd_id: str, openings: int) -> None:
    with conn() as c:
        c.execute(
            "UPDATE jd_meta SET openings=? WHERE jd_id=?",
            (max(1, int(openings or 1)), jd_id),
        )


def get_openings(jd_id: str) -> int:
    with conn() as c:
        r = c.execute("SELECT openings FROM jd_meta WHERE jd_id=?", (jd_id,)).fetchone()
    if not r:
        return 1
    return max(1, int(r["openings"] or 1))


def get_jd_by_id(jd_id: str) -> Optional[JDData]:
    with conn() as c:
        r = c.execute("SELECT * FROM jd_meta WHERE jd_id=?", (jd_id,)).fetchone()
    if not r:
        return None
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


def list_jds(company_id: Optional[str] = None) -> List[dict]:
    with conn() as c:
        if company_id:
            rows = c.execute(
                "SELECT jd_id, company_id, company, title, url, required_skills, "
                "min_experience_years, openings FROM jd_meta WHERE company_id=? "
                "ORDER BY company, title",
                (company_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT jd_id, company_id, company, title, url, required_skills, "
                "min_experience_years, openings FROM jd_meta ORDER BY company, title"
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
            "openings": max(1, int(r["openings"] or 1)),
        })
    return out


def delete_jd(jd_id: str) -> None:
    global _ids, _matrix
    with conn() as c:
        c.execute("DELETE FROM jd_meta WHERE jd_id=?", (jd_id,))
    with _lock:
        _load_vectors()
        if jd_id in _ids and _matrix is not None:
            idx = _ids.index(jd_id)
            _ids.pop(idx)
            _matrix = np.delete(_matrix, idx, axis=0)
            if _matrix.size == 0:
                _matrix = None
            _save_vectors()


def query_top_jds(resume_embedding: List[float], top_k: int) -> List[MatchScore]:
    with _lock:
        _load_vectors()
        if not _ids or _matrix is None or _matrix.size == 0:
            return []

        q = _normalize(np.asarray(resume_embedding, dtype=np.float32))
        sims = _matrix @ q
        k = min(top_k, len(_ids))
        top_idx = np.argsort(-sims)[:k]

        meta_by_id: Dict[str, dict] = {}
        with conn() as c:
            for i in top_idx:
                jid = _ids[int(i)]
                row = c.execute(
                    "SELECT company_id, company, title, url FROM jd_meta WHERE jd_id=?",
                    (jid,),
                ).fetchone()
                if row:
                    meta_by_id[jid] = dict(row)

        out: List[MatchScore] = []
        for i in top_idx:
            jid = _ids[int(i)]
            m = meta_by_id.get(jid, {})
            out.append(
                MatchScore(
                    jd_id=jid,
                    company_id=m.get("company_id") or "",
                    company=m.get("company") or "",
                    title=m.get("title") or "",
                    url=m.get("url") or "",
                    similarity_score=round(float(sims[int(i)]), 4),
                )
            )
        return out


def collection_size() -> int:
    try:
        with conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM jd_meta").fetchone()
            return int(row["n"] if row else 0)
    except Exception:
        return 0


def vector_count() -> int:
    with _lock:
        _load_vectors()
        return len(_ids)
