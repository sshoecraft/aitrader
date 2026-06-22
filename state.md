# aitrader — Living State

_Last updated: 2026-06-20 (1.6.0 — IBKR gateway merged back IN as the bundled
`gateway/` subdir; `./install.sh --broker ibkr` sets it up. 1.2.0 — default dashboard
ports → 2499/2500, ui_port now its own setting. 1.0.0 packaged as a shippable product:
`install.sh`/`uninstall.sh`, snapshot on a systemd timer. Live in production on paper
since ~0.13.)_

## What this is
Persistent autonomous AI trader (paper). The AI is the entire decision-maker;
this repo is infrastructure only. See `CLAUDE.md` (constitution) and `BRIEF.md`
(founding mandate).

## Locked decisions (§10, as amended)
- **Runtime/persistence:** **ccloop** (SUPERSEDES the original "long-lived resumed
  session" choice). Never-stop via ccloop's Stop hook; on context-fill → FRESH
  session relay (not compaction); state carried by journal + broker reconcile.
- **Asset scope:** multi-asset (stock/crypto/futures/forex).
- **Fuses:** kill switch = `systemctl stop aitrader` (option a) + paper-only. No notional/BP caps.
- **Broker:** IBKR paper (`ibkr_port=4002`) for EXECUTION. Reuse ABC + IBKR
  method bodies; clean-room the connection ownership (§A.3).
- **Data feed (0.11.0):** optional `data_broker=alpaca` fronts IBKR for
  stock/crypto bars+snapshots (live pre-market tape; IBKR paper returns nothing
  pre-open). `BrokerRouter` routes data→Alpaca, execution/account/fills→IBKR.
  Mirrors `/src/trader`'s data_broker split. See `docs/broker-data-feed.md`.
- **Model:** single model, NO tiering (Max 5x sub); run-dir `.claude/settings.json`;
  Fable when available. **Cadence:** agent-chosen + 5s floor (scheduler).
- **Config:** settings.toml only, no env vars. **Install:** `~/.local`, never `/src` (NFS).

## Build phases
- [x] **Phase 0 — Infrastructure tool servers + harness** (code complete; live broker
      run pending a gateway — see Environment gaps)
  - [x] Project scaffold (pyproject, package, paths, credentials, hygiene docs)
  - [x] Clean-copy pure primitives: `asset_types.py`, `broker.py` (ABC), `timeutil.py`
  - [x] `journal` MCP — notebook + positions-of-record + equity + orders-of-record
        (idempotency). **12 tools, unit-tested.** (`docs/journal-mcp.md`)
  - [x] `aitrader/brokers/ibkr_connection.py` + `ibkr_pool.py` — clean-room connection
        ownership (§A.3): each pool owns its thread + asyncio ib_async pump; paper fuse.
  - [x] `aitrader/brokers/ibkr.py` — `IBKRBroker`, reused method bodies, `client_tag`→
        `orderRef` idempotency, cognition stripped. (`docs/broker-ibkr.md`) + `futures.py`
  - [x] `aitrader/market_calendar.py` — clean-room multi-tier resolver
  - [x] `broker` MCP — 31 tools, owns its connection, graceful no-gateway. (`docs/broker-mcp.md`)
  - [x] `scheduler` MCP — 6 tools, blocking waits, chunked/cancellable, floor fuse. (`docs/scheduler-mcp.md`)
  - [x] fuses: paper-only (broker adapter). [HALT-file kill switch removed 2026-06-17 — kill = exit the session / `systemctl stop`.]
  - [x] `harness/loop.py` — drives `claude -p` (opus_reviewer pattern), resume-on-crash,
        session persistence, reconcile-on-wake via prompt. (`docs/runtime.md`)
  - [x] stub agent prompt + bounded smoke prompts
  - [x] **3 MCP servers launch + handshake over stdio (49 tools total)**
  - [x] **Live harness↔claude bridge proven:** bounded smoke test drove `claude -p`
        through scheduler+journal MCP tools, persisted a journal entry, exited rc=0 ($0.40).
  - [x] **Live capstone:** harness→`claude -p`→broker MCP reconciled the live paper
        account (DU0000000) + journaled, rc=0. The full loop works against real paper.
  - [x] **Exit criterion (§A.5) DEMONSTRATED:** stub looped unattended (reconcile→
        journal→wait→repeat) against live paper; killed mid-loop + relaunched →
        reconciled from truth + journal and continued. Found & fixed a session-id
        persistence bug (now saved on the init event, survives a harness kill).
        Full multi-hour soak left to ops; mechanism proven.
- [x] **Phase 1 — Constitution + first skills** (`prompts/constitution.md`, `skills/`)
- [x] **Account clean slate:** inherited forex residue flattened to USD (flat).
- [x] **Runtime = ccloop** (v0.3.0): custom harness DELETED; config → settings.toml
      (no env); installed to `~/.local` (never `/src`/NFS). See `runtime-ccloop` memory.
- [x] **Phase 2 — First light** — DONE. Live on paper (IBKR `DU0000000` + an Alpaca
      node), ccloop in tmux on the subscription, dashboard up. The full loop
      (reconcile→orient→decide→act→journal→wake) runs unattended; relay across
      context-fill proven.
- [x] **Phase 3 — Product packaging (1.0.0)** — `install.sh`/`uninstall.sh` front
      door (wizard + non-interactive), default port block 2499/2500 (was 7500/7501 pre-1.2.0), equity snapshot
      on a systemd timer (was cron), UI de-drifted to `ui/` + `~/.local/share/aitrader/ui`.
      IBKR gateway server first extracted to a separate repo, then (1.6.0) **merged back
      in as the bundled `gateway/` subdir** — lockstep release model; `./install.sh
      --broker ibkr` sets it up. README + LICENSE added. Still paper-only (`allow_live=false`).

## Environment — RESOLVED, live against paper
- **Installed to `~/.local`** (`make build && make install`): package in
  `~/.local/lib`, MCP scripts + `aitrader` wrapper in `~/.local/bin`, prompts/
  skills/run-dir in `~/.local/share/aitrader`. NO venv, nothing runs from `/src`.
- Config: `~/.config/aitrader/settings.toml` (wake_floor, allow_live, paths — no env).
  Model in run-dir `.claude/settings.json`. Secrets in `secrets.toml`
  (host 127.0.0.1, port 4002, client_id 40, account DU0000000).
- Runtime: **ccloop** via the `aitrader` launcher (reads criteria/task/cutoff from
  settings.toml, resumes latest `.ccloop/runs/` on restart). Run dir
  `~/.local/share/aitrader/run/` = CLAUDE.md (constitution) + .claude/settings.json
  (model); the 3 MCP servers are registered at user scope in `~/.claude.json` (not
  a run-dir .mcp.json).
- **Billing-safe runtime (ccloop 0.5.0+):** ccloop NEVER uses headless `claude -p`
  implicitly — it requires an explicit `--headless --accept-api-cost`, else it runs
  the interactive TUI (subscription) on a TTY and **refuses** with no TTY. So the
  service `systemd/aitrader.service` runs ccloop **inside tmux** (dedicated socket
  `-L aitrader`) to supply a PTY → interactive → subscription. Attach the live agent
  with `tmux -L aitrader attach`. Stop = `systemctl --user stop aitrader`.
- **Service stack (all `--user`, all enabled, lingering on → auto-start at boot):**
  `ibgateway` (broker=ibkr only; from the bundled **`gateway/`** subdir) →
  `ibgateway-ready` (oneshot readiness gate: blocks until the gateway API accepts a
  login, `bin/aitrader-gateway-wait`) → `aitrader` (agent, in tmux),
  `aitrader-api` (dashboard API, default :2499, client 80/90/100), `aitrader-ui`
  (default :2500, `After=aitrader-api`), `aitrader-snapshot.timer` (equity recorder).
  _(Deployed instances keep whatever ports are in their settings.toml until redeployed.)_
  The readiness gate exists because `After=ibgateway` only
  waits for the gateway *process*, not its ~10-90s login → connecting early caused
  an `Error 326` reconnect storm that wedged the dashboard after a reboot (v0.6.2).
  Service `aitrader.service` also needs `Environment=PATH=~/.local/bin:…` (v0.6.1)
  since the user-manager PATH omits it (else `execvp("ccloop")` fails → crash-loop).
- **IB Gateway (paper) co-located on clyde** as `ibgateway.service` (IBC 3.23.0 +
  GW 1044, headless Xvfb). `infra` decommissioned (its gateway stopped + disabled).
- **Live verified** (pre-ccloop): broker MCP connects, paper fuse confirms DU0000000,
  account/positions/orders flow; MCP servers handshake from `~/.local` installed scripts.
- ✅ **ccloop end-to-end proven in production:** ccloop loads the run dir's CLAUDE.md
  + user-scope MCP servers and drives the agent through full cycles, live on paper.

## Reuse provenance (from /src/trader — infra only)
- `broker.py` (ABC), `asset_types.py` — copied verbatim, imports renamed.
- TODO: `ibkr.py` method bodies, `market_calendar.py` resolver, `db.py` journal subset.
- NEVER port: `risk.py`/`check_risk_limits`, `compute_order_prices`, screeners,
  scoring, strategies, reviewers, indicator-gates.

## Next action
1. **Test-user install (clean-room product check)** — as a fresh user with no IBKR:
   `./install.sh -y --broker alpaca --alpaca-key … --alpaca-secret …`, enable the
   services, confirm `/status` connects on :2499, UI on :2500, no `ibgateway*`
   units, no `ib_async` pulled. Then `./uninstall.sh`. (See the plan's verification.)
2. **Stand up the bundled `gateway/`** for real on the IBKR node via
   `./install.sh --broker ibkr` (fills `~/ibc/config.ini`, enables `ibgateway`) so the
   dev box's broker=ibkr path has a live gateway.
3. Iterate on `prompts/constitution.md` + `skills/` from observed behavior —
   NEVER by adding decision code (BRIEF §8). Edit source, reinstall to redeploy.

(Done in 1.0.0: installer, port block, snapshot timer, gateway extraction, **Makefile
realigned with install.sh** — UI from `ui/`, serve dir `aitrader`, no gateway unit,
snapshot timer, broker-scoped pip extras.)

## Infra topology (durable)
- Gateway + brain co-located on **clyde** (this node). `infra` (QNAP VM) is out of
  the loop; its `ibgateway.service` is stopped + disabled.
- Gateway: `ibgateway.service` (system unit) → IBC `~/ibc` → GW `~/Jts/ibgateway/1044`,
  headless Xvfb, localhost API on 4002, TrustedIPs=127.0.0.1.
- aitrader has passwordless sudo on clyde (granted for gateway upkeep).
