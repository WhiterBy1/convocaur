"""Rellena top1_nombre / top1_valor_cop en rotacion_anual sin regenerar todo Cap.2."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "analisis" / "secop" / "secop_ctei_lineas_limpio.csv"
ABS_CAP = 1e13
FILES = [
    ROOT / "data" / "processed" / "secop" / "capacidad2_mercado.json",
    ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json",
]


def compute_rotacion() -> list[dict]:
    usecols = [
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
    rel = (base["valor_total_adjudicacion"] > 100 * base["precio_base"].clip(lower=1)) & base[
        "precio_base"
    ].notna()
    base = base[~((base["valor_total_adjudicacion"] > ABS_CAP) | rel)].copy()
    base["anio"] = base["fecha_de_publicacion_del"].dt.year

    out = []
    for anio in sorted(a for a in base["anio"].dropna().unique() if 2022 <= int(a) <= 2026):
        sub = base[base["anio"] == anio]
        m = sub.groupby("proveedor_id")["valor_total_adjudicacion"].sum().sort_values(ascending=False)
        if not len(m):
            continue
        top1_id = str(m.index[0])
        names = sub.loc[sub["proveedor_id"].astype(str) == top1_id, "proveedor_nombre"]
        nombre = str(names.mode().iloc[0])[:80] if len(names) else top1_id
        out.append({
            "anio": int(anio),
            "top1_nombre": nombre,
            "top1_valor_cop": float(m.iloc[0]),
            "top1_participacion_pct": round(float(m.iloc[0] / m.sum() * 100), 2),
        })
        print(anio, nombre, out[-1]["top1_participacion_pct"])
    return out


def patch(rot: list[dict]) -> None:
    by_year = {r["anio"]: r for r in rot}

    def walk(o: object) -> int:
        n = 0
        if isinstance(o, dict):
            if "rotacion_anual" in o and isinstance(o["rotacion_anual"], list):
                for row in o["rotacion_anual"]:
                    y = row.get("anio")
                    if y in by_year:
                        row["top1_nombre"] = by_year[y]["top1_nombre"]
                        row["top1_valor_cop"] = by_year[y]["top1_valor_cop"]
                        row["top1_participacion_pct"] = by_year[y]["top1_participacion_pct"]
                        n += 1
            for v in o.values():
                n += walk(v)
        elif isinstance(o, list):
            for v in o:
                n += walk(v)
        return n

    for path in FILES:
        data = json.loads(path.read_text(encoding="utf-8"))
        n = walk(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("patched", path.name, n)


if __name__ == "__main__":
    patch(compute_rotacion())
