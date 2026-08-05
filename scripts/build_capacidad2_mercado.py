"""Genera métricas Cap.2 (mercado) para el dashboard — lenguaje y cifras alineadas al notebook."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "analisis" / "secop" / "secop_ctei_lineas_limpio.csv"
OUT = ROOT / "data" / "processed" / "secop" / "capacidad2_mercado.json"
DASH = ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json"

# Misma regla de implausibles usada en el análisis SECOP
ABS_CAP = 1e13


def hhi(participacion: pd.Series) -> float:
    return float((participacion ** 2).sum() * 10000)


def main() -> None:
    print("Leyendo", CSV.name)
    usecols = [
        "id_del_proceso",
        "entidad",
        "adjudicado_bool",
        "valor_total_adjudicacion",
        "nit_del_proveedor_adjudicado",
        "nombre_del_proveedor",
        "fecha_de_publicacion_del",
        "precio_base",
    ]
    df = pd.read_csv(CSV, usecols=lambda c: c in usecols, low_memory=False)
    df["valor_total_adjudicacion"] = pd.to_numeric(df["valor_total_adjudicacion"], errors="coerce")
    df["precio_base"] = pd.to_numeric(df["precio_base"], errors="coerce")
    df["fecha_de_publicacion_del"] = pd.to_datetime(df["fecha_de_publicacion_del"], errors="coerce")
    if df["adjudicado_bool"].dtype == object:
        df["adjudicado_bool"] = df["adjudicado_bool"].astype(str).str.lower().isin(
            ["1", "true", "si", "sí", "yes"]
        )
    else:
        df["adjudicado_bool"] = df["adjudicado_bool"].fillna(False).astype(bool)

    base = df[
        df["adjudicado_bool"]
        & (df["valor_total_adjudicacion"] > 0)
        & df["valor_total_adjudicacion"].notna()
    ].copy()
    base["proveedor_id"] = (
        base["nit_del_proveedor_adjudicado"].fillna(base["nombre_del_proveedor"]).astype(str)
    )
    base["proveedor_nombre"] = base["nombre_del_proveedor"].fillna(base["proveedor_id"]).astype(str)

    # Implausible: absoluto o relativo a precio base
    rel = (base["valor_total_adjudicacion"] > 100 * base["precio_base"].clip(lower=1)) & base[
        "precio_base"
    ].notna()
    abs_bad = base["valor_total_adjudicacion"] > ABS_CAP
    base["flag_implausible"] = abs_bad | rel

    bruto = base.copy()
    limpio = base[~base["flag_implausible"]].copy()

    def mercado_tabla(frame: pd.DataFrame) -> pd.DataFrame:
        m = (
            frame.groupby(["proveedor_id", "proveedor_nombre"], as_index=False)[
                "valor_total_adjudicacion"
            ]
            .sum()
            .sort_values("valor_total_adjudicacion", ascending=False)
        )
        total = m["valor_total_adjudicacion"].sum()
        m["participacion"] = m["valor_total_adjudicacion"] / total if total else 0
        m["participacion_acum"] = m["participacion"].cumsum()
        return m

    merc_bruto = mercado_tabla(bruto)
    merc_limpio = mercado_tabla(limpio)

    hhi_antes = hhi(merc_bruto["participacion"])
    hhi_despues = hhi(merc_limpio["participacion"])
    n_80 = int((merc_limpio["participacion_acum"] <= 0.80).sum() + 1)
    n_prov = int(len(merc_limpio))
    pct_80 = n_80 / n_prov if n_prov else 0.0

    # Curva de Pareto (puntos cada ~2% de proveedores para la gráfica)
    pareto_curve = []
    for pct_prov in np.linspace(0.01, 1.0, 40):
        k = max(1, int(round(pct_prov * n_prov)))
        share = float(merc_limpio.head(k)["participacion"].sum())
        pareto_curve.append({
            "pct_proveedores": round(pct_prov * 100, 1),
            "pct_valor": round(share * 100, 1),
        })

    top15 = merc_limpio.head(15).copy()
    top_proveedores = [
        {
            "nombre": str(r.proveedor_nombre)[:60],
            "valor_cop": float(r.valor_total_adjudicacion),
            "participacion_pct": round(float(r.participacion) * 100, 2),
        }
        for r in top15.itertuples()
    ]

    # HHI por entidad (mín. 20 procesos)
    limpio["entidad"] = limpio["entidad"].fillna("Sin entidad").astype(str)
    filas_ent = []
    for ent, sub in limpio.groupby("entidad"):
        val = sub.groupby("proveedor_id")["valor_total_adjudicacion"].sum()
        if val.sum() <= 0:
            continue
        filas_ent.append({
            "entidad": ent[:70],
            "hhi": hhi(val / val.sum()),
            "proveedores": int(sub["proveedor_id"].nunique()),
            "procesos": int(sub["id_del_proceso"].nunique()),
            "valor_total_cop": float(val.sum()),
        })
    hhi_ent = pd.DataFrame(filas_ent)
    filtradas = hhi_ent[hhi_ent["procesos"] >= 20].sort_values("hhi", ascending=False)
    concentradas = filtradas.head(8).to_dict(orient="records")
    competitivas = filtradas.sort_values("hhi").head(5).to_dict(orient="records")

    # Rotación: overlap de top-50 proveedores entre años
    limpio["anio"] = limpio["fecha_de_publicacion_del"].dt.year
    anios = sorted([int(a) for a in limpio["anio"].dropna().unique() if 2022 <= a <= 2026])
    rotacion = []
    prev_top = None
    for anio in anios:
        sub = limpio[limpio["anio"] == anio]
        m = (
            sub.groupby("proveedor_id")["valor_total_adjudicacion"]
            .sum()
            .sort_values(ascending=False)
        )
        top = set(m.head(50).index.astype(str))
        overlap = None
        if prev_top is not None and top:
            overlap = round(100 * len(top & prev_top) / len(top | prev_top), 1)  # Jaccard %
        top1_id = str(m.index[0]) if len(m) else ""
        top1_nombre = ""
        if top1_id:
            names = sub.loc[sub["proveedor_id"].astype(str) == top1_id, "proveedor_nombre"]
            if len(names):
                top1_nombre = str(names.mode().iloc[0])[:80]
        rotacion.append({
            "anio": anio,
            "n_proveedores": int(m.shape[0]),
            "top1_participacion_pct": round(float(m.iloc[0] / m.sum() * 100), 2) if len(m) else 0,
            "top1_nombre": top1_nombre,
            "top1_valor_cop": float(m.iloc[0]) if len(m) else 0.0,
            "jaccard_top50_vs_anio_prev_pct": overlap,
        })
        prev_top = top

    lectura_hhi = (
        "Sin limpiar errores de datos el mercado parece un monopolio. "
        "Con la corrección, es un mercado abierto a nivel nacional."
        if hhi_despues < 1500
        else "El mercado muestra concentración moderada o alta incluso tras limpiar datos."
    )

    payload = {
        "meta": {
            "fuente_csv": CSV.name,
            "n_lineas_adjudicadas_limpias": int(len(limpio)),
            "n_implausibles_excluidos": int(base["flag_implausible"].sum()),
        },
        "titulo": "Mercado: ¿quién gana los contratos CTeI?",
        "subtitulo": "Concentración, competencia y rotación de proveedores (pesos adjudicados)",
        "kpis": {
            "hhi_antes": round(hhi_antes, 1),
            "hhi_despues": round(hhi_despues, 1),
            "nivel_concentracion": (
                "baja" if hhi_despues < 1500 else "moderada" if hhi_despues < 2500 else "alta"
            ),
            "proveedores_80pct_valor": n_80,
            "proveedores_total": n_prov,
            "pct_proveedores_80": round(pct_80 * 100, 1),
        },
        "hhi": {
            "antes_outliers": round(hhi_antes, 1),
            "despues_correccion": round(hhi_despues, 1),
            "lectura": lectura_hhi,
            "guia": [
                {"rango": "Menos de 1.500", "significado": "Mercado poco concentrado (competencia amplia)"},
                {"rango": "1.500 – 2.500", "significado": "Concentración moderada"},
                {"rango": "Más de 2.500", "significado": "Mercado muy concentrado"},
            ],
        },
        "pareto": {
            "proveedores_80pct_valor": n_80,
            "proveedores_total": n_prov,
            "pct_proveedores": pct_80,
            "lectura": (
                f"Hacen falta {n_80:,} proveedores (el {pct_80:.1%} del total) para sumar el 80% del valor. "
                "No es un mercado de un solo ganador."
            ),
            "curva": pareto_curve,
        },
        "top_proveedores": top_proveedores,
        "nichos_concentrados": [
            {
                "entidad": r["entidad"],
                "hhi": round(float(r["hhi"]), 1),
                "proveedores": int(r["proveedores"]),
                "procesos": int(r["procesos"]),
                "valor_total_cop": float(r["valor_total_cop"]),
            }
            for r in concentradas
        ],
        "nichos_competitivos": [
            {
                "entidad": r["entidad"],
                "hhi": round(float(r["hhi"]), 1),
                "proveedores": int(r["proveedores"]),
                "procesos": int(r["procesos"]),
            }
            for r in competitivas
        ],
        "rotacion_anual": rotacion,
        "rotacion_lectura": (
            "Los líderes del ranking de proveedores cambian bastante de un año a otro: "
            "el mercado no está “cerrado” a siempre los mismos nombres."
        ),
        "cierre_rosario": {
            "titulo": "Qué implica para la Universidad del Rosario",
            "puntos": [
                "A nivel nacional el mercado CTeI no está monopolizado: hay espacio para nuevos oferentes calificados, incluidas IES.",
                "Ojo con los nichos: algunas entidades compran casi siempre a los mismos proveedores — ahí la barrera no es el país, es el comprador.",
                "La rotación anual sugiere ventanas reales: conviene vigilar procesos nuevos, no solo “los de siempre”.",
                "Para Rosario: usar este mapa para priorizar entidades/segmentos más abiertos, y el matching Minciencias para armar el equipo docente cuando aparezca la convocatoria.",
            ],
        },
        "nota_metodologica": (
            "HHI = índice de concentración (0 ≈ competencia perfecta; 10.000 = un solo proveedor). "
            "Se calcula sobre líneas adjudicadas con valor > 0. "
            "Se excluyen valores implausibles (p. ej. montos extremos o >100× el precio base). "
            "Pareto: cuántos proveedores suman el 80% del valor adjudicado."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(
        f"HHI {hhi_antes:.1f} → {hhi_despues:.1f} | Pareto {n_80}/{n_prov} ({pct_80:.1%}) | top_ent={len(concentradas)}"
    )

    if DASH.exists():
        dash = json.loads(DASH.read_text(encoding="utf-8"))
    else:
        dash = {}
    dash["capacidad_2"] = {
        "titulo": payload["titulo"],
        "subtitulo": payload["subtitulo"],
        "kpis": payload["kpis"],
        "hhi": payload["hhi"],
        "pareto": payload["pareto"],
        "top_proveedores": top_proveedores,
        "nichos_hhi_ejemplo": [
            {"entidad": x["entidad"], "hhi": x["hhi"]} for x in concentradas[:5]
        ],
        "nichos_concentrados": payload["nichos_concentrados"],
        "nichos_competitivos": payload["nichos_competitivos"],
        "rotacion_anual": rotacion,
        "rotacion": payload["rotacion_lectura"],
        "rotacion_lectura": payload["rotacion_lectura"],
        "siguiente_mejora": (
            "Siguiente mejora natural: clasificar contratos por tema con lenguaje (embeddings), "
            "no solo por código de producto."
        ),
        "cierre_rosario": payload["cierre_rosario"],
        "nota_metodologica": payload["nota_metodologica"],
    }
    DASH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated", DASH)


if __name__ == "__main__":
    main()
