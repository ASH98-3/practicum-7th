"""
Semantic embeddings for resume <-> JD matching (core RAG retrieval).

Uses sentence-transformers (all-MiniLM-L6-v2 by default). If the model cannot
load, falls back to deterministic pseudo-embeddings so the API still runs.

Run inside the project venv so torch/chromadb binaries match this app.
"""
import hashlib
import math
import os
import re
from typing import List

from app.config import EMBEDDING_MODEL_NAME

_model = None
_model_load_failed = False
_load_error = ""
PSEUDO_DIM = 384

# Set FORCE_PSEUDO_EMBEDDINGS=1 only for emergency offline demos
_FORCE_PSEUDO = os.getenv("FORCE_PSEUDO_EMBEDDINGS", "").strip().lower() in {"1", "true", "yes"}


def _get_model():
    global _model, _model_load_failed, _load_error
    if _FORCE_PSEUDO:
        return None
    if _model is not None or _model_load_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"[embedder] loaded {EMBEDDING_MODEL_NAME}")
    except Exception as e:
        _model_load_failed = True
        _load_error = f"{type(e).__name__}: {e}"
        print(
            f"[embedder] Could not load '{EMBEDDING_MODEL_NAME}' ({_load_error}). "
            "Using pseudo-embeddings until the project venv has sentence-transformers/torch."
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
    if _FORCE_PSEUDO:
        return "pseudo (forced)"
    if _model_load_failed:
        return "pseudo (model load failed)"
    if _model is None:
        return "sentence-transformers (lazy)"
    return "sentence-transformers"
