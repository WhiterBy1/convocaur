# scripts/

Puntos de entrada del pipeline. Agregan `../src` al `PYTHONPATH` cuando hace falta.

## Minciencias / matching

| Script | Qué hace |
|--------|----------|
| `run_descarga.py` | Descarga anexos/TdR/resoluciones |
| `run_tdr_secciones.py` | Colecciona TdR o secciones |
| `run_nlp_piloto.py` | Extracción LLM + elegibilidad |
| `run_elegibilidad.py` | Solo elegibilidad sobre NLP ya guardado |
| `run_match.py` | Ranking híbrido (`--todas`, `--solo-faltantes`) |
| `run_matching_tests.py` | Smoke tests del matching |
| `run_ingest_nueva.py` | Ingesta completa TdR→NLP→eleg→match (CLI / sync) |

## SECOP — build de features para el dashboard

Estos scripts **materializan** lo explorado en los notebooks de `analisis/secop/` hacia JSON consumibles por la API (`data/processed/secop/` + `resumen_dashboard.json`).

| Script | Cap. | Origen / notebook de referencia | Salida principal |
|--------|------|----------------------------------|------------------|
| `build_capacidad1_mensual.py` | 1 | `Capacidad1_cierre.ipynb` | `capacidad1_mensual.json` |
| `build_capacidad2_mercado.py` | 2 | EDA + correcciones outliers / HHI-Pareto | `capacidad2_mercado.json` |
| `build_capacidad2_red.py` | 2 | Extensión post-notebook: grafo + ego Rosario | `capacidad2_red.json`, `capacidad2_rosario.json` |
| `build_capacidad3_prediccion.py` | 3 | Bitácora de `Capacidad3_entrenamiento_modelos.ipynb` | `capacidad3_prediccion.json` |
| `build_capacidad3_forecast_ts.py` | 3 | Extensión post-notebook: ETS/SARIMA/outlook | `capacidad3_forecast_ts.json` (+ enriquece Cap.3/dashboard) |

### Parches exógenos (features añadidas después del notebook)

No reentrenan modelos ni rehacen todo el Cap.2; **parchean JSON** ya generados:

| Script | Feature | Cuándo usarlo |
|--------|---------|----------------|
| `patch_es_ies.py` | Flag `es_ies` por heurística de razón social (UNIVERSIDAD, UPTC, UNISALLE…) | Tras `build_capacidad2_red.py` o si el filtro IES del UI falla |
| `patch_rotacion_top1.py` | `top1_nombre` / valor del #1 en `rotacion_anual` | Para tooltips “% del CTeI que aportó el #1” sin regenerar Cap.2 |

### Utilidades de front (no son features de datos)

| Script | Qué hace |
|--------|----------|
| `wrap_chart_inview.py` | Envuelve charts con `ChartInView` (animación al entrar en viewport) |
| `wrap_chart_height_divs.py` | Ajuste de wrappers de altura en charts |
| `fix_frontend_utf8.py` | Normaliza encoding del front |

## Orden sugerido — regenerar dashboard SECOP

```bash
cd convocaur
set PYTHONPATH=src
py -3.12 scripts/build_capacidad1_mensual.py
py -3.12 scripts/build_capacidad2_mercado.py
py -3.12 scripts/build_capacidad2_red.py
py -3.12 scripts/patch_es_ies.py
py -3.12 scripts/patch_rotacion_top1.py
py -3.12 scripts/build_capacidad3_prediccion.py
py -3.12 scripts/build_capacidad3_forecast_ts.py
```

Matching / NLP:

```bash
set PYTHONPATH=src
python scripts/run_match.py --solo-faltantes
python scripts/run_ingest_nueva.py --sync
```

UI: `frontend/` + API `backend/`  
Botones: sync Minciencias (`POST /api/minciencias/sync`), rankings (`POST /api/matching/run`), plan (`GET /api/plan/manejo`).
