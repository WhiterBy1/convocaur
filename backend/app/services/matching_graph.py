"""Grafo de matching: convocatoria ↔ docentes ↔ términos de peso."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def boost_detalle(row: dict) -> list[dict]:
    from convocaur.matching.ranker import (
        PREMIO_AREAS_1,
        PREMIO_AREAS_2,
        PREMIO_AREAS_5,
        PREMIO_CAT,
        PREMIO_CVLAC,
        W_EMB_DEFAULT,
        W_TFIDF_DEFAULT,
    )

    feats: list[dict] = []
    emb = float(row.get("score_emb") or 0)
    tfidf = float(row.get("score_tfidf") or 0)
    feats.append({
        "id": "emb",
        "tipo": "score",
        "label": "Similitud semántica",
        "detalle": "cosine embeddings",
        "aporte": round(W_EMB_DEFAULT * emb, 4),
        "crudo": round(emb, 4),
    })
    feats.append({
        "id": "tfidf",
        "tipo": "score",
        "label": "Términos literales",
        "detalle": "cosine TF-IDF",
        "aporte": round(W_TFIDF_DEFAULT * tfidf, 4),
        "crudo": round(tfidf, 4),
    })

    if row.get("tiene_cvlac") in (True, "True", "true", 1, 1.0):
        feats.append({
            "id": "cvlac",
            "tipo": "boost",
            "label": "CvLAC presente",
            "detalle": f"+{PREMIO_CVLAC}",
            "aporte": PREMIO_CVLAC,
        })

    cat = str(row.get("categoria") or "")
    cat_l = cat.lower()
    cat_boost, cat_tag = 0.0, None
    cat_labels = [
        ("emérito", "Emérito"),
        ("emerito", "Emérito"),
        ("senior", "Senior"),
        ("asociado", "Asociado"),
        ("junior", "Junior"),
    ]
    for key, label in cat_labels:
        if key in cat_l:
            cat_boost = PREMIO_CAT[key]
            cat_tag = label
            break
    if cat_boost:
        feats.append({
            "id": "categoria",
            "tipo": "boost",
            "label": f"Categoría {cat_tag}",
            "detalle": cat[:90],
            "aporte": cat_boost,
        })

    try:
        n_areas = int(row.get("n_areas") or 0)
    except (TypeError, ValueError):
        n_areas = 0
    if n_areas >= 5:
        area_b, area_d = PREMIO_AREAS_5, f"{n_areas} áreas (+{PREMIO_AREAS_5})"
    elif n_areas >= 2:
        area_b, area_d = PREMIO_AREAS_2, f"{n_areas} áreas (+{PREMIO_AREAS_2})"
    elif n_areas >= 1:
        area_b, area_d = PREMIO_AREAS_1, f"{n_areas} área (+{PREMIO_AREAS_1})"
    else:
        area_b, area_d = 0.0, ""
    if area_b:
        feats.append({
            "id": "areas",
            "tipo": "boost",
            "label": "Áreas de investigación",
            "detalle": area_d,
            "aporte": area_b,
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


_STOP = {
    "de", "la", "el", "en", "y", "a", "los", "del", "las", "un", "una", "para",
    "con", "por", "al", "se", "su", "que", "o", "como", "más", "mas", "es",
    "the", "and", "of", "to", "in", "for", "on", "or", "an", "is", "are",
}


def _snippet(text: str, term: str, window: int = 110) -> str | None:
    """Recorte del texto alrededor del término (evidencia legible)."""
    if not text or not term:
        return None
    low = text.lower()
    # probar frase completa y tokens
    candidates = [term.lower()]
    if " " in term:
        candidates.extend(term.lower().split())
    pos = -1
    hit = term
    for c in candidates:
        pos = low.find(c)
        if pos >= 0:
            hit = c
            break
    if pos < 0:
        return None
    start = max(0, pos - window // 3)
    end = min(len(text), pos + len(hit) + window)
    frag = text[start:end].strip().replace("\n", " ")
    if start > 0:
        frag = "…" + frag
    if end < len(text):
        frag = frag + "…"
    return frag


def terminos_peso(
    texto_conv: str,
    texto_doc: str,
    *,
    top_n: int = 7,
) -> list[dict[str, Any]]:
    """Términos (1-2 grams) con mayor producto TF-IDF + citas de evidencia."""
    docs = [(texto_conv or "").strip() or " ", (texto_doc or "").strip() or " "]
    try:
        vec = TfidfVectorizer(
            max_features=6000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            token_pattern=r"(?u)\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}\b",
        )
        X = vec.fit_transform(docs)
        names = vec.get_feature_names_out()
        q = X[0].toarray().ravel()
        d = X[1].toarray().ravel()
        contrib = q * d
        order = np.argsort(contrib)[::-1]
    except Exception:
        return _fallback_overlap(docs[0], docs[1], top_n)

    out: list[dict[str, Any]] = []
    for i in order:
        w = float(contrib[i])
        if w <= 0:
            break
        term = str(names[i])
        parts = term.lower().split()
        if all(p in _STOP for p in parts):
            continue
        item = {
            "id": re.sub(r"[^a-z0-9]+", "_", term.lower())[:40],
            "term": term,
            "peso": round(w, 5),
            "peso_conv": round(float(q[i]), 5),
            "peso_doc": round(float(d[i]), 5),
            "evidencia_docente": _snippet(docs[1], term),
            "evidencia_convocatoria": _snippet(docs[0], term),
        }
        out.append(item)
        if len(out) >= top_n:
            break
    return out


def _fallback_overlap(a: str, b: str, top_n: int) -> list[dict[str, Any]]:
    tok = re.findall(r"[a-záéíóúñ]{4,}", (a or "").lower())
    set_b = set(re.findall(r"[a-záéíóúñ]{4,}", (b or "").lower()))
    shared = [t for t in tok if t in set_b and t not in _STOP]
    from collections import Counter
    c = Counter(shared)
    out = []
    for w, n in c.most_common(top_n):
        out.append({
            "id": w,
            "term": w,
            "peso": float(n),
            "peso_conv": float(n),
            "peso_doc": float(n),
            "evidencia_docente": _snippet(b, w),
            "evidencia_convocatoria": _snippet(a, w),
        })
    return out


def build_grafo(
    conv_id: str,
    numero: str,
    records: list[dict],
    *,
    texto_conv: str = "",
    textos_docente: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Nodos:
      - convocatoria (centro)
      - profesor (más cerca si score_final alto)
      - termino (palabras/frases con más peso compartido)
      - aporte (boosts: CvLAC, categoría) — secundarios
    Distancia conv↔profesor ~ 1 - score (se usa en el force layout del front).
    """
    textos_docente = textos_docente or {}
    nodes: list[dict] = [{
        "id": conv_id,
        "kind": "convocatoria",
        "label": f"Convocatoria {numero}",
        "score": None,
        "val": 1.0,
    }]
    links: list[dict] = []
    term_seen: dict[str, dict] = {}  # term_id global → node

    for r in records:
        pid = str(r.get("id") or "")
        if not pid:
            continue
        score = float(r.get("score_final") or 0)
        # distancia normalizada 0..1 (0 = pegado a la conv)
        distancia = max(0.05, min(1.0, 1.0 - score))
        caracts = r.get("caracteristicas") or boost_detalle(r)

        from convocaur.matching.corpus import _nombre_persona

        nombre = _nombre_persona(r.get("nombre"), pid)
        doc_text = textos_docente.get(pid) or ""
        terms = terminos_peso(texto_conv, doc_text, top_n=6) if texto_conv else []
        r["terminos_clave"] = terms
        r["nombre"] = nombre

        nodes.append({
            "id": pid,
            "kind": "profesor",
            "label": nombre,
            "rank": r.get("rank"),
            "score": score,
            "score_emb": r.get("score_emb"),
            "score_tfidf": r.get("score_tfidf"),
            "facultad": r.get("facultad"),
            "caracteristicas": caracts,
            "terminos_clave": terms,
            "distancia": round(distancia, 4),
            "val": max(score, 0.05),
        })
        links.append({
            "source": conv_id,
            "target": pid,
            "kind": "match",
            "score": score,
            "distancia": round(distancia, 4),
            # linkDistance tip: el front usa esto
            "length": round(40 + distancia * 160, 1),
            "score_emb": r.get("score_emb"),
            "score_tfidf": r.get("score_tfidf"),
        })

        # términos puente: convocatoria — término — profesor
        for t in terms:
            tid = f"term::{t['id']}"
            if tid not in term_seen:
                term_seen[tid] = {
                    "id": tid,
                    "kind": "termino",
                    "label": t["term"][:28],
                    "nombre": t["term"],
                    "peso": t["peso"],
                    "val": t["peso"],
                }
                nodes.append(term_seen[tid])
                links.append({
                    "source": conv_id,
                    "target": tid,
                    "kind": "termino_conv",
                    "score": t["peso"],
                    "length": round(55 + max(0, 0.4 - t["peso"]) * 80, 1),
                })
            else:
                # acumular peso si varios docentes lo comparten
                term_seen[tid]["peso"] = max(float(term_seen[tid].get("peso") or 0), t["peso"])
                term_seen[tid]["val"] = term_seen[tid]["peso"]

            links.append({
                "source": pid,
                "target": tid,
                "kind": "termino_doc",
                "score": t["peso"],
                "length": round(35 + max(0, 0.3 - t["peso"]) * 70, 1),
            })

        # boosts visibles (sin emb/tfidf genéricos — ya están en términos)
        for feat in caracts:
            if feat.get("tipo") != "boost":
                continue
            if float(feat.get("aporte") or 0) <= 0:
                continue
            fid = f"{pid}::{feat['id']}"
            nodes.append({
                "id": fid,
                "kind": "aporte",
                "label": feat["label"][:22],
                "aporte": feat["aporte"],
                "detalle": feat.get("detalle"),
                "tipo_aporte": feat["tipo"],
                "parent": pid,
                "val": float(feat["aporte"]),
            })
            links.append({
                "source": pid,
                "target": fid,
                "kind": "aporte",
                "score": feat["aporte"],
                "length": 48,
            })

    return {
        "nodes": nodes,
        "links": links,
        "lectura": (
            "La convocatoria está al centro. Cada docente se acerca según su score "
            "(mayor match = menor distancia). Los nodos intermedios son palabras/frases "
            "con más peso compartido (TF-IDF) entre el texto de la convocatoria y el del docente."
        ),
    }
