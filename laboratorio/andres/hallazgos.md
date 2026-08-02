# Hallazgos — Andrés

Resumen corto de lo explorado en [exploracion.ipynb](exploracion.ipynb). Detalle y código en el notebook; acá solo las conclusiones.

## Mapa de cobertura — un solo universo, no grupos distintos

Todo el notebook usa **95 convocatorias (NLP)** como universo de referencia. Los otros conteos que aparecen (14) **no son un grupo separado** — es un subconjunto anidado del mismo universo: `listado (14) ⊂ NLP (95)`. Es decir, de las 95 convocatorias que conocemos, solo 14 tienen datos del scrape original (monto, cronograma, documentos). La elegibilidad, en cambio, **ya no es un subconjunto**: se corrió sobre las 95 completas (antes solo cubría 3). Todas las secciones del notebook reportan sus conteos contra ese mismo denominador de 95.

## Montos (Minciencias)

La convocatoria **48** (SGR — biodiversidad y bioeconomía) concentra el mayor monto (~$750.000 millones COP), seguida por Colombia Inteligente - Infraestructura IA (~$630.000 millones) y Agro por la Vida y por la Tierra (~$446.000 millones). 14 de las 15 convocatorias tienen monto identificable en `total_recursos_texto`.

**Nota técnica:** `data/raw/minciencias/` (incluido el listado original) salió del repo — se movió a un respaldo en Google Drive (ver `catalogo_datos.md`) porque pesaba ~2GB. Esta sección usa `convocatorias_processed` (`data/processed/minciencias/minciencias_convocatorias_processed.csv`), que tiene el mismo contenido y no depende de ese raw ausente.

## Cronograma y plazos

El plazo entre apertura y cierre varía bastante: desde **26 días** (convocatoria 973, formación capital humano Cundinamarca) hasta **80 días** (convocatoria 51, Córdoba). Vale la pena cruzar esto con monto — una convocatoria grande con poco margen de preparación es más riesgosa que una mediana con tiempo de sobra.

## Segmentación por tipo de convocatoria

Las 95 mezclan familias distintas que probablemente se comportan muy diferente entre sí. Clasificamos por palabras clave (título cuando existe, `fuente_recursos`, y `objetivo` como respaldo): **27 SGR** (regalías), **17 Becas/formación**, **15 Minciencias regular**, **4 Publindex**, **3 Movilidad académica**. Quedan **25 sin clasificar** (tienen texto pero no coincide con ningún patrón) y **4 sin dato**. No es una clasificación perfecta — es honesta sobre lo que sí y no se pudo inferir con las señales disponibles. La proporción de alianza obligatoria varía fuerte por tipo: casi 100% en Movilidad académica y Becas/formación, ~83% en SGR, 0% en Publindex.

## Documentos requeridos

`documentos_processed` cubre las mismas 14 convocatorias del listado (no las 95 del NLP expandido). La convocatoria **48** exige el mayor número de anexos (16); varias SGR piden entre 10-14. Predomina el tipo `anexo`, seguido de `resultado`. Es un proxy simple de carga documental para priorizar cuál convocatoria requiere más trabajo de armado de propuesta.

## Requisitos, criterios y financiación en detalle

Sobre las 95 convocatorias con NLP: el tipo de requisito más común es **documental** (792 ocurrencias), seguido de **habilitante** (291), **técnico** (151), **otro** (114), **financiero** (102) y **alianza** (43). Casi todo es **obligatorio** (1421) vs deseable (72) — poco margen para incumplir requisitos.

Financiación: el plazo de ejecución típico ronda los **31 meses** (rango 5-96), y ahora **70 de 95** convocatorias tienen ese dato extraído (antes 49/95), y **26 de 95** especifican contrapartida (antes 17/95). La mejora viene directo de la corrección de la extracción de secciones y el reproceso del NLP.

## Calidad de las extracciones NLP — el hallazgo que más cambió

De las 95 convocatorias con NLP, ahora solo **1 sigue completamente vacía** (`convocatoria_942`, 0/6 campos) y **1 más con extracción pobre** (`convocatoria_39`, 2/6). **65 de 95 están realmente completas (6/6)**. Antes de la corrección de secciones + reproceso de NLP, esto era: 22 completamente vacías, 33 con ≤2 campos poblados, solo 30 realmente completas.

**Nota metodológica:** se corrigió `campo_poblado()` en la sección 11 — antes contaba `financiacion` como "poblado" con solo que fuera un dict no vacío, sin revisar si sus 8 sub-campos tenían contenido real. Encontré 5 convocatorias donde `financiacion` era un dict con **todo en `None`** y aun así contaba como campo poblado; con el fix, esas 5 bajan un poco su completitud (el 6/6 pasó de 66 a 65 tras corregirlo).

## NLP (95 convocatorias) vs elegibilidad (95 convocatorias) — gap cerrado

Jose expandió el procesamiento NLP de 3 a 95 convocatorias, y el paso de elegibilidad (que decide si Rosario puede postularse) **ya se corrió sobre las 95 completas** — este era el hallazgo más accionable de la versión anterior de este documento, y ya está resuelto.

De las 95, **61 dan `puede_postularse=True`** y 34 `no_elegible`. Por modo entre las elegibles: 38 `solo_en_alianza`, 12 `sola`, 8 `elegible_con_condiciones`, 2 `solo_como_aliado`, 1 `puede_sola_o_alianza`.

## Cobertura CvLAC de docentes

353 de 612 docentes tienen CvLAC. Medicina y Ciencias de la Salud concentra el mayor volumen absoluto de docentes, pero también el mayor número absoluto de docentes **sin** CvLAC — la cobertura relativa es más alta en Jurisprudencia y en las Vicerrectorías. Distribución de categoría (de los que sí tienen CvLAC): 86 Junior, 54 Senior, 46 Asociado, 2 Emérito.

## Dos sistemas de matching en paralelo

**El mío (este notebook, sección 13):** baseline simple sin embeddings — cuenta coincidencias entre las palabras clave de cada convocatoria (`objetivo` + `lineas_tematicas`) y el texto de perfil de cada docente, con un score que premia tener CvLAC y categoría Senior/Asociado. Corre automáticamente sobre todas las convocatorias que tengan elegibilidad calculada y `puede_postularse=True` — **ahora son 61** (antes 3, escaló solo sin tocar código). Resultado: **57 `equipo_suficiente="parcial"`, 4 `"insuficiente"`** — nunca sale "suficiente" a propósito: falta cruzar con grupos A1/A/B/C y sede regional.

**El de Jose (`laboratorio/jose/matching/`):** un sistema real con embeddings de OpenRouter (`openai/text-embedding-3-small`) + TF-IDF como respaldo local, con boost por CvLAC/categoría, documentado a fondo en su `DECISIONES.md`. Incluye un web explorer (`laboratorio/jose/web/`, FastAPI + HTML). No verifiqué en esta pasada si ya lo escaló al pool actual de 95/61 convocatorias — pendiente de confirmar con él (está trabajando en la siguiente capa del roadmap). Requiere `scikit-learn`, `fastapi`, `uvicorn` — **no están en `requirements.txt` todavía**.

## Grupos A1/A/B/C y sede regional: NO se pueden cruzar todavía

No existe ningún campo con la clasificación GrupLAC (A1/A/B/C) ni con sede regional en los datos actuales — ni en `json_profesores/`, ni en el CSV de docentes. Esto no es una tarea de notebook: haría falta un scraper nuevo de GrupLAC, documentado como pendiente en [capacidad_urosario.md](../../docs/capacidad_urosario.md#huecos-conocidos). Por eso ningún matching (el mío ni el de Jose) inventa grupos — [docs/arquitectura.md](../../docs/arquitectura.md) lo prohíbe explícitamente.

## Siguiente paso natural

1. ~~Filtrar el pool NLP por calidad de extracción antes de gastar LLM en elegibilidad~~ — ya no aplica, la calidad mejoró drásticamente (65/95 completas) y elegibilidad ya se corrió sobre las 95.
2. ~~Correr elegibilidad sobre las convocatorias restantes~~ — hecho, 95/95.
3. Extender el matching de Jose (ya tiene embeddings reales) al pool completo de 61 convocatorias elegibles, en vez de seguir invirtiendo en el baseline de palabras clave.
4. Agregar `scikit-learn`, `fastapi`, `uvicorn` a `requirements.txt` para que el trabajo de Jose sea reproducible por el resto del equipo.
5. Investigar aparte los 2 casos residuales de extracción pobre (`convocatoria_39`, `convocatoria_942`) — posible TdR con estructura muy atípica.

## Dónde están los datos generados

Todo en `salidas/` (gitignored, no se sube a `main`):

- `cronograma_plazos.csv` — apertura, cierre y días de margen por convocatoria
- `anexos_por_convocatoria.csv` — número de anexos exigidos, por convocatoria
- `panorama_nlp_todas.csv` — las 95 convocatorias con NLP, con o sin elegibilidad, con `tipo_convocatoria`
- `panorama_por_tipo_convocatoria.csv` — monto promedio y % alianza obligatoria, agrupado por tipo
- `comparativo_nlp_elegibilidad.csv` — las 95 convocatorias, todas con elegibilidad calculada
- `requisitos_por_tipo.csv` — conteo de requisitos por tipo, todas las convocatorias NLP
- `financiacion_detalle.csv` — plazo y contrapartida por convocatoria
- `calidad_extracciones_nlp.csv` — cuántos de los 6 campos clave están poblados, por convocatoria
- `cobertura_cvlac_por_facultad.csv`
- `resumen_cobertura.csv` — las 61 convocatorias elegibles, con `equipo_suficiente`
- `shortlist_keyword_convocatoria_{N}.csv` — una por cada una de las 61 convocatorias elegibles
