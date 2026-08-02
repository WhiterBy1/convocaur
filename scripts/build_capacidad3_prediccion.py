"""Arma Cap.3 (predicción) para el dashboard a partir de bitácora + manifest + Cap.1."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BITACORA = ROOT / "analisis" / "secop" / "salidas_capacidad3" / "bitacora_hallazgos.csv"
MANIFEST = ROOT / "analisis" / "secop" / "salidas_capacidad3" / "modelos" / "manifest.json"
CAP1 = ROOT / "data" / "processed" / "secop" / "capacidad1_mensual.json"
OUT = ROOT / "data" / "processed" / "secop" / "capacidad3_prediccion.json"
DASH = ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json"

MES_ES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _row(df: pd.DataFrame, paso: str) -> dict:
    hit = df[df["paso"] == paso]
    if hit.empty:
        return {}
    return hit.iloc[0].to_dict()


def _outlook_mercado(horizonte: int = 6) -> dict:
    """Proyección estacional de volumen/valor a partir de Cap.1 (no es ML)."""
    if not CAP1.exists():
        return {}
    cap1 = json.loads(CAP1.read_text(encoding="utf-8"))
    serie = cap1.get("serie_mensual") or []
    if len(serie) < 12:
        return {}

    # Evitar meses incompletos al final: si el último mes tiene <40% del promedio del mismo mes, saltarlo
    by_month: dict[int, list[dict]] = {}
    for r in serie:
        by_month.setdefault(int(r["mes"]), []).append(r)

    last = serie[-1]
    last_mes = int(last["mes"])
    peers = [r for r in by_month.get(last_mes, []) if r["periodo"] != last["periodo"]]
    if peers:
        avg_n = sum(r["n_procesos"] for r in peers) / len(peers)
        if avg_n > 0 and last["n_procesos"] < 0.4 * avg_n:
            serie = serie[:-1]
            last = serie[-1]

    y0, m0 = int(last["anio"]), int(last["mes"])
    # ancla: promedio de los últimos 12 meses observados (nivel reciente)
    recent = serie[-12:]
    nivel_n = sum(r["n_procesos"] for r in recent) / len(recent)
    nivel_v = sum(r["valor_sin_mega_cop"] for r in recent) / len(recent)

    # estacionalidad relativa (factor mes / media anual) con valor sin megas
    factores_n: dict[int, float] = {}
    factores_v: dict[int, float] = {}
    for mes, rows in by_month.items():
        # excluir el último mes si quedó incompleto ya filtrado
        nn = [r["n_procesos"] for r in rows]
        vv = [r["valor_sin_mega_cop"] for r in rows]
        factores_n[mes] = (sum(nn) / len(nn)) if nn else 1.0
        factores_v[mes] = (sum(vv) / len(vv)) if vv else 1.0
    media_n = sum(factores_n.values()) / max(len(factores_n), 1)
    media_v = sum(factores_v.values()) / max(len(factores_v), 1)

    proy = []
    y, m = y0, m0
    for _ in range(horizonte):
        m += 1
        if m > 12:
            m = 1
            y += 1
        fn = (factores_n.get(m, media_n) / media_n) if media_n else 1.0
        fv = (factores_v.get(m, media_v) / media_v) if media_v else 1.0
        n_est = round(nivel_n * fn)
        v_est = nivel_v * fv
        # mismo mes año anterior (si existe) como referencia
        mismo = next((r for r in serie if int(r["anio"]) == y - 1 and int(r["mes"]) == m), None)
        proy.append(
            {
                "periodo": f"{y:04d}-{m:02d}",
                "etiqueta": f"{MES_ES[m]} {y}",
                "anio": y,
                "mes": m,
                "n_procesos_estimado": n_est,
                "valor_sin_mega_estimado_cop": v_est,
                "n_procesos_mismo_mes_anio_ant": mismo["n_procesos"] if mismo else None,
                "valor_sin_mega_mismo_mes_anio_ant_cop": (
                    mismo["valor_sin_mega_cop"] if mismo else None
                ),
            }
        )

    # últimos 6 meses observados para el gráfico (pasado + futuro)
    hist = [
        {
            "periodo": r["periodo"],
            "etiqueta": r.get("etiqueta") or r["periodo"],
            "n_procesos": r["n_procesos"],
            "valor_sin_mega_cop": r["valor_sin_mega_cop"],
            "tipo": "observado",
        }
        for r in serie[-6:]
    ]
    fut = [
        {
            "periodo": p["periodo"],
            "etiqueta": p["etiqueta"],
            "n_procesos": p["n_procesos_estimado"],
            "valor_sin_mega_cop": p["valor_sin_mega_estimado_cop"],
            "tipo": "proyeccion",
        }
        for p in proy
    ]

    pico = max(proy, key=lambda p: p["n_procesos_estimado"])
    valle = min(proy, key=lambda p: p["n_procesos_estimado"])

    return {
        "metodo": "estacionalidad + nivel reciente (últimos 12 meses)",
        "honestidad": (
            "No es un modelo de machine learning del mercado. "
            "Es una proyección razonable: ‘así suele moverse este mes’ × el ritmo reciente. "
            "Sirve para planear, no para cifrar contratos exactos."
        ),
        "ancla_hasta": last["periodo"],
        "horizonte_meses": horizonte,
        "serie_combinada": hist + fut,
        "proximos_meses": proy,
        "lectura": (
            f"En los próximos {horizonte} meses, el patrón histórico apunta a más actividad en "
            f"{pico['etiqueta']} (~{pico['n_procesos_estimado']} procesos) y menos en "
            f"{valle['etiqueta']} (~{valle['n_procesos_estimado']}). "
            "Valores en pesos constantes sin megacontratos (mejor proxy del mercado cotidiano)."
        ),
        "para_empresa": [
            "Decidir en qué meses reforzar vigilancia de SECOP y capacidad de propuesta.",
            "Anticipar picos de competencia (más procesos = más oportunidades y más rivales).",
            "Alinear cash-flow / equipos con meses históricamente más activos.",
        ],
    }


def main() -> None:
    df = pd.read_csv(BITACORA)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}

    univ = _row(df, "2.universo")
    cens = _row(df, "3.censura")
    adj = _row(df, "5.adj.competitivo_completo")
    solo = _row(df, "5.adj.solo_resueltos")
    presup = _row(df, "6.presupuesto")
    seg = _row(df, "7.segmento")

    auc = float(adj.get("auc_roc") or 0)
    auc_solo = float(solo.get("auc_roc") or 0)
    acc_pres = float(presup.get("acc_hgb") or 0)
    acc_pres_triv = float(presup.get("acc_trivial") or 0)
    acc_seg = float(seg.get("acc_hgb") or 0)
    acc_seg_triv = float(seg.get("acc_trivial") or 0)

    outlook = _outlook_mercado(6)

    payload = {
        "titulo": "Predicción: cómo se mueve el mercado (y un proceso concreto)",
        "subtitulo": (
            "Primero: panorama de los próximos meses con el histórico SECOP. "
            "Después (opcional): modelo por proceso — útil al evaluar una oportunidad puntual."
        ),
        "outlook_mercado": outlook,
        "para_empresa": {
            "titulo": "¿Para qué le sirve esto a una empresa o a Rosario?",
            "capas": [
                {
                    "id": "mercado",
                    "nombre": "Capa 1 — Mercado (lo que pediste)",
                    "pregunta": "¿Cómo se comportará la contratación CTeI en los próximos meses?",
                    "uso": (
                        "Planear: cuándo mirar SECOP, cuándo preparar equipos, "
                        "en qué meses hay más procesos (y competencia)."
                    ),
                    "como": "Proyección estacional sobre Cap.1 (nivel reciente × patrón del mes).",
                },
                {
                    "id": "proceso",
                    "nombre": "Capa 2 — Proceso (herramienta secundaria)",
                    "pregunta": "Si aparece / publicamos ESTE proceso, ¿qué dice el histórico de casos parecidos?",
                    "uso": (
                        "Bid/no-bid: priorizar follow-up de licitaciones competitivas "
                        "con mayor chance de adjudicación y filtrar por rango de presupuesto."
                    ),
                    "como": "Modelos ML entrenados en ~70k procesos competitivos (no predicen el mercado entero).",
                },
            ],
        },
        "kpis": {
            "auc_adjudicacion": round(auc, 3),
            "auc_pct": round(auc * 100, 1),
            "n_competitivos": int(univ.get("n") or 0),
            "tasa_adjudicacion": float(univ.get("tasa_adjudicacion") or 0),
            "fecha_corte": manifest.get("fecha_corte", "2025-07-01"),
            "modelo_recomendado": "LightGBM (solo modalidades competitivas)",
        },
        "universo": {
            "n_competitivos": int(univ.get("n") or 0),
            "tasa_adjudicacion": float(univ.get("tasa_adjudicacion") or 0),
            "n_resueltos": int(cens.get("n_resuelto") or 0),
            "n_abiertos": int(cens.get("n_abiertos") or 0),
            "lectura": (
                "Solo ~15% de los procesos CTeI son de modalidad competitiva. "
                "En contratación directa/especial casi nunca aparece “adjudicado” en los datos, "
                "así que el modelo útil se entrena solo en el universo competitivo."
            ),
        },
        "pregunta_adjudicacion": {
            "pregunta": "¿Se adjudicará este proceso competitivo?",
            "usar": True,
            "metrica_nombre": "Capacidad de distinguir sí/no",
            "metrica_valor": round(auc * 100, 1),
            "metrica_guia": "50% = azar · 80%+ = muy útil",
            "accuracy_pct": round(float(adj.get("accuracy") or 0) * 100, 1),
            "modelo": "LightGBM",
            "n_train": int(adj.get("n_train") or 0),
            "n_test": int(adj.get("n_test") or 0),
            "lectura": (
                f"El modelo acierta el orden de probabilidad con AUC {auc:.0%}: "
                "mejor que el azar y usable al momento de publicar el proceso "
                "(sin mirar el resultado futuro)."
            ),
        },
        "pregunta_adjudicacion_mala": {
            "pregunta": "¿Y si solo miramos procesos ya cerrados?",
            "usar": False,
            "metrica_valor": round(auc_solo * 100, 1),
            "modelo": "Regresión logística",
            "lectura": (
                f"AUC {auc_solo:.0%} — parece decente en aciertos brutos, pero engaña: "
                "no sirve para decidir en vivo. No usar este enfoque en producción."
            ),
        },
        "pregunta_presupuesto": {
            "pregunta": "¿En qué rango de presupuesto caerá el proceso?",
            "usar": True,
            "acc_modelo_pct": round(acc_pres * 100, 1),
            "acc_trivial_pct": round(acc_pres_triv * 100, 1),
            "f1_macro": round(float(presup.get("f1_macro") or 0), 3),
            "bins": ["Bajo (Q1)", "Medio-bajo (Q2)", "Medio-alto (Q3)", "Alto (Q4)"],
            "lectura": (
                f"El modelo acierta el rango ~{acc_pres:.0%} de las veces, frente a ~{acc_pres_triv:.0%} "
                "si siempre se elige la categoría más común. Útil como brújula de magnitud, no como cifra exacta."
            ),
        },
        "pregunta_segmento": {
            "pregunta": "¿Será educación, gestión o investigación/tecnología?",
            "usar": False,
            "acc_modelo_pct": round(acc_seg * 100, 1),
            "acc_trivial_pct": round(acc_seg_triv * 100, 1),
            "clases": [
                "Gestión / profesionales (80)",
                "Ingeniería / investigación (81)",
                "Educación / capacitación (86)",
            ],
            "lectura": (
                f"El modelo ({acc_seg:.0%}) apenas supera al atajo trivial ({acc_seg_triv:.0%}). "
                "Con tablas solas no alcanza: el siguiente paso es leer el objeto del contrato con lenguaje (embeddings)."
            ),
        },
        "comparativo": [
            {
                "id": "adj",
                "tarea": "¿Se adjudica? (competitivo)",
                "etiqueta_metrica": "Calidad del ranking (AUC)",
                "valor_pct": round(auc * 100, 1),
                "baseline_pct": 50.0,
                "baseline_nombre": "Azar",
                "usar": True,
            },
            {
                "id": "adj_malo",
                "tarea": "¿Se adjudica? (solo cerrados)",
                "etiqueta_metrica": "Calidad del ranking (AUC)",
                "valor_pct": round(auc_solo * 100, 1),
                "baseline_pct": 50.0,
                "baseline_nombre": "Azar",
                "usar": False,
            },
            {
                "id": "pres",
                "tarea": "Rango de presupuesto",
                "etiqueta_metrica": "% de aciertos",
                "valor_pct": round(acc_pres * 100, 1),
                "baseline_pct": round(acc_pres_triv * 100, 1),
                "baseline_nombre": "Siempre lo más común",
                "usar": True,
            },
            {
                "id": "seg",
                "tarea": "Tipo de sector",
                "etiqueta_metrica": "% de aciertos",
                "valor_pct": round(acc_seg * 100, 1),
                "baseline_pct": round(acc_seg_triv * 100, 1),
                "baseline_nombre": "Siempre lo más común",
                "usar": False,
            },
        ],
        "reglas_uso": [
            {
                "titulo": "Sí usar",
                "items": [
                    "Outlook de mercado (estacionalidad) para planear los próximos meses.",
                    "Probabilidad de adjudicación en modalidades competitivas al evaluar un proceso concreto.",
                    "Rango presupuestal como filtro de magnitud (no como cifra exacta).",
                ],
            },
            {
                "titulo": "No usar",
                "items": [
                    "El modelo por proceso como si fuera un forecast del mercado nacional.",
                    "Modelos entrenados solo con procesos ya resueltos para decidir en vivo.",
                    "Clasificar el sector solo con variables tabulares (casi no gana al atajo).",
                ],
            },
        ],
        "cierre_rosario": {
            "titulo": "Qué implica para la Universidad del Rosario",
            "puntos": [
                "Usar el outlook de meses para concentrar vigilancia SECOP cuando el mercado se anima.",
                "Ante un proceso competitivo concreto, el modelo ML ayuda a priorizar follow-up (chance de adjudicación + rango de monto).",
                "Para encajar facultades y grupos con el tema, el matching Minciencias ↔ docentes sigue siendo la pieza correcta.",
                "Cap.1–2 describen el pasado; Cap.3 proyecta ritmo cercano + triage de oportunidades; matching dice con quién presentarse.",
            ],
        },
        "nota_metodologica": (
            "Outlook de mercado: proyección estacional (nivel de los últimos 12 meses × factor típico del mes), "
            "valores sin megacontratos. "
            f"Modelos por proceso: corte {manifest.get('fecha_corte', '2025-07-01')} "
            "(entrenar pasado / probar futuro). "
            "AUC: calidad de ranking (0.5 = azar). "
            "Artefactos en analisis/secop/salidas_capacidad3/modelos/."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)

    if DASH.exists():
        dash = json.loads(DASH.read_text(encoding="utf-8"))
    else:
        dash = {}

    # Mantener claves legacy que Cap3Panel / overview puedan leer
    dash["capacidad_3"] = {
        **payload,
        "adjudicacion_competitivo": {
            "modelo": "LightGBM",
            "auc_roc": auc,
            "accuracy": float(adj.get("accuracy") or 0),
            "n_train": int(adj.get("n_train") or 0),
            "n_test": int(adj.get("n_test") or 0),
            "usar_en_produccion": True,
            "lectura": payload["pregunta_adjudicacion"]["lectura"],
        },
        "adjudicacion_solo_resueltos": {
            "modelo": "Logística",
            "auc_roc": auc_solo,
            "accuracy": float(solo.get("accuracy") or 0),
            "usar_en_produccion": False,
            "lectura": payload["pregunta_adjudicacion_mala"]["lectura"],
        },
        "presupuesto_bins": {
            "modelo": "HistGradientBoosting",
            "acc_trivial": acc_pres_triv,
            "acc_modelo": acc_pres,
            "f1_macro": float(presup.get("f1_macro") or 0),
            "bins_labels": ["Q1_bajo", "Q2", "Q3", "Q4_alto"],
        },
        "segmento_unspsc": {
            "modelo": "HistGradientBoosting",
            "acc_trivial": acc_seg_triv,
            "acc_modelo": acc_seg,
            "f1_macro": float(seg.get("f1_macro") or 0),
            "clases": ["80", "81", "86"],
            "lectura": payload["pregunta_segmento"]["lectura"],
        },
        "comparativo_modelos": [
            {
                "tarea": c["tarea"],
                "metrica": c["etiqueta_metrica"],
                "valor": c["valor_pct"] / 100.0,
                "baseline": c["baseline_pct"] / 100.0,
            }
            for c in payload["comparativo"]
        ],
    }
    if "meta" not in dash:
        dash["meta"] = {}
    dash["meta"]["fecha_corte_modelo"] = manifest.get("fecha_corte", "2025-07-01")

    DASH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated", DASH)
    print(f"AUC={auc:.3f} presup={acc_pres:.3f} vs {acc_pres_triv:.3f} seg={acc_seg:.3f} vs {acc_seg_triv:.3f}")


if __name__ == "__main__":
    main()
