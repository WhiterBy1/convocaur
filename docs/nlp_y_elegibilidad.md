# NLP y elegibilidad Rosario

## Objetivo

Convertir secciones de TdR en **JSON tipado** y decidir si la **Universidad del Rosario (IES)** puede postularse.

---

## Flujo NLP

```mermaid
flowchart TD
  S[JSON secciones TdR] --> M[map_seccion → claves P0]
  M --> L[OpenRouter LLM por sección]
  L --> J[JSON tipado ExtraccionTdr]
  J --> R[Reglas elegibilidad IES]
  R --> LLM2[LLM juicio final]
  LLM2 --> V[veredicto_final]
```

### Secciones P0

| Clave | Uso |
|-------|-----|
| `objetivo` | Resumen de la convocatoria |
| `dirigida_a` | Actores + alianza obligatoria |
| `lineas_tematicas` | Modalidades / ejes |
| `requisitos` | Habilitantes / documentales |
| `rechazo` | Causales |
| `financiacion` | Monto, plazos, contrapartida |
| `criterios` | Criterios y puntajes |

---

## Schema de salida (resumen)

```mermaid
classDiagram
  class ExtraccionTdr {
    convocatoria
    objetivo
    alianza_obligatoria
    actores_elegibles[]
    lineas_tematicas[]
    requisitos[]
    causales_rechazo[]
    criterios_evaluacion[]
    financiacion
    elegibilidad_urosario
  }
  class ActorElegible {
    tipo
    rol
    condicion
  }
  class Financiacion {
    monto_total_cop
    plazo_min_meses
    plazo_max_meses
    contrapartida_pct_min
    fuente_recursos
  }
  ExtraccionTdr --> ActorElegible
  ExtraccionTdr --> Financiacion
```

---

## Elegibilidad Rosario

```mermaid
flowchart TD
  A[actores_elegibles] --> B{¿Hay actor tipo IES/universidad?}
  B -->|No| N[no_elegible]
  B -->|Sí| C{¿Alianza obligatoria?}
  C -->|Sí| D[solo_en_alianza]
  C -->|No| E[puede_sola_o_alianza]
  D --> F[rol sugerido ejecutora/aliado]
  E --> F
  F --> G[condiciones pendientes<br/>territorio / grupos / acreditación]
```

Perfil institucional fijo: `nlp/perfil_urosario.py` (IES privada, sede Bogotá, actor SNCTI).

### Piloto verificado

| Conv | ¿Puede? | Modo | Rol |
|------|---------|------|-----|
| 48 | Sí | solo en alianza | ejecutora |
| 45 | Sí | sola o alianza | ejecutora |
| 976 | Sí | solo en alianza | ejecutora |

---

## Configuración LLM

```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
```

Cliente HTTP en `nlp/extract_llm.py` (sin SDK pesado).  
Input = **sección**, no PDF completo.

---

## Salidas

```text
data/processed/minciencias/nlp/convocatoria_{N}_nlp.json
data/processed/minciencias/elegibilidad/convocatoria_{N}_elegibilidad.json
```

Comandos:

```bash
set PYTHONPATH=src
python scripts/run_nlp_piloto.py --convocatorias 48,45,976
python scripts/run_elegibilidad.py --convocatorias 48,45,976
```
