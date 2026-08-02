from __future__ import annotations

import json
from typing import Any


def boost_detalle(row: dict) -> list[dict]:
    feats: list[dict] = []
    emb = float(row.get("score_emb") or 0)
    tfidf = float(row.get("score_tfidf") or 0)
    feats.append({
        "id": "emb",
        "tipo": "score",
        "label": "Similitud semántica",
        "detalle": "cosine embeddings",
        "aporte": round(0.7 * emb, 4),
        "crudo": round(emb, 4),
    })
    feats.append({
        "id": "tfidf",
        "tipo": "score",
        "label": "Términos literales",
        "detalle": "cosine TF-IDF",
        "aporte": round(0.3 * tfidf, 4),
        "crudo": round(tfidf, 4),
    })

    if row.get("tiene_cvlac") in (True, "True", "true", 1, 1.0):
        feats.append({
            "id": "cvlac",
            "tipo": "boost",
            "label": "CvLAC presente",
            "detalle": "+0.02",
            "aporte": 0.02,
        })

    cat = str(row.get("categoria") or "")
    cat_l = cat.lower()
    cat_boost, cat_tag = 0.0, None
    if "emérito" in cat_l or "emerito" in cat_l:
        cat_boost, cat_tag = 0.05, "Emérito"
    elif "senior" in cat_l:
        cat_boost, cat_tag = 0.04, "Senior"
    elif "asociado" in cat_l:
        cat_boost, cat_tag = 0.03, "Asociado"
    elif "junior" in cat_l:
        cat_boost, cat_tag = 0.02, "Junior"
    if cat_boost:
        feats.append({
            "id": "categoria",
            "tipo": "boost",
            "label": f"Categoría {cat_tag}",
            "detalle": cat[:90],
            "aporte": cat_boost,
        })

    fac = row.get("facultad")
    if fac and str(fac).strip() and str(fac) != "nan":
        feats.append({
            "id": "facultad",
            "tipo": "contexto",
            "label": str(fac),
            "detalle": "facultad (contexto)",
            "aporte": 0.0,
        })

    feats.sort(key=lambda f: (-float(f.get("aporte") or 0), f.get("tipo") != "score"))
    return feats


def build_grafo(conv_id: str, numero: str, records: list[dict]) -> dict[str, Any]:
    nodes = [{
        "id": conv_id,
        "kind": "convocatoria",
        "label": f"Convocatoria {numero}",
        "score": None,
    }]
    links = []
    for r in records:
        pid = str(r.get("id") or "")
        if not pid:
            continue
        caracts = r.get("caracteristicas") or boost_detalle(r)
        nodes.append({
            "id": pid,
            "kind": "profesor",
            "label": r.get("nombre") or pid,
            "rank": r.get("rank"),
            "score": r.get("score_final"),
            "facultad": r.get("facultad"),
            "caracteristicas": caracts,
        })
        links.append({
            "source": conv_id,
            "target": pid,
            "score": r.get("score_final"),
            "score_emb": r.get("score_emb"),
            "score_tfidf": r.get("score_tfidf"),
            "boost": r.get("boost"),
        })
        for feat in caracts:
            if feat.get("tipo") not in ("score", "boost"):
                continue
            if float(feat.get("aporte") or 0) <= 0:
                continue
            fid = f"{pid}::{feat['id']}"
            nodes.append({
                "id": fid,
                "kind": "aporte",
                "label": feat["label"],
                "aporte": feat["aporte"],
                "detalle": feat.get("detalle"),
                "tipo_aporte": feat["tipo"],
                "parent": pid,
            })
            links.append({
                "source": pid,
                "target": fid,
                "score": feat["aporte"],
                "kind": "aporte",
            })
    return {"nodes": nodes, "links": links}
