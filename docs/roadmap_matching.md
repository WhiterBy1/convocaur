# Roadmap — matching con embeddings / RAG

## Meta

Dado una convocatoria (o un proyecto interno), responder:

1. **¿Qué profesores son más aptos?**
2. **¿Tenemos equipo suficiente?** (cobertura + brechas)

---

## Diseño propuesto

```mermaid
flowchart TD
  Q[Consulta: objetivo + líneas + requisitos NLP] --> E1[Embedding consulta]
  P[Chunks por docente<br/>áreas + CvLAC + proyectos] --> IDX[Índice vectorial]
  E1 --> RET[Top-k similares]
  IDX --> RET
  RET --> FILT[Filtros duros<br/>categoría / facultad / elegibilidad]
  FILT --> SCORE[Score cobertura]
  SCORE --> OUT[Equipo sugerido + brechas]
  OUT --> RAG[Opcional: LLM explica con evidencia]
```

---

## Orden de implementación

```mermaid
flowchart LR
  A[1. Filtro elegibilidad convocatoria] --> B[2. Índice embeddings 353 CvLAC]
  B --> C[3. Top-k + cobertura mínima]
  C --> D[4. RAG explicativo]
  D --> E[5. Incluir 259 sin CvLAC + GrupLAC]
```

1. **No rankear** convocatorias donde Rosario es `no_elegible`.
2. Indexar chunks de docentes con CvLAC (mejor señal).
3. Reglas de cobertura (p.ej. ≥1 Senior/Asociado, ≥2 líneas afines).
4. RAG solo para justificación.
5. Completar grupos A1/A/B y los sin CvLAC.

---

## Salida esperada (futuro)

```json
{
  "convocatoria": "976",
  "equipo_suficiente": "parcial",
  "candidatos": [
    {"id": "...", "score": 0.81, "rol_sugerido": "investigador_principal"}
  ],
  "brechas": ["falta evidencia sede regional", "sin grupo A1 explícito"]
}
```

Este documento es la hoja de ruta de evolución (índice vectorial, RAG, GrupLAC).

**Estado actual:** piloto operativo de matching híbrido
(embeddings + TF-IDF + boost) con UI grafo en
[`frontend/`](../frontend/) + [`backend/`](../backend/) — ver
[`matching_decisiones.md`](matching_decisiones.md).

Cómo encaja en el relato del reto (SECOP + Minciencias):
[`del_reto_a_mvp.md`](del_reto_a_mvp.md).

