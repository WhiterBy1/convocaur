"""Ranking por afinidad absoluta + premios de perfil (escala 0–1)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from convocaur.matching.corpus import meta_docente, texto_convocatoria
from convocaur.matching.embedders import OpenRouterEmbedder, TfidfEmbedder

W_EMB_DEFAULT = 0.85
W_TFIDF_DEFAULT = 0.15

# Premios de perfil: trayectoria y completitud del CV (sumados a la similitud).
PREMIO_CVLAC = 0.12
PREMIO_CAT = {
    "emerito": 0.18,
    "emérito": 0.18,
    "senior": 0.16,
    "asociado": 0.13,
    "junior": 0.09,
}
PREMIO_AREAS_1 = 0.03
PREMIO_AREAS_2 = 0.05
PREMIO_AREAS_5 = 0.08


def premio_perfil(meta: dict[str, Any]) -> float:
    """Premios por trayectoria/completitud del perfil (no por posición en el pool)."""
    p = 0.0
    if meta.get("tiene_cvlac") in (True, "True", "true", 1, 1.0):
        p += PREMIO_CVLAC

    cat_raw = meta.get("categoria")
    if cat_raw is None or (isinstance(cat_raw, float) and np.isnan(cat_raw)):
        cat = ""
    else:
        cat = str(cat_raw).lower()
    for key, val in PREMIO_CAT.items():
        if key in cat:
            p += val
            break

    try:
        n_areas = int(meta.get("n_areas") or 0)
    except (TypeError, ValueError):
        n_areas = 0
    if n_areas >= 5:
        p += PREMIO_AREAS_5
    elif n_areas >= 2:
        p += PREMIO_AREAS_2
    elif n_areas >= 1:
        p += PREMIO_AREAS_1

    return float(p)


# Alias histórico
def _boost(meta: dict[str, Any]) -> float:
    return premio_perfil(meta)


def afinidad_base(
    sim_emb: np.ndarray,
    sim_tfidf: np.ndarray,
    *,
    w_emb: float = W_EMB_DEFAULT,
    w_tfidf: float = W_TFIDF_DEFAULT,
    tiene_emb: bool = True,
) -> np.ndarray:
    """Similitud texto↔texto en [0, 1], sin premios de perfil."""
    sim_emb = np.asarray(sim_emb, dtype=np.float64)
    sim_tfidf = np.asarray(sim_tfidf, dtype=np.float64)
    if not tiene_emb:
        return np.clip(sim_tfidf, 0.0, 1.0).astype(np.float32)
    score = w_emb * sim_emb + w_tfidf * sim_tfidf
    return np.clip(score, 0.0, 1.0).astype(np.float32)


def afinidad_absoluta(
    sim_emb: np.ndarray,
    sim_tfidf: np.ndarray,
    *,
    w_emb: float = W_EMB_DEFAULT,
    w_tfidf: float = W_TFIDF_DEFAULT,
    tiene_emb: bool = True,
) -> np.ndarray:
    """Compat: solo similitud base (sin premios)."""
    return afinidad_base(
        sim_emb, sim_tfidf, w_emb=w_emb, w_tfidf=w_tfidf, tiene_emb=tiene_emb
    )


def score_con_premios(
    sim_base: np.ndarray,
    premios: np.ndarray,
) -> np.ndarray:
    """score_final = clip(similitud + premio_perfil, 0, 1)."""
    return np.clip(
        np.asarray(sim_base, dtype=np.float64) + np.asarray(premios, dtype=np.float64),
        0.0,
        1.0,
    ).astype(np.float32)


def calibrar_scores(raw: np.ndarray, **_kwargs: Any) -> np.ndarray:
    """DEPRECATED: solo clip."""
    return np.clip(np.asarray(raw, dtype=np.float64), 0.0, 1.0).astype(np.float32)


def rankear_convocatoria(
    nlp: dict[str, Any],
    docentes: list[dict[str, Any]],
    *,
    or_embedder: OpenRouterEmbedder | None,
    tfidf: TfidfEmbedder,
    doc_texts: list[str],
    doc_emb: np.ndarray | None,
    w_emb: float = W_EMB_DEFAULT,
    w_tfidf: float = W_TFIDF_DEFAULT,
    top_k: int = 10,
) -> pd.DataFrame:
    q_text = texto_convocatoria(nlp)
    metas = [meta_docente(d) for d in docentes]

    sim_tfidf = tfidf.similarities(q_text)
    tiene_emb = or_embedder is not None and doc_emb is not None

    if tiene_emb:
        q_emb = or_embedder.embed_texts([q_text], show_progress=False)[0]
        sim_emb = or_embedder.similarities(q_emb, doc_emb)
    else:
        sim_emb = np.zeros_like(sim_tfidf)

    sim_base = afinidad_base(
        sim_emb, sim_tfidf, w_emb=w_emb, w_tfidf=w_tfidf, tiene_emb=tiene_emb
    )
    premios = np.array([premio_perfil(m) for m in metas], dtype=np.float32)
    score_final = score_con_premios(sim_base, premios)

    rows = []
    for i, m in enumerate(metas):
        rows.append({
            **m,
            "score_final": float(score_final[i]),
            "score_raw": float(sim_base[i]),
            "score_emb": float(sim_emb[i]),
            "score_tfidf": float(sim_tfidf[i]),
            "boost": float(premios[i]),
            "query_chars": len(q_text),
            "doc_chars": len(doc_texts[i]),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("score_final", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df.head(top_k)
