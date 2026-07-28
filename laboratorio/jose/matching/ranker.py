"""Ranking híbrido embeddings + TF-IDF + boosts suaves."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from corpus import meta_docente, texto_convocatoria, texto_docente
from embedders import OpenRouterEmbedder, TfidfEmbedder


def _boost(meta: dict[str, Any]) -> float:
    b = 0.0
    if meta.get("tiene_cvlac"):
        b += 0.02
    cat = (meta.get("categoria") or "").lower()
    if "emérito" in cat or "emerito" in cat:
        b += 0.05
    elif "senior" in cat:
        b += 0.04
    elif "asociado" in cat:
        b += 0.03
    elif "junior" in cat:
        b += 0.02
    return b


def rankear_convocatoria(
    nlp: dict[str, Any],
    docentes: list[dict[str, Any]],
    *,
    or_embedder: OpenRouterEmbedder | None,
    tfidf: TfidfEmbedder,
    doc_texts: list[str],
    doc_emb: np.ndarray | None,
    w_emb: float = 0.7,
    w_tfidf: float = 0.3,
    top_k: int = 10,
) -> pd.DataFrame:
    q_text = texto_convocatoria(nlp)
    metas = [meta_docente(d) for d in docentes]

    sim_tfidf = tfidf.similarities(q_text)

    if or_embedder is not None and doc_emb is not None:
        q_emb = or_embedder.embed_texts([q_text], show_progress=False)[0]
        sim_emb = or_embedder.similarities(q_emb, doc_emb)
        score = w_emb * sim_emb + w_tfidf * sim_tfidf
    else:
        sim_emb = np.zeros_like(sim_tfidf)
        score = sim_tfidf

    boosts = np.array([_boost(m) for m in metas], dtype=np.float32)
    score_final = score + boosts

    rows = []
    for i, m in enumerate(metas):
        rows.append({
            **m,
            "score_final": float(score_final[i]),
            "score_emb": float(sim_emb[i]),
            "score_tfidf": float(sim_tfidf[i]),
            "boost": float(boosts[i]),
            "query_chars": len(q_text),
            "doc_chars": len(doc_texts[i]),
        })

    df = pd.DataFrame(rows).sort_values("score_final", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df.head(top_k)
