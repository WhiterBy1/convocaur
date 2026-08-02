# backend/

FastAPI que sirve overview, SECOP Cap.1–3 y matching.

```bat
cd convocaur
set PYTHONPATH=src;backend
py -3.12 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> Cap.3 (predicción en vivo) requiere **Python 3.12** + `lightgbm` para cargar los `.joblib`.

Docs interactivas: http://127.0.0.1:8000/docs
