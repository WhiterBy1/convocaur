# Hallazgos — exploración de datos

Resumen de lo explorado al consolidar el pipeline (antes vivía en labs personales). Las cifras de cobertura actuales están en el [README maestro](../README.md).


## Mapa de cobertura — un solo universo, no grupos distintos

Todo el notebook usa **95 convocatorias (NLP)** como universo de referencia. Los otros conteos que aparecen (14, 3) **no son grupos separados** — son subconjuntos anidados del mismo universo: `elegibilidad (3) ⊂ listado (14) ⊂ NLP (95)`. Es decir, de las 95 convocatorias que conocemos, solo 14 tienen datos del scrape original (monto, cronograma, documentos) y de esas 14, solo 3 tienen elegibilidad calculada. Todas las secciones del notebook ahora reportan sus conteos contra ese mismo denominador de 95 para que sea consistente de principio a fin.

## Montos (Minciencias)

La convocatoria **48** (SGR — biodiversidad y bioeconomía) concentra el mayor monto (~$750.000 millones COP), seguida por Colombia Inteligente - Infraestructura IA (~$630.000 millones) y Agro por la Vida y por la Tierra (~$446.000 millones). 14 de las 15 convocatorias tienen monto identificable en `total_recursos_texto`.

**Nota técnica:** `data/raw/minciencias/` (incluido el listado original) salió del repo — Jose lo movió a un respaldo en Google Drive (ver `catalogo_datos.md`) porque pesaba ~2GB. Esta sección ahora usa `convocatorias_processed` (`data/processed/minciencias/minciencias_convocatorias_processed.csv`), que tiene el mismo contenido y no depende de ese raw ausente.

## Cronograma y plazos

El plazo entre apertura y cierre varía bastante: desde **26 días** (convocatoria 973, formación capital humano Cundinamarca) hasta **80 días** (convocatoria 51, Córdoba). Vale la pena cruzar esto con monto — una convocatoria grande con poco margen de preparación es más riesgosa que una mediana con tiempo de sobra. Antes no mirábamos esto: `actividades`/`actividades_processed` estaban cargadas desde el inicio del notebook pero nunca se usaban.

## Segmentación por tipo de convocatoria

Las 95 mezclaban familias distintas que probablemente se comportan muy diferente entre sí. Clasificamos por palabras clave (título cuando existe, `fuente_recursos`, y `objetivo` como respaldo): **21 SGR** (regalías), **14 Minciencias regular**, **9 Becas/formación**, **4 Movilidad académica**, **2 Publindex**. Quedan **16 sin clasificar** (tienen texto pero no coincide con ningún patrón) y **29 sin dato** (coincide con las de extracción vacía, ver más abajo). No es una clasificación perfecta — es honesta sobre lo que sí y no se pudo inferir con las señales disponibles.

## Documentos requeridos

`documentos_processed` cubre las mismas 14 convocatorias del listado (no las 95 del NLP expandido). La convocatoria **48** exige el mayor número de anexos (16); varias SGR piden entre 10-14. Predomina el tipo `anexo` (137 de 230 documentos), seguido de `resultado` (28). Es un proxy simple de carga documental para priorizar cuál convocatoria requiere más trabajo de armado de propuesta.

## Requisitos, criterios y financiación en detalle

Sobre las 95 convocatorias con NLP: el tipo de requisito más común es **documental** (625 ocurrencias), seguido de **habilitante** (244), técnico (100), financiero (54) y alianza (25). Casi todo es **obligatorio** (1064) vs deseable (60) — poco margen para incumplir requisitos.

Financiación: el plazo de ejecución típico ronda los **36 meses** (rango 3-60), pero solo **49 de 95** convocatorias tienen ese dato extraído, y apenas **17 de 95** especifican contrapartida. Esto ya empalma con el siguiente hallazgo — muchos campos vacíos no son "no aplica", son extracción incompleta.

## Calidad de las extracciones NLP — hallazgo importante

De las 95 convocatorias con NLP, **22 tienen los 6 campos clave completamente vacíos** (`objetivo`, `actores_elegibles`, `lineas_tematicas`, `requisitos`, `criterios_evaluacion`, `financiacion`) y **33 tienen 2 o menos poblados**. Solo 30 de 95 están realmente completas (6/6). Esto explica por qué el panorama de alianza/financiación tenía tantos `None`: no es que esas convocatorias no exijan alianza o no tengan plazo — es que su extracción NLP quedó casi en blanco, probablemente porque el TdR no tenía la estructura esperada o la extracción no encontró contenido.

**Implicación práctica:** antes de correr elegibilidad o matching sobre alguna de las 92 convocatorias sin elegibilidad todavía, filtrar primero por `calidad_extracciones_nlp.csv` — no vale la pena gastar LLM en evaluar elegibilidad sobre una extracción vacía.

## NLP (95 convocatorias) vs elegibilidad (3 convocatorias) — el gap real

Jose expandió el procesamiento NLP de 3 a **95 convocatorias**. Pero el paso de elegibilidad (que decide si Rosario puede postularse) **solo se corrió para las 3 originales**: 45, 48, 976. Las 92 restantes tienen texto NLP tipado (con calidad variable, ver arriba) pero nadie evaluó todavía si Rosario es actor elegible en ellas.

De las 3 con elegibilidad calculada, todas dan `puede_postularse=True`. 48 y 976 exigen alianza obligatoria (Rosario solo puede entrar como ejecutora dentro de una alianza); 45 permite ir sola o en alianza.

**Este es el pendiente más accionable hoy:** correr `scripts/run_elegibilidad.py` sobre las convocatorias restantes con buena calidad de extracción (no las 92 a ciegas). Cuesta llamadas a LLM (revisar presupuesto/modelo con el equipo antes de lanzarlo).

## Cobertura CvLAC de docentes

353 de 612 docentes tienen CvLAC. Medicina y Ciencias de la Salud concentra el mayor volumen absoluto de docentes, pero también el mayor número absoluto de docentes **sin** CvLAC — la cobertura relativa es más alta en Jurisprudencia y en las Vicerrectorías. Distribución de categoría (de los que sí tienen CvLAC): 86 Junior, 54 Senior, 46 Asociado, 2 Emérito.

## Matching consolidado

El baseline por keywords de exploración quedó como referencia histórica (shortlists en `data/processed/exploracion/`).

El sistema **canónico** vive en el proyecto:

- Código: `src/convocaur/matching/`
- Decisiones: [`matching_decisiones.md`](matching_decisiones.md)
- UI: `frontend/` + API `backend/`
- CLI: `python scripts/run_match.py`
- Dependencias: `scikit-learn`, `fastapi`, `uvicorn` ya están en `requirements.txt`

## Grupos A1/A/B/C y sede regional: NO se pueden cruzar todavía

No existe ningún campo con la clasificación GrupLAC (A1/A/B/C) ni con sede regional en los datos actuales — ni en `json_profesores/`, ni en el CSV de docentes. Esto no es una tarea de notebook: haría falta un scraper nuevo de GrupLAC, documentado como pendiente en [capacidad_urosario.md](capacidad_urosario.md#huecos-conocidos). Por eso el matching no inventa grupos — [arquitectura.md](arquitectura.md) lo prohíbe explícitamente.

## Siguiente paso natural

1. Filtrar el pool NLP por calidad de extracción antes de gastar LLM en elegibilidad sobre convocatorias con extracción pobre.
2. Correr elegibilidad sobre las convocatorias restantes que sí tengan buena calidad de extracción.
3. Extender el matching híbrido a ese pool depurado.

## Dónde están los datos generados

Exploración conservada en `data/processed/exploracion/`:

- `cobertura_cvlac_por_facultad.csv`
- `shortlist_keyword_convocatoria_{45,48,976}.csv`

Matching canónico en `data/processed/matching/`.
