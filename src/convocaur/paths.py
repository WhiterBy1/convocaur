"""Rutas canónicas del proyecto ConvocaUR."""

from __future__ import annotations

from pathlib import Path

# convocaur/  (raíz del proyecto limpio)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA = PROJECT_ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
CONFIG = PROJECT_ROOT / "config"
DOCS = PROJECT_ROOT / "docs"

# --- Minciencias ---
RAW_MINCIENCIAS = RAW / "minciencias"
RAW_MINCIENCIAS_ARCHIVOS = RAW_MINCIENCIAS / "archivos"
RAW_MINCIENCIAS_TDR = RAW_MINCIENCIAS / "tdr"

PROC_MINCIENCIAS = PROCESSED / "minciencias"
PROC_SECCIONES = PROC_MINCIENCIAS / "secciones"
PROC_NLP = PROC_MINCIENCIAS / "nlp"
PROC_ELEGIBILIDAD = PROC_MINCIENCIAS / "elegibilidad"

LISTADO_CSV = RAW_MINCIENCIAS / "convocatorias_listado_raw.csv"
ACTIVIDADES_CSV = RAW_MINCIENCIAS / "convocatorias_actividades_raw.csv"
DOCUMENTOS_CSV = RAW_MINCIENCIAS / "convocatorias_documentos_raw.csv"

# --- Universidad del Rosario ---
RAW_UROSARIO = RAW / "urosario"
JSON_PROFESORES = RAW_UROSARIO / "json_profesores"
DOCENTES_CSV = RAW_UROSARIO / "docentes_urosario_con_id.csv"
SIN_CVLAC_CSV = RAW_UROSARIO / "sin_cvlac.csv"

# --- Secrets ---
ENV_FILE = PROJECT_ROOT / ".env"


def ensure_data_dirs() -> None:
    for p in [
        RAW_MINCIENCIAS_ARCHIVOS,
        RAW_MINCIENCIAS_TDR,
        JSON_PROFESORES,
        PROC_SECCIONES,
        PROC_NLP,
        PROC_ELEGIBILIDAD,
    ]:
        p.mkdir(parents=True, exist_ok=True)
