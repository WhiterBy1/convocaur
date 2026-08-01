"""Carga canónica de datos Minciencias / Rosario (sin labs personales)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from convocaur import paths as P


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def cargar_minciencias() -> dict[str, Any]:
    """CSVs raw/processed + NLP/secciones/elegibilidad disponibles."""
    nlp = {}
    for f in sorted(P.PROC_NLP.glob("convocatoria_*_nlp.json")):
        nlp[f.stem.replace("_nlp", "")] = _read_json(f)

    secciones = {}
    for f in sorted(P.PROC_SECCIONES.glob("convocatoria_*_secciones.json")):
        secciones[f.stem.replace("_secciones", "")] = _read_json(f)

    elegibilidad = {}
    for f in sorted(P.PROC_ELEGIBILIDAD.glob("convocatoria_*_elegibilidad.json")):
        elegibilidad[f.stem.replace("_elegibilidad", "")] = _read_json(f)

    return {
        "listado": _safe_csv(P.LISTADO_CSV),
        "actividades": _safe_csv(P.ACTIVIDADES_CSV),
        "documentos": _safe_csv(P.DOCUMENTOS_CSV),
        "convocatorias_processed": _safe_csv(
            P.PROC_MINCIENCIAS / "minciencias_convocatorias_processed.csv"
        ),
        "actividades_processed": _safe_csv(
            P.PROC_MINCIENCIAS / "minciencias_actividades_processed.csv"
        ),
        "documentos_processed": _safe_csv(
            P.PROC_MINCIENCIAS / "minciencias_documentos_processed.csv"
        ),
        "nlp_por_convocatoria": nlp,
        "secciones_por_convocatoria": secciones,
        "elegibilidad_por_convocatoria": elegibilidad,
        "rutas": {
            "raw": str(P.RAW_MINCIENCIAS),
            "tdr": str(P.RAW_MINCIENCIAS_TDR),
            "archivos": str(P.RAW_MINCIENCIAS_ARCHIVOS),
            "nlp": str(P.PROC_NLP),
            "secciones": str(P.PROC_SECCIONES),
            "elegibilidad": str(P.PROC_ELEGIBILIDAD),
        },
    }


def cargar_urosario(
    cargar_json_profesores: bool = False,
    limite_json: int | None = 20,
) -> dict[str, Any]:
    """Docentes CSV + sin_cvlac. Por defecto no carga los ~600 JSON."""
    docentes = _safe_csv(P.DOCENTES_CSV)
    sin_cvlac = _safe_csv(P.SIN_CVLAC_CSV)

    profesores: dict[str, Any] = {}
    if cargar_json_profesores and P.JSON_PROFESORES.exists():
        files = sorted(P.JSON_PROFESORES.glob("*.json"))
        if limite_json is not None:
            files = files[:limite_json]
        for f in files:
            profesores[f.stem] = _read_json(f)

    return {
        "docentes": docentes,
        "sin_cvlac": sin_cvlac,
        "profesores_json": profesores,
        "n_json_disponibles": (
            len(list(P.JSON_PROFESORES.glob("*.json"))) if P.JSON_PROFESORES.exists() else 0
        ),
        "rutas": {
            "docentes_csv": str(P.DOCENTES_CSV),
            "sin_cvlac": str(P.SIN_CVLAC_CSV),
            "json_profesores": str(P.JSON_PROFESORES),
        },
    }


def cargar_profesor(profesor_id: str) -> dict[str, Any]:
    path = P.JSON_PROFESORES / f"{profesor_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return _read_json(path)


def guardar_salida(nombre: str, obj: Any, base: Path | None = None) -> Path:
    """
    Guarda un resultado bajo data/processed/ (por defecto matching/).

    - DataFrame → CSV
    - dict/list → JSON
    - str → TXT
    """
    out = base or P.PROC_MATCHING
    out.mkdir(parents=True, exist_ok=True)
    dest = out / nombre

    if isinstance(obj, pd.DataFrame):
        if not dest.suffix:
            dest = dest.with_suffix(".csv")
        dest.parent.mkdir(parents=True, exist_ok=True)
        obj.to_csv(dest, index=False, encoding="utf-8")
    elif isinstance(obj, (dict, list)):
        if not dest.suffix:
            dest = dest.with_suffix(".json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        if not dest.suffix:
            dest = dest.with_suffix(".txt")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(str(obj), encoding="utf-8")

    return dest


def cargar_todo(
    cargar_json_profesores: bool = False,
    limite_json: int | None = 20,
) -> dict[str, Any]:
    """Carga Minciencias + Rosario + rutas de salidas del matching."""
    return {
        "salidas": P.PROC_MATCHING,
        "minciencias": cargar_minciencias(),
        "urosario": cargar_urosario(
            cargar_json_profesores=cargar_json_profesores,
            limite_json=limite_json,
        ),
        "proyecto": P.PROJECT_ROOT,
    }
