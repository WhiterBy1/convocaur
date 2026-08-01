# scripts/

Puntos de entrada del pipeline. Agregan `../src` al `PYTHONPATH`.

| Script | Qué hace |
|--------|----------|
| `run_descarga.py` | Descarga anexos/TdR/resoluciones |
| `run_tdr_secciones.py` | Colecciona TdR o secciones |
| `run_nlp_piloto.py` | Extracción LLM + elegibilidad |
| `run_elegibilidad.py` | Solo elegibilidad sobre NLP ya guardado |
| `run_match.py` | Ranking híbrido (`--todas`, `--solo-faltantes`) |
| `run_matching_tests.py` | Smoke tests del matching |

```bash
cd convocaur
set PYTHONPATH=src
python scripts/run_match.py --solo-faltantes
```

UI: `frontend/` + API `backend/`  
Botones: sync Minciencias (`POST /api/minciencias/sync`) y rankings (`POST /api/matching/run`).
