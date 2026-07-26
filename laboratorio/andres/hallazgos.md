# Hallazgos — Andrés

Resumen corto de lo explorado en [exploracion.ipynb](exploracion.ipynb). Detalle y código en el notebook; acá solo las conclusiones.

## Montos (Minciencias, listado completo)

La convocatoria **48** (SGR — biodiversidad y bioeconomía) concentra el mayor monto del listado (~$750.000 millones COP), seguida por Colombia Inteligente - Infraestructura IA (~$630.000 millones) y Agro por la Vida y por la Tierra (~$446.000 millones). 14 de las 15 convocatorias del listado tienen monto identificable en `total_recursos_texto`.

## Piloto NLP + elegibilidad (48, 45, 976)

Las 3 dan `puede_postularse=True` para Rosario. 48 y 976 exigen alianza obligatoria (Rosario solo puede entrar como ejecutora dentro de una alianza); 45 permite ir sola o en alianza.

## Cobertura CvLAC de docentes

353 de 612 docentes tienen CvLAC. Medicina y Ciencias de la Salud concentra el mayor volumen absoluto de docentes, pero también el mayor número absoluto de docentes **sin** CvLAC — la cobertura relativa es más alta en Jurisprudencia y en las Vicerrectorías. Distribución de categoría (de los que sí tienen CvLAC): 86 Junior, 54 Senior, 46 Asociado, 2 Emérito.

## Prototipo de matching por palabras clave

Baseline simple (sin embeddings) que cuenta coincidencias entre las palabras clave de cada convocatoria (`objetivo` + `lineas_tematicas`) y el texto de perfil de cada docente (`areas_investigacion` + `lineas_investigacion`), con un score que premia tener CvLAC y categoría Senior/Asociado.

Corrido sobre las 3 convocatorias piloto (filtrando primero por elegibilidad, como pide el paso 1 del [roadmap de matching](../../docs/roadmap_matching.md)): las 3 quedan en `equipo_suficiente="parcial"` porque siempre aparece al menos un Senior/Asociado en el top-15. **"Parcial" y no "suficiente" a propósito** — falta cruzar con grupos A1/A/B/C (aún no tabulados) y sede regional antes de confiar en esa cobertura.

Limitación conocida: coincidencia por palabra suelta, sin semántica ni sinónimos. Sirve como shortlist inicial a revisar a mano, no como ranking final.

## Pendiente real: grupos A1/A/B/C y sede regional NO se pueden cruzar todavía

Revisé los 612 JSON de `json_profesores/` y el CSV de docentes: **no existe ningún campo con la clasificación GrupLAC (A1/A/B/C)** ni con sede regional. Solo hay `facultad` (Bogotá, sin distinción de sede) y `afiliaciones` (texto libre con el nombre del grupo, pero no su categoría Minciencias). Esto no es una tarea de notebook — es un gap de datos: haría falta un scraper nuevo de GrupLAC (como `urosario/scrape_cvlac.py` pero para grupos), documentado como pendiente en [capacidad_urosario.md](../../docs/capacidad_urosario.md#huecos-conocidos). Por eso el prototipo de matching **no inventa grupos** — [docs/arquitectura.md](../../docs/arquitectura.md) lo prohíbe explícitamente ("No inventar grupos A1 sin fuente"). El equipo tendría que priorizar ese scraper antes de que cualquier notebook pueda cruzar esta info.

## Siguiente paso natural

Reemplazar el conteo de palabras por embeddings reales, siguiendo el orden de implementación de [roadmap_matching.md](../../docs/roadmap_matching.md) (pasos 2-5). Es un salto de alcance mayor: nueva dependencia de modelo de embeddings, y probablemente vive en `src/convocaur/` vía PR en vez de en este notebook personal, porque lo usaría todo el equipo.

## Dónde están los datos generados

Todo en `salidas/` (gitignored, no se sube a `main`):

- `comparativo_nlp_elegibilidad_piloto.csv`
- `cobertura_cvlac_por_facultad.csv`
- `resumen_cobertura_piloto.csv`
- `shortlist_keyword_convocatoria_{45,48,976}.csv`
