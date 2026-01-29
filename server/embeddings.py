from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
from light_embed import TextEmbedding  # type: ignore[import-untyped]


_MODEL_CACHE: Dict[str, TextEmbedding] = {}
_DIM_CACHE: Dict[str, int] = {}


def _apply_hf_token(token: Optional[str]) -> None:
    """
    Configure Hugging Face auth for gated/private model downloads.
    This never sends user text to any external API; it only affects model weight downloads.
    """
    if not token:
        return
    # Common env vars respected by huggingface_hub / transformers
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = token
    os.environ["HUGGINGFACE_API_KEY"] = token


def _get_model(model_id: str, token: Optional[str]) -> TextEmbedding:
    _apply_hf_token(token)
    if model_id in _MODEL_CACHE:
        return _MODEL_CACHE[model_id]
    # TextEmbedding will download weights/onnx files if missing (public models need no token)
    try:
        model = TextEmbedding(model_name_or_path=model_id)
    except TypeError:
        # Backward/alt signature support
        model = TextEmbedding(model_id)
    _MODEL_CACHE[model_id] = model
    return model


def embed_one(model_id: str, text: str, *, token: Optional[str] = None) -> Tuple[List[float], int]:
    model = _get_model(model_id, token)
    vecs = model.encode([text])
    # vecs shape: (1, dim)
    arr2d = np.asarray(vecs, dtype=np.float32)
    if arr2d.ndim != 2 or arr2d.shape[0] < 1:
        _DIM_CACHE[model_id] = 0
        return [], 0
    arr = np.asarray(arr2d[0], dtype=np.float32)
    dim = int(arr.shape[0])
    _DIM_CACHE[model_id] = dim
    return arr.tolist(), dim


def embed_many(model_id: str, texts: List[str], *, token: Optional[str] = None) -> Tuple[List[List[float]], int]:
    model = _get_model(model_id, token)
    vecs = model.encode(texts)
    arr = np.asarray(vecs, dtype=np.float32)
    dim = int(arr.shape[1]) if arr.ndim == 2 and arr.shape[0] > 0 else 0
    _DIM_CACHE[model_id] = dim
    return [row.tolist() for row in arr], dim


