"""Forecast Cap.3 — modelos de series de tiempo del mercado CTeI.

Compara baseline estacional, Holt-Winters (ETS) y SARIMA con backtest.
Escribe outlook_mercado enriquecido en capacidad3_prediccion.json + resumen_dashboard.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "analisis" / "secop" / "secop_ctei_procesos_deflactado_sin_implausibles.csv"
CAP1 = ROOT / "data" / "processed" / "secop" / "capacidad1_mensual.json"
OUT_FORECAST = ROOT / "data" / "processed" / "secop" / "capacidad3_forecast_ts.json"
CAP3 = ROOT / "data" / "processed" / "secop" / "capacidad3_prediccion.json"
DASH = ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json"

MES_ES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
SEGMENTOS = {
    "80": "Gestión y servicios profesionales",
    "81": "Ingeniería, investigación y tecnología",
    "86": "Educación y capacitación",
}
HORIZONTE = 6
BACKTEST_H = 6


def _drop_incomplete(serie: pd.DataFrame, col: str = "n_procesos") -> pd.DataFrame:
    s = serie.sort_values("periodo").reset_index(drop=True)
    if len(s) < 14:
        return s
    last = s.iloc[-1]
    peers = s[(s["mes"] == last["mes"]) & (s["periodo"] != last["periodo"])]
    if peers.empty:
        return s
    avg = peers[col].mean()
    if avg > 0 and last[col] < 0.4 * avg:
        return s.iloc[:-1].reset_index(drop=True)
    return s


def _load_series() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Serie total (Cap.1) + series por segmento desde CSV si existe."""
    if not CAP1.exists():
        raise FileNotFoundError(CAP1)
    cap1 = json.loads(CAP1.read_text(encoding="utf-8"))
    total = pd.DataFrame(cap1["serie_mensual"]).sort_values("periodo").reset_index(drop=True)
    total = _drop_incomplete(total)

    by_seg = _load_segment_series(set(total["periodo"]))
    return total, by_seg


def _load_segment_series(periodos_ok: set[str]) -> dict[str, pd.DataFrame]:
    """Cuenta mensual por UNSPSC leyendo el CSV en chunks (evita OOM)."""
    by_seg: dict[str, pd.DataFrame] = {}
    if not CSV.exists():
        return by_seg

    # Detectar columnas reales
    header = pd.read_csv(CSV, nrows=0).columns.tolist()
    need = ["fecha_de_publicacion_del", "segmento_unspsc"]
    if any(c not in header for c in need):
        print("  aviso: CSV sin columnas de segmento; se omite desglose")
        return by_seg

    counts: dict[str, dict[str, int]] = {c: {} for c in SEGMENTOS}
    usecols = need[:]
    if "flag_valor_implausible" in header:
        usecols.append("flag_valor_implausible")

    for chunk in pd.read_csv(CSV, usecols=usecols, chunksize=80_000, low_memory=True):
        chunk["fecha_de_publicacion_del"] = pd.to_datetime(
            chunk["fecha_de_publicacion_del"], errors="coerce"
        )
        chunk = chunk[chunk["fecha_de_publicacion_del"].notna()]
        chunk = chunk[chunk["fecha_de_publicacion_del"] >= "2022-01-01"]
        if "flag_valor_implausible" in chunk.columns:
            impl = chunk["flag_valor_implausible"]
            if impl.dtype == object:
                mask_impl = impl.astype(str).str.lower().isin(["1", "true", "si", "sí"])
            else:
                mask_impl = impl.fillna(False).astype(bool)
            chunk = chunk[~mask_impl]
        chunk["periodo"] = chunk["fecha_de_publicacion_del"].dt.to_period("M").astype(str)
        seg = (
            chunk["segmento_unspsc"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )
        for code in SEGMENTOS:
            sub = chunk.loc[seg == code, "periodo"]
            if sub.empty:
                continue
            vc = sub.value_counts()
            for periodo, n in vc.items():
                counts[code][str(periodo)] = counts[code].get(str(periodo), 0) + int(n)

    for code, cmap in counts.items():
        rows = []
        for periodo, n in sorted(cmap.items()):
            if periodo not in periodos_ok:
                continue
            rows.append({
                "periodo": periodo,
                "anio": int(periodo[:4]),
                "mes": int(periodo[5:7]),
                "n_procesos": n,
                "valor_sin_mega_cop": float(n),  # placeholder; forecast usa n_procesos
            })
        if rows:
            sdf = pd.DataFrame(rows).sort_values("periodo").reset_index(drop=True)
            by_seg[code] = _drop_incomplete(sdf)
    return by_seg


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true > 0
    if not mask.any():
        return float("inf")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def _seasonal_forecast(y: np.ndarray, h: int, season: int = 12) -> np.ndarray:
    """Seasonal naïve: y_{t+h} = y_{t+h-s}."""
    out = []
    hist = list(y.astype(float))
    for _ in range(h):
        val = hist[-season] if len(hist) >= season else hist[-1]
        out.append(val)
        hist.append(val)
    return np.array(out)


def _seasonal_level_forecast(y: np.ndarray, h: int, season: int = 12) -> np.ndarray:
    """Nivel reciente (12m) × factor estacional relativo."""
    if len(y) < season:
        return _seasonal_forecast(y, h, season)
    nivel = float(np.mean(y[-season:]))
    factors = []
    for m in range(season):
        vals = y[m::season]
        factors.append(float(np.mean(vals)) if len(vals) else nivel)
    media_f = float(np.mean(factors)) or 1.0
    # último mes del índice = len(y)-1; siguiente es mes (len(y) % season)
    start = len(y) % season
    out = []
    for i in range(h):
        idx = (start + i) % season
        out.append(nivel * (factors[idx] / media_f))
    return np.array(out)


def _ets_forecast(y: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except ImportError:
        return None
    if len(y) < 24:
        return None
    try:
        # log1p estabiliza picos (p. ej. enero)
        y_log = np.log1p(np.maximum(y, 0))
        model = ExponentialSmoothing(
            y_log,
            trend="add",
            seasonal="add",
            seasonal_periods=12,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True, use_brute=True)
        pred_log = np.asarray(fit.forecast(h), dtype=float)
        pred = np.expm1(pred_log)
        resid = np.asarray(y_log - fit.fittedvalues, dtype=float)
        resid = resid[np.isfinite(resid)]
        sigma = float(np.std(resid)) if len(resid) else 0.2
        lo = np.expm1(pred_log - 1.64 * sigma * np.sqrt(1 + np.arange(1, h + 1) / 12))
        hi = np.expm1(pred_log + 1.64 * sigma * np.sqrt(1 + np.arange(1, h + 1) / 12))
        return np.maximum(pred, 0), np.maximum(lo, 0), np.maximum(hi, 0)
    except Exception:
        return None


def _sarima_forecast(y: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
    except ImportError:
        return None
    if len(y) < 30:
        return None
    y_log = np.log1p(np.maximum(y, 0))
    candidates = [
        ((1, 0, 1), (0, 1, 1, 12)),
        ((0, 1, 1), (0, 1, 1, 12)),
        ((1, 1, 0), (0, 1, 1, 12)),
        ((1, 0, 0), (1, 1, 0, 12)),
    ]
    best = None
    best_aic = float("inf")
    for order, seasonal in candidates:
        try:
            fit = SARIMAX(
                y_log,
                order=order,
                seasonal_order=seasonal,
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit(disp=False, maxiter=200)
            if np.isfinite(fit.aic) and fit.aic < best_aic:
                best_aic = float(fit.aic)
                best = fit
        except Exception:
            continue
    if best is None:
        return None
    try:
        fc = best.get_forecast(h)
        pred_log = np.asarray(fc.predicted_mean, dtype=float)
        ci = fc.conf_int(alpha=0.2)
        lo_log = np.asarray(ci.iloc[:, 0], dtype=float)
        hi_log = np.asarray(ci.iloc[:, 1], dtype=float)
        return (
            np.maximum(np.expm1(pred_log), 0),
            np.maximum(np.expm1(lo_log), 0),
            np.maximum(np.expm1(hi_log), 0),
        )
    except Exception:
        return None


def _seasonal_median_forecast(y: np.ndarray, h: int, season: int = 12) -> np.ndarray:
    """Mediana del mismo mes (robusto a picos como ene-2026)."""
    out = []
    n = len(y)
    for i in range(h):
        idx = (n + i) % season
        vals = y[idx::season]
        out.append(float(np.median(vals)) if len(vals) else float(y[-1]))
    return np.array(out)


def _seasonal_anclado_forecast(y: np.ndarray, h: int, season: int = 12) -> np.ndarray:
    """Patrón estacional relativo anclado al ÚLTIMO valor (evita saltos en el empalme)."""
    last = float(y[-1])
    if last <= 0:
        return _seasonal_level_forecast(y, h, season)
    factors = []
    for m in range(season):
        vals = y[m::season]
        factors.append(float(np.mean(vals)) if len(vals) else last)
    last_idx = (len(y) - 1) % season
    f_last = factors[last_idx] or 1.0
    start = len(y) % season
    out = []
    for i in range(h):
        idx = (start + i) % season
        out.append(last * (factors[idx] / f_last))
    return np.array(out)


def _backtest(y: np.ndarray, h: int = BACKTEST_H) -> list[dict[str, Any]]:
    """Backtest multi-origen (últimas 3 ventanas) → ranking más estable."""
    origins = []
    end = len(y)
    for k in range(3):
        train_end = end - h * (k + 1)
        if train_end < 24:
            break
        origins.append(train_end)
    if not origins:
        train_end = len(y) - h
        if train_end < 18:
            return []
        origins = [train_end]

    models = [
        ("estacional_naive", lambda yt, hh: (_seasonal_forecast(yt, hh), None, None)),
        ("estacional_nivel", lambda yt, hh: (_seasonal_level_forecast(yt, hh), None, None)),
        ("estacional_anclado", lambda yt, hh: (_seasonal_anclado_forecast(yt, hh), None, None)),
        ("estacional_mediana", lambda yt, hh: (_seasonal_median_forecast(yt, hh), None, None)),
        ("holt_winters", lambda yt, hh: _ets_forecast(yt, hh) or (None, None, None)),
        ("sarima", lambda yt, hh: _sarima_forecast(yt, hh) or (None, None, None)),
    ]
    acc: dict[str, list[tuple[float, float]]] = {n: [] for n, _ in models}

    for train_end in origins:
        y_train, y_test = y[:train_end], y[train_end : train_end + h]
        for name, fn in models:
            out = fn(y_train, len(y_test))
            if out[0] is None:
                continue
            pred = out[0]
            acc[name].append((_mape(y_test, pred), _rmse(y_test, pred)))

    results = []
    for name, _ in models:
        if not acc[name]:
            continue
        mapes = [a[0] for a in acc[name]]
        rmses = [a[1] for a in acc[name]]
        results.append({
            "modelo": name,
            "mape_pct": round(float(np.mean(mapes)), 2),
            "mape_mediana_pct": round(float(np.median(mapes)), 2),
            "rmse": round(float(np.mean(rmses)), 1),
            "n_ventanas": len(acc[name]),
            "n_test_por_ventana": h,
        })
    results.sort(key=lambda r: (r["mape_mediana_pct"], r["mape_pct"], r["rmse"]))
    return results


def _bands_from_resid(y: np.ndarray, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # sigma robusto: mediana de |y_t - y_{t-12}|
    if len(y) >= 24:
        diffs = np.abs(y[12:] - y[:-12])
        sigma = float(np.median(diffs))
    else:
        sigma = float(np.std(y[-12:])) if len(y) >= 12 else float(np.std(y))
    scale = np.sqrt(1 + np.arange(1, len(pred) + 1) / 12)
    lo = np.maximum(pred - 1.64 * sigma * scale, 0)
    hi = pred + 1.64 * sigma * scale
    return lo, hi


def _predict_named(name: str, y: np.ndarray, h: int):
    if name == "holt_winters":
        return _ets_forecast(y, h)
    if name == "sarima":
        return _sarima_forecast(y, h)
    if name == "estacional_mediana":
        pred = _seasonal_median_forecast(y, h)
        lo, hi = _bands_from_resid(y, pred)
        return pred, lo, hi
    if name == "estacional_nivel":
        pred = _seasonal_level_forecast(y, h)
        lo, hi = _bands_from_resid(y, pred)
        return pred, lo, hi
    if name == "estacional_anclado":
        pred = _seasonal_anclado_forecast(y, h)
        lo, hi = _bands_from_resid(y, pred)
        return pred, lo, hi
    if name == "estacional_naive":
        pred = _seasonal_forecast(y, h)
        lo, hi = _bands_from_resid(y, pred)
        return pred, lo, hi
    return None


def _jump_ratio(y: np.ndarray, pred: np.ndarray) -> float:
    last = float(y[-1])
    if last <= 0:
        return 0.0
    return abs(float(pred[0]) - last) / last


def _fit_best(
    y: np.ndarray,
    h: int,
    ranking: list[dict[str, Any]],
    *,
    prefer_continuity: bool = False,
) -> tuple[str, np.ndarray, np.ndarray, np.ndarray]:
    order = [r["modelo"] for r in ranking] if ranking else []
    fallback = [
        "estacional_nivel",
        "estacional_mediana",
        "holt_winters",
        "sarima",
        "estacional_naive",
        "estacional_anclado",
    ]
    # Valor: evitar el salto del naïve al mismo mes del año pasado, PERO no
    # anclar al último mes si ese punto es atípico (arrastra toda la curva).
    if prefer_continuity:
        last = float(y[-1])
        nivel_12 = float(np.mean(y[-12:])) if len(y) >= 12 else float(np.mean(y))
        last_is_outlier = bool(nivel_12 > 0 and (last < 0.55 * nivel_12 or last > 1.8 * nivel_12))

        # Nunca naïve aquí: copia el año pasado y genera saltos absurdos tras un mes flojo.
        # Anclado solo si el último mes es “normal” y su MAPE no es malo.
        ban = {"estacional_naive"}
        if last_is_outlier:
            ban.add("estacional_anclado")

        order_pref = [m for m in order if m not in ban]
        # priorizar nivel / mediana / ets antes que anclado
        prefer_first = [
            m
            for m in (
                "estacional_nivel",
                "estacional_mediana",
                "holt_winters",
                "sarima",
                "estacional_anclado",
            )
            if m in order_pref
        ]
        order_pref = prefer_first + [m for m in order_pref if m not in prefer_first]

        candidates: list[tuple[str, np.ndarray, np.ndarray, np.ndarray, float, float]] = []
        mape_by = {
            r["modelo"]: float(r.get("mape_mediana_pct") or r["mape_pct"]) for r in ranking
        }
        for name in order_pref + [m for m in fallback if m not in ban]:
            if any(c[0] == name for c in candidates):
                continue
            out = _predict_named(name, y, h)
            if not out:
                continue
            pred, lo, hi = out
            jr = _jump_ratio(y, pred)
            mape = mape_by.get(name, 999.0)
            if name == "estacional_anclado" and mape_by:
                best_m = min(mape_by.values())
                if mape > best_m * 1.25:
                    continue
            candidates.append((name, pred, lo, hi, jr, mape))
        if not candidates:
            out = _predict_named("estacional_nivel", y, h)
            if out:
                return "estacional_nivel", out[0], out[1], out[2]
        else:
            best_mape = min(c[5] for c in candidates)
            # Empalme razonable; si nadie cumple, quedarse con el de menor salto
            ok = [c for c in candidates if c[4] <= 1.0 and c[5] <= best_mape * 1.5]
            pool = ok or sorted(candidates, key=lambda c: (c[4], c[5]))[:2]
            # MAPE primero entre empalmes ok; si el salto es enorme, penalizar
            pool.sort(key=lambda c: (c[5] + (0 if c[4] <= 1.0 else 40), c[4]))
            name, pred, lo, hi, _, _ = pool[0]
            return name, pred, lo, hi

    for name in order + fallback:
        out = _predict_named(name, y, h)
        if out:
            return name, out[0], out[1], out[2]
    pred = _seasonal_nivel_forecast(y, h)
    lo, hi = _bands_from_resid(y, pred)
    return "estacional_nivel", pred, lo, hi


def _future_periods(last_periodo: str, h: int) -> list[dict[str, Any]]:
    y, m = int(last_periodo[:4]), int(last_periodo[5:7])
    out = []
    for _ in range(h):
        m += 1
        if m > 12:
            m = 1
            y += 1
        out.append({
            "periodo": f"{y:04d}-{m:02d}",
            "etiqueta": f"{MES_ES[m]} {y}",
            "anio": y,
            "mes": m,
        })
    return out


def _forecast_metric(
    df: pd.DataFrame, col: str, label: str, *, prefer_continuity: bool = False
) -> dict[str, Any]:
    y = df[col].astype(float).to_numpy()
    ranking = _backtest(y)
    modelo, pred, lo, hi = _fit_best(
        y, HORIZONTE, ranking, prefer_continuity=prefer_continuity
    )
    futuros = _future_periods(str(df.iloc[-1]["periodo"]), HORIZONTE)

    proximos = []
    for i, meta in enumerate(futuros):
        proximos.append({
            **meta,
            "punto": float(pred[i]),
            "lo_80": float(lo[i]),
            "hi_80": float(hi[i]),
        })

    hist_tail = df.tail(12)
    serie = []
    for _, r in hist_tail.iterrows():
        serie.append({
            "periodo": r["periodo"],
            "etiqueta": f"{MES_ES[int(r['mes'])]} {int(r['anio'])}",
            "tipo": "observado",
            "valor": float(r[col]),
            "lo_80": None,
            "hi_80": None,
        })
    for p in proximos:
        serie.append({
            "periodo": p["periodo"],
            "etiqueta": p["etiqueta"],
            "tipo": "proyeccion",
            "valor": p["punto"],
            "lo_80": p["lo_80"],
            "hi_80": p["hi_80"],
        })

    best = ranking[0] if ranking else {"modelo": modelo, "mape_pct": None, "rmse": None}
    pico = max(proximos, key=lambda x: x["punto"])
    valle = min(proximos, key=lambda x: x["punto"])
    total_h = float(sum(p["punto"] for p in proximos))

    return {
        "metric_id": col,
        "nombre": label,
        "unidad": "procesos" if "n_" in col else "COP constantes",
        "modelo_elegido": modelo,
        "backtest": ranking,
        "mejor_backtest": best,
        "ancla_hasta": str(df.iloc[-1]["periodo"]),
        "horizonte_meses": HORIZONTE,
        "serie": serie,
        "proximos_meses": proximos,
        "resumen": {
            "total_horizonte": total_h,
            "mes_pico": {"etiqueta": pico["etiqueta"], "valor": pico["punto"]},
            "mes_valle": {"etiqueta": valle["etiqueta"], "valor": valle["punto"]},
            "promedio_mensual": total_h / HORIZONTE,
        },
    }


def _segment_panel(
    total: pd.DataFrame, by_seg: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Panel periodo × total + conteos por segmento (suma = total)."""
    m = total[["periodo", "anio", "mes", "n_procesos"]].rename(
        columns={"n_procesos": "total"}
    )
    for code, sdf in by_seg.items():
        m = m.merge(
            sdf[["periodo", "n_procesos"]].rename(columns={"n_procesos": code}),
            on="periodo",
            how="inner",
        )
    return m.sort_values("periodo").reset_index(drop=True)


def _share_matrix(panel: pd.DataFrame, codes: list[str]) -> np.ndarray:
    tot = panel["total"].to_numpy(dtype=float)
    tot = np.where(tot > 0, tot, np.nan)
    shares = np.column_stack([panel[c].to_numpy(dtype=float) / tot for c in codes])
    # filas inválidas → uniforme
    bad = ~np.isfinite(shares).all(axis=1)
    if bad.any():
        shares[bad] = 1.0 / len(codes)
    # renormalizar
    shares = shares / shares.sum(axis=1, keepdims=True)
    return shares


def _forecast_shares(
    panel: pd.DataFrame, codes: list[str], h: int, method: str = "estacional_blend"
) -> np.ndarray:
    """Proyecta participaciones (h × n_seg) que suman 1 por fila."""
    shares = _share_matrix(panel, codes)
    meses = panel["mes"].to_numpy(dtype=int)
    n = len(panel)
    # promedio por mes calendario
    seasonal = np.zeros((12, len(codes)))
    for m in range(1, 13):
        mask = meses == m
        if mask.any():
            seasonal[m - 1] = np.median(shares[mask], axis=0)
        else:
            seasonal[m - 1] = shares[-12:].mean(axis=0) if n >= 12 else shares.mean(axis=0)
        s = seasonal[m - 1].sum()
        if s > 0:
            seasonal[m - 1] /= s

    recent = shares[-12:].mean(axis=0) if n >= 12 else shares.mean(axis=0)
    recent = recent / recent.sum()

    last_m = int(meses[-1])
    out = []
    for i in range(h):
        nm = last_m + i + 1
        while nm > 12:
            nm -= 12
        seas = seasonal[nm - 1]
        if method == "estacional_mes":
            row = seas
        elif method == "reciente_12m":
            row = recent
        else:  # blend: 70% estacional del mes + 30% mix reciente
            row = 0.7 * seas + 0.3 * recent
            row = row / row.sum()
        out.append(row)
    return np.asarray(out, dtype=float)


def _backtest_segment_approaches(
    total: pd.DataFrame, by_seg: dict[str, pd.DataFrame], h: int = BACKTEST_H
) -> dict[str, Any]:
    """Compara forecast independiente vs top-down (total × shares)."""
    codes = [c for c in SEGMENTOS if c in by_seg]
    panel = _segment_panel(total, {c: by_seg[c] for c in codes})
    y_total = panel["total"].to_numpy(dtype=float)

    origins = []
    end = len(panel)
    for k in range(3):
        train_end = end - h * (k + 1)
        if train_end < 24:
            break
        origins.append(train_end)
    if not origins:
        return {"metodos": [], "por_segmento": {}}

    methods = ["topdown_blend", "topdown_estacional", "topdown_reciente", "independiente"]
    err: dict[str, dict[str, list[float]]] = {
        m: {c: [] for c in codes} for m in methods
    }

    for train_end in origins:
        train_panel = panel.iloc[:train_end].copy()
        test_panel = panel.iloc[train_end : train_end + h]
        y_tr = y_total[:train_end]
        # Total: estacional naïve (rápido y suele ganar en esta serie; evita SARIMA anidado)
        pred_tot = _seasonal_forecast(y_tr, len(test_panel))

        share_specs = {
            "topdown_blend": "estacional_blend",
            "topdown_estacional": "estacional_mes",
            "topdown_reciente": "reciente_12m",
        }
        for mname, smethod in share_specs.items():
            sh = _forecast_shares(train_panel, codes, len(test_panel), smethod)
            for j, code in enumerate(codes):
                pred = pred_tot * sh[:, j]
                actual = test_panel[code].to_numpy(dtype=float)
                err[mname][code].append(_mape(actual, pred))

        # independiente: mediana estacional del segmento (baseline honesto, sin nested HW)
        for code in codes:
            y_seg = train_panel[code].to_numpy(dtype=float)
            pred_s = _seasonal_median_forecast(y_seg, len(test_panel))
            actual = test_panel[code].to_numpy(dtype=float)
            err["independiente"][code].append(_mape(actual, pred_s))

    metodos = []
    por_seg: dict[str, list[dict[str, Any]]] = {c: [] for c in codes}
    for mname in methods:
        mapes_all = []
        for code in codes:
            vals = err[mname][code]
            if not vals:
                continue
            med = float(np.median(vals))
            mean = float(np.mean(vals))
            mapes_all.append(med)
            por_seg[code].append({
                "modelo": mname,
                "mape_mediana_pct": round(med, 2),
                "mape_pct": round(mean, 2),
            })
        if mapes_all:
            metodos.append({
                "modelo": mname,
                "mape_mediana_pct": round(float(np.mean(mapes_all)), 2),
                "mape_pct": round(float(np.mean([
                    np.mean(err[mname][c]) for c in codes if err[mname][c]
                ])), 2),
            })
    metodos.sort(key=lambda r: r["mape_mediana_pct"])
    for code in codes:
        por_seg[code].sort(key=lambda r: r["mape_mediana_pct"])
    return {"metodos": metodos, "por_segmento": por_seg, "codes": codes, "panel": panel}


def _forecast_segments_topdown(
    total: pd.DataFrame,
    by_seg: dict[str, pd.DataFrame],
    n_fc: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bt = _backtest_segment_approaches(total, by_seg)
    codes = bt.get("codes") or [c for c in SEGMENTOS if c in by_seg]
    panel = bt.get("panel")
    if panel is None:
        panel = _segment_panel(total, {c: by_seg[c] for c in codes})

    best_method = (bt["metodos"][0]["modelo"] if bt["metodos"] else "topdown_blend")
    share_method = {
        "topdown_blend": "estacional_blend",
        "topdown_estacional": "estacional_mes",
        "topdown_reciente": "reciente_12m",
        "independiente": "estacional_blend",  # fallback si gana indep usamos topdown igual? 
    }.get(best_method, "estacional_blend")

    # Si independiente gana el promedio, aún preferimos top-down blend salvo que
    # mejore >10% en mediana global (independiente suele overfittear ruido).
    if best_method == "independiente":
        # usar el mejor top-down disponible
        top = next((m for m in bt["metodos"] if m["modelo"].startswith("topdown")), None)
        indep = bt["metodos"][0]
        if top and indep["mape_mediana_pct"] < top["mape_mediana_pct"] * 0.9:
            # independiente claramente mejor → forecast por serie
            return _forecast_segments_independent(by_seg, bt), bt
        best_method = top["modelo"] if top else "topdown_blend"
        share_method = {
            "topdown_blend": "estacional_blend",
            "topdown_estacional": "estacional_mes",
            "topdown_reciente": "reciente_12m",
        }.get(best_method, "estacional_blend")

    pred_tot = np.array([p["punto"] for p in n_fc["proximos_meses"]], dtype=float)
    lo_tot = np.array([p["lo_80"] for p in n_fc["proximos_meses"]], dtype=float)
    hi_tot = np.array([p["hi_80"] for p in n_fc["proximos_meses"]], dtype=float)
    sh = _forecast_shares(panel, codes, HORIZONTE, share_method)
    futuros = _future_periods(str(panel.iloc[-1]["periodo"]), HORIZONTE)

    nombres_metodo = {
        "topdown_blend": "Top-down: total × (70% share estacional + 30% reciente)",
        "topdown_estacional": "Top-down: total × share del mes",
        "topdown_reciente": "Top-down: total × share 12m",
        "independiente": "Serie independiente por segmento",
    }

    segmentos = []
    for j, code in enumerate(codes):
        pred = pred_tot * sh[:, j]
        lo = lo_tot * sh[:, j]
        hi = hi_tot * sh[:, j]
        proximos = [{**futuros[i], "punto": float(pred[i]), "lo_80": float(lo[i]), "hi_80": float(hi[i]), "share": float(sh[i, j])} for i in range(HORIZONTE)]
        # serie hist + proy
        hist = by_seg[code].tail(12)
        serie = []
        for _, r in hist.iterrows():
            serie.append({
                "periodo": r["periodo"],
                "etiqueta": f"{MES_ES[int(r['mes'])]} {int(r['anio'])}",
                "tipo": "observado",
                "valor": float(r["n_procesos"]),
                "lo_80": None,
                "hi_80": None,
            })
        for p in proximos:
            serie.append({
                "periodo": p["periodo"],
                "etiqueta": p["etiqueta"],
                "tipo": "proyeccion",
                "valor": p["punto"],
                "lo_80": p["lo_80"],
                "hi_80": p["hi_80"],
            })
        seg_rank = bt["por_segmento"].get(code) or []
        best_seg = seg_rank[0] if seg_rank else {}
        # métrica del método elegido (no del independiente)
        met_row = next((r for r in seg_rank if r["modelo"] == best_method), best_seg)
        pico = max(proximos, key=lambda x: x["punto"])
        segmentos.append({
            "codigo": code,
            "nombre": SEGMENTOS[code],
            "modelo_elegido": best_method,
            "modelo_nombre": nombres_metodo.get(best_method, best_method),
            "mape_backtest_pct": met_row.get("mape_mediana_pct", met_row.get("mape_pct")),
            "mape_media_pct": met_row.get("mape_pct"),
            "comparativo_local": seg_rank,
            "share_proximos": [float(sh[i, j]) for i in range(HORIZONTE)],
            "proximos_meses": proximos,
            "serie": serie,
            "total_horizonte": float(pred.sum()),
            "mes_pico": {"etiqueta": pico["etiqueta"], "valor": pico["punto"]},
        })

    bt_out = {
        "metodo_elegido": best_method,
        "metodo_nombre": nombres_metodo.get(best_method, best_method),
        "lectura": (
            "Los segmentos son ruidosos en nivel absoluto; las participaciones son estables. "
            "Por eso se proyecta el total y se reparte con shares (top-down), en lugar de "
            "entrenar un SARIMA/estacional aparte por UNSPSC."
        ),
        "comparativo_metodos": bt["metodos"],
        "por_segmento": bt["por_segmento"],
    }
    return segmentos, bt_out


def _forecast_segments_independent(
    by_seg: dict[str, pd.DataFrame], bt: dict[str, Any]
) -> list[dict[str, Any]]:
    segmentos = []
    for code, nombre in SEGMENTOS.items():
        if code not in by_seg:
            continue
        fc = _forecast_metric(by_seg[code], "n_procesos", nombre)
        seg_rank = (bt.get("por_segmento") or {}).get(code) or []
        segmentos.append({
            "codigo": code,
            "nombre": nombre,
            "modelo_elegido": "independiente",
            "modelo_nombre": f"Independiente ({fc['modelo_elegido']})",
            "mape_backtest_pct": (seg_rank[0] if seg_rank else fc["mejor_backtest"]).get(
                "mape_mediana_pct",
                fc["mejor_backtest"].get("mape_pct"),
            ),
            "comparativo_local": seg_rank,
            "proximos_meses": fc["proximos_meses"],
            "serie": fc["serie"],
            "total_horizonte": fc["resumen"]["total_horizonte"],
            "mes_pico": fc["resumen"]["mes_pico"],
        })
    return segmentos


def build_outlook(total: pd.DataFrame, by_seg: dict[str, pd.DataFrame]) -> dict[str, Any]:
    n_fc = _forecast_metric(total, "n_procesos", "Cantidad de procesos CTeI")
    # Valor: anclar al nivel reciente para no saltar al agosto del año pasado
    v_fc = _forecast_metric(
        total, "valor_sin_mega_cop", "Valor sin megacontratos", prefer_continuity=True
    )

    segmentos, seg_meta = _forecast_segments_topdown(total, by_seg, n_fc)

    # ranking de modelos en n_procesos
    ranking = n_fc["backtest"]
    winner = n_fc["modelo_elegido"]
    mape_w = next((r["mape_pct"] for r in ranking if r["modelo"] == winner), None)
    mape_base = next(
        (r.get("mape_mediana_pct") or r["mape_pct"] for r in ranking if r["modelo"] == "estacional_nivel"),
        None,
    )
    mape_w_rank = next(
        (r.get("mape_mediana_pct") or r["mape_pct"] for r in ranking if r["modelo"] == winner),
        mape_w,
    )
    mejora = None
    if mape_w_rank is not None and mape_base is not None and mape_base > 0:
        mejora = round((1 - mape_w_rank / mape_base) * 100, 1)

    nombres = {
        "holt_winters": "Holt-Winters log (ETS estacional)",
        "sarima": "SARIMA log-estacional",
        "estacional_nivel": "Estacional × nivel reciente",
        "estacional_naive": "Estacional naïve",
        "estacional_mediana": "Estacional mediana (robusto a picos)",
        "estacional_anclado": "Estacional anclado al último mes",
    }

    mape_med = next(
        (r.get("mape_mediana_pct") for r in ranking if r["modelo"] == winner), None
    )
    lectura = (
        f"Modelo elegido para volumen: {nombres.get(winner, winner)}. "
        f"Backtest en {ranking[0].get('n_ventanas', 1) if ranking else 1} ventanas "
        f"de {BACKTEST_H} meses"
        + (
            f"; MAPE mediana {mape_med}% (media {mape_w}%)."
            if mape_med is not None
            else (f"; MAPE {mape_w}%." if mape_w is not None else ".")
        )
        + (
            f" Mejora {mejora}% vs baseline estacional×nivel."
            if mejora is not None and mejora > 0
            else " En esta serie corta el estacional robusto suele empatar o ganar a SARIMA/ETS."
        )
        + f" Pico esperado: {n_fc['resumen']['mes_pico']['etiqueta']} "
        f"(~{int(round(n_fc['resumen']['mes_pico']['valor']))} procesos)."
    )

    return {
        "metodo": nombres.get(winner, winner),
        "metodo_id": winner,
        "honestidad": (
            "Forecast de serie mensual con backtest fuera de muestra. "
            "Las bandas son intervalo ~80% (no garantía). "
            "El valor en pesos es más volátil que el conteo de procesos; "
            "usar el conteo para planear capacidad y el valor como orden de magnitud."
        ),
        "ancla_hasta": n_fc["ancla_hasta"],
        "horizonte_meses": HORIZONTE,
        "lectura": lectura,
        "mejora_vs_estacional_pct": mejora,
        "comparativo_modelos": ranking,
        "nombres_modelos": nombres,
        "procesos": n_fc,
        "valor": v_fc,
        "por_segmento": segmentos,
        "segmentacion": seg_meta,
        "para_empresa": [
            "Planear en qué meses reforzar vigilancia SECOP y equipos de propuesta.",
            "Usar el pico proyectado para anticipar competencia y carga de trabajo.",
            "Mirar el desglose por segmento (educación / ingeniería / gestión) para enfocar oferta.",
            "Las bandas muestran incertidumbre: planear con el rango, no solo el punto central.",
        ],
        # compat UI anterior
        "serie_combinada": [
            {
                "periodo": r["periodo"],
                "etiqueta": r["etiqueta"],
                "n_procesos": r["valor"],
                "valor_sin_mega_cop": next(
                    (x["valor"] for x in v_fc["serie"] if x["periodo"] == r["periodo"]),
                    None,
                ),
                "n_lo": r["lo_80"],
                "n_hi": r["hi_80"],
                "tipo": r["tipo"],
            }
            for r in n_fc["serie"]
        ],
        "proximos_meses": [
            {
                "periodo": p["periodo"],
                "etiqueta": p["etiqueta"],
                "n_procesos_estimado": p["punto"],
                "n_lo_80": p["lo_80"],
                "n_hi_80": p["hi_80"],
                "valor_sin_mega_estimado_cop": next(
                    (v["punto"] for v in v_fc["proximos_meses"] if v["periodo"] == p["periodo"]),
                    None,
                ),
                "valor_lo_80": next(
                    (v["lo_80"] for v in v_fc["proximos_meses"] if v["periodo"] == p["periodo"]),
                    None,
                ),
                "valor_hi_80": next(
                    (v["hi_80"] for v in v_fc["proximos_meses"] if v["periodo"] == p["periodo"]),
                    None,
                ),
            }
            for p in n_fc["proximos_meses"]
        ],
    }


def main() -> None:
    print("Cargando series…")
    total, by_seg = _load_series()
    print(f"  total meses={len(total)} segmentos={list(by_seg)}")

    print("Entrenando / backtest…")
    outlook = build_outlook(total, by_seg)

    OUT_FORECAST.parent.mkdir(parents=True, exist_ok=True)
    OUT_FORECAST.write_text(json.dumps(outlook, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT_FORECAST)

    # Fusionar en Cap.3
    if CAP3.exists():
        cap3 = json.loads(CAP3.read_text(encoding="utf-8"))
    else:
        cap3 = {}

    cap3["titulo"] = "Futuro del mercado CTeI: forecast a 6 meses"
    cap3["subtitulo"] = (
        "Modelos de series de tiempo (Holt-Winters / SARIMA / estacional) con backtest. "
        "El modelo por proceso queda como herramienta secundaria de bid/no-bid."
    )
    cap3["outlook_mercado"] = outlook
    if "para_empresa" not in cap3 or not isinstance(cap3.get("para_empresa"), dict):
        cap3["para_empresa"] = {
            "titulo": "¿Para qué le sirve esto a una empresa o a Rosario?",
            "capas": [
                {
                    "id": "mercado",
                    "nombre": "Capa 1 — Mercado (principal)",
                    "pregunta": "¿Cómo se comportará la contratación CTeI en los próximos 6 meses?",
                    "uso": "Planear vigilancia SECOP, equipos y picos de competencia.",
                    "como": f"Serie de tiempo: {outlook['metodo']}.",
                },
                {
                    "id": "proceso",
                    "nombre": "Capa 2 — Proceso (secundaria)",
                    "pregunta": "Si aparece ESTE proceso, ¿qué dice el histórico de casos parecidos?",
                    "uso": "Bid/no-bid sobre una licitación competitiva concreta.",
                    "como": "Modelos ML (LightGBM) sobre ~70k procesos competitivos.",
                },
            ],
        }
    else:
        capas = cap3["para_empresa"].get("capas") or []
        for c in capas:
            if c.get("id") == "mercado":
                c["como"] = (
                    f"Serie de tiempo: {outlook['metodo']} "
                    f"(elegido por menor MAPE en backtest multi-ventana)."
                )
                c["pregunta"] = "¿Cómo se comportará la contratación CTeI en los próximos 6 meses?"
    cap3["reglas_uso"] = [
        {
            "titulo": "Sí usar",
            "items": [
                "Forecast de volumen (procesos) con bandas para planear los próximos meses.",
                "Desglose por segmento UNSPSC para enfocar oferta.",
                "Modelo por proceso (competitivo) solo para priorizar una oportunidad concreta.",
            ],
        },
        {
            "titulo": "No usar",
            "items": [
                "El punto central del forecast como cifra exacta de contratos.",
                "SARIMA/ETS a ciegas si el backtest pierde frente al estacional (aquí se elige el mejor).",
                "El modelo por proceso como si fuera el forecast del mercado nacional.",
            ],
        },
    ]
    cap3["nota_metodologica"] = (
        "Mercado: comparación estacional naïve / estacional×nivel / mediana / "
        "Holt-Winters(log) / SARIMA(log) con backtest en 3 ventanas de 6 meses; "
        f"ganador actual = {outlook['metodo']}. "
        "Bandas ~80%. Artefacto: data/processed/secop/capacidad3_forecast_ts.json. "
        "Proceso: modelos Cap.3 en analisis/secop/salidas_capacidad3/modelos/."
    )
    CAP3.write_text(json.dumps(cap3, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated", CAP3)

    if DASH.exists():
        dash = json.loads(DASH.read_text(encoding="utf-8"))
        if "capacidad_3" not in dash:
            dash["capacidad_3"] = {}
        dash["capacidad_3"].update({
            "titulo": cap3["titulo"],
            "subtitulo": cap3["subtitulo"],
            "outlook_mercado": outlook,
            "para_empresa": cap3.get("para_empresa"),
        })
        # preservar resto de claves ya presentes
        for k, v in cap3.items():
            if k not in dash["capacidad_3"]:
                dash["capacidad_3"][k] = v
            elif k in ("titulo", "subtitulo", "outlook_mercado", "para_empresa"):
                dash["capacidad_3"][k] = v
        # forzar overwrite de campos de forecast
        dash["capacidad_3"]["titulo"] = cap3["titulo"]
        dash["capacidad_3"]["subtitulo"] = cap3["subtitulo"]
        dash["capacidad_3"]["outlook_mercado"] = outlook
        if "para_empresa" in cap3:
            dash["capacidad_3"]["para_empresa"] = cap3["para_empresa"]
        DASH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Updated", DASH)

    print("Modelo procesos:", outlook["metodo"], "MAPE ranking:", outlook["comparativo_modelos"])


if __name__ == "__main__":
    main()
