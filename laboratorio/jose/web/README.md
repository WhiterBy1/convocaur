# Web explorer — Matching José

UI HTML + FastAPI para revisar inputs/outputs del matching docente ↔ convocatoria **sin Streamlit**.

## Arranque

```bash
cd convocaur/laboratorio/jose
python web/api.py
```

O en Windows: doble clic en `web/lanzar.bat`.

Abre [http://127.0.0.1:8765](http://127.0.0.1:8765).

Dependencias: `fastapi`, `uvicorn`, `pandas` (y el paquete `convocaur` / código en `matching/`).

```bash
pip install fastapi uvicorn pandas
```

## Qué muestra

| Vista | Fuente |
|-------|--------|
| Flujo del score híbrido | `/api/flujo` |
| Lista de convocatorias con ranking | `salidas/matching/ranking_*.csv` |
| NLP + texto de matching | `data/processed/minciencias/nlp/` |
| Ranking top-k | CSV ya calculados |
| Ficha docente (HUB + CvLAC) | `data/raw/urosario/json_profesores/` |

No recalcula embeddings: solo explora lo ya generado. Para regenerar rankings:

```bash
python matching/run_match.py
```

## API útil

- `GET /api/health`
- `GET /api/convocatorias`
- `GET /api/convocatorias/{id}` — NLP + elegibilidad
- `GET /api/convocatorias/{id}/ranking?top=20`
- `GET /api/profesores/{id}`
