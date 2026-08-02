"""Genera serie mensual Cap.1 en pesos reales (alineado a Capacidad1_cierre.ipynb)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "analisis" / "secop" / "secop_ctei_procesos_deflactado_sin_implausibles.csv"
OUT = ROOT / "data" / "processed" / "secop" / "capacidad1_mensual.json"
DASH = ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json"

SEGMENTOS = {
    "80": "Gestión y servicios profesionales",
    "81": "Ingeniería, investigación y tecnología",
    "86": "Educación y capacitación",
}
MES_NOM = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def main() -> None:
    print("Leyendo", CSV.name)
    df = pd.read_csv(CSV, low_memory=False)
    df["fecha_de_publicacion_del"] = pd.to_datetime(df["fecha_de_publicacion_del"], errors="coerce")
    df["valor_adjudicado_total_real"] = pd.to_numeric(df["valor_adjudicado_total_real"], errors="coerce")
    df["precio_base_real"] = pd.to_numeric(df.get("precio_base_real"), errors="coerce")
    df["n_proveedores_adjudicados"] = pd.to_numeric(df.get("n_proveedores_adjudicados"), errors="coerce")
    df["adjudicado_proceso"] = df.get("adjudicado_proceso")
    if df["adjudicado_proceso"].dtype == object:
        df["adjudicado_proceso"] = (
            df["adjudicado_proceso"].astype(str).str.lower().isin(["1", "true", "si", "sí", "yes"])
        )
    else:
        df["adjudicado_proceso"] = df["adjudicado_proceso"].fillna(False).astype(bool)

    # El CSV preferido ya excluye implausibles; si existe el flag, respetarlo.
    if "flag_valor_implausible" in df.columns:
        impl = df["flag_valor_implausible"]
        if impl.dtype == object:
            df["flag_valor_implausible"] = impl.astype(str).str.lower().isin(["1", "true", "si", "sí"])
        else:
            df["flag_valor_implausible"] = impl.fillna(False).astype(bool)
    else:
        df["flag_valor_implausible"] = False

    df_adj = df[df["adjudicado_proceso"] & ~df["flag_valor_implausible"]].copy()
    percentil_995 = df_adj["valor_adjudicado_total_real"].quantile(0.995)
    df["flag_fondo_administrado"] = (
        (~df["flag_valor_implausible"])
        & df["adjudicado_proceso"]
        & (df["valor_adjudicado_total_real"] > percentil_995)
        & (df["n_proveedores_adjudicados"] == 1)
    )

    df_base = df[df["fecha_de_publicacion_del"].notna() & ~df["flag_valor_implausible"]].copy()
    df_base = df_base[df_base["fecha_de_publicacion_del"] >= "2022-01-01"]
    df_base["periodo"] = df_base["fecha_de_publicacion_del"].dt.to_period("M").astype(str)

    n_fondos = int(df["flag_fondo_administrado"].sum())
    valor_total = float(df_base["valor_adjudicado_total_real"].fillna(0).sum())
    valor_fondos = float(
        df_base.loc[df_base["flag_fondo_administrado"], "valor_adjudicado_total_real"].fillna(0).sum()
    )
    pct_fondos = (valor_fondos / valor_total) if valor_total else 0.0

    rows = []
    for periodo, g in df_base.groupby("periodo"):
        v_all = float(g["valor_adjudicado_total_real"].fillna(0).sum())
        v_sin = float(g.loc[~g["flag_fondo_administrado"], "valor_adjudicado_total_real"].fillna(0).sum())
        rows.append({
            "periodo": str(periodo),
            "anio": int(str(periodo)[:4]),
            "mes": int(str(periodo)[5:7]),
            "etiqueta": f"{MES_NOM[int(str(periodo)[5:7])]} {str(periodo)[:4]}",
            "n_procesos": int(len(g)),
            "valor_total_cop": v_all,
            "valor_sin_mega_cop": v_sin,
        })
    serie = pd.DataFrame(rows).sort_values("periodo")

    # Mix de sectores (sobre procesos base)
    seg = df_base["segmento_unspsc"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    vc = seg.value_counts(normalize=True)
    mix = [
        {"codigo": c, "nombre": SEGMENTOS[c], "pct": float(vc.get(c, 0.0))}
        for c in ["81", "80", "86"]
    ]

    by_mes = (
        serie.groupby("mes")
        .agg(
            n_procesos_promedio=("n_procesos", "mean"),
            valor_promedio_cop=("valor_total_cop", "mean"),
        )
        .reset_index()
        .sort_values("mes")
    )
    estacional = [
        {
            "mes": int(r.mes),
            "nombre": MES_NOM[int(r.mes)],
            "n_procesos_promedio": round(float(r.n_procesos_promedio), 1),
            "valor_promedio_cop": float(r.valor_promedio_cop),
        }
        for r in by_mes.itertuples()
    ]

    mes_pico = max(estacional, key=lambda x: x["n_procesos_promedio"]) if estacional else None

    payload = {
        "meta": {
            "fuente_csv": CSV.name,
            "unidad_valor": "COP constantes (IPC DANE)",
            "valor_campo": "valor_adjudicado_total_real",
            "umbral_mega_cop": float(percentil_995),
            "desde": serie["periodo"].iloc[0] if len(serie) else None,
            "hasta": serie["periodo"].iloc[-1] if len(serie) else None,
            "n_procesos": int(len(df_base)),
            "valor_total_cop": valor_total,
            "n_megacontratos": n_fondos,
            "pct_valor_megacontratos": pct_fondos,
        },
        "serie_mensual": serie.to_dict(orient="records"),
        "estacionalidad_mensual": estacional,
        "unspsc_mix": mix,
        "cierre_rosario": {
            "titulo": "Qué implica para la Universidad del Rosario",
            "puntos": [
                f"Concentrar la vigilancia de SECOP en meses históricamente más activos"
                + (f" (p. ej. {mes_pico['nombre']})" if mes_pico else "")
                + ".",
                "Al leer el tamaño del mercado, preferir la serie sin megacontratos: refleja mejor las oportunidades cotidianas de I+D y servicios.",
                "Hay espacio claro en educación/capacitación e investigación/tecnología — alineado con facultades y centros de Rosario.",
                "Estas tendencias dicen cuándo mirar el mercado; el matching Minciencias responde con qué docentes postular.",
            ],
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print(
        f"meses={len(serie)} procesos={len(df_base)} fondos={n_fondos} pct={pct_fondos:.3f} umbral={percentil_995:,.0f}"
    )

    if DASH.exists():
        dash = json.loads(DASH.read_text(encoding="utf-8"))
    else:
        dash = {}

    dash["capacidad_1"] = {
        "titulo": "Tendencias: cómo se mueve la contratación CTeI",
        "subtitulo": "Mes a mes, en pesos constantes (ajustados por inflación)",
        "kpis": {
            "n_procesos": int(len(df_base)),
            "valor_total_cop": valor_total,
            "n_megacontratos": n_fondos,
            "pct_valor_megacontratos": pct_fondos,
            "desde": payload["meta"]["desde"],
            "hasta": payload["meta"]["hasta"],
        },
        "serie_mensual": payload["serie_mensual"],
        "estacionalidad_mensual": estacional,
        "unspsc_mix": mix,
        "fondos_administrados": {
            "n_procesos": n_fondos,
            "pct_valor": pct_fondos,
            "nota": (
                "Contratos excepcionalmente grandes (un solo proveedor, percentil 99.5). "
                "Distorsionan la lectura del mercado si no se miran aparte."
            ),
        },
        "estacionalidad": {
            "lectura": "Hay meses más activos, pero el patrón no se repite igual todos los años.",
            "mes_pico": mes_pico,
        },
        "cierre_rosario": payload["cierre_rosario"],
        "nota_metodologica": (
            "Valores en pesos constantes (IPC DANE). Universo UNSPSC 80/81/86 como proxy CTeI. "
            "Megacontratos: adjudicados con un proveedor por encima del percentil 99.5 del valor real."
        ),
    }
    DASH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated", DASH)


if __name__ == "__main__":
    main()
