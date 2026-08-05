# analisis/secop — vía SECOP del reto

Ubicación canónica:

```text
convocaur/analisis/secop/
```

Análisis de **SECOP II filtrado a CTeI** (proxy UNSPSC **80 / 81 / 86**) para las
tres capacidades del reto Universidad del Rosario:

1. Tendencias históricas  
2. Dinámicas de mercado  
3. Predicción (baseline de adjudicación)

## Narrativa completa (SECOP + Minciencias + matching)

[`docs/del_reto_a_mvp.md`](../../docs/del_reto_a_mvp.md)

## Archivos

| Archivo | Rol | Git |
|---------|-----|-----|
| `secop_ctei_lineas.csv` / `secop_ctei_procesos.csv` | Extracción SECOP CTeI | ignorado (grande) |
| `*_limpio.csv` | Deduplicados | ignorado |
| `secop_ctei_procesos_deflactado.csv` | COP constantes | ignorado |
| `anex-IPC-jun2026.xlsx` | Anexo IPC DANE | versionable |
| `ipc_dane_mensual_interpolado_TOTAL.csv` | Serie mensual operativa | versionable |
| `*.ipynb` | Análisis Cap. 1–3 | versionable |

Rutas Python: `convocaur.paths.SECOP`, `SECOP_PROCESOS_LIMPIO`, etc.

## Notebooks (orden de lectura)

1. `EDA_SECOP_CTeI_limpio.ipynb`
2. `Correcciones_outliers_y_modelado.ipynb` / `*_Completo.ipynb`
3. `Capacidad1_cierre.ipynb`
4. `Modelo_baseline_adjudicacion.ipynb` (baseline corto)
5. **`Capacidad3_entrenamiento_modelos.ipynb`** ← entrenamiento Cap. 3

Salidas del entrenamiento: `salidas_capacidad3/` (métricas + bitácora).  
Modelos `.joblib`: `salidas_capacidad3/modelos/` (gitignored; servir con **scikit-learn==1.6.1**).

Kernel: **Python 3.12** + `scikit-learn==1.6.1` (+ `lightgbm` / `joblib`).

Los notebooks usan rutas **relativas** a esta carpeta (CSV al lado del `.ipynb`).

## Scripts exógenos → features del dashboard

Lo que se ve en la UI **no se regenera solo abriendo el `.ipynb`**. Tras el análisis, los builds viven en `scripts/`:

| Feature en UI | Script |
|---------------|--------|
| Serie mensual Cap.1 | `scripts/build_capacidad1_mensual.py` |
| HHI / Pareto / rotación Cap.2 | `scripts/build_capacidad2_mercado.py` |
| Grafo mercado + ego Rosario + peers IES | `scripts/build_capacidad2_red.py` |
| Flag IES en red/peers | `scripts/patch_es_ies.py` |
| Nombre del #1 en rotación anual | `scripts/patch_rotacion_top1.py` |
| KPIs Cap.3 desde bitácora | `scripts/build_capacidad3_prediccion.py` |
| Outlook / forecast series de tiempo | `scripts/build_capacidad3_forecast_ts.py` |

Detalle y orden de ejecución: [`scripts/README.md`](../../scripts/README.md).

Fuente abierta: SECOP II en datos.gov.co (`p6dx-8zbt`).
