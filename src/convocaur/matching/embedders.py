"""Embedders: OpenRouter (principal) + TF-IDF (baseline local)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger("matching.embedders")

OPENROUTER_URL = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_EMB_MODEL = "openai/text-embedding-3-small"


def _load_env(convocaur_root: Path) -> None:
    load_dotenv(convocaur_root / ".env")
    load_dotenv(convocaur_root.parent / ".env")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class TfidfEmbedder:
    """Baseline local, determinista."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(
            max_features=12000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self.matrix = None
        self.docs: list[str] = []

    def fit_transform(self, docs: list[str]) -> np.ndarray:
        self.docs = docs
        self.matrix = self.vectorizer.fit_transform(docs)
        return self.matrix

    def transform(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.transform(texts)

    def similarities(self, query: str, doc_matrix=None) -> np.ndarray:
        q = self.transform([query])
        m = doc_matrix if doc_matrix is not None else self.matrix
        return cosine_similarity(q, m).ravel()


class OpenRouterEmbedder:
    """Embeddings vía OpenRouter con cache en disco."""

    def __init__(
        self,
        cache_dir: Path,
        model: str | None = None,
        batch_size: int = 32,
    ) -> None:
        self.model = model or os.getenv("OPENROUTER_EMBED_MODEL", DEFAULT_EMB_MODEL)
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or api_key.endswith("..."):
            raise RuntimeError("Falta OPENROUTER_API_KEY en .env")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/convocaur",
            "X-Title": "ConvocaUR-Matching",
        }
        self._mem: dict[str, list[float]] = {}
        self._load_cache_index()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{self.model.replace('/', '_')}__{key}.json"

    def _load_cache_index(self) -> None:
        # lazy: se lee por archivo al pedir
        pass

    def _get_cached(self, text: str) -> list[float] | None:
        key = _hash_text(self.model + "\n" + text)
        if key in self._mem:
            return self._mem[key]
        path = self._cache_path(key)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            vec = data["embedding"]
            self._mem[key] = vec
            return vec
        return None

    def _put_cache(self, text: str, embedding: list[float]) -> None:
        key = _hash_text(self.model + "\n" + text)
        self._mem[key] = embedding
        path = self._cache_path(key)
        path.write_text(
            json.dumps({"model": self.model, "sha": key, "embedding": embedding}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": texts}
        last_err = None
        for intento in range(3):
            try:
                resp = requests.post(
                    OPENROUTER_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
                body = resp.json()
                data = sorted(body["data"], key=lambda x: x["index"])
                return [row["embedding"] for row in data]
            except Exception as exc:
                last_err = exc
                log.warning("Embed batch fallo (%s): %s", intento + 1, exc)
                time.sleep(1.5 * (intento + 1))
        raise RuntimeError(f"No se pudo embeddear batch: {last_err}")

    def embed_texts(self, texts: list[str], show_progress: bool = True) -> np.ndarray:
        vectors: list[list[float] | None] = [None] * len(texts)
        pending_idx: list[int] = []
        pending_txt: list[str] = []

        for i, t in enumerate(texts):
            cached = self._get_cached(t)
            if cached is not None:
                vectors[i] = cached
            else:
                pending_idx.append(i)
                pending_txt.append(t)

        if show_progress:
            log.info(
                "Embeddings: %s cache hit, %s a pedir (%s)",
                len(texts) - len(pending_txt),
                len(pending_txt),
                self.model,
            )

        for start in range(0, len(pending_txt), self.batch_size):
            chunk = pending_txt[start : start + self.batch_size]
            idxs = pending_idx[start : start + self.batch_size]
            embs = self._embed_batch(chunk)
            for j, emb in enumerate(embs):
                vectors[idxs[j]] = emb
                self._put_cache(chunk[j], emb)
            time.sleep(0.2)

        arr = np.array(vectors, dtype=np.float32)
        # normalizar L2 para cosine = dot
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def similarities(self, query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        return (doc_vecs @ query_vec.T).ravel()
