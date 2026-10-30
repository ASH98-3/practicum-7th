"""
This is the semantic-matching NLP model — NOT the LLM. It converts resume/JD
text into a fixed-length dense vector so Chroma can do nearest-neighbor search.

Lazily loads sentence-transformers on first use (so importing this module is
cheap, and environments without internet/model access can still import the
rest of the codebase). If the model can't be loaded (no internet to download
weights, package missing, etc.), falls back to a deterministic hash-based
pseudo-embedding — same interface, same vector length family, just not
semantically meaningful. That fallback exists purely so the rest of the
pipeline (Chroma storage, similarity search, ATS scoring) can be exercised
and demoed without a model download; swap it out before you actually trust
match quality.
"""
import hashlib
import math
import re
from typing import List

from app.config import EMBEDDING_MODEL_NAME

_model = None
_model_load_failed = False
PSEUDO_DIM = 384  # matches all-MiniLM-L6-v2's real output dimension


def _get_model():
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as e:
        _model_load_failed = True
        print(
            f"[embedder] Could not load '{EMBEDDING_MODEL_NAME}' "
            f"({type(e).__name__}: {e}). Falling back to pseudo-embeddings — "
            "matches will NOT be semantically meaningful until this is fixed "
            "(usually a missing internet connection or `pip install sentence-transformers`)."
        )
    return _model


def _pseudo_embedding(text: str, dim: int = PSEUDO_DIM) -> List[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9\.\+#]+", text.lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_text(text: str) -> List[float]:
    """Single string -> vector."""
    model = _get_model()
    if model is None:
        return _pseudo_embedding(text)
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Batch version — much faster than looping embed_text for bulk JD ingestion."""
    model = _get_model()
    if model is None:
        return [_pseudo_embedding(t) for t in texts]
    return model.encode(texts, normalize_embeddings=True).tolist()


def build_embedding_text(title: str, skills: List[str], body: str) -> str:
    """Put the highest-signal fields FIRST. Models like MiniLM truncate long
    input (~256 tokens), so a real JD/resume would otherwise be embedded from
    its boilerplate intro only."""
    return f"{title}. Skills: {', '.join(skills)}. {body}".strip()


def embedder_status() -> str:
    """Report status without forcing a model download (keeps /api/status fast)."""
    if _model_load_failed:
        return "fallback"
    if _model is None:
        return "ready (loads on first match)"
    return "sentence-transformers"
