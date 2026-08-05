"""Inferencia Cap.3 — carga joblib y predice adjudicación / presupuesto / segmento."""

from __future__ import annotations

import math
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[3]
MODELOS = ROOT / "analisis" / "secop" / "salidas_capacidad3" / "modelos"

SEGMENTO_NOMBRE = {
    "80": "Gestión y servicios profesionales",
    "81": "Ingeniería, investigación y tecnología",
    "86": "Educación y capacitación",
}

PRESUPUESTO_NOMBRE = {
    "Q1_bajo": "Bajo",
    "Q2": "Medio-bajo",
    "Q3": "Medio-alto",
    "Q4_alto": "Alto",
}


class ModelUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_bundles() -> dict[str, Any]:
    try:
        import joblib
    except ImportError as exc:
        raise ModelUnavailable("Falta joblib") from exc

    paths = {
        "adj": MODELOS / "adjudicacion_competitivo.joblib",
        "pres": MODELOS / "presupuesto_bins.joblib",
        "seg": MODELOS / "segmento_unspsc.joblib",
    }
    missing = [k for k, p in paths.items() if not p.exists()]
    if missing:
        raise ModelUnavailable(f"Faltan modelos en disco: {missing}. Ruta: {MODELOS}")

    try:
        return {k: joblib.load(p) for k, p in paths.items()}
    except Exception as exc:
        raise ModelUnavailable(
            "No se pudieron cargar los .joblib. Pin scikit-learn==1.6.1 "
            f"(versión de entrenamiento). Detalle: {exc}"
        ) from exc


def models_status() -> dict[str, Any]:
    try:
        b = _load_bundles()
        adj = b["adj"]
        return {
            "ok": True,
            "ruta": str(MODELOS),
            "fecha_corte": adj.get("fecha_corte"),
            "modelo_adjudicacion": adj.get("modelo_recomendado"),
            "n_entidades_conocidas": len(adj.get("entidad_te_map") or {}),
        }
    except ModelUnavailable as exc:
        return {"ok": False, "error": str(exc), "ruta": str(MODELOS)}


def _modalidades_disponibles(adj: dict) -> list[str]:
    cols = adj.get("feature_columns") or []
    mods = []
    prefix = "modalidad_de_contratacion_"
    for c in cols:
        if c.startswith(prefix):
            mods.append(c[len(prefix) :])
    # también las del dict de tasas (pueden no tener dummy)
    for m in adj.get("tasa_modalidad_train") or {}:
        if m not in mods:
            mods.append(m)
    return sorted(mods)


def _departamentos_disponibles(adj: dict) -> list[str]:
    cols = adj.get("feature_columns") or []
    deps = []
    prefix = "departamento_agrupado_"
    for c in cols:
        if c.startswith(prefix):
            deps.append(c[len(prefix) :])
    return sorted(deps)


def predict_meta() -> dict[str, Any]:
    st = models_status()
    if not st.get("ok"):
        return {**st, "presets": _presets_fallback()}
    adj = _load_bundles()["adj"]
    pres = _load_bundles()["pres"]
    return {
        **st,
        "modalidades": _modalidades_disponibles(adj),
        "departamentos": _departamentos_disponibles(adj),
        "presupuesto_labels": [
            {"id": lab, "nombre": PRESUPUESTO_NOMBRE.get(lab, lab)}
            for lab in (pres.get("labels") or [])
        ],
        "presupuesto_cortes_cop": [
            None if not np.isfinite(x) else float(x) for x in (pres.get("bins") or [])
        ],
        "presets": _presets(),
        "campos": {
            "precio_base_cop": "Precio base estimado del proceso (pesos)",
            "duracion_meses": "Duración estimada (meses)",
            "numero_de_lotes": "Número de lotes",
            "mes_publicacion": "Mes de publicación (1–12)",
            "anio_publicacion": "Año de publicación",
            "modalidad": "Modalidad de contratación",
            "departamento": "Departamento de la entidad",
            "entidad": "Nombre de la entidad (opcional; si se conoce mejora la señal)",
        },
    }


def _vectorize(adj: dict, payload: dict[str, Any]) -> pd.DataFrame:
    feats = list(adj["feature_columns"])
    row = {c: 0.0 for c in feats}

    precio = float(payload.get("precio_base_cop") or 0)
    if precio < 0:
        precio = 0
    if "log_precio_base_real" in row:
        row["log_precio_base_real"] = float(math.log1p(precio))

    med = adj.get("medianas_impute") or {}
    dur = payload.get("duracion_meses")
    lotes = payload.get("numero_de_lotes")
    row["duracion"] = float(dur if dur is not None else med.get("duracion", 6))
    row["numero_de_lotes"] = float(lotes if lotes is not None else med.get("numero_de_lotes", 0))
    row["mes_publicacion"] = float(payload.get("mes_publicacion") or 6)
    row["anio_publicacion"] = float(payload.get("anio_publicacion") or 2025)

    entidad = (payload.get("entidad") or "").strip()
    te_map = adj.get("entidad_te_map") or {}
    if entidad and entidad in te_map:
        row["entidad_te"] = float(te_map[entidad])
    else:
        row["entidad_te"] = float(adj.get("entidad_te_global") or 0.5)

    modalidad = payload.get("modalidad") or ""
    mod_col = f"modalidad_de_contratacion_{modalidad}"
    if mod_col in row:
        row[mod_col] = 1.0

    depto = payload.get("departamento") or "OTRO"
    dep_col = f"departamento_agrupado_{depto}"
    if dep_col in row:
        row[dep_col] = 1.0
    elif "departamento_agrupado_OTRO" in row:
        row["departamento_agrupado_OTRO"] = 1.0

    return pd.DataFrame([row])[feats]


def predict(payload: dict[str, Any]) -> dict[str, Any]:
    bundles = _load_bundles()
    adj = bundles["adj"]
    pres = bundles["pres"]
    seg = bundles["seg"]

    X_adj = _vectorize(adj, payload)
    model = adj[adj["modelo_recomendado"]]
    proba = float(model.predict_proba(X_adj)[0, 1])

    # presupuesto / segmento usan subset de columnas
    def align(bundle: dict) -> pd.DataFrame:
        cols = list(bundle["feature_columns"])
        base = {c: 0.0 for c in cols}
        for c in cols:
            if c in X_adj.columns:
                base[c] = float(X_adj.iloc[0][c])
        # entidad_te / duración ya vienen en X_adj cuando existen
        if "entidad_te" in base and "entidad_te" in X_adj.columns:
            base["entidad_te"] = float(X_adj.iloc[0]["entidad_te"])
        for c in ("duracion", "numero_de_lotes", "mes_publicacion", "anio_publicacion", "log_precio_base_real"):
            if c in base and c in X_adj.columns:
                base[c] = float(X_adj.iloc[0][c])
        # one-hots
        for c in cols:
            if c.startswith("modalidad_") or c.startswith("departamento_"):
                if c in X_adj.columns:
                    base[c] = float(X_adj.iloc[0][c])
        return pd.DataFrame([base])[cols]

    X_pres = align(pres)
    X_seg = align(seg)
    bin_id = str(pres["model_hgb"].predict(X_pres)[0])
    seg_id = str(seg["model_hgb"].predict(X_seg)[0])

    # lectura humana
    if proba >= 0.65:
        lectura_adj = "Alta probabilidad de adjudicación según el modelo."
    elif proba >= 0.45:
        lectura_adj = "Probabilidad intermedia: conviene revisar competencia y requisitos."
    else:
        lectura_adj = "Baja probabilidad de adjudicación en este perfil de proceso."

    return {
        "ok": True,
        "input": payload,
        "adjudicacion": {
            "probabilidad": round(proba, 4),
            "probabilidad_pct": round(proba * 100, 1),
            "modelo": adj.get("modelo_recomendado"),
            "lectura": lectura_adj,
            "usar": True,
        },
        "presupuesto": {
            "bin": bin_id,
            "nombre": PRESUPUESTO_NOMBRE.get(bin_id, bin_id),
            "lectura": (
                "Rango estimado sin usar el monto como trampa: el modelo infiere la magnitud "
                "desde duración, modalidad, lugar y entidad."
            ),
            "usar": True,
            "nota": "Puede diferir del precio que escribiste a propósito (así se entrenó).",
        },
        "segmento": {
            "codigo": seg_id,
            "nombre": SEGMENTO_NOMBRE.get(seg_id, seg_id),
            "lectura": "Clasificación tabular débil: tómalo como pista, no como verdad.",
            "usar": False,
        },
    }


def _presets() -> list[dict[str, Any]]:
    return [
        {
            "id": "licitacion_bogota",
            "nombre": "Licitación en Bogotá · presupuesto alto",
            "descripcion": "Proceso competitivo grande en Distrito Capital.",
            "payload": {
                "precio_base_cop": 2_500_000_000,
                "duracion_meses": 18,
                "numero_de_lotes": 1,
                "mes_publicacion": 3,
                "anio_publicacion": 2025,
                "modalidad": "Licitación pública",
                "departamento": "Distrito Capital de Bogotá",
                "entidad": "",
            },
        },
        {
            "id": "minima_cuantia",
            "nombre": "Mínima cuantía · proceso chico",
            "descripcion": "Contrato pequeño, corto, fuera de Bogotá.",
            "payload": {
                "precio_base_cop": 45_000_000,
                "duracion_meses": 3,
                "numero_de_lotes": 1,
                "mes_publicacion": 9,
                "anio_publicacion": 2025,
                "modalidad": "Mínima cuantía",
                "departamento": "Boyacá",
                "entidad": "",
            },
        },
        {
            "id": "abreviada_valle",
            "nombre": "Selección abreviada · Valle",
            "descripcion": "Cuantía media, duración típica.",
            "payload": {
                "precio_base_cop": 320_000_000,
                "duracion_meses": 8,
                "numero_de_lotes": 2,
                "mes_publicacion": 6,
                "anio_publicacion": 2025,
                "modalidad": "Selección Abreviada de Menor Cuantía",
                "departamento": "Valle del Cauca",
                "entidad": "",
            },
        },
        {
            "id": "subasta_antioquia",
            "nombre": "Subasta inversa · Antioquia (OTRO dpto. map)",
            "descripcion": "Modalidad competitiva con presión de precio.",
            "payload": {
                "precio_base_cop": 900_000_000,
                "duracion_meses": 12,
                "numero_de_lotes": 1,
                "mes_publicacion": 1,
                "anio_publicacion": 2025,
                "modalidad": "Selección abreviada subasta inversa",
                "departamento": "OTRO",
                "entidad": "",
            },
        },
    ]


def _presets_fallback() -> list[dict[str, Any]]:
    return _presets()
