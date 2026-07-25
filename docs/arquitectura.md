# Arquitectura ConvocaUR

## Visión

ConvocaUR transforma **documentos públicos de Minciencias** y **perfiles Rosario** en datos tipados para:

1. evaluar **elegibilidad institucional**;
2. preparar **matching de talento** (embeddings/RAG);
3. alimentar tablas tipo `maestro_convocatorias` y `requisitos_convocatoria`.

No es un scraper genérico: cada etapa produce un artefacto auditable en `data/`.

---

## Capas

```mermaid
flowchart TB
  subgraph L1 [1. Adquisición]
    A1[Scrape HTML Minciencias]
    A2[Descarga PDF/DOCX/XLSX]
    A3[Scrape HUB-UR docentes]
    A4[Scrape CvLAC Scienti]
  end

  subgraph L2 [2. Estructuración]
    B1[Clasificación documentos]
    B2[Colección TdR normalizada]
    B3[Corte por tabla de contenido]
    B4[Perfil docente + bloque cvlac]
  end

  subgraph L3 [3. Comprensión]
    C1[Mapeo secciones canónicas]
    C2[LLM OpenRouter → JSON tipado]
    C3[Reglas + LLM elegibilidad IES]
  end

  subgraph L4 [4. Decisión / matching futuro]
    D1[Veredicto Rosario]
    D2[Embeddings / RAG equipo]
  end

  L1 --> L2 --> L3 --> L4
```

---

## Qué SÍ hace / qué NO hace

| Sí | No |
|----|----|
| Extraer requisitos, actores, montos, criterios de TdR | Predecir adjudicaciones SECOP |
| Decir si Rosario entra como IES y en qué modo | Inventar grupos A1 sin fuente |
| Inventariar docentes + CvLAC | Sustituir capacidad financiera interna |
| Dejar JSON/CSV reproducibles | Entrenar el modelo final de mercado |

---

## Paquete Python

```text
src/convocaur/
├── paths.py           # única fuente de rutas data/
├── minciencias/       # scrape, descarga, TdR, secciones
├── urosario/          # docentes HUB + CvLAC
└── nlp/               # LLM, schemas, elegibilidad
```

Los scripts de `scripts/` solo orquestan; la lógica vive en el paquete.

---

## Dependencias externas

```mermaid
flowchart LR
  APP[ConvocaUR] -->|HTTPS| MC[minciencias.gov.co]
  APP -->|HTTPS| HUB[research-hub.urosario.edu.co]
  APP -->|HTTPS| SCI[scienti.minciencias.gov.co]
  APP -->|API chat| OR[OpenRouter<br/>deepseek-v4-flash]
```

Secretos solo en `.env` (nunca en git).

---

## Flujo de valor hacia el reto

```mermaid
mindmap
  root((ConvocaUR))
    Tendencias CTeI
      Fechas
      Montos
      Líneas temáticas
    Encaje Rosario
      Elegibilidad IES
      Requisitos tipados
      Talento docentes/CvLAC
    Matching futuro
      Embeddings
      Cobertura de equipo
      Brechas
```
