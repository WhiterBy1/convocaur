from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PROC = ROOT / "data" / "processed"
PROC_MATCHING = PROC / "matching"
PROC_SECOP = PROC / "secop"
DASHBOARD_JSON = PROC_SECOP / "resumen_dashboard.json"
BITACORA = ROOT / "analisis" / "secop" / "salidas_capacidad3" / "bitacora_hallazgos.csv"
MANIFEST = ROOT / "analisis" / "secop" / "salidas_capacidad3" / "modelos" / "manifest.json"


@lru_cache(maxsize=1)
def _dashboard_mtime() -> float:
    return DASHBOARD_JSON.stat().st_mtime if DASHBOARD_JSON.exists() else 0.0


def load_dashboard() -> dict[str, Any]:
    """Lee resumen_dashboard.json (cache invalidada si cambia el archivo)."""
    if not DASHBOARD_JSON.exists():
        return {"error": "Falta resumen_dashboard.json"}
    mtime = DASHBOARD_JSON.stat().st_mtime
    return _load_dashboard_cached(mtime)


@lru_cache(maxsize=2)
def _load_dashboard_cached(_mtime: float) -> dict[str, Any]:
    return json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))


def load_bitacora() -> list[dict]:
    if not BITACORA.exists():
        return []
    df = pd.read_csv(BITACORA)
    return json.loads(df.to_json(orient="records", force_ascii=False))


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _titulos_por_numero() -> dict[str, str]:
    path = PROC / "minciencias" / "minciencias_convocatorias_processed.csv"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    df = pd.read_csv(path, dtype=str)
    if "numero" not in df.columns or "titulo" not in df.columns:
        return out
    for _, row in df.iterrows():
        num = str(row["numero"]).strip().replace(".0", "")
        tit = str(row.get("titulo") or "").strip()
        if num and tit and tit.lower() != "nan":
            out[num] = tit
    return out


def matching_summary() -> dict:
    """Lista TODAS las convocatorias con NLP (+ flags de ranking/elegibilidad)."""
    from convocaur.paths import PROC_ELEGIBILIDAD, PROC_NLP

    resumen_path = PROC_MATCHING / "resumen_match.json"
    resumen = []
    if resumen_path.exists():
        resumen = json.loads(resumen_path.read_text(encoding="utf-8"))
    by_key = {r["convocatoria"]: r for r in resumen}
    titulos = _titulos_por_numero()

    nlp_files = sorted(PROC_NLP.glob("convocatoria_*_nlp.json")) if PROC_NLP.exists() else []
    convocatorias = []
    for f in nlp_files:
        key = f.stem.replace("_nlp", "")
        numero = key.replace("convocatoria_", "")
        meta = by_key.get(key, {})
        ranking_path = PROC_MATCHING / f"ranking_{key}.csv"
        eleg_path = PROC_ELEGIBILIDAD / f"{key}_elegibilidad.json"

        puede = None
        modo = None
        if eleg_path.exists():
            try:
                eleg = json.loads(eleg_path.read_text(encoding="utf-8"))
                vf = eleg.get("veredicto_final") or eleg
                puede = vf.get("puede_postularse")
                modo = vf.get("modo")
            except Exception:
                pass

        objetivo = ""
        try:
            nlp = json.loads(f.read_text(encoding="utf-8"))
            objetivo = (nlp.get("objetivo") or "").strip()
            if puede is None and isinstance(nlp.get("elegibilidad_urosario"), dict):
                vf = nlp["elegibilidad_urosario"].get("veredicto_final") or nlp["elegibilidad_urosario"]
                puede = vf.get("puede_postularse")
                modo = modo or vf.get("modo")
        except Exception:
            pass

        convocatorias.append({
            "id": key,
            "numero": numero,
            "titulo": titulos.get(numero) or "",
            "objetivo_preview": (objetivo[:140] + "…") if len(objetivo) > 140 else objetivo,
            "top1_id": meta.get("top1_id"),
            "top1_nombre": meta.get("top1_nombre") or meta.get("top1_id"),
            "top1_score": meta.get("top1_score"),
            "n_candidatos_pool": meta.get("n_candidatos_pool"),
            "uso_embeddings": meta.get("uso_embeddings"),
            "tiene_nlp": True,
            "tiene_ranking": ranking_path.exists(),
            "tiene_elegibilidad": eleg_path.exists(),
            "puede_postularse": puede,
            "modo_elegibilidad": modo,
        })

    # Orden: primero con ranking, luego por número desc
    def sort_key(c: dict) -> tuple:
        num = int(c["numero"]) if str(c["numero"]).isdigit() else 0
        return (0 if c["tiene_ranking"] else 1, -num)

    convocatorias.sort(key=sort_key)

    cache_dir = PROC_MATCHING / "cache_embeddings"
    n_cache = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
    n_rank = sum(1 for c in convocatorias if c["tiene_ranking"])
    n_elegibles = sum(1 for c in convocatorias if c.get("puede_postularse") is True)

    return {
        "formula": "0.7·cos(emb) + 0.3·cos(tfidf) + boost",
        "modelo_embeddings": "openai/text-embedding-3-small",
        "n_cache_embeddings": n_cache,
        "n_nlp": len(convocatorias),
        "n_con_ranking": n_rank,
        "n_sin_ranking": len(convocatorias) - n_rank,
        "n_elegibles": n_elegibles,
        "convocatorias": convocatorias,
    }


def project_stats() -> dict:
    from convocaur.paths import JSON_PROFESORES, PROC_ELEGIBILIDAD, PROC_NLP, SIN_CVLAC_CSV

    n_nlp = len(list(PROC_NLP.glob("convocatoria_*_nlp.json"))) if PROC_NLP.exists() else 0
    n_eleg = (
        len(list(PROC_ELEGIBILIDAD.glob("convocatoria_*_elegibilidad.json")))
        if PROC_ELEGIBILIDAD.exists()
        else 0
    )
    n_prof = len(list(JSON_PROFESORES.glob("*.json"))) if JSON_PROFESORES.exists() else 0
    n_sin = 0
    if SIN_CVLAC_CSV.exists():
        n_sin = len(pd.read_csv(SIN_CVLAC_CSV))
    n_rank = len(list(PROC_MATCHING.glob("ranking_convocatoria_*.csv"))) if PROC_MATCHING.exists() else 0

    return {
        "nlp_convocatorias": n_nlp,
        "elegibilidad": n_eleg,
        "docentes_json": n_prof,
        "sin_cvlac": n_sin,
        "con_cvlac_approx": max(n_prof - n_sin, 0),
        "rankings_matching": n_rank,
    }
