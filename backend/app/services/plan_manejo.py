"""Plan de manejo: elegibles Minciencias + match docente + señal SECOP Cap.3."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from app.services.cap3_predict import ModelUnavailable, models_status, predict
from app.services.data import PROC, PROC_MATCHING, load_dashboard, matching_summary

PROC_NLP = PROC / "minciencias" / "nlp"
PROC_CSV = PROC / "minciencias" / "minciencias_convocatorias_processed.csv"

# Umbral de afinidad para considerar un docente “en el equipo potencial”
SCORE_EQUIPO_MIN = 0.65
TOP_DOCENTES = 8
TOP_PLANES = 8


def _load_fechas() -> dict[str, str]:
    out: dict[str, str] = {}
    if not PROC_CSV.exists():
        return out
    df = pd.read_csv(PROC_CSV, dtype=str)
    if "numero" not in df.columns:
        return out
    for _, row in df.iterrows():
        num = str(row.get("numero") or "").strip().replace(".0", "")
        fa = str(row.get("fecha_apertura") or "").strip()
        if num and fa and fa.lower() != "nan":
            out[num] = fa[:10]
    return out


def _es_reciente(fecha: str | None, anio_min: int = 2023) -> bool:
    if not fecha:
        return False
    try:
        return int(fecha[:4]) >= anio_min
    except ValueError:
        return False


def _load_nlp(key: str) -> dict[str, Any]:
    path = PROC_NLP / f"{key}_nlp.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _financiacion(nlp: dict[str, Any]) -> dict[str, Any]:
    fin = nlp.get("financiacion") or {}
    if not isinstance(fin, dict):
        return {}
    return fin


def _pick_from_list(items: list[str], *needles: str) -> str:
    low = [(m, m.lower()) for m in items]
    for needle in needles:
        n = needle.lower()
        for original, ml in low:
            if n in ml:
                return original
    return items[0] if items else ""


def _payload_secop_proxy(nlp: dict[str, Any], fecha_apertura: str | None) -> dict[str, Any]:
    """Arma el input del modelo Cap.3 con datos de la convocatoria Minciencias."""
    from app.services.cap3_predict import _departamentos_disponibles, _load_bundles, _modalidades_disponibles

    fin = _financiacion(nlp)
    monto = fin.get("monto_total_cop")
    try:
        precio = float(monto) if monto is not None else 500_000_000.0
    except (TypeError, ValueError):
        precio = 500_000_000.0
    if precio <= 0:
        precio = 500_000_000.0

    plazo = fin.get("plazo_max_meses") or fin.get("plazo_min_meses") or 18
    try:
        duracion = float(plazo)
    except (TypeError, ValueError):
        duracion = 18.0
    duracion = max(3.0, min(duracion, 60.0))

    mes, anio = 6, datetime.now().year
    if fecha_apertura and len(fecha_apertura) >= 7:
        try:
            anio = int(fecha_apertura[:4])
            mes = int(fecha_apertura[5:7])
        except ValueError:
            pass

    try:
        adj = _load_bundles()["adj"]
        mods = _modalidades_disponibles(adj)
        deps = _departamentos_disponibles(adj)
    except ModelUnavailable:
        mods, deps = [], []

    # Concurso de méritos ≈ dinámica competitiva de CTeI; fallback a licitación.
    modalidad = _pick_from_list(mods, "concurso", "mrito", "licit")
    departamento = _pick_from_list(deps, "bogot", "distrito")

    return {
        "precio_base_cop": precio,
        "duracion_meses": duracion,
        "numero_de_lotes": 1,
        "mes_publicacion": mes,
        "anio_publicacion": anio,
        "modalidad": modalidad,
        "departamento": departamento,
        "entidad": "MINCIENCIAS",
    }


def _load_ranking(key: str, top: int = TOP_DOCENTES) -> list[dict[str, Any]]:
    path = PROC_MATCHING / f"ranking_{key}.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    if "score_final" in df.columns:
        df = df.sort_values("score_final", ascending=False)
    df = df.head(top)
    rows = json.loads(df.to_json(orient="records", force_ascii=False))
    for i, r in enumerate(rows, start=1):
        r["rank"] = int(r.get("rank") or i)
        r["nombre"] = _nombre_limpio(r.get("nombre"), r.get("id"))
        r["rol"] = _rol_docente(r["rank"])
        for k in ("score_final", "score_raw", "score_emb", "score_tfidf", "boost"):
            if k in r and r[k] is not None:
                try:
                    r[k] = round(float(r[k]), 4)
                except (TypeError, ValueError):
                    pass
    return rows


def _nombre_limpio(nombre: str | None, fallback: str | None = None) -> str:
    from convocaur.matching.corpus import _nombre_persona

    return _nombre_persona(nombre, fallback)


def _rol_docente(rank: int, cat: str | None = None) -> str:
    del cat  # solo dos roles
    return "Investigador" if int(rank or 99) == 1 else "Co-investigador"


def _acciones_plan(
    *,
    alianza: bool | None,
    docentes: list[dict],
    lineas: list[str],
    p_adj: float | None,
) -> list[str]:
    acciones = [
        "Confirmar disponibilidad y conflicto de interés del equipo propuesto.",
        "Cruzar líneas temáticas de la convocatoria con áreas CvLAC de cada docente.",
    ]
    if docentes:
        ip = docentes[0].get("nombre") or docentes[0].get("id")
        acciones.insert(0, f"Contactar a {ip} como Investigador y validar disponibilidad.")
    if alianza is True:
        acciones.append(
            "La alianza es obligatoria: identificar coejecutor (IES/centro) y carta de intención."
        )
    elif alianza is False:
        acciones.append("Alianza no obligatoria: evaluar si un aliado fortalece elegibilidad o cobertura.")
    facs = {str(d.get("facultad") or "").strip() for d in docentes if d.get("facultad")}
    facs.discard("")
    if len(facs) >= 2:
        acciones.append(
            "Aprovechar cobertura multi-facultad del equipo para el componente interdisciplinar."
        )
    if lineas:
        acciones.append(
            "Redactar justificación de encaje con: " + "; ".join(lineas[:3]) + "."
        )
    if p_adj is not None and p_adj < 0.45:
        acciones.append(
            "Señal SECOP de adjudicación baja: revisar modalidad/presupuesto proxy y competencia histórica."
        )
    elif p_adj is not None and p_adj >= 0.55:
        acciones.append(
            "Señal SECOP favorable: priorizar esta convocatoria en el portafolio del semestre."
        )
    acciones.append("Actualizar evidencias CvLAC (proyectos, productos) antes del cierre.")
    return acciones


def _riesgos_plan(docentes: list[dict], alianza: bool | None, n_fuertes: int) -> list[str]:
    riesgos: list[str] = []
    if n_fuertes < 2:
        riesgos.append("Pocos docentes con afinidad alta: riesgo de cobertura temática insuficiente.")
    sin_cvlac = [d for d in docentes if not d.get("tiene_cvlac")]
    if sin_cvlac:
        riesgos.append("Hay perfiles sin CvLAC completo en el top: puede debilitar elegibilidad formal.")
    if alianza is True:
        riesgos.append("Dependencia de aliado externo: retrasos en cartas o NIT pueden tumbar la postulación.")
    cats = " ".join(str(d.get("categoria") or "") for d in docentes).lower()
    if "senior" not in cats and "asociado" not in cats and docentes:
        riesgos.append("Sin Senior/Asociado visible en el equipo: revisar requisitos de categoría Minciencias.")
    if not riesgos:
        riesgos.append("Riesgo residual: cambios de TdR o cupos; monitorear portal Minciencias.")
    return riesgos


def _prioridad(match_score: float | None, p_adj: float | None, puede: bool | None) -> float:
    m = float(match_score) if match_score is not None else 0.0
    p = float(p_adj) if p_adj is not None else 0.0
    eleg = 1.0 if puede is True else (0.35 if puede is None else 0.0)
    return round(0.45 * m + 0.40 * p + 0.15 * eleg, 4)


def _lineas_nombres(nlp: dict[str, Any]) -> list[str]:
    out = []
    for ln in nlp.get("lineas_tematicas") or []:
        if isinstance(ln, dict) and ln.get("nombre"):
            out.append(str(ln["nombre"]))
        elif isinstance(ln, str):
            out.append(ln)
    return out[:6]


def build_plan_manejo(*, top_planes: int = TOP_PLANES) -> dict[str, Any]:
    summary = matching_summary()
    fechas = _load_fechas()
    modelo = models_status()

    convocatorias_meta = summary.get("convocatorias") or []
    elegibles = [c for c in convocatorias_meta if c.get("puede_postularse") is True]
    recientes = [
        c for c in elegibles
        if _es_reciente(fechas.get(str(c.get("numero") or "")))
    ]
    # Preferir recientes; si hay pocas, usar todas las elegibles
    base = recientes if len(recientes) >= 3 else elegibles

    oportunidades: list[dict[str, Any]] = []
    for c in base:
        key = c["id"]
        nlp = _load_nlp(key)
        fecha = fechas.get(str(c.get("numero") or ""))
        docentes = _load_ranking(key) if c.get("tiene_ranking") else []
        fuertes = [d for d in docentes if float(d.get("score_final") or 0) >= SCORE_EQUIPO_MIN]
        if not fuertes and docentes:
            fuertes = docentes[:3]

        secop_proxy: dict[str, Any] | None = None
        p_adj = None
        if modelo.get("ok"):
            payload = _payload_secop_proxy(nlp, fecha)
            try:
                pred = predict(payload)
                adj = pred.get("adjudicacion") or {}
                p_adj = adj.get("probabilidad")
                secop_proxy = {
                    "probabilidad": p_adj,
                    "probabilidad_pct": adj.get("probabilidad_pct"),
                    "lectura": adj.get("lectura"),
                    "modelo": adj.get("modelo"),
                    "payload": payload,
                    "presupuesto_bin": (pred.get("presupuesto") or {}).get("nombre"),
                    "nota": (
                        "Señal del modelo SECOP CTeI (LightGBM) usando presupuesto, plazo y "
                        "calendario de la convocatoria Minciencias como proxy de proceso competitivo."
                    ),
                }
            except Exception as exc:
                secop_proxy = {"error": str(exc), "probabilidad": None}

        top1_score = c.get("top1_score")
        if top1_score is None and docentes:
            top1_score = docentes[0].get("score_final")
        try:
            top1_score_f = float(top1_score) if top1_score is not None else None
        except (TypeError, ValueError):
            top1_score_f = None

        prio = _prioridad(top1_score_f, p_adj, c.get("puede_postularse"))
        alianza = nlp.get("alianza_obligatoria")
        lineas = _lineas_nombres(nlp)

        equipo = []
        for d in fuertes[:6]:
            equipo.append({
                "id": d.get("id"),
                "nombre": _nombre_limpio(d.get("nombre"), d.get("id")),
                "facultad": d.get("facultad"),
                "categoria": d.get("categoria"),
                "score_final": d.get("score_final"),
                "rol": _rol_docente(int(d.get("rank") or 99), d.get("categoria")),
            })

        plan = None
        if equipo:
            plan = {
                "investigador_principal": equipo[0],
                "equipo": equipo,
                "acciones": _acciones_plan(
                    alianza=alianza if isinstance(alianza, bool) else None,
                    docentes=equipo,
                    lineas=lineas,
                    p_adj=p_adj,
                ),
                "riesgos": _riesgos_plan(equipo, alianza if isinstance(alianza, bool) else None, len(fuertes)),
                "lineas_tematicas": lineas,
                "alianza_obligatoria": alianza,
            }

        oportunidades.append({
            "id": key,
            "numero": c.get("numero"),
            "titulo": c.get("titulo") or f"Convocatoria {c.get('numero')}",
            "objetivo_preview": c.get("objetivo_preview"),
            "fecha_apertura": fecha,
            "reciente": _es_reciente(fecha),
            "puede_postularse": c.get("puede_postularse"),
            "modo_elegibilidad": c.get("modo_elegibilidad"),
            "tiene_ranking": c.get("tiene_ranking"),
            "match": {
                "top1_id": c.get("top1_id") or (equipo[0]["id"] if equipo else None),
                "top1_nombre": _nombre_limpio(
                    c.get("top1_nombre") or (equipo[0]["nombre"] if equipo else None),
                    c.get("top1_id"),
                ) if (c.get("top1_nombre") or equipo) else None,
                "top1_score": top1_score_f,
                "n_docentes_equipo": len(fuertes),
                "docentes": docentes[:5],
            },
            "secop_proxy": secop_proxy,
            "prioridad": prio,
            "plan_manejo": plan,
        })

    oportunidades.sort(key=lambda x: (-(x.get("prioridad") or 0), -(x.get("match", {}).get("top1_score") or 0)))

    # Planes detallados solo para las de mayor prioridad
    for i, op in enumerate(oportunidades):
        if i >= top_planes:
            op["plan_manejo"] = None
            op["en_plan"] = False
        else:
            op["en_plan"] = bool(op.get("plan_manejo"))

    mercado = {}
    dash = load_dashboard()
    if not dash.get("error"):
        u = dash.get("universo") or {}
        cap3 = dash.get("capacidad3") or dash.get("cap3") or {}
        mercado = {
            "n_procesos_cteI": u.get("n_procesos_total") or u.get("n"),
            "n_competitivos": u.get("n_competitivos"),
            "auc_adjudicacion": cap3.get("auc") or dash.get("cap3_auc"),
            "nota": "Contexto de mercado SECOP CTeI usado como referencia del modelo de adjudicación.",
        }

    n_con_match = sum(1 for o in oportunidades if o.get("tiene_ranking"))
    n_en_plan = sum(1 for o in oportunidades if o.get("en_plan"))

    return {
        "ok": True,
        "generado_en": datetime.now().isoformat(timespec="seconds"),
        "resumen": {
            "n_nlp": summary.get("n_nlp"),
            "n_elegibles": summary.get("n_elegibles"),
            "n_oportunidades": len(oportunidades),
            "n_con_ranking": n_con_match,
            "n_en_plan": n_en_plan,
            "n_recientes": len(recientes),
            "umbral_equipo": SCORE_EQUIPO_MIN,
            "formula_prioridad": "0.45*match + 0.40*P(adj SECOP proxy) + 0.15*elegibilidad",
        },
        "modelo_secop": modelo,
        "mercado_secop": mercado,
        "nota_metodologica": (
            "Se combinan tres capas ya construidas: (1) elegibilidad Rosario sobre NLP Minciencias, "
            "(2) ranking docente↔convocatoria, (3) probabilidad de adjudicación del modelo SECOP Cap.3 "
            "alimentado con presupuesto/plazo de cada convocatoria como proxy. "
            "La P(adj) no es un veredicto Minciencias; es una señal de factibilidad competitiva CTeI."
        ),
        "oportunidades": oportunidades,
        "planes": [o for o in oportunidades if o.get("en_plan")],
    }
