# scripts/

Puntos de entrada del pipeline. Todos agregan `../src` al `PYTHONPATH`.

| Script | Qué hace |
|--------|----------|
| `run_descarga.py` | Descarga anexos/TdR/resoluciones |
| `run_tdr_secciones.py` | Colecciona TdR o secciones |
| `run_nlp_piloto.py` | Extracción LLM + elegibilidad |
| `run_elegibilidad.py` | Solo elegibilidad sobre NLP ya guardado |
| `run_match.py` | Ranking híbrido docente ↔ convocatoria |
| `run_matching_tests.py` | Smoke tests del matching |

Ejemplo:

```bash
cd convocaur
set PYTHONPATH=src
python scripts/run_match.py --convocatorias 45,48,976
python web/api.py
```
