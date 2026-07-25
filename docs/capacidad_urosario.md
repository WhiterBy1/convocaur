# Capacidad Universidad del Rosario

## Objetivo

Construir el lado **oferta** del sistema: quién investiga, en qué, con qué evidencia (HUB-UR + CvLAC).

---

## Flujo

```mermaid
flowchart TD
  H[HUB-UR listado docentes] --> CSV[docentes_urosario_con_id.csv]
  CSV --> J[json_profesores/id.json]
  J -->|si hay URL CvLAC| CV[bloque cvlac en el mismo JSON]
  J -->|sin URL usable| S[sin_cvlac.csv]
```

---

## Artefactos

| Archivo / carpeta | Qué es |
|-------------------|--------|
| `data/raw/urosario/docentes_urosario_con_id.csv` | 613 docentes: `id`, facultad, cargo, link, `json_file` |
| `data/raw/urosario/json_profesores/*.json` | Perfil HUB (áreas, pubs, proyectos, enlaces) |
| `…/json_profesores/*.json` → clave `cvlac` | Enriquecimiento Scienti (353 docentes) |
| `data/raw/urosario/sin_cvlac.csv` | 259 ids **sin link CvLAC** en el hub (no es fallo de red) |

---

## Qué trae el HUB vs CvLAC

```mermaid
flowchart LR
  subgraph hub [HUB-UR]
    H1[Facultad / cargo]
    H2[Áreas investigación]
    H3[Publicaciones Pure]
    H4[Links ORCID/Scholar/CvLAC]
  end

  subgraph cvlac [CvLAC Scienti]
    C1[Categoría investigador]
    C2[Líneas investigación]
    C3[Proyectos tipificados]
    C4[Artículos / formación / experiencia]
  end

  hub --> Perfil[Perfil consolidado]
  cvlac --> Perfil
```

### Categorías Minciencias vistas en el piloto CvLAC

- Investigador Junior  
- Investigador Asociado  
- Investigador Senior  
- Investigador Emérito  
- (+ muchos sin categoría declarada en datos generales)

---

## Módulos

| Módulo | Rol |
|--------|-----|
| `urosario/scrape_docentes.py` | Recorre CSV, baja perfiles HUB → JSON |
| `urosario/cvlac_parser.py` | Parsea HTML CvLAC → dict por secciones |
| `urosario/scrape_cvlac.py` | Inserta `cvlac` en JSON existentes |
| `urosario/hub.py` | Utilidades KPI / perfiles (legado notebook) |

---

## Huecos conocidos

```mermaid
flowchart TB
  OK[353 con CvLAC] --> NEXT1[Normalizar categoría / líneas a tablas]
  GAP[259 sin CvLAC] --> NEXT2[Buscar cod_rh por ORCID/nombre]
  ALL[612 perfiles] --> NEXT3[Grupos A1/A/B/C vía GrupLAC]
  ALL --> NEXT4[Alianzas y sedes regionales institucionales]
```

Sin grupos categorizados y sin presencia territorial, el matching semántico puede sugerir talento bueno que **aún no habilita** algunas convocatorias SGR.
