# Deploy ConvocaUR (Vercel + Fly.io)

## Arquitectura

| Pieza | Plataforma | URL típica |
|-------|------------|------------|
| Frontend (Vite/React) | **Vercel** | `https://….vercel.app` |
| API (FastAPI) | **Fly.io** | `https://convocaur-api.fly.dev` |

El front usa `VITE_API_URL` en build para apuntar al API.

## 1. Backend en Fly (una vez)

En una terminal **interactiva** (PowerShell fuera de Cursor, o Cursor con TTY):

```powershell
cd c:\Users\jquin\Documents\ServiSquadReto\convocaur
$env:Path = "$env:USERPROFILE\.fly\bin;$env:Path"

flyctl auth login
flyctl apps create convocaur-api --org personal   # si aún no existe
flyctl deploy
```

Comprobar:

```powershell
curl https://convocaur-api.fly.dev/api/health
```

Secretos opcionales (solo si vas a correr matching/ingest en vivo):

```powershell
flyctl secrets set OPENROUTER_API_KEY=sk-...
```

## 2. Frontend en Vercel

```powershell
cd c:\Users\jquin\Documents\ServiSquadReto\convocaur\frontend
vercel link   # primera vez
vercel env add VITE_API_URL production
# valor: https://convocaur-api.fly.dev
vercel --prod
```

O en un solo comando:

```powershell
cd frontend
$env:VITE_API_URL="https://convocaur-api.fly.dev"
vercel --prod --yes --env VITE_API_URL=https://convocaur-api.fly.dev
```

## 3. Archivos de deploy en el repo

- `Dockerfile` + `requirements-api.txt` + `.dockerignore` + `fly.toml`
- `frontend/vercel.json` (SPA rewrite)
- `frontend/src/lib/api.ts` lee `VITE_API_URL`

## Notas

- La imagen Docker incluye `data/processed`, profesores JSON y modelos Cap.3 (`.joblib`).
- No mete PDFs Minciencias ni cache de embeddings (regenerables).
- VM Fly: 2 GB RAM (LightGBM + pandas).
- CORS del API ya permite cualquier origen (`*`).
