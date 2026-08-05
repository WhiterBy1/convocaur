# Design

<!-- impeccable:design-schema 1 -->

## World

**Expediente desk** — light Operate UI for a Rosario research-office desk: warm seashell paper, French Blue stamp accent, Merriweather + Source Sans 3, folder/blotter rhythm.

Seed: `0d9367fd` · assigned grounded #6 · mode Operate.

## Surfaces

- **Home:** brand-led first viewport + status expediente (SECOP / Matching).
- **SECOP:** tabs Tendencias / Mercado / Predicción — findings + charts.
- **Matching:** tree/graph + sync; same tokens.

## Color

Strategy: Restrained. Palette: Seashell / Wheat / Powder Blue / French Blue / Midnight Violet.

| Token | Value | Role |
|-------|-------|------|
| `--bg` | `#FFF4EB` Seashell | Paper ground |
| `--bg-elev` | `#fffaf5` | Raised sheets |
| `--ink` | `#3D1534` Midnight Violet | Body / titles |
| `--muted` | `#6a5a68` | Secondary |
| `--accent` | `#3E4B8E` French Blue | Primary actions, focus |
| `--powder` / charts | `#A6BCC9` | Chart series 2 |
| `--wheat` | `#F6E0B6` | Soft highlight |
| `--coral` | `#8b3a4a` | Warnings / weak models |

## Typography

**Boldonse** for hero/section titles; **Merriweather** for panel headings; **Source Sans 3** for UI/body/numbers. Accent: French Blue `#3E4B8E` (no red pop).

## Components

- Primary button: filled French Blue on seashell.
- Ghost button: elevated sheet + line.
- Tabs: underline accent, no pills.
- Panels: open border-top on page; `panel-rosario` = elevated sheet with soft shadow.
- Charts: French Blue / Powder / Midnight / coral; light tooltips.

## Motion

Short fades on home entry (~0.45–0.55s). No page-load choreography. Graph settle only.

## Anti-references

Dark neon dashboards; purple SaaS gradients; cream+terracotta editorial; nested card grids; eyebrow kickers.
