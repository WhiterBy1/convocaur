# scripts/

Puntos de entrada del pipeline. Todos agregan `../src` al `PYTHONPATH`.

| Script | Qué hace |
|--------|----------|
| `run_descarga.py` | Descarga anexos/TdR/resoluciones |
| `run_tdr_secciones.py` | Colecciona TdR (`python run_tdr_secciones.py`) o secciones (`… secciones`) |
| `run_nlp_piloto.py` | Extracción LLM + elegibilidad |
| `run_elegibilidad.py` | Solo elegibilidad sobre NLP ya guardado |

Ejemplo:

```bash
cd convocaur
set PYTHONPATH=src
python scripts/run_elegibilidad.py --convocatorias 48,45,976
```
