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
WEB = PROJECT_ROOT / "web"
ANALISIS = PROJECT_ROOT / "analisis"

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

# --- Matching ---
PROC_MATCHING = PROCESSED / "matching"
PROC_MATCHING_CACHE = PROC_MATCHING / "cache_embeddings"
PROC_EXPLORACION = PROCESSED / "exploracion"

# --- SECOP CTeI (análisis de mercado Cap. 1–3) ---
SECOP = ANALISIS / "secop"
SECOP_PROCESOS_RAW = SECOP / "secop_ctei_procesos.csv"
SECOP_LINEAS_RAW = SECOP / "secop_ctei_lineas.csv"
SECOP_PROCESOS_LIMPIO = SECOP / "secop_ctei_procesos_limpio.csv"
SECOP_LINEAS_LIMPIO = SECOP / "secop_ctei_lineas_limpio.csv"
SECOP_PROCESOS_DEFLACTADO = SECOP / "secop_ctei_procesos_deflactado.csv"
SECOP_PROCESOS_DEFLACTADO_CLEAN = SECOP / "secop_ctei_procesos_deflactado_sin_implausibles.csv"
SECOP_IPC_XLSX = SECOP / "anex-IPC-jun2026.xlsx"
SECOP_IPC_CSV = SECOP / "ipc_dane_mensual_interpolado_TOTAL.csv"
SECOP_MODELOS = SECOP / "salidas_capacidad3" / "modelos"

# Compat: aliases antiguos (código/docs previos)
LAB = ANALISIS
LAB_SECOP = SECOP

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
        PROC_MATCHING,
        PROC_MATCHING_CACHE,
        PROC_EXPLORACION,
    ]:
        p.mkdir(parents=True, exist_ok=True)
