# ui — the aitrader dashboard frontend

`ui/` is the React + TypeScript + Vite single-page app for aitrader. It is part of
this one project (not a separate repo) — just the frontend half, the way
`aitrader/` is the backend half. It is a **read + mechanical-control** surface over
the dashboard API: it shows account, positions, orders, the equity curve, and the
agent's own recorded rationale, and offers mechanical actions (close a position,
cancel an order, edit settings). **No trading cognition lives here** (CLAUDE.md §2,
the hard boundary) — the UI only displays what the agent decided and the broker
reports.

## Journal markdown rendering

JournalFeed renders each entry via react-markdown + remark-gfm. The agent
often opens a GFM table on the line directly after a section label
("REVIEW:") or inside a list item ("- GATE:"); remark-gfm treats those pipe
rows as lazy paragraph continuation and renders run-on text. `normalizeTables`
(JournalFeed.tsx, 1.42.2) inserts a blank line at every pipe/non-pipe boundary
before the text reaches ReactMarkdown so tables always parse as their own
blocks. Do not remove it, and do not "fix" this by prompting the agent to
journal differently — the DB body is the record (and is correct); this is
purely display normalization.

## How it connects to the backend

- The SPA talks to the dashboard API (`aitrader/api.py`, the `aitrader-api`
  service) over HTTP.
- The API base is injected at **runtime** via the static server's `/config.js`
  route (`window.__API_PORT__` / `__API_HOST__`), so the same build points at any
  API port with no rebuild. Default API port **2499** (`aitrader/config.py`);
  fallback in `ui/src/api.ts` is also 2499. See `docs/api.md` for endpoints.

## Build & serve

- Built + deployed by the top-level `./install.sh` (copies prebuilt `ui/dist` →
  `~/.local/share/aitrader/ui`, installs `ui/bin/trader_ui`) or `make ui` from the
  repo root. `cd ui && npm run build` produces `dist/`.
- Served by **`ui/bin/trader_ui`** — a small stdlib `http.server` that serves the
  SPA (with index.html fallback) and emits `/config.js`. The `aitrader-ui` launcher
  (`bin/aitrader-ui`) execs it with `--port`/`--api-port` from `settings.toml`; the
  `aitrader-ui.service` systemd unit runs that launcher. There is no separate UI
  service or build — those are the top-level units/installer.

## Source layout (`ui/`)

```
src/
  main.tsx            React entry point
  App.tsx             root component, data refresh loop
  api.ts              all HTTP calls + runtime API-base resolution
  types.ts            response interfaces
  App.css             styles
  components/
    Header.tsx        connection/equity/cash/P&L/heat + equity chart (VTI overlay)
    PositionsTable.tsx open positions (stop/limit/heat)
    OrdersTable.tsx   open orders
    TradesTable.tsx   fill history + realized P&L (period dropdown)
    LogPeek.tsx       tail of the agent's ccloop session log
    SettingsPanel.tsx dynamic settings editor (renders from /settings JSON)
bin/trader_ui         static server (SPA + /config.js port injection)
dist/                 built output (deployed to ~/.local/share/aitrader/ui)
public/  index.html  vite.config.ts  tsconfig*.json  package.json  node_modules/
```

Inert endpoints: aitrader has no screeners/strategies/analyze cognition, so those
tabs/calls return safe empties and the corresponding UI is dormant. `/review` is
*not* inert — it surfaces the agent's own recorded rationale (position-of-record +
journal entries).

## Equity chart VTI benchmark (Header.tsx)

Range selector: `1D / 1W / 2W / 1M / 3M / 6M / 1Y`. Each range maps to a
`portfolio_history` period (equity line, journal-backed via `portfolio_since` →
`PORTFOLIO_PERIOD_DAYS` in `api.py`) and a `/bars` `(start, timeframe)` pair for
the VTI overlay. **The VTI `/bars` start (`periodStartISO`) is NOT the equity
window** — for 1D it looks back 7 days, not to today's midnight, because Alpaca
returns bars only chronologically *from* `start` (a today-start yields ZERO bars
on a weekend/holiday); IBKR pads backwards so it tolerated the narrow start. The
extra lookback only feeds alignment + Mode-B session selection. Adding a range is front-end + (if a new day-window) one
`PORTFOLIO_PERIOD_DAYS` entry — no broker change, since `get_bars` on all three
brokers is driven by an explicit `start` ISO + timeframe, never a period name.

The masthead equity sparkline overlays a VTI benchmark (amber dashed). Equity
comes from `/portfolio_history` (journal snapshots, **24/7** because crypto runs
around the clock); VTI comes from `/bars` and only exists during equity-market
sessions. The two grids don't always overlap, so the overlay has **two modes**:

- **Mode A — windows overlap** (the normal case, incl. weekday intraday): VTI is
  sampled at each equity timestamp via nearest-bar (`alignBars`) and rebased to
  the first sample. It shares the equity x-grid, so the crosshair tooltip can
  report VTI% at every hovered equity point (`benchVals`).
- **Mode B — windows don't overlap** (1D on a **weekend/overnight**: equity is
  today's 24/7 crypto snapshots while VTI's latest bars are a prior session):
  nearest-bar would snap *every* equity point onto a single VTI bar → a flat 0%
  line hidden behind the (also-flat) equity line — the "VTI line missing on 1D"
  bug. Instead, plot VTI's own **most-recent session** (`lastSessionBars`) on its
  own time axis, rebased to that session's first bar, spanning the chart width.
  The VTI session is then resampled onto the equity x-grid (`resampleByX`) so the
  crosshair tooltip + amber dot still report a VTI% at the hovered screen position
  (matching the line at that x); the footer VTI% / Δ stats render too. Mode chosen
  by `windowsOverlap` (epoch-range intersection of the equity timestamps vs the VTI
  bars). Added in UI 1.4.3; Mode-B tooltip restored in UI 1.5.1.
