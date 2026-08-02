# Dashboard ConvocaUR

## Arquitectura

- **Frontend:** Node / Vite + React (`frontend/`) → http://127.0.0.1:5173
- **Backend:** FastAPI (`backend/`) → http://127.0.0.1:8000

## Arranque

Terminal 1 — API:

```bat
cd convocaur
set PYTHONPATH=src;backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

O `backend\lanzar.bat`.

Terminal 2 — UI:

```bat
cd convocaur\frontend
npm install
npm run dev
```

Abre http://127.0.0.1:5173

## Qué muestra

1. **Inicio** — panorama SECOP + matching  
2. **SECOP** — Cap. 1 (tendencias), Cap. 2 (mercado/HHI), Cap. 3 (modelos)  
3. **Matching** — grafo interactivo convocatoria → docentes → aportes al score  

Datos SECOP tipados: `data/processed/secop/resumen_dashboard.json`  
Rankings: `data/processed/matching/`
