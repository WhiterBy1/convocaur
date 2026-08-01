"""
API mínima para explorar el matching docente ↔ convocatoria.

Uso:
  python web/api.py
  → http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.matching.corpus import (  # noqa: E402
    meta_docente,
    texto_convocatoria,
    texto_docente,
)
from convocaur.paths import (  # noqa: E402
    JSON_PROFESORES,
    PROC_ELEGIBILIDAD,
    PROC_MATCHING,
    PROC_MATCHING_CACHE,
    PROC_NLP,
)

SALIDAS = PROC_MATCHING
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="ConvocaUR Matching", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(404, f"No existe {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _profesor_path(profesor_id: str) -> Path:
    return JSON_PROFESORES / f"{profesor_id}.json"


def _cache_stats() -> dict:
    cache_dir = PROC_MATCHING_CACHE
    files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
    bytes_total = sum(f.stat().st_size for f in files)
    return {
        "dir": str(cache_dir),
        "n_vectores": len(files),
        "size_mb": round(bytes_total / (1024 * 1024), 2),
        "modelo": "openai/text-embedding-3-small",
        "estrategia": (
            "Cache en disco por hash(modelo+texto). "
            "Docentes y convocatorias se embeddean una vez; "
            "si el texto no cambia, no se vuelve a pagar OpenRouter. "
            "La UI solo lee rankings CSV ya calculados."
        ),
        "cuando_vector_db": (
            "Con ~600 docentes el cache+numpy basta. "
            "Una vector DB (Chroma/Qdrant/pgvector) aporta cuando haya "
            "consultas en vivo, filtros por metadatos, muchas convocatorias "
            "nuevas o miles de perfiles sin recargar todo en RAM."
        ),
    }


@app.get("/api/health")
def health() -> dict:
    rankings = sorted(SALIDAS.glob("ranking_convocatoria_*.csv"))
    return {
        "ok": True,
        "rankings": [p.name for p in rankings],
        "n_profesores_json": len(list(JSON_PROFESORES.glob("*.json"))) if JSON_PROFESORES.exists() else 0,
        "cache_embeddings": _cache_stats(),
    }


@app.get("/api/embeddings/cache")
def embeddings_cache() -> dict:
    return _cache_stats()


@app.get("/api/flujo")
def flujo() -> dict:
    return {
        "titulo": "Match docente / convocatoria",
        "score": "0.7 * cosine(embeddings) + 0.3 * cosine(tfidf) + boost categoría/CvLAC",
        "modelo_embeddings": "openai/text-embedding-3-small (OpenRouter)",
        "pasos": [
            {"id": 1, "nombre": "Input convocatoria", "detalle": "JSON NLP: objetivo, líneas, requisitos, criterios"},
            {"id": 2, "nombre": "Input docente", "detalle": "HUB + CvLAC: áreas, líneas, proyectos, categoría"},
            {"id": 3, "nombre": "TF-IDF", "detalle": "Baseline léxico local (sklearn)"},
            {"id": 4, "nombre": "Embeddings", "detalle": "Vectores semánticos vía OpenRouter (cache en disco)"},
            {"id": 5, "nombre": "Score híbrido", "detalle": "Combinación + boost suave"},
            {"id": 6, "nombre": "Output ranking", "detalle": "Top-k CSV en data/processed/matching/"},
        ],
        "notas": [
            "No reemplaza elegibilidad institucional (alianza, sede, grupos A1).",
            "Los rankings viven en data/processed/matching/.",
        ],
    }


@app.get("/api/convocatorias")
def listar_convocatorias() -> list[dict]:
    resumen_path = SALIDAS / "resumen_match.json"
    resumen = _load_json(resumen_path) if resumen_path.exists() else []
    by_key = {r["convocatoria"]: r for r in resumen}

    items = []
    for csv_path in sorted(SALIDAS.glob("ranking_convocatoria_*.csv")):
        key = csv_path.stem.replace("ranking_", "")
        meta = by_key.get(key, {})
        nlp_path = PROC_NLP / f"{key}_nlp.json"
        eleg_path = PROC_ELEGIBILIDAD / f"{key}_elegibilidad.json"
        items.append({
            "id": key,
            "numero": key.replace("convocatoria_", ""),
            "tiene_nlp": nlp_path.exists(),
            "tiene_elegibilidad": eleg_path.exists(),
            "top1_id": meta.get("top1_id"),
            "top1_nombre": meta.get("top1_nombre") or meta.get("top1_id"),
            "top1_score": meta.get("top1_score"),
            "n_candidatos_pool": meta.get("n_candidatos_pool"),
            "uso_embeddings": meta.get("uso_embeddings"),
        })
    return items


@app.get("/api/convocatorias/{conv_id}")
def detalle_convocatoria(conv_id: str) -> dict:
    if not conv_id.startswith("convocatoria_"):
        conv_id = f"convocatoria_{conv_id}"

    nlp_path = PROC_NLP / f"{conv_id}_nlp.json"
    if not nlp_path.exists():
        raise HTTPException(404, f"Sin NLP para {conv_id}")

    nlp = _load_json(nlp_path)
    nlp_view = {k: v for k, v in nlp.items() if k != "elegibilidad_urosario"}
    texto = texto_convocatoria(nlp)

    eleg = None
    eleg_path = PROC_ELEGIBILIDAD / f"{conv_id}_elegibilidad.json"
    if eleg_path.exists():
        eleg_raw = _load_json(eleg_path)
        eleg = eleg_raw.get("veredicto_final") or eleg_raw

    return {
        "id": conv_id,
        "texto_matching": texto,
        "nlp": {
            "objetivo": nlp_view.get("objetivo"),
            "alianza_obligatoria": nlp_view.get("alianza_obligatoria"),
            "actores_elegibles": nlp_view.get("actores_elegibles") or [],
            "lineas_tematicas": nlp_view.get("lineas_tematicas") or [],
            "requisitos": nlp_view.get("requisitos") or [],
            "criterios_evaluacion": nlp_view.get("criterios_evaluacion") or [],
            "financiacion": nlp_view.get("financiacion"),
            "causales_rechazo": nlp_view.get("causales_rechazo") or [],
        },
        "elegibilidad_urosario": eleg,
    }


def _boost_detalle(row: dict) -> list[dict]:
    """Desglosa el boost y señales que explican el puntaje (misma lógica que ranker._boost)."""
    feats: list[dict] = []
    emb = float(row.get("score_emb") or 0)
    tfidf = float(row.get("score_tfidf") or 0)
    feats.append({
        "id": "emb",
        "tipo": "score",
        "label": "Similitud semántica",
        "detalle": "cosine embeddings (áreas, líneas, perfil vs TdR)",
        "aporte": round(0.7 * emb, 4),
        "crudo": round(emb, 4),
    })
    feats.append({
        "id": "tfidf",
        "tipo": "score",
        "label": "Términos literales",
        "detalle": "cosine TF-IDF (palabras del TdR que también aparecen en el perfil)",
        "aporte": round(0.3 * tfidf, 4),
        "crudo": round(tfidf, 4),
    })

    if row.get("tiene_cvlac") in (True, "True", "true", 1, 1.0):
        feats.append({
            "id": "cvlac",
            "tipo": "boost",
            "label": "CvLAC presente",
            "detalle": "perfil con bloque CvLAC (+0.02)",
            "aporte": 0.02,
        })

    cat = str(row.get("categoria") or "")
    cat_l = cat.lower()
    cat_boost = 0.0
    cat_tag = None
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
            "detalle": (cat[:90] + "…") if len(cat) > 90 else cat,
            "aporte": cat_boost,
        })

    fac = row.get("facultad")
    if fac and str(fac).strip() and str(fac) != "nan":
        feats.append({
            "id": "facultad",
            "tipo": "contexto",
            "label": str(fac),
            "detalle": "facultad del docente (contexto, no suma al score)",
            "aporte": 0.0,
        })

    n_areas = row.get("n_areas")
    try:
        n_areas_i = int(n_areas) if n_areas is not None and str(n_areas) != "nan" else 0
    except (TypeError, ValueError):
        n_areas_i = 0
    if n_areas_i:
        feats.append({
            "id": "areas",
            "tipo": "contexto",
            "label": f"{n_areas_i} áreas de investigación",
            "detalle": "entran al texto que se embeade",
            "aporte": 0.0,
        })

    pid = row.get("id")
    if pid:
        ppath = _profesor_path(str(pid))
        if ppath.exists():
            try:
                doc = json.loads(ppath.read_text(encoding="utf-8"))
                areas = [str(a) for a in (doc.get("areas_investigacion") or [])[:4] if a]
                for i, a in enumerate(areas):
                    feats.append({
                        "id": f"area_{i}",
                        "tipo": "senal",
                        "label": a[:48],
                        "detalle": "área HUB usada en el corpus de matching",
                        "aporte": 0.0,
                    })
                cv = doc.get("cvlac") or {}
                lineas = cv.get("lineas_investigacion") or []
                for i, ln in enumerate(lineas[:3]):
                    lab = ln if isinstance(ln, str) else (ln.get("nombre") if isinstance(ln, dict) else str(ln))
                    if lab:
                        feats.append({
                            "id": f"linea_{i}",
                            "tipo": "senal",
                            "label": str(lab)[:48],
                            "detalle": "línea CvLAC en el texto embebido",
                            "aporte": 0.0,
                        })
            except Exception:
                pass

    feats.sort(key=lambda f: (-float(f.get("aporte") or 0), f.get("tipo") != "score"))
    return feats


def _grafo_match(conv_id: str, numero: str, records: list[dict]) -> dict:
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
        caracts = r.get("caracteristicas") or _boost_detalle(r)
        nodes.append({
            "id": pid,
            "kind": "profesor",
            "label": (r.get("nombre") or pid),
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


@app.get("/api/convocatorias/{conv_id}/ranking")
def ranking_convocatoria(conv_id: str, top: int = 20) -> dict:
    if not conv_id.startswith("convocatoria_"):
        conv_id = f"convocatoria_{conv_id}"
    path = SALIDAS / f"ranking_{conv_id}.csv"
    if not path.exists():
        raise HTTPException(404, f"No hay ranking para {conv_id}. Corre scripts/run_match.py")

    df = pd.read_csv(path)
    full = df.copy()
    if top > 0:
        df = df.head(top)
    records = json.loads(df.to_json(orient="records", force_ascii=False))
    for r in records:
        r["caracteristicas"] = _boost_detalle(r)

    numero = conv_id.replace("convocatoria_", "")
    return {
        "convocatoria": conv_id,
        "n": len(records),
        "n_pool": int(len(full)),
        "rows": records,
        "grafo": _grafo_match(conv_id, numero, records),
    }


@app.get("/api/profesores/{profesor_id}")
def detalle_profesor(profesor_id: str) -> dict:
    path = _profesor_path(profesor_id)
    if not path.exists():
        raise HTTPException(404, f"Profesor no encontrado: {profesor_id}")
    doc = _load_json(path)
    if not doc.get("id"):
        doc["id"] = profesor_id
    return {
        "meta": meta_docente(doc),
        "texto_matching": texto_docente(doc),
        "areas_investigacion": doc.get("areas_investigacion") or [],
        "perfil_profesional": (doc.get("perfil_profesional") or "")[:1200],
        "tiene_cvlac": bool(doc.get("cvlac")),
        "cvlac_datos_generales": (doc.get("cvlac") or {}).get("datos_generales"),
        "cvlac_lineas": ((doc.get("cvlac") or {}).get("lineas_investigacion") or [])[:12],
        "url": doc.get("url"),
    }


@app.get("/")
def index() -> FileResponse:
    index = STATIC / "index.html"
    if not index.exists():
        raise HTTPException(500, "Falta static/index.html")
    return FileResponse(index)


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def main() -> None:
    import uvicorn

    print("ConvocaUR Matching UI → http://127.0.0.1:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
