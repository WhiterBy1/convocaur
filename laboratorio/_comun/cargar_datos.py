"""
Utilidades compartidas del laboratorio ConvocaUR.

Uso desde un notebook en laboratorio/<persona>/:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path.cwd().parents[1] / "src"))
    sys.path.insert(0, str(Path.cwd().parent / "_comun"))

    from cargar_datos import cargar_todo
    datos = cargar_todo(persona="josue")
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Raíz del proyecto limpio: convocaur/
LAB_DIR = Path(__file__).resolve().parent          # laboratorio/_comun
CONVOCAUR_ROOT = LAB_DIR.parents[1]                # convocaur/
sys.path.insert(0, str(CONVOCAUR_ROOT / "src"))

from convocaur import paths as P  # noqa: E402


def salidas_dir(persona: str) -> Path:
    """Carpeta de escritura exclusiva de la persona (gitignored)."""
    out = CONVOCAUR_ROOT / "laboratorio" / persona.lower() / "salidas"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def cargar_minciencias() -> dict[str, Any]:
    """CSVs raw + processed + NLP/secciones/elegibilidad disponibles."""
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
        "convocatorias_processed": _safe_csv(P.PROC_MINCIENCIAS / "minciencias_convocatorias_processed.csv"),
        "actividades_processed": _safe_csv(P.PROC_MINCIENCIAS / "minciencias_actividades_processed.csv"),
        "documentos_processed": _safe_csv(P.PROC_MINCIENCIAS / "minciencias_documentos_processed.csv"),
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


def cargar_urosario(cargar_json_profesores: bool = False, limite_json: int | None = 20) -> dict[str, Any]:
    """
    Docentes CSV + sin_cvlac.

    Por defecto NO carga los 612 JSON en memoria (pesado).
    Si cargar_json_profesores=True, carga hasta `limite_json` (None = todos).
    """
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
        "n_json_disponibles": len(list(P.JSON_PROFESORES.glob("*.json"))) if P.JSON_PROFESORES.exists() else 0,
        "rutas": {
            "docentes_csv": str(P.DOCENTES_CSV),
            "sin_cvlac": str(P.SIN_CVLAC_CSV),
            "json_profesores": str(P.JSON_PROFESORES),
        },
    }


def cargar_profesor(profesor_id: str) -> dict[str, Any]:
    """Carga un único JSON de profesor por id (slug)."""
    path = P.JSON_PROFESORES / f"{profesor_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return _read_json(path)


def guardar_salida(persona: str, nombre: str, obj: Any) -> Path:
    """
    Guarda un resultado SOLO en laboratorio/<persona>/salidas/.

    - DataFrame → CSV
    - dict/list → JSON
    - str → TXT
    """
    out = salidas_dir(persona)
    dest = out / nombre

    if isinstance(obj, pd.DataFrame):
        if not dest.suffix:
            dest = dest.with_suffix(".csv")
        obj.to_csv(dest, index=False, encoding="utf-8")
    elif isinstance(obj, (dict, list)):
        if not dest.suffix:
            dest = dest.with_suffix(".json")
        dest.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        if not dest.suffix:
            dest = dest.with_suffix(".txt")
        dest.write_text(str(obj), encoding="utf-8")

    return dest


def cargar_todo(persona: str, cargar_json_profesores: bool = False, limite_json: int | None = 20) -> dict[str, Any]:
    """Carga Minciencias + Rosario + ruta de salidas de la persona."""
    return {
        "persona": persona.lower(),
        "salidas": salidas_dir(persona),
        "minciencias": cargar_minciencias(),
        "urosario": cargar_urosario(
            cargar_json_profesores=cargar_json_profesores,
            limite_json=limite_json,
        ),
        "proyecto": CONVOCAUR_ROOT,
    }
