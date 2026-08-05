# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: staff and researchers at **Universidad del Rosario** (Vicerrectoría / research office) who must decide which Minciencias convocatorias and SECOP CTeI opportunities to pursue, with whom (docentes), and how the market is moving.

Secondary: ServiSquad / challenge evaluators reviewing the three capacidades of the reto.

*(Assumed from repo + conversation; not re-interviewed.)*

## Product Purpose

**ConvocaUR** turns public SECOP CTeI procurement data and Minciencias TdR into an actionable workspace: market diagnosis (Cap.1–3), Rosario-centric network insights, and docente↔convocatoria matching with eligibility.

Success: a research manager can open the app, see where Rosario sits in the market, and leave with a shortlist of convocatorias + matching faculty without reading raw CSVs.

## Positioning

Not a generic SECOP dashboard. The differentiator is **Rosario as the analytical anchor** (ego-network, competitors, eligibility_urosario, HUB/CvLAC docentes) wired to matching—not national vanity metrics alone.

## Operating Context

- Desktop-first internal tool; Spanish UI copy.
- Data lives on the filesystem under `data/processed/` served by FastAPI; frontend is Vite/React.
- Heavy views: force graphs, Recharts time series, matching trees, forecast demos.
- Sessions are task-oriented (scan → drill → act), not marketing.

## Capabilities and Constraints

- Tabs/routes: Home overview, SECOP (3 capacidades), Matching (sync Minciencias + rankings).
- Cap.2 network is a navigable sample + Rosario ego, not full SECOP graph in-browser.
- Cap.3 market forecast is precomputed TS; process ML is an optional demo.
- Do not invent SECOP figures, AUC scores, or eligibility verdicts—render from API/JSON only.
- Stack (incumbent): React + Vite + TypeScript, FastAPI backend, Recharts, react-force-graph-2d.

## Brand Commitments

- Product name: **ConvocaUR**.
- Institutional subject: Universidad del Rosario / Colegio Mayor Nuestra Señora del Rosario.
- Voice: direct, technical-but-clear Spanish; findings over essays (user preference).
- Binding avoidances from product owner + harness rules: no purple-indigo SaaS gradient look; no Inter/Roboto/Arial defaults as display; no nested card dashboards; findings-first Cap.3; graphs must stay readable.

## Evidence on Hand

- Processed SECOP dashboard JSON, Cap.2 Rosario analysis, Cap.3 forecast artifacts.
- Minciencias NLP + matching rankings under `data/processed/`.
- Docs: `docs/arquitectura.md`, `docs/capacidad_urosario.md`, README.

Do not fabricate testimonials, logos beyond what exists in-repo, or fake KPIs.

## Product Principles

1. **Rosario first** — every market view should answer “what does this mean for UR?”.
2. **Findings over prose** — lead with numbers and charts; methodology in details.
3. **Honest scope** — label samples, bands, and weak models; never dress uncertainty as precision.
4. **Operate, don’t decorate** — scanability and consistent controls beat visual novelty.
5. **One job per section** — no hero clutter; dashboards stay task-shaped.

## Accessibility & Inclusion

Target WCAG AA contrast for body text; keyboard-focusable controls; Spanish as primary language. No product-specific AT requirement documented beyond that.
