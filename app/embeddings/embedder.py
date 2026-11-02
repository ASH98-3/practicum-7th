"""
Embedding helper for resume <-> JD similarity.

On Windows, loading sentence-transformers / torch has been causing hard
process kills (access violations) in this project environment. We therefore
default to deterministic pseudo-embeddings on Windows so matching stays up.
Set FORCE_REAL_EMBEDDINGS=1 to try the real model anyway.
"""
import hashlib
import math
import os
import platform
import re
from typing import List

from app.config import EMBEDDING_MODEL_NAME

_model = None
_model_load_failed = False
PSEUDO_DIM = 384

_FORCE_REAL = os.getenv("FORCE_REAL_EMBEDDINGS", "").strip().lower() in {"1", "true", "yes"}
_USE_PSEUDO = (platform.system() == "Windows" and not _FORCE_REAL) or (
    os.getenv("FORCE_PSEUDO_EMBEDDINGS", "").strip().lower() in {"1", "true", "yes"}
)


def _get_model():
    global _model, _model_load_failed
    if _USE_PSEUDO:
        return None
    if _model is not None or _model_load_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as e:
        _model_load_failed = True
        print(
            f"[embedder] Could not load '{EMBEDDING_MODEL_NAME}' "
            f"({type(e).__name__}: {e}). Using pseudo-embeddings."
        )
    return _model


def _pseudo_embedding(text: str, dim: int = PSEUDO_DIM) -> List[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9\.\+#]+", (text or "").lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h // dim) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_text(text: str) -> List[float]:
    model = _get_model()
    if model is None:
        return _pseudo_embedding(text)
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    if model is None:
        return [_pseudo_embedding(t) for t in texts]
    return model.encode(texts, normalize_embeddings=True).tolist()


def build_embedding_text(title: str, skills: List[str], body: str) -> str:
    return f"{title}. Skills: {', '.join(skills)}. {body}".strip()


def embedder_status() -> str:
    if _USE_PSEUDO:
        return "pseudo (windows-safe)"
    if _model_load_failed:
        return "fallback"
    if _model is None:
        return "ready (loads on first match)"
    return "sentence-transformers"
