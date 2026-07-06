# aitrader — Living State

_Last updated: 2026-07-06 (1.32.3 — **step 9 PROTECT hardened: a `pending_cancel` is NOT a stop.**
MSFT sat NAKED ~4 days while the agent reported "stop 386 (pending cancel)" every cycle — the 07-02 stop's
cancel jammed in Alpaca `pending_cancel` (reserved the 76 shares → replacement rejected; also matched
9(b)'s status-blind (symbol,side,qty) test → counted as protection, never replaced). Price bled through
386 to 384 (−$400). Fix: 9(b) MATCH → a FORCED TABLE with a STATUS column + WORKING? judgment; only
new/accepted/held count; pending_cancel/canceled/replaced/rejected/expired/filled = NONE → place fresh.
9(c) gains the blocked-shares edge (NAKED — BLOCKED by stuck order, retry); 9(d) VERIFY requires a WORKING
stop id. Manually placed the missing stop `sl_msft_20260706_1` @ 380.50 (under 07-06 session low 381.33),
order a054da8d status=new. Deployed via make const. See [[stop-verify-must-check-order-status]].
1.32.2 (07-04) — symbol sanitizer (`asset_types.clean_symbol`) absorbs the vLLM last-arg trailing-backtick
that wedged the agent in a `BNB/USD\`` get_snapshots reject loop; applied to every symbol arg in broker +
journal MCP. See [[vllm-gemma-trailing-backtick-lastarg]].
1.32.1 (07-04) — HISTORY step-7 check: fakeable prose line → FORCED TABLE (cells pasted from
transactions_read); killed the "no recent activity" escape. Surfaces history, never gates.
1.32.0 — **transaction-history ledger the agent can read by symbol + timeframe.**
Churn root cause (XRP: ~$1k lost re-buying a just-stop-churned name, then re-buying it AGAIN next cycle):
the agent has NO memory of its own executions — journal is prose, orders_of_record had 15 rows for 548
fills, positions_of_record purged to 0. New `transactions` table (journal_db 0.2.0): one row per broker
FILL, PK fill_id, idempotent upsert. `sync_transactions` (broker MCP 0.7.0) mirrors the broker fill stream
into it — incremental + throttled (≤1/45s), backfills the broker's ~30d, then persists beyond it; reason =
agent's recorded intent OR a factual exit label (stopped out/take profit/manual), NEVER computed P&L.
`transactions_read(symbol, since, limit)` (journal MCP 0.2.0) = the agent's own trade history, newest-first.
Constitution: step-7 neutral HISTORY line before any (re-)entry (REPORTS the recent buy/sell sequence, does
NOT gate — re-entering a churned name is the agent's call, §2); step-5(c) points at transactions_read;
Placing-an-Order step 1 records structured intent (the reason source). NO FIFO/P&L/win-rate by design — the
raw sequence is the signal. Deploy: make build+install (broker/journal code) + make const + restart. Agent
was HALTED during this build; XRP position left as-is per user. Clean test of "missing feedback loop vs model
ceiling." Deploy + end-to-end verification PENDING as of this write._

_Prior: 2026-07-03 (1.28.0 — weekend = PRICED CONDITION, not calendar veto. First live 1.27.0 cycle
used the card as a blanket veto (one citation for five names, no step-4/7 numbers — the 1.10.0 failure
mode), and the user challenged the veto's premise: crypto is 24/7 and THIS agent can watch all weekend;
the account's own data shows NO weekend-entry penalty (Sat 41%/−$2.4k, Sun 47%/−$0.2k vs Mon 53%/−$4.2k,
Wed 40%/−$6.0k). card-crypto weekend paragraph rewritten (qualifying Saturday setup = qualifying setup;
demands structural stop + staying on watch); action-clause closer (card sharpens step-4/7, never replaces);
constitution step 11 gains the off-hours leash: holding crypto → never sleep past ~2h, around the clock;
only a flat book earns a long sleep. Deploy: make const both nodes + card copy/index-clear/restart.
1.27.0 — constitution step 7 gains the **CARD LINE** sub-step: first carded-class
entry per session forces `memory_get` of the class card, and EVERY carded entry (crypto/forex/futures/
options/leveraged-ETP) must write `CARD <class>: "<card line arguing hardest AGAINST this trade>" — <why it
survives / evidence that overrides>` before placement; no line = step-7 failure; memory error → line says so
and trade proceeds. Step 10 journals the line; step A now points at the enforcement (its prose rider was
proven dead — zero card reads in atrader's journal, per the step-not-prose doctrine). Deploy: make const on
both nodes; atrader needs install.sh first for the 1.26.0 card. Verify: next carded entry renders the line.
1.26.0 — card-crypto now carries the predecessor's autopsy: the 6.7% crypto
win rate's three causes (recovery-chasing in broken structure; re-entry after stop-outs — the single
biggest documented loss source; sub-1% noise-harvester stops) + the weekend-ENTRY corollary incl. Alpaca
stop-LIMIT gap-through risk. Trigger: atrader bought ~$20k BTC+SOL (~31% of equity) Friday 13:23 ET into
the July-4 long weekend on a "confirmed recovery" thesis with 0.6%/1.1% stops — and the journal shows no
card-* was ever read (step-A prose rider doesn't bind the local model). Proposed to user, NOT applied:
constitution forced card-read artifact at first entry per class per session. Deploy: install.sh on the
atrader node overwrites the card (canon).
1.25.0 — IBKR forex/futures availability now from REAL contract hours:
`get_available_types` gates both flags on the live tradingHours windows of representative contracts
(EUR/USD IDEALPRO; ES front month) via `parse_trading_hours`, cached per (class, ET date), weekday-math
fallback only when the gateway can't answer. Verified live against the paper gateway on the holiday:
futures window ends 13:00 ET (CME halt) from the broker's own string; SPY session gate returns closed.
Deploy: make build+install + restart broker MCP/api on the IBKR node.
1.24.0 — holiday-aware market sessions. Found live: on the observed-July-4
holiday BOTH nodes reported stocks open — `get_market_session` was pure weekday math on both drivers (the
old trader's Alpaca-clock dependency was dropped in the clean-room port and holiday awareness went with
it). Both drivers now gate the clock math on their OWN calendar (Alpaca /v2/calendar 0.5.0, IBKR SPY
liquidHours 1.3.0; cached per ET date; weekday-math fallback only when the calendar is unreachable, never
cached), holidays are `closed` with no extended windows, half-days end regular at the true early close.
market_calendar 0.2.0: NOT_TRADING_DAY sentinel — a library-confirmed holiday returns None instead of a
fabricated weekday-16:00 close, so `market_status` and `wait_until_session_close` are holiday-correct.
IBKR session methods are routed-async with undecorated body helpers (route_to must not re-enter). Deploy:
make build+install + restart broker MCP/api per node. See docs/market-calendar.md + CHANGELOG 1.24.0.
1.19.0 — new `make const` target: deploys `prompts/constitution.md` → run-dir
`CLAUDE.md` + restarts aitrader (constitution-only, mirrors make api/ui; does NOT touch settings/model/MCP
like make run-dir). The constitution deploy command going forward.
1.18.0 — constitution step 9 PROTECT gains a **(e) TRAIL WINNERS** pass:
every position green since entry must have its stop ratcheted UP under the most recent higher-low/MA
(`modify_order`), forced artifact `old → new → structure-level`. Locks in profit via the stop (no TP —
a fixed target is the §8-banned injected logic); closing line reframes a profitable stop-out as SUCCESS,
not the cash-is-failure. Driven by both models holding multi-% winners on entry-era stops and never
selling for a profit. Deploy: `make const`. See ccmemory `constitution-stops-and-tool-mechanics`.
1.17.0 — journal feed renders **Markdown**: `JournalFeed` now uses
react-markdown + remark-gfm (GFM tables), so the agent's survey/ranking tables render as real tables
(monospace, horizontal-scroll on the narrow rail) instead of raw `|`-pipes. UI 1.5.3→1.6.0; `make ui`.
1.16.1 — fix: VTI benchmark line vanished off-hours. The 1.16.0 `/benchmark`
emitted bar `t` as a bare epoch int, but the UI's `dayKey()` parses the session by leading `YYYY-MM-DD`,
so off-hours "Mode B" session grouping kept 1 bar → no line. api.py 0.6.1 now emits `t` as an ISO-UTC
string (drop-in for the broker `/bars` format); API-only redeploy, UI unchanged.
1.16.0 — dashboard VTI benchmark is now **broker-independent**: new
`GET /benchmark` (api.py 0.6.0) pulls VTI from Yahoo's keyless v8 chart endpoint, RTH-only, cached, keyed
on chart period; UI Header fetches it instead of broker `/bars`. Fixes atrader (+0.43%) vs itrader
(+0.05%) showing different VTI% for the same timestamp — broker-sourced VTI rebased to different feeds —
and works on IBKR-only nodes. See ccmemory `benchmark-broker-independent-yahoo`.
1.15.0 — constitution gains an explicit **step 9 PROTECT** (JOURNAL→10,
WAKE→11): every cycle, every position must carry a VERIFIED live GTC stop-market, after the live gemma
agent held a 1.83x book overnight with 2 of 9 stops and then confabulated "all protected." Mandates a
stop's EXISTENCE (agent still picks the price) — not the reverted 2026-06-18 stop *level* mandate; see
ccmemory `constitution-stops-and-tool-mechanics`. Deploy per node with `make run-dir`.
1.14.0 — Alpaca node sector classification: `AlpacaBroker.get_classification`
sources `{sector, industry}` from Yahoo's keyless quote-search endpoint, fixing the dashboard "By Sector"
donut that bucketed every atrader position as "Unclassified" (Alpaca's API has no fundamental data, and
only IBKR previously implemented `get_classification`). See ccmemory `alpaca-sector-via-yahoo-search`.
1.12.0 — the constitution's whole DISPOSITION is now a forced-artifact
PROCEDURE, not prose. After 1.10.0 (fusion) deployed and itrader STILL refused to trade — surveyed
at the index level, wrote "0 candidates" without pulling names, defaulted to HOLD, confessed "I'll
make it on your word" — the lesson landed: models execute numbered STEPS with a required output and
ignore PROSE they merely agree with. `prompts/constitution.md` rewritten as THE LOOP (steps 0–10),
each producing an artifact you can't skip: REGIME+catalyst-scope, a SURVEY table (≥5 names+numbers,
missing row = can't sleep), a per-holding YES/NO re-justify verdict, and a GATE (deploy ANY settled
cash a ranked candidate beats / margin is a tool / to HOLD you must write the disqualifying NUMBER —
"wait/settle/catalyst" without a number is not permitted). 13 principles demoted to "lenses inside
the steps"; tool-mechanics block preserved byte-for-byte; 1.11.0 — buying power + real unsettled cash
on the Allocation panel + /status (IBKR SettledCash) + positions CLI fix. See `docs/trading-knowledge.md`
§1.12.0 + ccmemory `constitution-steps-not-prose`. 1.10.0 — fused the agent's trading guidance into ONE disposition
voice. An audit found 11 of the 16 `lesson-*` notes were duplicates of the 12 constitution
principles, and the two channels carried 9 action-vs-caution SEAMS the live agent (Opus)
kept resolving toward inaction (it sat in 36% cash through an opening bell and "settled" by
sleeping 25 min). Fix: collapsed each seam into one both-halves directive (action first,
caution as the bound), folded the 11 duplicates into ~13 principles (added a time-of-day/
horizon principle), kept only the 5 genuinely asset-specific notes as on-demand `card-*`
(crypto/forex/futures/options/leveraged-etp), rebalanced toward action (every "cash is
legitimate" bound to a survey test), and switched journal prose to LOCAL time
(`now().local`; ET retained as the NYSE session clock). `install.sh` now removes the 16
retired notes + overwrites cards on install (a `git pull` + `./install.sh` migrates an
existing store). See `docs/trading-knowledge.md` §1.10.0. 1.9.0 — forex/futures are surveyable again: `get_tradeable_assets`
now enumerates the major IDEALPRO pairs (`FOREX_UNIVERSE`) + every `FUTURES_SPECS` contract
(was `[]` — the old screener that backfilled the universe was correctly deleted as cognition
but never replaced); `reqMarketDataType(3)` delayed fallback so paper/unsubscribed snapshots
return quotes not all-zeros; `EUR.USD` TWS dot notation normalized to `EUR/USD`. The forex
contract/order/position plumbing itself was verified a faithful, complete port of
`/src/archive/trader` — not the bug. 1.8.0 — seeded the agent with mined trading wisdom: a
12-principle judgment core in the constitution + ~16 ccmemory `lesson-*` notes; FULL
anti-passivity rebalance (trade quality dominates activity); contamination wipe of agent
memory+journal on both nodes. See `docs/trading-knowledge.md`. 1.6.0 — IBKR gateway merged back IN as the bundled
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
