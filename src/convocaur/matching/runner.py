"""Ejecuta ranking docente ↔ convocatoria y persiste CSV + resumen."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from convocaur.cargar_datos import guardar_salida
from convocaur.matching.corpus import cargar_docentes_json, cargar_nlp_dir, texto_docente
from convocaur.matching.embedders import OpenRouterEmbedder, TfidfEmbedder, _load_env
from convocaur.matching.ranker import W_EMB_DEFAULT, W_TFIDF_DEFAULT, rankear_convocatoria
from convocaur.paths import (
    JSON_PROFESORES,
    PROC_MATCHING,
    PROC_MATCHING_CACHE,
    PROC_NLP,
    PROJECT_ROOT,
    ensure_data_dirs,
)

log = logging.getLogger("matching.runner")

ProgressCb = Callable[[dict[str, Any]], None]


def _normalize_keys(convocatorias: list[str] | None, nlp_all: dict) -> list[str]:
    if not convocatorias:
        return sorted(nlp_all.keys())
    keys = []
    for c in convocatorias:
        c = str(c).strip()
        if not c:
            continue
        key = c if c.startswith("convocatoria_") else f"convocatoria_{c}"
        keys.append(key)
    return keys


def _merge_resumen(nuevos: list[dict]) -> list[dict]:
    path = PROC_MATCHING / "resumen_match.json"
    existentes: dict[str, dict] = {}
    if path.exists():
        for row in json.loads(path.read_text(encoding="utf-8")):
            existentes[row["convocatoria"]] = row
    for row in nuevos:
        existentes[row["convocatoria"]] = row
    merged = [existentes[k] for k in sorted(existentes.keys())]
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def run_matching(
    convocatorias: list[str] | None = None,
    *,
    top_k: int = 15,
    limite_docentes: int | None = None,
    sin_embeddings: bool = False,
    solo_faltantes: bool = False,
    w_emb: float = W_EMB_DEFAULT,
    w_tfidf: float = W_TFIDF_DEFAULT,
    on_progress: ProgressCb | None = None,
) -> dict[str, Any]:
    """Rankea convocatorias con NLP y escribe rankings en data/processed/matching/."""
    ensure_data_dirs()
    _load_env(PROJECT_ROOT)

    nlp_all = cargar_nlp_dir(PROC_NLP)
    keys = _normalize_keys(convocatorias, nlp_all)

    missing_nlp = [k for k in keys if k not in nlp_all]
    if missing_nlp:
        raise ValueError(f"Faltan NLP JSON: {missing_nlp}")

    if solo_faltantes:
        keys = [k for k in keys if not (PROC_MATCHING / f"ranking_{k}.csv").exists()]

    if not keys:
        return {
            "ok": True,
            "procesadas": [],
            "mensaje": "Nada pendiente: todas las convocatorias pedidas ya tienen ranking.",
            "uso_embeddings": False,
        }

    def progress(payload: dict[str, Any]) -> None:
        if on_progress:
            on_progress(payload)

    progress({"fase": "docentes", "mensaje": "Cargando docentes…", "total": len(keys), "hecho": 0})

    docentes = cargar_docentes_json(JSON_PROFESORES, limite=limite_docentes)
    doc_texts = [texto_docente(d) for d in docentes]
    if not docentes:
        raise RuntimeError("No hay docentes con texto usable para matching.")

    tfidf = TfidfEmbedder()
    tfidf.fit_transform(doc_texts)

    or_emb = None
    doc_emb = None
    if not sin_embeddings:
        progress({"fase": "embeddings", "mensaje": "Embeddings de docentes…", "total": len(keys), "hecho": 0})
        try:
            or_emb = OpenRouterEmbedder(cache_dir=PROC_MATCHING_CACHE)
            doc_emb = or_emb.embed_texts(doc_texts, show_progress=False)
        except Exception as exc:
            log.error("Embeddings no disponibles (%s). Solo TF-IDF.", exc)
            or_emb = None
            doc_emb = None

    resumen_nuevos: list[dict] = []
    errores: list[dict] = []
    for i, key in enumerate(keys):
        progress({
            "fase": "ranking",
            "mensaje": f"Rankeando {key}…",
            "convocatoria": key,
            "total": len(keys),
            "hecho": i,
        })
        try:
            df = rankear_convocatoria(
                nlp_all[key],
                docentes,
                or_embedder=or_emb,
                tfidf=tfidf,
                doc_texts=doc_texts,
                doc_emb=doc_emb,
                w_emb=w_emb,
                w_tfidf=w_tfidf,
                top_k=top_k,
            )
        except Exception as exc:
            log.exception("Fallo ranking %s; reintento solo TF-IDF", key)
            try:
                df = rankear_convocatoria(
                    nlp_all[key],
                    docentes,
                    or_embedder=None,
                    tfidf=tfidf,
                    doc_texts=doc_texts,
                    doc_emb=None,
                    w_emb=w_emb,
                    w_tfidf=w_tfidf,
                    top_k=top_k,
                )
                errores.append({"convocatoria": key, "error": str(exc), "fallback": "tfidf"})
            except Exception as exc2:
                errores.append({"convocatoria": key, "error": str(exc2), "fallback": None})
                continue

        csv_name = f"ranking_{key}.csv"
        path = PROC_MATCHING / csv_name
        df.to_csv(path, index=False, encoding="utf-8")
        guardar_salida(csv_name, df)
        row = {
            "convocatoria": key,
            "n_candidatos_pool": len(docentes),
            "top1_id": df.iloc[0]["id"] if len(df) else None,
            "top1_nombre": df.iloc[0]["nombre"] if len(df) else None,
            "top1_score": float(df.iloc[0]["score_final"]) if len(df) else None,
            "uso_embeddings": or_emb is not None,
            "archivo": str(path),
        }
        resumen_nuevos.append(row)

    merged = _merge_resumen(resumen_nuevos)
    progress({
        "fase": "listo",
        "mensaje": f"Listo: {len(resumen_nuevos)} rankings",
        "total": len(keys),
        "hecho": len(keys),
    })
    return {
        "ok": True,
        "procesadas": resumen_nuevos,
        "n_procesadas": len(resumen_nuevos),
        "errores": errores,
        "uso_embeddings": or_emb is not None,
        "resumen_total": len(merged),
    }
