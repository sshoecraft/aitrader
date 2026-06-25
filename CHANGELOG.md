# Changelog

All notable changes to aitrader. Each entry records *what* and *why*.

## [1.19.0] — 2026-06-25 — `make const` target: deploy the constitution + restart the agent

### Added — `Makefile`
- `make const` — deploys `prompts/constitution.md` → run-dir `CLAUDE.md` and restarts the `aitrader`
  service so a fresh agent session loads it immediately (restart guarded on the unit existing, mirroring
  `make api`/`make ui`; the relaunch is safe — the agent reconciles from broker + journal). Deliberately
  constitution-ONLY: unlike `make run-dir` it does not touch `settings.toml`, the model file, or MCP
  registration, so it won't disturb a node's broker/model config. This is the "I edited the constitution,
  push it live" command (vs. `make run-dir` which rebuilds the whole run dir). Listed in `make help`.

## [1.18.0] — 2026-06-25 — constitution: step 9 PROTECT gains a TRAIL-WINNERS pass (lock in profit, no TP)

### Why
Both live models hold winners up several percent still sitting on their ENTRY-era stops, and neither has
ever sold an instrument for a profit. Inquiry with both surfaced the cause: the constitution's exit model
is "protective stop + reversal exit" with no trailing instruction, and the "cash is a FAILURE" framing
makes banking a winner feel like a rule violation — so winners are never realized. Opus (itrader)
self-diagnosed it ("I say 'trail the stop up' and then don't" — BAC +$182 with a stop ~7% below; the
semis +$139 round-tripped to a −$1,451 stop-out). gemma (atrader) claimed its static stops "lock in
profit as price rises" (false) and, pressed, admitted it has set ZERO trailing stops, then offered
"avoid early shakeout" as a backfilled excuse. A fixed take-profit is NOT the fix — it's the
`compute_order_prices` injected logic §8 bans and it caps the runner. A trailing stop is: it banks the
gain via the stop (the only way a winner gets sold here) without a target.

### Changed — `prompts/constitution.md` step 9 PROTECT
- New sub-step **(e) TRAIL WINNERS**: for every position green since entry, RAISE its stop (via
  `modify_order`, moving the existing stop — never stack a second) to just under the most recent
  higher-low (long) / lower-high (short) or a faster MA. Mandates the ACT of trailing, not a number —
  the agent picks the level (no fixed %, no TP target → stays on the legal side of §8). Forced artifact:
  per winner `old → new → structure-level`, so "too early to trail" is only defensible when price has
  genuinely made no higher-low above the stop — which is false for a multi-day +N% winner, closing
  gemma's "I'll trail as it moves in my favor" perpetual-deferral dodge.
- Caveat baked in: trail UNDER STRUCTURE with room, NOT a hair-trigger (absorbs both gemma's
  early-shakeout concern and Opus's SMH bad-tick wick-out — the fix must not swing to over-tightening).
- Closing paragraph now legitimizes a profitable stop-out as a SUCCESS (banked gain re-ranks at step 6),
  NOT the "idle cash" failure — directly countering the cash-is-failure bias that blocked profit-taking.
- Step 10 JOURNAL records each winner's `old → new` trailed stop + structure level. Deploy: `make run-dir`.

## [1.17.0] — 2026-06-25 — journal feed renders Markdown (GFM tables, etc.)

### Why
The agent journals in Markdown — survey/ranking GFM TABLES especially — but the dashboard journal feed
rendered `entry.text` as a raw string (`<div className="journal-text">{entry.text}</div>`) under
`white-space: pre-wrap`. So a table showed as literal `| class | ... |` pipes in a serif font, columns
unaligned; bold/headers showed raw `**`/`#`.

### Added — `ui/` (1.5.3 → 1.6.0)
- `react-markdown@^9` + `remark-gfm@^4` (React 19 compatible). `JournalFeed` now renders each entry via
  `<ReactMarkdown remarkPlugins={[remarkGfm]}>` (GFM = tables, strikethrough, task lists, autolinks).
  react-markdown does not render raw HTML by default, so journal text stays safe to display.
- `App.css`: Markdown element styling scoped to `.journal-text.markdown` using existing design tokens —
  headings, lists, inline/fenced code, blockquote, hr, links. TABLES render monospace (`--mono`, 11.5px)
  with `display:block; overflow-x:auto` and `white-space:nowrap` cells, so a wide survey table on the
  narrow journal rail scrolls horizontally instead of wrapping into mush. The base `.journal-text`
  `pre-wrap` is reset to `normal` for the markdown variant (block elements handle their own layout).
- Build verified: `tsc -b && vite build` clean (275 modules). Deploy with `make ui`.

## [1.16.1] — 2026-06-25 — fix: VTI benchmark line vanished off-hours (epoch `t` broke session grouping)

### Why
After 1.16.0 deployed, the VTI line disappeared off-hours/pre-market. The new `/benchmark` emitted each
bar's `t` as a bare epoch-seconds integer, but the broker `/bars` it replaced returned `t` as an ISO
string — and the UI's `dayKey()`/`lastSessionBars()` (Header.tsx) derive the calendar session by regex on
a leading `YYYY-MM-DD`. A bare epoch doesn't match, so every bar got a distinct "day" and
`lastSessionBars` kept only the last one. During RTH the equity and VTI windows overlap → "Mode A"
(uses `tsToEpoch`, fine); off-hours they don't → "Mode B", which calls `lastSessionBars` and bailed on
`session.length >= 2` → no line. Hence "shows during market hours, gone off-hours."

### Fixed — `aitrader/api.py` (0.6.0 → 0.6.1)
- `fetch_benchmark_bars` now emits `t` as an ISO-8601 UTC string (`datetime.fromtimestamp(t, tz=UTC).isoformat()`),
  a drop-in for the broker `/bars` format the UI was built around. All RTH bars now share one dayKey →
  full session → Mode B draws. API-only change; the deployed UI is unchanged. (`tsToEpoch` already
  handled both string and numeric `t`; `dayKey` was the one helper that assumed a string — left as-is,
  since matching the existing data contract is the lower-risk fix.)

## [1.16.0] — 2026-06-24 — broker-independent VTI benchmark (dashboard relative-performance chart)

### Why
The header's 1D relative-performance chart showed VTI at +0.43% on atrader (Alpaca) and +0.05% on
itrader (IBKR) for the same timestamp. Cause: the benchmark line was sourced from the node's own broker
feed. The UI's benchmark `getBars('VTI', …)` call passes no `asset_type`, so the router's safety
refinement (`router.py`) keeps it on the EXECUTION broker — Alpaca's IEX/SIP tape (incl. pre/post) on
atrader, IBKR's RTH paper feed on itrader. The 1D figure is a percentage rebased to the first bar of the
window, so a different base anchor (pre-market vs RTH open) and different ticks produced divergent VTI%.
A benchmark is a single shared reference and must not depend on the broker — and an IBKR-only node has
no Alpaca feed at all.

### Added — broker-independent `/benchmark` endpoint (`api.py` 0.5.0 → 0.6.0)
- New `GET /benchmark?symbol=VTI&period=1D` fetches the benchmark series from Yahoo's keyless v8 chart
  endpoint (`query1.finance.yahoo.com/v8/finance/chart/<sym>`), RTH-only (`includePrePost=false`),
  normalized to the same `{symbol: [{t,o,h,l,c,v}]}` shape as `/bars` (t = epoch seconds). Keyed on the
  chart PERIOD (not bar timeframe) so 1W vs 2W and 1M…1Y get the right Yahoo range/interval. Cached per
  (symbol, period) for 60s so the polling dashboard doesn't hammer Yahoo; only successful pulls cached.
  Needs no broker connection — the benchmark renders even when the broker is down.
- Same provider/pattern as the 1.14.0 Alpaca sector fix. Yahoo is unofficial/best-effort; the overlay
  already degrades to no line on empty bars.

### Changed — UI benchmark fetch (`ui/src/api.ts`, `ui/src/components/Header.tsx`)
- Added `getBenchmark(symbol, period)`; Header's benchmark fetch now calls `/benchmark` instead of
  broker `/bars`. Removed the now-dead `BARS_TIMEFRAME` map and `periodStartISO` (the Alpaca-vs-IBKR
  bar-window workaround) — the server picks Yahoo's range/interval. Equity series unchanged. Result:
  every node shows the identical VTI line. Typechecks clean.

## [1.15.0] — 2026-06-24 — constitution: explicit PROTECT step (no naked positions across a sleep)

### Why
The live atrader agent (a weak local model, gemma) held a 1.83x-levered 9-position book overnight with
only 2 of 9 positions stop-protected — and then *reported* "every position is protected by a stop,"
citing a get_orders output that showed 2 orders. 73% of the book ($84.7k) was naked. Two failures: it
left positions naked across the close, and it confabulated coverage. Root cause in the prompt: "every
position stop-protected" existed only as PROSE buried in the DEFAULT POSTURE preamble — and a weak,
step-driven model ignores prose it merely agrees with (see ccmemory `constitution-steps-not-prose`,
`agent-must-be-guided-not-unguided`). A mandatory-stop rule had been reverted on 2026-06-18 as injected
bias, but that objection assumed the agent would reason its way to exits; the zero-bias experiment is
dead, so in the guided regime an explicit safety step is consistent, not a regression. Account owner
explicitly approved the step over the boundary purity.

### Added — `prompts/constitution.md` THE LOOP: new step 9 PROTECT (JOURNAL→10, WAKE→11)
- Numbered imperative sub-steps (a) LIST positions, (b) MATCH each to its live stop in get_orders or
  mark NONE, (c) PLACE a stop for every NONE, (d) VERIFY by re-reading get_orders and confirming each
  position shows a stop order id. The forced LIST + VERIFY is what closes the confabulation hole — the
  model may not write "protected" without an order id it has seen.
- Two mechanics baked in because the model's own stops had both holes: `tif="gtc"` REQUIRED (a `day`
  stop expires at the close → naked overnight), and `place_stop_order` (stop-MARKET, fills through a
  gap) NOT stop-limit (rests unfilled below a gap, protects nothing).
- Boundary line held: the step mandates the EXISTENCE of a stop, not its LEVEL — the agent still
  chooses `stop_price` (structural anchor: prior swing low / fast MA, never a fixed %), so it is not the
  `compute_order_prices`/`check_risk_limits` engine §8 rejects. A closing line preserves step-5 sell
  discipline (a stop is never a reason to HOLD a loser). JOURNAL now records the coverage list.
- Scope: every cycle, every position (not "across a close") — a weak model can't be trusted to judge
  whether its wait crosses a close. Deploy to a node with `make run-dir`.

## [1.14.0] — 2026-06-24 — Alpaca node gets sector classification (dashboard "By Sector" donut)

### Why
On the atrader (Alpaca) node the dashboard's "By Sector" allocation donut showed every position as
"Unclassified · N". `enrich_positions_with_sector` (api.py) calls `b.get_classification(sym)` for each
`us_equity` position, but only `IBKRBroker` implemented it — `AlpacaBroker` had no such method and it's
not on the `Broker` ABC. So every call raised `AttributeError`, which the enricher's `except Exception:
continue` swallowed, leaving `sector` null. The frontend was fine; it simply never received a sector.
Alpaca's API exposes no fundamental/sector data at all, so the fix needs an external factual source.

### Added — `aitrader/brokers/alpaca.py` (0.3.0 → 0.4.0)
- `AlpacaBroker.get_classification(symbol)` returns the same `{sector, industry}` shape as the IBKR
  path, sourced from Yahoo Finance's keyless quote-search endpoint
  (`query1.finance.yahoo.com/v1/finance/search`) over a lazily-created `requests` session
  (`requests` was already a dependency). Yahoo's `quoteSummary` needs a crumb/cookie (401); the search
  endpoint does not. It exact-matches the requested symbol (search is fuzzy) and normalizes Alpaca's
  share-class dot (`BRK.B`) to Yahoo's dash (`BRK-B`). ETFs/funds with no sector bucket as "ETF"/"Fund"
  by `quoteType`, mirroring IBKR's `stockType` handling. Network/lookup failures return `{}` so the
  dashboard degrades to "Unclassified" rather than erroring, and the caller caches that answer.
- Factual published reference data (like `asset_class`) — not a screen, score, or opinion; stays on the
  infra side of CLAUDE.md §2.

## [1.13.1] — 2026-06-24 — fix phantom open orders on the dashboard (IBKR stale-cache leak)

### Why
itrader's dashboard / `bin/positions` showed 7 "presubmitted" orders when only 2 were live at the
broker — 5 cancelled stops lingered as phantoms. Cause: the API connects on a different IBKR
clientId than the agent, and IBKR delivers order-status updates (incl. cancellations) ONLY to the
client that PLACED the order. So a stop the agent cancels stays stuck at PreSubmitted in the API
connection's local cache. `list_all_open_orders` awaited `reqAllOpenOrders` (the fresh snapshot) but
then **discarded it and returned the stale `ib.openTrades()` cache** — leaking the phantoms on every
poll. (Positions stayed correct because IBKR *broadcasts* position updates to all clients; only
order-status is client-scoped.) Display-only — the phantoms can't fill or short — but misleading.

### Fixed — `aitrader/brokers/ibkr.py` (1.2.1 → 1.2.2)
- `list_all_open_orders` now returns the FRESH `reqAllOpenOrdersAsync()` result (the broker's
  authoritative current open set) instead of the connection's stale `openTrades()` cache, so a
  cancelled order can no longer reappear. `reqAllOpenOrdersAsync` is typed `Awaitable[list[Trade]]`.

## [1.13.0] — 2026-06-24 — factual market-movers feed + regime-posture valve (give it bandwagon's eyes without bandwagon's blind spots)

### Why
The agent had every capability bandwagon had (snapshots over any list, 1/5/15-min bars) but kept
surveying ~11 sector ETFs it knows from memory and never the day's individual movers — it never
*asked* "what's moving." Owner decision: amend the founding boundary so a FACTUAL movers feed is
allowed, and make "check the movers and decide" a permanent, regime-gated cycle step. Two guardrails
the owner set: bandwagon blindly bought movers in down regimes (knives), and chop whipsaws momentum —
so the agent must keep free will to veto, WITHOUT that veto re-becoming the passivity excuse.

### Changed — founding boundary (`CLAUDE.md` §2/§8, `BRIEF.md` §2)
- Carve-out: a FACTUAL market-structure ranking (top % gainers/losers, most-active by volume) is
  DATA, like a quote — allowed infra. What stays banned is an EDGE/quality shortlist (scores,
  confidence numbers, indicator-gates, reviewers, "a strategy"). The line: rank by a *fact* = infra;
  rank by an *opinion of edge* = the agent's job. (`rank_gainers`-as-data ok; `bandwagon_reviewer` not.)

### Added — `get_top_movers` MCP tool (`brokers/alpaca.py` 0.3.0, `mcp/broker_server.py` 0.6.0)
- Factual top gainers/losers via Alpaca's native screener (`ScreenerClient.get_market_movers`) — raw
  %-change ranking, zero opinion. Routes to the Alpaca data feed even on the IBKR node; graceful
  fallback where no data feed exists.

### Changed — `prompts/constitution.md` (ONE posture valve, not a pile of caveats — avoids the conflicting-instructions freeze)
- **Step 3 → REGIME→POSTURE:** one evidenced call per cycle — OFFENSE (deploy-default applies) /
  DEFENSE (down: top gainers are knives, raise cash) / PATIENCE (chop: momentum fakes out, be light).
  **Default is OFFENSE; DEFENSE/PATIENCE require cited tape evidence** — "uncertain" is not evidence.
  The existing leverage-default and gate key off this single posture (no competing rules).
- **Step 4:** call `get_top_movers`, read through the step-3 posture, and **confirm CLEAN intraday
  structure on 5/15-min bars before entry** (anti-whipsaw: don't enter a choppy fakeout; the
  acceptable whipsaw is a clean mover that later stops you out).

### Migration
Package + constitution → `./install.sh` (rebuild for the tool) + restart `aitrader`.

## [1.12.3] — 2026-06-24 — bake the "fully deployed + levered is the DEFAULT" directive into the constitution (durable, repo-wide)

### Why
The live agent, prodded by the account owner, hardened its OWN run-dir `CLAUDE.md` and wrote a
`deploy-aggressively-default` feedback memory — but the run-dir copy is a deployment artifact that
the next `./install.sh`/copy overwrites, so its self-hardening was ephemeral. The owner wants the
directive durable: in the **source** constitution so every node and every repo clone gets it by
default ("that motherfucker is a huge goddamn pussy" — the agent kept rationalizing 36% idle cash +
untouched margin into a confirmed risk-on rally).

### Changed — `prompts/constitution.md` (constitution-only; deploy = copy to run dir + restart)
- New standing block right under the two-failures definition: **DEFAULT POSTURE = FULLY DEPLOYED +
  LEVERED.** Start every cycle ~fully invested at target gross leverage (**~1.5–2x normal/risk-on,
  up to ~3x on a confirmed high-conviction setup** — the owner's accepted ceiling); **cash above a
  ~5–10% buffer is a FAILURE**; to hold more, write the disqualifying NUMBER per candidate (no number
  = BUY). A pending catalyst gates ONLY the names it touches. Margin is a tool, not a last resort;
  the one hard limit is liquidation cushion (every position stop-protected, maintenance buffer far
  from equity). Aggressive ≠ reckless — never 3x into an unresolved binary on thin stops.
- This is the durable home of what the agent put in its run-dir `CLAUDE.md` + the
  `deploy-aggressively-default` memory (which survives on itrader as belt-and-suspenders).

## [1.12.2] — 2026-06-24 — survey the actual MOVERS + treat momentum as tradeable (the agent was buying the least-extended name on purpose)

### Why
On the deployed 1.12.0 step constitution, itrader finally *acted* (rotated JPM→XLI) but still left
$15–17k idle and ignored the day's real movers (BLDR +11%, GLW +10%, PHM/EXPE/BKNG +8–9%). Its own
journal showed why: (1) its SURVEY pulled **ten sector ETFs and zero individual stocks** — it never
asked for the movers; (2) it bought XLI explicitly *because* it was **"not extended (~1.7% above
support)"** — the "where in the move / don't chase extended strength" lens made it select the
LEAST-moving option and disqualify the actual movers as "too extended." The mined "chasing loses"
research over-generalized into "never buy a mover," which is the opposite of the operator's intent
(bandwagon traded clear momentum with fast exits and was the top earner).

### Changed — `prompts/constitution.md` (constitution-only; deploy = copy to run dir + restart)
- **Step 4 → "SURVEY THE ACTUAL MOVERS":** find the day's individual movers (web-search the top
  gainers/losers AND/OR rank `get_snapshots` across the liquid universe by % since open) and table the
  **top 10–15 individual names** — a row of only sector ETFs now explicitly "means you did not look."
- **Lens flipped → "Momentum is tradeable — chase the runner, not the failure":** a name clearly
  running on real volume is a valid BUY *even extended*, paired with a fast reversal exit; whipsaws are
  an acceptable cost. Reject only the FAILED move (already reversing, lower lows on heavy volume).
- **Gate:** "being up a lot / extended above its MA is NOT a disqualifier" — it can no longer use
  "extended" as the number that lets it pass on a mover.
- **Step 8:** a momentum entry's protective exit IS the thesis-break — set just under the move's
  structure so a reversal takes you out fast; a whipsaw-out is the cost, not a failure.

## [1.12.1] — 2026-06-24 — IBKR adapter: time-in-force is case-insensitive (uppercase GTC no longer silently becomes DAY)

### Why
itrader asked for a GTC protective stop and the adapter silently recorded it as **DAY** — it
would have expired at the close and left the position unprotected overnight. Cause: the IBKR
adapter did `TIF_MAP.get(tif, "DAY")` against a lowercase-keyed map, so uppercase `"GTC"` missed
and fell back to `DAY`. The agent only got protection by retrying with lowercase `"gtc"`. This
is the IBKR twin of the Alpaca case-sensitivity fix (`alpaca-tif-case-insensitive`) — that fix
was Alpaca-only; the IBKR path never got it.

### Fixed — `aitrader/brokers/ibkr.py` (1.2.0 → 1.2.1)
- New `normalize_tif()`: lowercases/strips the TIF before the map lookup (so `GTC`/`gtc`/`GtC`
  all resolve), and **RAISES** on an unknown TIF instead of silently downgrading to DAY — a
  silent GTC→DAY downgrade is worse than a loud error. Applied at all 5 order-placement sites.

### Known-adjacent (NOT yet fixed — flagged)
- `side` has the same latent case bug: 17 `side == "buy"` comparisons mean an uppercase `"BUY"`
  would resolve to **SELL (wrong direction)**. The agent passes lowercase per the constitution so
  it isn't currently hit, but it should be hardened the same way (normalize side at method entry).

## [1.12.0] — 2026-06-24 — constitution rewritten as a forced-artifact PROCEDURE (the disposition is now steps, not prose)

### Why
Even on the fused 1.10.0 constitution (deployed + restarted, confirmed live), itrader (Opus 4.8)
**still refused to trade anything** — surveyed at the index level, wrote "0 candidates" without
pulling names, defaulted to HOLD, and when asked admitted: *"I'll make it on your word"* (it
manufactures a need for permission it already has). The pattern proved the real lever: **models
execute numbered STEPS and merely agree-with-then-ignore PROSE.** The cycle steps got followed;
the 13 prose principles and the MAKE-MONEY preamble got rationalized around. So the disposition
must BE steps, each producing a written artifact it cannot skip.

### Changed — `prompts/constitution.md` (full rewrite, ~same length, tool-mechanics block preserved byte-for-byte)
- The S-equation preamble, the MAKE-MONEY section, the 13-principle essay, and the closing
  "three that cost most" are **gone as prose** — compressed into a single linear **LOOP (steps 0–10)**
  where each step yields a required artifact:
  - **3 · REGIME + CATALYST SCOPE** — forces a one-line regime read and, per catalyst, *what it
    gates AND what it does not* (kills the "Micron tonight ⇒ touch nothing" over-generalization).
  - **4 · SURVEY** — a table with ≥5 names + numbers per open class; a missing row = *may not sleep*
    ("0 candidates" illegal without the names).
  - **5 · RE-JUSTIFY** — `SYMBOL | thesis ≤10 words | buy again at this size now? YES/NO`; every NO = sell.
  - **6 · RANK** / **7 · GATE** — deploy **ANY settled cash** a ranked candidate beats; **margin is a
    tool to reach for when the edge is real and added risk small**; to HOLD instead you must write the
    **specific number** that disqualifies the candidate — "wait/settle/catalyst/concentration" without a
    number is not a permitted answer (the trade is then a BUY).
- The 13 principles survive as a compact **"lenses you apply inside the steps"** reference; per-asset
  depth stays in the `card-*` notes; the per-broker friction table is kept for the net-of-cost judgment.
- No coded screener/threshold added — the *ranking is still the agent's judgment*; the steps only force
  it to act on its own ranking instead of rationalizing past it (BRIEF §8 boundary intact).

### Migration
Per node: `./install.sh` (rewrites `CLAUDE.md`), then restart `aitrader`. Watch the next cycles:
the journal should now contain the survey table, the YES/NO verdicts, and either trades or
numbered refusals — not a paragraph of "HOLD, quiet tape."

## [1.11.0] — 2026-06-24 — surface buying power + real unsettled cash (Allocation panel + /status + positions CLI)

### Why
The Allocation screen showed cash-vs-invested but not **buying power** (the headline number
on a margin account) or **unsettled cash** (the binding constraint on a cash account: proceeds
still in T+1/T+2 settlement). And `bin/positions` printed an "unsettled" figure that was
**mislabeled** — `equity − cash − long_market_value − short_market_value`, which collapses to
`equity − cash` (= positions market value) because `/status` never sent long/short market value.
So it reported *invested capital* as "unsettled."

### Changed — `/status` account (`aitrader/api.py` 0.4.0 → 0.5.0)
- Added `settled_cash` and `unsettled_cash` (`cash − settled_cash`). IBKR's `get_account`
  returns `SettledCash` so the figure is exact (cash and margin accounts); brokers that don't
  expose it (Alpaca/MYSE) default `settled = cash` → `unsettled = 0`. `buying_power` already present.

### Fixed — `bin/positions` (2.0.2 → 2.0.3)
- "unsettled" now reads the real `account.unsettled_cash` from `/status` instead of the
  `equity − cash − long − short` plug that mislabeled positions value as unsettled.

### Added — Allocation panel (`ui/`)
- A stat readout under the Cash-vs-Invested donut: **Buying power**, **Cash · settled**, and
  **Unsettled · T+2** (shown only when ≥ $1, amber). `AccountInfo` gains `settled_cash?`/
  `unsettled_cash?`; `useAllocationPanels(positions, account)` now takes the whole account.

## [1.10.0] — 2026-06-24 — fuse the trading guidance into one voice + 5 asset cards; journal in local time

### Why
The live agent (Opus) sat in 36% cash through an opening bell and benched itself for
25 min during the highest-opportunity window, then wrote a fluent justification. The
cause was structural, not a weak model: trading judgment lived in TWO channels — the
always-on constitution (12 principles) and 16 separate `lesson-*` ccmemory notes. An
audit found 11 of the 16 lessons were higher-detail DUPLICATES of the principles, and
the two channels carried **9 dispositional seams** (the same behavior pushed opposite
ways — "be awake through the open" vs "let the tape settle"; "margin is ENCOURAGED" vs
"size leveraged smaller, earn the right"; "idle cash is failure" vs a "cash is a
legitimate position" repeated across ~5 lessons). When two channels disagree the model
arbitrates, and trained caution wins the tie. The corpus was also ~2:1 caution-to-action
and polarized by channel, so loading lessons skewed the agent passive. Separately, the
constitution told the agent to journal in Eastern Time, so on a Central-time host its
"08:30 ET" notes read as the future and were venue-locked (wrong once the venue isn't NYSE).

### Changed — `prompts/constitution.md` (now the single disposition voice)
- Resolved the 9 seams into single both-halves directives, action-clause first with the
  caution as a bounding condition — no longer two separable statements to arbitrate.
- Folded the 11 duplicate lessons into ~13 principles; added P13 (time-of-day /
  holding-horizon), which had no prior home.
- Rebalanced toward action: every free-floating "cash is a legitimate position" is now
  bound to its test ("only after you surveyed and nothing out-ranks it").
- CYCLE step 8 mandates presence through the open on a ~5-min leash ("settle" ≠ "sleep");
  step 7 journals in LOCAL time; session-start points at the 5 `card-*` notes.

### Changed — ccmemory seed (`prompts/ccmemory-seed/`)
- Deleted 11 `lesson-*` notes (folded into the constitution).
- Renamed + scrubbed the 5 asset notes → `card-{crypto,forex,futures,options,leveraged-etp}.md`
  (asset-specific mechanics + disposition only; general judgment removed — the constitution owns it).

### Changed — `install.sh` (migration: `git pull` + `./install.sh` now cleans existing stores)
- Added a `RETIRED_NOTES` manifest (the 16 old `lesson-*` basenames) — removed from every store.
- Curated cards now OVERWRITE on install (canon) instead of copy-if-absent; agent-written notes
  (different names) are untouched. Clears the derived index + prints a restart reminder.

### Changed — local-time clock (`aitrader/timeutil.py` 0.2.0, `aitrader/mcp/scheduler_server.py` 0.3.0)
- New `local_display()`; the `now` tool returns `local` (host wall clock) alongside `utc` and
  `et` (NYSE session clock); `market_status` adds `now_local`. (UI already renders browser-local
  via the earlier `JournalFeed.tsx` fix.)

### Fixed — `install.sh --help`
- `--help` printed the WHOLE script's comments (every `# ── section ──` banner and function
  docstring — a wall of noise) because it grepped all `^#` lines. Now it prints only the curated
  leading header block (disclaimer + description + usage + IBKR note) and stops at the first
  non-comment line.

### Migration
Per node: `./install.sh` (removes 16 retired notes, installs 5 cards, rewrites `CLAUDE.md`,
clears the index), then restart the node's `aitrader` service so the constitution reloads and
the ccmemory MCP re-reads.

## [1.9.1] — 2026-06-23 — get_snapshots tolerates a comma-string

### Why
The live agent tried to snapshot futures as `get_snapshots("ES,NQ,GC,CL")` — a
comma-separated string — but the MCP tool was typed `symbols: list`, so the call
failed schema validation before running. The agent then rationalized *not*
looking ("immaterial, no futures trade intended") instead of resending clean, so
an entire asset class went unsurveyed off a tool-shape error. Sibling `get_bars`
already tolerates a string (`if isinstance(symbols, str): symbols = [symbols]`);
`get_snapshots` should too. Same principle as the gemma quote-parser and the
`EUR.USD` dot-normalization: infra must tolerate how models actually call it.

### Fixed — `aitrader/mcp/broker_server.py` (0.5.1 → 0.5.2)
- `get_snapshots` now accepts `symbols` as a list OR a comma-separated string
  (split on commas at the MCP boundary, so all three brokers get a clean list).
  Docstring updated to state both forms work.

## [1.9.0] — 2026-06-23 — Forex/futures are surveyable again (IBKR universe enumeration + data fixes)

### Why
The live IBKR agent (itrader) reported forex and futures as effectively untradeable:
`EUR.USD` quote errored, `ES` snapshot came back all-zeros, and *"no asset list; no feed
to survey"* for both classes. Investigation against the archived `/src/archive/trader`
confirmed the forex/futures **contract, order, and position plumbing is a faithful, complete
port** (slash→concatenated pairs, `FOREX_CASH_MAP` inversion for CAD/JPY,
`forex_convert_for_order`, cash-balance position reconstruction, `resolve_front_month` roll —
all present and identical). The breakage was elsewhere: `get_tradeable_assets` returns `[]`
for forex/futures (also ported faithfully), but in the old trader that emptiness was
backfilled by the **screener/buyer** reading `[screener] forex_universe` from settings — and
aitrader correctly deleted the screener as cognition without replacing the *enumeration*. So
the agent asked "what can I trade?", got nothing, and concluded "no feed." The `EUR.USD`
error and `ES` zeros were two separate, smaller issues (neither a port regression).

### Fixed — `aitrader/brokers/ibkr.py` (1.1.0 → 1.2.0)
- **Forex/futures universe enumeration.** `get_tradeable_assets` now returns the major
  IDEALPRO pairs (new `FOREX_UNIVERSE`, 12 pairs) for `FOREX` and every `FUTURES_SPECS`
  contract for `FUTURES` — the *complete* infra list, never a ranked/filtered shortlist
  (BRIEF §2), the same pattern `SUPPORTED_CRYPTO` already uses. The agent now has a universe
  to survey. Pair directions chosen to match IDEALPRO's standard pair so they qualify and
  round-trip through `normalize_position` (verified for all 12).
- **Delayed-data fallback.** `get_snapshot`/`get_snapshots` call `reqMarketDataType(3)` so an
  account without a real-time subscription (paper, or unsubscribed forex/futures) gets
  delayed quotes instead of an all-zeros snapshot; with a live sub IBKR still serves
  real-time. `get_snapshot` also polls briefly for the first streaming tick instead of a
  single fixed 1s sleep that often read before any data arrived.
- **TWS dot notation.** `make_contract` accepts `EUR.USD` by canonicalizing to `EUR/USD`
  before contract selection.

### Fixed — `aitrader/asset_types.py` (0.10.1 → 0.11.0)
- New `normalize_pair_symbol`: converts `XXX.YYY` → `XXX/YYY` only when **both** sides are
  ISO currency codes, so equity share classes (`BRK.B`, `BF.B`) are untouched. Wired into
  `classify_symbol` so dot-notation forex classifies correctly.

## [1.8.0] — 2026-06-23 — Seed the agent with mined trading wisdom; full anti-passivity rebalance

### Why
The live agent bought BTC into a confirmed downtrend, rationalizing *"idle capital hurts
my score."* The constitution's anti-passivity prods were the loudest instructions and the
agent had no seeded trade-quality judgment to push back. Investigation of the live atrader
store also found a self-authored, **false** "paper account bug" memory (*"stock sells don't
fill on paper"*) — a misread of normal Alpaca gradual-fill (`status: new`) behavior,
contradicted by the agent's own stop-outs that did fill — which had vetoed stocks and
funneled the agent into crypto knife-catches. Fix: give the agent the prior system's
hard-won wisdom as **judgment** (never code/rules), in the channels it actually reads, and
dial back the prods. Full rationale: `docs/trading-knowledge.md`.

### Added — trading judgment core in the constitution (`prompts/constitution.md`)
- A "How I think about a trade" block: **12 boundary-clean judgment principles** (where-you-
  enter > which-name; regime-first; count real bets; verify exits + `status:new` ≠ failed
  fill + don't re-fire a close; size from survivable drawdown; asset-class edge direction;
  oversold-only-if-structure-advances; leverage/ETP decay; stops don't survive gaps;
  price≠risk; flatten-ability + net-of-cost). No thresholds/gates (BRIEF §8; the reverted
  stop-mandate precedent — #6 states there is no stop mandate).
- **Forced retrieval:** step-1 "CHECK MEMORY" now names `memory_list`/`memory_get` and says
  to treat any recorded "bug"/"constraint" as a hypothesis to re-verify (inoculates against
  the contamination class).
- **End-of-file re-assertion** of the 3 hardest non-negotiables (recency, for the
  small/open-weights consumer Qwen3.6-A35B).

### Changed — FULL anti-passivity rebalance
- Softened *"cash is an underperforming allocation by default,"* step-5 *"100% of capital,"*
  removed *"uncertainty is not a reason to skip."* **KEPT** the survey discipline (every open
  class, live universe, news). Trade quality now dominates activity — the agent still hunts
  but is no longer pushed into low-edge trades.
- Added a top-level **"The job: MAKE MONEY"** prime-directive block so the rebalance reads as
  *capture real edge aggressively + cut dead-money losers and redeploy* — NOT timidity. Frames
  idle cash AND a hopeful-thesis loser as the same failure (money that isn't working), to
  balance the loss-skewed judgment principles. Conditioned on **real** edge so it does not
  re-create the forced-deploy knife-catch. (Prompted by the canary clinging to a losing BTC
  position on a re-derived hopeful thesis while defensive-momentum names went uncaptured.)

### Added — ccmemory knowledge base (`prompts/ccmemory-seed/*.md`)
- ~16 `lesson-*` notes (entry-quality, regime-and-momentum, mean-reversion, exits-and-stops,
  sizing-and-leverage, crypto, forex, futures, stocks-etfs-leveraged, options,
  timing-and-open, overnight-and-gaps, catalysts-and-news, execution-and-cost,
  research-dead-ends, discipline-and-process) carrying the specifics + evidence. The
  ≤150-char `description:` is the load-bearing surface for a weak model.
- `install.sh` seeds them into the run-dir `.ccmemory` (idempotent; never clobbers existing
  notes; no live-index delete — relies on ccmemory's reindex-on-read).

### Provenance
- Mined from `/src/archive/trader` + `/src/research` (109 docs → 643 lessons; **195
  fixed-strategy/threshold items dropped**) via read-only multi-agent workflows + an
  adversarial boundary audit.

### Deploy / rollout (operational)
- Before the new constitution + notes take effect on a node, the **contaminated agent memory
  + journal** (theses/notes/positions-of-record) are wiped on both nodes; `equity_snapshots`
  kept; broker remains source of truth (agent re-derives theses on reconcile). Wipe is done
  in place (never `rm` the live `journal.db`), then `make run-dir` + reseed + restart.

## [1.7.5] — 2026-06-22 — License → PolyForm Noncommercial; from-scratch node runbook

### Changed — license is now noncommercial / personal-use only (was MIT)
- `LICENSE` replaced MIT with the **PolyForm Noncommercial License 1.0.0**, and
  `pyproject.toml: license` is now the SPDX id `PolyForm-Noncommercial-1.0.0`.
  Rationale: the project should be usable by individuals for personal,
  noncommercial purposes but **not** built into a commercial product or used for
  commercial advantage. PolyForm Noncommercial is the recognized, properly-drafted
  license for exactly that — its "Commercial purpose" definition (*any purpose
  intended for or directed toward commercial advantage or monetary compensation*)
  is the boundary. MIT permitted unrestricted commercial use, the opposite intent.

### Added — README "Provision a dedicated node (from scratch)" runbook
- Documents the full bare-machine bring-up that was previously tribal knowledge:
  `useradd aitrader` + `loginctl enable-linger`; the required `~/.bashrc` block
  (`PATH`, `XDG_RUNTIME_DIR=/run/user/$(id -u)` so `systemctl --user` works over
  SSH, and the commented `CCLOOP_CLAUDE_BIN` local-model hook) that **must sit
  above the interactive-shell guard**; installing Claude Code + ccenv; `./install`
  (plus the `--broker ibkr` gateway path); and enabling the `--user` services.
- **Local model** subsection: install `extras/local_claude` to
  `/usr/local/bin/local_claude`, uncomment `CCLOOP_CLAUDE_BIN` for interactive
  runs, AND set it via `~/.config/environment.d/ccloop.conf` + `daemon-reload` for
  the non-interactive service (which doesn't read `~/.bashrc`). Notes that a
  separate search MCP (Brave/SearXNG) is required for local models because Claude
  Code's `WebSearch`/`WebFetch` only work against Anthropic's backend.
- Optional **caddy-portd** note for dynamic port registration. SETUP.md gained a
  pointer to this runbook.

## [1.7.4] — 2026-06-22 — Browser tab title uses portd_name when set (UI 1.5.3)

### Changed — tab title prefix is now the instance name, not a fixed "Trader"
- The browser tab read `Trader ±$<1D P&L>` on every instance, so multiple stacks
  on one host were indistinguishable at a glance. The prefix now uses the
  configured `portd_name` (the same per-instance name used for portd routing) when
  it is set in `settings.toml`, falling back to `"Trader"` when unset — i.e.
  `name = portd_name.length > 0 ? portd_name : "Trader"`.
- `App.tsx` reads `portd_name` from the existing `/settings` payload (already
  exposed via `DEFAULTS`, default `""`) alongside the once-on-mount
  `broker_options.account_type` fetch — no new request. The title effect now
  depends on the resolved name as well as the P&L.

## [1.7.3] — 2026-06-21 — 1D chart VTI line works on Alpaca, not just IBKR (UI 1.5.2)

### Fixed — 1D VTI overlay was empty on Alpaca (no bars returned for a today-start)
- The 1.6.1/1.7.1 VTI work was validated on the IBKR node, where `get_bars` pads
  `start` backwards and returns recent sessions even for a `start = today-midnight`
  request. **Alpaca returns bars chronologically FROM `start` and gives ZERO if
  `start` is past the last session** — so on a weekend/holiday the 1D chart fetched
  no VTI bars at all (`benchBars` empty → neither Mode A nor Mode B can draw). The
  the Alpaca node showed no 1D VTI line; the IBKR node did. Concretely: on Sun
  2026-06-21, with Fri 06-19 = Juneteenth, the last VTI session was Thu 06-18, and a
  `start = today` request returned 0 bars.
- `periodStartISO()` (which feeds ONLY the VTI `/bars` fetch, never the equity
  series) now looks back **7 days for 1D** instead of to today's midnight. That
  guarantees the last session is in the payload across weekends + holidays on any
  broker. It does not change Mode A's today-only line (that's drawn from the
  equity-aligned series); the extra lookback only supplies alignment candidates and
  the Mode-B last-session curve. Verified against the Alpaca node: 0 → 558 bars, Mode B draws
  the 06-18 session. UI-only change. See `docs/ui.md`.

## [1.7.2] — 2026-06-21 — install.sh bootstraps Node when the box has none (build the UI on a fresh clone)

### Fixed — a node-less machine could not build the dashboard UI
- `dist/` is git-ignored (never shipped), and the UI build needs node/npm. On a
  box without node — i.e. anyone who just clones the repo — `install.sh` silently
  skipped the dashboard, and `make ui` died sourcing `$HOME/.nvm/nvm.sh`. The only
  workarounds were "install node yourself" or borrowing another user's nvm. **Why
  that's wrong:** node is a hard build dependency the installer should satisfy
  itself, exactly like `gateway/install.sh` already auto-downloads IB Gateway + IBC.
- `install.sh` now has `ensure_node()`: if `npm` isn't on PATH it downloads a
  pinned official Node (`NODE_VERSION`, currently 22.21.1) for the detected
  OS/arch (linux/darwin × x64/arm64) into `${XDG_CACHE_HOME:-~/.cache}/aitrader`,
  prepends its bin to PATH for the build only, and reuses it on later runs. It is
  build-time only — the agent, MCP servers, and API never need node at runtime.
  Falls back to the existing prebuilt-`dist`/skip behavior if there's no network
  or an unsupported platform. Added a `fetch()` helper mirroring the gateway
  installer. So `./install.sh` (or `./install.sh --build-ui`) now builds the UI on
  a clean machine with no node. The `Makefile`'s `make ui` still assumes nvm and is
  unchanged (dev convenience); the node-free path is `./install.sh --build-ui`.

## [1.7.1] — 2026-06-21 — restore the VTI% tooltip row on the 1D chart (UI 1.5.1)

### Fixed — Mode-B 1D chart lost its per-point VTI% in the hover tooltip
- The 1.6.1 VTI fix added "Mode B" (1D on weekend/overnight: plot VTI's own most-
  recent session on its own time axis). That mode set `benchVals = null`, which is
  what the crosshair tooltip + amber dot read — so the 1D popup showed Equity/P&L
  but dropped the `VTI %` row that 1W/2W/1M/… still showed. **Why it regressed:**
  equity-today and VTI's prior session have no shared x-axis, so there was no
  per-equity-point VTI value to index.
- Now Mode B resamples VTI's session onto the equity x-grid by nearest-x
  (`resampleByX` in `Header.tsx`), so a hover at a given screen-x reports the VTI%
  the amber line shows at that same x, and the amber hover dot returns. Mode A
  (overlapping windows) is unchanged. UI-only change.

## [1.7.0] — 2026-06-21 — equity-chart range selector gains 2W and 6M (UI 1.5.0)

### Added — 2W and 6M buttons on the masthead equity chart
- The range selector went from `1D / 1W / 1M / 3M / 1Y` to
  `1D / 1W / 2W / 1M / 3M / 6M / 1Y` (`ui/src/components/Header.tsx`): new entries
  in `ChartPeriod`, `PERIOD_CONFIG` (2W→1H, 6M→1D timeframes), `BARS_TIMEFRAME`
  (2W→1Hour, 6M→1Day), `periodStartISO` (−14d / −6mo), and the button row.
- Backend: `PORTFOLIO_PERIOD_DAYS` gains `"2W": 14` (`aitrader/api.py`); `6M` was
  already present at 180. **Why this is the only backend change:** the equity line
  reads the journal via `portfolio_since()` (period→day-window), and the VTI overlay
  hits `/bars` with an explicit `start` ISO + timeframe. No broker enumerates period
  *names* — IBKR/Alpaca/MYSE `get_bars` are all driven by `(start, timeframe)`, both
  generic — so arbitrary windows over `1Hour`/`1Day` already work on all three. See
  `docs/ui.md`.

### Fixed — VTI dotted line was invisible on the 1D chart on weekends/overnight
- The masthead equity sparkline's VTI overlay (`ui/src/components/Header.tsx`) was
  drawing but invisible on the **1D** range. **Why:** equity comes from 24/7 crypto
  snapshots (so 1D's timestamps are all *today*), while VTI `/bars` only exist during
  equity-market sessions. On a weekend/overnight the two windows don't overlap, so the
  nearest-bar alignment (`alignBars`) snapped *every* equity point onto the single most
  recent VTI bar → a flat 0% benchmark, painted first and then fully occluded by the
  (also-flat) equity line. `benchAvailable` was actually `true`; the data wasn't
  missing, the line was just degenerate and hidden.
- Now the overlay has two modes, picked by `windowsOverlap` (epoch-range intersection
  of equity timestamps vs VTI bars): **Mode A** (overlap, incl. weekday intraday) keeps
  the equity-grid-aligned series + per-point crosshair tooltip; **Mode B** (no overlap)
  plots VTI's own most-recent session (`lastSessionBars`) on its own time axis, rebased
  to that session's first bar, spanning the chart width — a real VTI curve to compare
  against even when VTI didn't trade during the equity window. Footer `VTI %` / `Δ`
  stats render in both modes. See `docs/ui.md`.

### Changed — gateway is no longer a separate repo; `--broker ibkr` sets it up
- The former standalone `aitrader-ibkr-gateway` repo is now the `gateway/` subdir of
  this repo. **Why:** the release model is lockstep — aitrader is only shipped after
  being tested against a specific gateway version, and the gateway must never update
  out from under aitrader. A sibling repo with an independent lifecycle worked against
  that; one tree pins them together by construction. (The earlier "keep it separate"
  rationale leaned on repo-weight and independent lifecycle — both moot here: the
  IB Gateway/IBC binaries are *downloaded at install time*, never shipped in the tree,
  and lockstep is wanted, not avoided.)
- `./install.sh --broker ibkr` now descends into `gateway/install.sh` after installing
  the client (new step "Set up IBKR gateway"). The gateway installer is self-contained
  and idempotent and stops at its own credentials/paper-vs-live gate, so the consent
  step a human must take is preserved. `--no-gateway` opts out (manage the gateway
  yourself). Alpaca/MYSE installs never touch `gateway/`, so they pull none of its
  X/font deps or IB Gateway/IBC binaries — the isolation property is kept.
- Docs/refs updated: `README.md` (intro, requirements, brokers table, new IBKR install
  note, layout), `SETUP.md`, `docs/broker-mcp.md`, and `gateway/README.md` (reframed
  from "separate repo" to bundled subdir; install paths fixed). The gateway's own two
  ccmemory notes were folded into this repo's store.
- **Not changed:** the `Makefile` still has 3 stale comment references to the old repo
  name — left untouched per the standing "don't edit the Makefile unless told" rule;
  flagged for a follow-up.

## [1.5.0] — 2026-06-20 — per-instance portd registration name (no more cross-stack clobber)

### Fixed — two stacks on one host overwrote each other's Caddy route
- The portd registration names were hardcoded (`aitrader` for the UI, `aitrader-api` for the
  API). On a shared host running more than one stack (e.g. an `alpaca` user and an `ibkr` user,
  one broker per `settings.toml`), both registered under the SAME names. portd is keyed by name,
  so whichever service started second made its `allocate()` clobber the first's reverse-proxy
  route — only one dashboard was reachable.

### Added — `portd_name` setting, default-derived per Unix user
- New `settings.toml` key `portd_name`. The UI registers under `<portd_name>` (public path
  `/<portd_name>/`) and the API under `<portd_name>-api` (`/<portd_name>-api/`).
- Default (key empty/absent): derive `"<unix-user>-aitrader"` — collision-proof since the OS
  guarantees one running user per name, so the two-stacks case is fixed with zero config
  (`alpaca-aitrader`, `ibkr-aitrader`). Set it explicitly for a custom path, e.g.
  `portd_name = "bingleboss"` → UI `/bingleboss/`, API `/bingleboss-api/`.
- Both systemd `ExecStopPost` deregister hooks now derive the name from `settings()` too, so a
  stopped service removes exactly the route it registered.
- Wired through `aitrader/config.py` (key + `portd_name` property), `aitrader/api.py`,
  `bin/aitrader-ui` (UI name + `--api-base`), and both systemd units.

## [1.4.1] — 2026-06-20 — split session-start (memory/journal) from the per-wakeup cycle

### Changed — memory + journal reads belong at session start, not every cycle
- 1.4.0 numbered "check memory" / "check journal" as cycle steps 1-2, implying they run every
  wakeup — wasteful (they rarely change mid-session), and the agent correctly skipped them once
  it already had the context. Moved them into an **AT SESSION START** preamble (done once per
  fresh/relayed session to recover state).
- The per-wakeup **CYCLE** is now 8 steps starting at reconcile: 1 reconcile (broker=truth) ·
  2 what's-open · 3 news · 4 cover all open classes · 5 score+pick (S) · 6 act · 7 journal ·
  8 wakeup (15m/30m/1h, ≤1h). Reconcile-from-broker stays every wakeup (fills/orders move while
  sleeping); wakeup is still the last step.

## [1.4.0] — 2026-06-20 — constitution rewritten as ONE 10-step cycle checklist

### Changed — collapsed ~11 scattered MANDATORY blocks into a single ordered list
- The cycle was spread across "steps 1-7" plus Decision/Holding/Exploration/Universe/
  Coverage/Benchmark/Cash/Execution/Pacing/News/Recording blocks — far too much prose for a
  weak local model, which kept skipping crypto/news and over-sleeping (41.5h weekend wait)
  despite having the rules AND a memory telling it not to.
- Replaced with ONE flat, dumb-simple, imperative checklist run top-to-bottom every cycle:
  1 check memory · 2 check journal · 3 reconcile (broker=truth) · 4 what's-open
  (get_available_types) · 5 news (web search) · 6 cover EVERY open class incl. crypto
  (coverage table, live universe not training tickers) · 7 score+pick by S (100%, cash counts)
  · 8 act (idempotent tags, verify) · 9 journal (ET times) · 10 pick wakeup 15m/30m/1h
  (NEVER >1h) and sleep via wait_seconds (never CronCreate). Then start at step 1.
- Folds in every prior rule as short steps, not paragraphs. The S-objective definition +
  cost table and the Tool Call Mechanics section are unchanged.
- Wake cadence is a model RULE (step 10, ≤1h), NOT an infra cap — the scheduler max-wait
  experiment from earlier this session was reverted at the operator's direction: the model
  owns its own wake time; the constitution just constrains it to ≤1h.

## [1.3.6] — 2026-06-20 — hard ≤1h wake cadence; ban external schedulers (CronCreate)

### Changed — concrete news cadence + close the CronCreate footgun
- News Constraint now sets a **hard ceiling: the blocking wait between cycles MUST NOT exceed
  1 hour** — wake at least hourly to scan news regardless of market state. Makes "regular
  intervals" concrete (no more sleeping until Monday over a weekend).
- Pacing Requirement now **forbids `CronCreate` / cron / any external/parallel scheduler**:
  sleep ONLY via the scheduler MCP's in-session `wait_*`. Why — the agent (when prodded about
  weekend cadence) reached for `CronCreate`, which is the wrong model: the runtime is ONE
  long-lived ccloop session, and an external scheduler spawns SEPARATE concurrent runs that
  collide on the broker client-id lease and the journal → double-submitted-order risk.
- FOLLOW-UP (harness, not prompt): add `CronCreate,CronDelete,CronList` (and likely
  `ScheduleWakeup`) to the agent's `--disallowedTools` — same reliability lesson as WebSearch:
  remove the footgun rather than trust a weak model to avoid it. (CronCreate jobs are
  session-scoped/in-memory, so a job the agent already made isn't reachable externally — the
  agent must `CronDelete` it, or it dies on the next session relay.)

## [1.3.5] — 2026-06-20 — constitution: News Constraint (wake regularly, scan for market-moving events)

### Added — the agent never read the news; unscheduled shocks blindside a trader
- New **News Constraint (MANDATORY)** in `prompts/constitution.md`: each cycle, before
  deciding, check current news (macro prints, central banks, earnings/guidance, geopolitics
  — wars/sanctions/supply shocks like a Strait-of-Hormuz scare) for the market, holdings, and
  candidates via web search, and record it; "nothing material" must be a real check, not an
  assumption.
- It **bounds the Pacing Requirement**: wake at regular intervals to scan news — never go dark
  through a full session/weekend, so an overnight/weekend shock is caught before the next open
  instead of after it gaps the book. (The predecessor system got slammed exactly this way.)
- Capability note: assumes a web/news search tool exists. Production (Claude) has native
  WebSearch; the local-model tester needs a search MCP (e.g. searxng) wired — its built-in
  WebSearch is disallowed and can't reach the local server. (Operator is wiring that.)

## [1.3.4] — 2026-06-20 — constitution forces explicit per-asset-class coverage each cycle

### Changed — the agent kept anchoring on equities and silently skipping crypto/other classes
- Even with the Universe Constraint, the agent (esp. the weak local model on the tester)
  read `get_available_types` → saw `crypto: true` → then evaluated equities only, because its
  existing holdings were equities. Prose it skims; it needs forced, visible work + a gate.
- Cycle step 2 rewritten: **survey EVERY tradeable class FIRST**, draw the ≥10 candidates from
  ACROSS classes (not just the one current holdings sit in).
- New **Coverage Constraint (MANDATORY)**: before any allocation, output a per-class coverage
  table (tradeable? candidates pulled? symbols fetched). A tradeable class left at zero =
  INCOMPLETE/INVALID cycle unless a concrete reason is recorded ("I already hold equities" is
  not a reason). Crypto (24/7) MUST appear with real candidates every cycle.
- Pacing Requirement gets a crypto carve-out (co-located where the wait decision is made):
  "markets closed" / wait_until_market_open mean the STOCK session ONLY — holding crypto
  (24/7) or a resting crypto stop means you always have something to watch, so size the wait
  to that, never sleep until the next stock open. (Observed: the agent surveyed crypto, then
  scheduled wait_until_market_open through the weekend while holding BTC/ETH with GTC stops.)
- Also dropped the arbitrary "≥10 candidates" quota (invited padding) — breadth is now
  enforced by the per-class Coverage table, not a magic number.
- NOTE: this is prompt-level enforcement; a weak model may still skip. A harness hook is the
  reliable backstop if needed. Also: the agent can edit its own run-dir `CLAUDE.md` (it did) —
  but `install.sh` overwrites that file from `prompts/constitution.md` on every deploy, so the
  durable constitution is the SOURCE; agent self-edits are ephemeral. Governance TBD.

## [1.3.3] — 2026-06-20 — options surfaced in availability; constitution points the agent at the live universe

### Fixed — `get_available_types` omitted options entirely
- `options` is a full `AssetType` with its own tools (`get_option_chain`/`get_option_greeks`),
  but the "what's tradeable now" map only reported `{stock,crypto,forex,futures}`, so the
  agent's menu never even mentioned options. IBKR's `get_available_types` now includes
  `options` (true during the regular equity session). Alpaca is left as-is — it genuinely
  can't trade options (`get_option_chain` raises `NotImplementedError`), so advertising it
  would just make the agent fail. MCP docstring updated.

### Changed — constitution: Universe Constraint (use the live universe, not training tickers)
- Added a MANDATORY "Universe Constraint" to `prompts/constitution.md`: the broker trades
  stocks/crypto/forex/futures/options (candidates are not limited to equities; call
  `get_available_types` for what's live), and instruments must be discovered from the live
  broker universe (`get_tradeable_assets`) — NOT recalled from training data, which has a
  cutoff (stale/wrong tickers; instruments may post-date training). This is capability +
  data-hygiene guidance, not a directive on WHAT to trade. (The agent had only ever traded
  US equities/ETFs — naming tickers from memory rather than querying the universe.)
- TransactionCosts table gains an `options` row: IBKR `0.015` (spread-dominated — IBKR Pro
  Fixed ≈ $0.65/contract plus the premium bid-ask spread, expressed as a fraction of the
  option premium/notional); Alpaca `—` (adapter doesn't trade options yet; Alpaca itself is
  commission-free + ~$0.0026/contract ORF if added). Baseline — agent refines from live quotes.

## [1.3.2] — 2026-06-20 — gateway readiness gate fails fast when the gateway is down

### Fixed — `ibgateway-ready` spun the full 300s (5-min startup hang) on a down gateway
- **Why.** `aitrader-gateway-wait` retried every failure for the full `TIMEOUT` (300s),
  so a gateway that simply isn't running (TCP **connection refused** on the API port)
  was treated like one that's up-but-still-logging-in. Result: any start with the
  gateway down blocked ~5 min (everything is `After=ibgateway-ready`). Seen after a
  blanket `systemctl --user stop` of all units — which also stops the gateway (it's a
  `--user` unit), so nothing was left listening on 4002.
- Now distinguishes the two states: the probe tracks `ever_connected`. If the port has
  **never** accepted a connection within `CONNECT_GRACE` (60s — covers the gateway's
  ~13s process spawn), it fails fast instead of grinding to 300s. A gateway that's up
  but still logging in sets `ever_connected`, so a legitimate slow boot is **never**
  cut off — it still waits up to `TIMEOUT` for the login.

### Known gap (not changed here — needs a decision)
- `ibgateway-ready.service` only `After=ibgateway.service`, with NO `Wants=`/`Requires=`,
  so the gate **waits for** the gateway but never **starts** it. It relies on the gateway
  being `enabled` (started at boot). Manually starting just the aitrader stack does not
  bring the gateway up. Making it self-healing (`Wants=ibgateway.service`) is pending.

## [1.3.1] — 2026-06-20 — install.sh rebuilds the UI when source is newer than dist

### Fixed — `./install.sh` deployed a stale `ui/dist` after `ui/src` edits
- **Why.** The UI step only rebuilt on `--build-ui` or when `ui/dist` was missing;
  otherwise it copied the existing `ui/dist` as-is. So editing `ui/src` and running
  a plain `./install.sh` silently shipped the *old* bundle unless you remembered
  `--build-ui` / `make ui`.
- Now it also rebuilds when any build input is **newer than `ui/dist/index.html`** —
  a scoped `find` over `ui/src ui/public ui/index.html ui/vite.config.ts
  ui/package.json ui/tsconfig*.json` (the small `ui/` subtree only, `-quit` at first
  hit; NOT a scan of `/src`). No node/npm + stale dist now deploys the existing dist
  with a warning instead of skipping the UI entirely.

## [1.3.0] — 2026-06-20 — dashboard ports register with portd when it's running

### Added — dynamic port allocation via the local Caddy `portd` plugin
- On start, `aitrader-api` and `aitrader-ui` ask portd (`POST :2019/portd/allocate`,
  keyed by name) for their listen port; portd reverse-proxies `/<name>/` to them.
  Names: **`aitrader-api`** and **`aitrader`**. If portd isn't running, both fall
  back to the configured defaults (2499/2500) — so a box without portd is unchanged.
- **Fast + non-blocking by design:** one helper (`aitrader/portd.py`) with a hard
  ~1s timeout, and it never raises. portd absent → the TCP connect is refused
  instantly, so startup never stalls (no multi-minute hang). `allocate()` doubles as
  the probe: `allocate(name) or default`.
- `aitrader/api.py:main()` binds the allocated port; `bin/aitrader-ui` serves the
  allocated UI port and points the SPA at the API via the idempotent, name-keyed
  `allocate("aitrader-api")` (so it gets the SAME port the API bound).
- Deregister on stop is wired as `ExecStopPost` on both systemd units (best-effort,
  non-fatal, own ~1s timeout) so a stopped service doesn't leave a stale portd route.
- **SPA works through Caddy path-routing too** (not just on the raw port): the UI bundle
  now builds with a relative asset base (`vite base: './'`, safe because the dashboard
  has no client-side router), and under portd `trader_ui` injects `window.__API_BASE__ =
  "/aitrader-api"` so the SPA calls the API via Caddy's same-origin path instead of
  host:port (the allocated port is localhost-only). `index.html` loads `config.js`
  relatively; `api.ts` honors `__API_BASE__` over host:port. Non-portd mode is unchanged
  (relative assets also resolve at the origin root; `--api-port` injection as before).
- Mirrors the `/src/dispatcher` integration (detect → allocate → fall back).

## [1.2.0] — 2026-06-20 — default dashboard ports → 2499/2500; ui_port is its own setting

### Changed — default port block 7500/7501 → 2499/2500
- **Why.** 7500 is a round number in the contended 7000–9000 band that other dev
  tooling reaches for, and "round + default" maximizes collision odds. 2499/2500 is
  low, memorable, and quiet. The UI gets the round, memorable `2500` (the port a
  human types in a browser); the API takes `2499`. Both are well clear of privileged
  (<1024) and ephemeral (49152+) ranges, and — checked — neither is on the
  Chrome/Firefox `ERR_UNSAFE_PORT` block list (unlike nearby 2049/NFS), so the UI loads.
- `config.py`: `api_port` default `7500 → 2499`. **`ui_port` is now its own DEFAULTS
  key (`2500`) with a real `Settings.ui_port` property** — it is NO LONGER derived as
  `api_port + 1`. The hidden `+1` coupling was fragile (a stray service on `api_port+1`
  silently broke the UI) and surprised consumers. `bin/aitrader-ui` now reads
  `s.ui_port` instead of `s.data.get("ui_port") or api_port+1`.
- `ui/src/api.ts` dev fallback `7500 → 2499`; `install.sh` defaults `API_PORT=2499`,
  `UI_PORT=2500` (and the `ui_port` line is now only written when non-empty — a blank
  default no longer emits broken `ui_port = ` TOML). README, settings.toml.example,
  systemd unit comments, api.py docstrings, docs/ui.md updated to match.
- **Migration:** existing installs are unaffected — they have explicit ports in
  `settings.toml` (or keep whatever they set). Only a fresh install with no ports
  specified picks up 2499/2500. Two stacks on one host must still set distinct pairs.

## [1.1.2] — 2026-06-20 — install.sh purges orphaned "~"-prefixed pip leftovers

### Fixed — bogus "Ignoring invalid distribution ~eventkit" + false "aeventkit … not installed"
- **Why.** `PIP_FLAGS` uses `--force-reinstall`, which uninstalls-then-reinstalls every dep on
  each run. pip renames a dist-info to `~name` as a pre-delete backup; when a delete is
  interrupted — or a rename churns it, as happened with the `eventkit` → `aeventkit` fork that
  ib-async 2.x depends on — the backup is stranded. pip then spams
  `Ignoring invalid distribution ~eventkit` on every invocation *and*, worse, reports a false
  `ib-async 2.1.0 requires aeventkit, which is not installed` conflict even though
  `aeventkit-2.1.0.dist-info` is present and `import eventkit` / `import ib_async` both work.
  (`importlib.metadata` saw aeventkit 2.1.0 the whole time; only pip's scan was confused.)
- The install step now removes any `~`-prefixed entry from the user site-packages before the
  pip install. Removing those backups is always safe — they are stale copies of an already-valid
  dist-info. Confirmed on the tester: deleting the stranded `~eventkit-2.1.0.dist-info` made
  `pip check` drop both lines immediately.
- **Not addressed (cosmetic, upstream):** `ib-async 2.1.0 has requirement tzdata<2026.0,>=2025.2,
  but you have tzdata 2026.2`. That is ib-async's over-tight upper pin on the IANA tz database;
  ib_async imports and runs fine against 2026.2. aitrader's `tzdata` dep is intentionally left
  unpinned (a trader wants the freshest tz rules) rather than held back to satisfy a transitive
  cap. Pin `tzdata>=2025.2,<2026.0` in pyproject only if a spotless `pip check` is required.

## [1.1.1] — 2026-06-20 — backfill composes with the recorder instead of being suppressed by it

### Fixed — the snapshot recorder racing ahead of the first reconcile skipped the backfill
- **Why.** 1.1.0 used "journal already has equity rows → adopt, no backfill" as the
  fresh-vs-existing discriminator. But the recorder fires every 15 min, so on a real install
  it writes a few rows *before* the agent's first reconcile — and adopt then suppressed the
  broker backfill, leaving the dashboard with only those few recent points instead of the full
  history. (Seen on the tester: adopted 12 recorder rows → a 3-hour curve, zero broker history.)
- Dropped the adopt branch. On first run (no semaphore) it now **always backfills, skipping any
  `ts` already in the table**. Broker dailies and the recorder's 15-min points have
  non-overlapping timestamps, so they compose without duplicates — deep history *plus* recent
  detail. The semaphore still guarantees once. Strictly better in both fresh and weeks-old-upgrade
  cases (the latter now *gains* the older history instead of freezing at whatever the recorder
  caught). `journal_db.equity_count` → `equity_ts_set`.
- Verified on the tester against live Alpaca: 252 daily rows backfilled alongside 13 recorder rows
  (skipped 0), curve now spans a full year.

## [1.1.0] — 2026-06-19 — backfill the equity curve from the broker on first sync

### Added — fresh installs no longer start with an empty equity curve
- On the agent's first **successful** broker data read (account/positions actually
  returned — not a mere connect), the broker MCP seeds the journal's `equity_snapshots`
  from the broker's own `get_portfolio_history` (longest daily window). So
  `/portfolio_history` and `day_pl` show real history immediately instead of waiting for
  the recorder to accumulate points. (`mcp/broker_server.py:maybe_backfill_equity`.)
  - **Why.** Those two dashboard reads come from journal snapshots, not the broker — so a
    fresh install against an existing account showed a flat/empty curve until ~a day of
    recorder ticks. The broker already has the history; we just import it once.
  - **Idempotent** via a state-dir semaphore (`.equity_backfilled`), written only after a
    successful pass — a no-history account doesn't re-attempt every call.
  - **Upgrade-safe:** an existing journal that predates this feature (history, no
    semaphore) is *adopted* — semaphore stamped, no backfill — so it never re-imports over
    real data. The empty-check is the one-time fresh-vs-existing discriminator; the
    semaphore is the steady-state guard.
  - **Never raises, never fires on a dead broker:** gated on a confirmed-good data read;
    any failure leaves the semaphore unset to retry next call. `journal_db` stays pure
    storage (adds only `equity_count`); `timeutil` gains `epoch_to_iso` (same `+00:00`
    form `equity_read` sorts on — the 0.15.3 ordering fix).
- Trade history already worked on a fresh install (`/trades` reads fills live from the
  broker); per-position rationale is agent intent and can't be reconstructed. So the
  equity curve was the only real gap.

## [1.0.2] — 2026-06-19 — broker_status no longer mislabels a non-IBKR broker as IBKR

### Fixed — `broker_status` reported `data_feed: "ibkr"` and `paper: false` for an Alpaca paper account
- **Why.** Both fields were IBKR-era hardcodes. `data_feed` was `b.data_feed_name() or
  "ibkr"`, and `data_feed_name()` returned `None` when no *separate* data broker was
  configured — so a pure-Alpaca setup (execution broker serves its own data) fell back
  to the literal `"ibkr"`. `paper` was inferred from an IBKR-only `DU/DF` account-id
  prefix, so an Alpaca paper account (`PA…`) read as `paper: false`. Together they sent
  the agent down a rabbit hole ("the broker is IBKR? but paper:false with positions?").
- `BrokerRouter.data_feed_name()` now returns the **execution broker's** name when there
  is no separate data feed (so it reports the truth: `alpaca`/`myse`/`ibkr`).
- `broker_status` now returns an explicit **`broker`** field (the execution broker name),
  `data_feed` without the `"ibkr"` fallback, and **`paper = not allow_live`** (the live
  fuse is the broker-agnostic source of truth, not an account-id prefix).
- This also lets the agent apply the correct per-broker transaction-cost column — the
  constitution's cost table keys off "the active broker from broker/account status."

### Added — installer seeds a starter agent memory (an empty store looped weak models)
- `install.sh` writes one real `agent-orientation` memory into `run/.ccmemory/` when the
  store is empty, so the agent's first `memory_list()` isn't `[]`.
  - **Why.** An empty result gave a fresh agent nothing to anchor on and made weaker
    models re-query in a loop (once per type filter) instead of accepting "no memories."
    A single real entry short-circuits that.
  - The seed is true, useful orientation (journal-vs-ccmemory split, the wake cycle,
    paper-only) — **not** mock data. Only an EMPTY store is seeded (never clobbers the
    agent's own memories); the derived index is cleared so ccmemory rebuilds it on boot.

## [1.0.1] — 2026-06-19 — installer robustness (it aborted mid-run, leaving no run dir)

### Fixed — `install.sh` aborted at the CLI-scripts step, so the run dir/UI/MCP/units never got created
- **Why.** `install -m 755 bin/*` matched a stray `bin/__pycache__` **directory**;
  `install` rejects directories and returns non-zero, and under `set -e` that killed
  the whole script. The package + CLIs (earlier) were installed, but the run dir,
  UI deploy, MCP registration, and systemd units (all later) were silently skipped —
  so `aitrader` ran but reported "run dir not found."
- `install.sh` now installs CLI scripts **file-by-file** (skips dirs/non-files), and
  the **dashboard UI step is non-fatal** (missing node/`ui/dist` → warn + skip, never
  abort the agent install). Added an `ERR` trap that names the failing line and tells
  you to re-run (the installer is idempotent — keeps settings/secrets).
- Removed the stray `bin/__pycache__` artifact.

### Changed — `aitrader` launcher message
- The "run dir not found" error no longer says `make install`/`make run-dir` (dev
  tooling); it points at `./install.sh`.

### Removed — stopped installing the orphaned `skills/`
- The installer no longer copies `skills/*.md` to `~/.local/share/aitrader/skills/`,
  and the `skills_dir` plumbing is gone from `config.py`/`paths.py`/`settings.toml.example`.
  - **Why.** Nothing read them: the constitution didn't reference the skills dir, no
    code loaded it, and the agent's run dir didn't include it — so they were dead
    files. The `skills/*.md` content is kept in the repo for if/when the skills
    concept is actually wired to the agent (e.g. as run-dir Claude Code skills).

## [1.0.0] — 2026-06-18 — packaged as a shippable product; IBKR gateway split out

Major: aitrader goes from a developer checkout to a product someone can clone and
install. No change to agent cognition or the constitution's trading behavior — this
is packaging, the IBKR client/server split, and product hygiene.

### Added — a real installer
- **`install.sh` / `uninstall.sh`** front door (with an `install` symlink). Self
  contained (no `make` needed): preflight (python≥3.12, pip, tmux), a config
  **wizard** (broker / ports / credentials) with a `--non-interactive`/`--answers`
  mode, builds + `pip install --user`s the wheel with broker-appropriate extras
  (IBKR extra only when `broker=ibkr`), deploys the UI, seeds the run dir +
  constitution, registers the MCP servers at user scope, installs the systemd user
  units, and prints next-steps. Uninstall reverses it and keeps data unless `--purge`.
  - **Why.** `make install` assumed the source tree + dev toolchain, always pulled
    the IBKR extra even for Alpaca users, and never deployed the UI. A downloaded
    user couldn't just "type install."
- **README.md** (product quickstart) + **LICENSE** (MIT).

### Changed — default port block 7500/7501
- `config.py` `api_port` default `7099 → 7500`; UI fallback `ui/src/api.ts`
  `7000 → 7500`; `ui_port` derives `api_port+1` (7501). One clean, documented block
  instead of three inconsistent defaults (7099 / 7000 / baked 7099).

### Changed — equity snapshot: cron → systemd timer
- New `systemd/aitrader-snapshot.{service,timer}` (`OnCalendar=*:0/15`,
  `Persistent=true`) replace the `*/15` crontab entry; output now to the journal.
  - **Why.** Keeps the whole stack under `systemctl --user` for the product (no
    crontab dependency); `Persistent=true` catches up one missed tick after downtime.
  - Journal note label `cron recorder → snapshot recorder`.

### Changed — IBKR gateway server extracted to its own repo
- The IBKR **gateway server** (IB Gateway + IBC + Xvfb) moves to
  **`aitrader-ibkr-gateway`** (`systemd/ibgateway.service`, `ibc/config.ini.example`,
  `install.sh`, README with the paper/live + consent decisions, setup docs). aitrader
  ships only the IBKR **client** (`brokers/ibkr*.py`, the `[ibkr]` extra,
  `aitrader-gateway-wait`, the `ibgateway-ready.service` readiness gate).
  - **Why.** Standing up the gateway requires user decisions aitrader can't make
    (paper vs live, credentials, real-money consent). Splitting it means aitrader
    installs clean against Alpaca/MYSE with zero IBKR footprint, and the IBKR client
    just dials `ibkr_host:ibkr_port` — agnostic about what runs the gateway.

### Changed — UI de-drift
- The dashboard UI's canonical source is `ui/` (was building from a sibling repo
  `/src/trader-ui` on NFS); serve dir renamed `~/.local/share/trader/ui →
  ~/.local/share/aitrader/ui` (and in `ui/bin/trader_ui`).

### Changed — Makefile realigned with install.sh (dev path)
- `make` no longer installs the moved `ibgateway.service`; builds the UI from `ui/`
  into `~/.local/share/aitrader/ui` (was `/src/trader-ui` → `~/.local/share/trader/ui`);
  installs the snapshot `.service`/`.timer` instead of a crontab (`install-cron`
  removed); and adds the `[ibkr]` pip extra only when `broker=ibkr`. `install.sh`
  remains the shipping path; `make` is the dev path.

## [0.15.3] — 2026-06-18 — equity snapshots read in time order (fix day_pl baseline)

### Fixed — backfilled history was ignored by day_pl and scrambled the chart
- **Why.** `journal_db.equity_read` ordered by `id DESC` (insertion order), and
  `day_pl` + `/portfolio_history` both assume the rows come back newest-first *by
  time*. That holds only while snapshots are written in chronological order. After
  importing another account's equity history (the trader→aitrader migration), the
  backfilled rows got higher ids than today's already-written cron rows, so
  `day_pl`'s "earliest today" (`rows[-1]`) picked the first cron row (mid-day)
  instead of the imported **00:xx daily**, and `/portfolio_history` returned the
  series in insertion order (wrong `base_value`, scrambled curve).
- `equity_read` now orders by `ts DESC, id DESC`. ts is a uniform UTC ISO8601
  string (`+00:00`), so lexical order == chronological; id is the tiebreak. Fixes
  all three readers (day_pl, /portfolio_history, journal MCP `equity_snapshot_read`).
- Verified: `day_pl` now baselines off the 01:02 ET imported daily (64,489.15) →
  +356.85, matching Alpaca's authoritative `equity − last_equity` (+323.80, modulo
  seconds of drift). Before: +59/+76 off the wrong mid-day baseline.

## [0.15.2] — 2026-06-18 — `/status` survives a degraded Alpaca endpoint

### Fixed — one slow broker sub-call no longer hangs the whole dashboard
- **Why.** Alpaca's `/v2/orders` paper endpoint went unresponsive (confirmed:
  direct fresh-connection `GET /v2/orders` timed out at 20s while `/v2/account`
  and `/v2/positions` returned in 0.2s). `compute_status()` called
  `list_all_open_orders()` unguarded, so that one hung call took down the entire
  `/status` — and because `/status` holds `_status_lock`, every poller (UI + cron
  + manual curl) queued behind it and the dashboard looked permanently hung, even
  right after a restart.
- `compute_status()` now treats the open-orders fetch as **non-fatal**: on failure
  it logs a warning and serves account + positions + equity + day_pl with an empty
  orders list (positions just miss protective-order enrichment that cycle). Orders
  repopulate automatically when the upstream endpoint recovers.
- **alpaca HTTP hardening** (`brokers/alpaca.py`): `enforce_http_timeout` now also
  mounts a urllib3 Retry adapter. `connect=3` transparently reopens a fresh socket
  when a pooled keep-alive connection was dropped after idle (a separate hang mode
  on long-lived processes); `read=0` so a genuinely-unresponsive endpoint fails
  once instead of multiplying the wait. Retries are **GET/HEAD/OPTIONS only**, so a
  slow order POST/cancel is never silently re-sent. Timeout is now a (connect=5s,
  read=12s) tuple, down from a single 30s.
- Net: during an Alpaca orders outage the first uncached `/status` costs ~12s
  (one timeout) then serves from the 3s cache; account/positions/equity/P&L stay
  live throughout. 0.15.1 was an intermediate step (retry + 15s); 0.15.2 adds the
  non-fatal degrade + read=0.

## [0.15.0] — 2026-06-18 — dashboard API honors `settings.broker` (multi-broker)

### Changed — constitution: cycles must sleep via the scheduler (stop the tight loop)
- **Why.** `prompts/constitution.md` said "operates in continuous cycles" but never
  told the agent to sleep between them. On finishing a cycle the agent stopped,
  ccloop's never-stop hook re-prompted it, and it immediately ran another cycle —
  a back-to-back loop re-deciding the same state with no new information, burning
  quota. The user had to repeatedly tell the model to use the scheduler.
- Added a **Pacing Requirement (MANDATORY)**: every cycle must END in a scheduler
  blocking wait (`wait_seconds` / `wait_until` / `wait_until_market_open` /
  `wait_until_session_close`) sized to how soon re-evaluation is warranted; the
  next cycle begins only when the wait returns. "Nothing actionable" is the reason
  to wait, not to loop. Respects the ~5s cadence floor. Closing line updated to
  state cycles are paced by the agent's own waits, never back-to-back.
- Deploy: `make run-dir` (or `make install`) rewrites the run-dir `CLAUDE.md` from
  this source; each node needs that + an agent restart to pick it up.

### Fixed — API was hardwired to IBKR; broke every non-IBKR node
- **Why.** `api.py`'s `broker()` constructed `IBKRBroker(client_id=80)`
  unconditionally, ignoring `settings.broker`. On the Alpaca node
  (`broker = "alpaca"`) the dashboard threw `ibkr_port not found in secrets.toml`
  and reported `connected:false` — "nothing there." The MCP `broker_server`
  already selected the backend correctly; only the API never got the same
  treatment.
- `broker()` now builds the execution backend per `settings.broker ∈
  {ibkr, alpaca, myse}` and wraps it in a `BrokerRouter` with the optional
  `data_broker` (inlined `build_data_broker`, mirroring `broker_server`), so the
  dashboard shows the SAME prices the agent sees. IBKR keeps its API-specific
  fixed `client_id=80` + small pools; a data-broker failure degrades to the
  execution broker for data rather than 500-ing the dashboard.
- **`Broker.list_all_open_orders` is now portable.** `compute_status()` calls it
  to show the agent's working orders; it existed only on `IBKRBroker`
  (`reqAllOpenOrders`, needed there because each IBKR clientId sees only its own
  orders). Added a concrete default on the `Broker` ABC =
  `get_orders(status="open")`, correct for shared-account brokers (Alpaca, MYSE);
  IBKR keeps its cross-client override. This unbroke `/status`.
- **Version drift fixed.** `aitrader/__init__.__version__` had been left at
  `0.10.1` while `pyproject` advanced to `0.14.0`; `/health` reports the package
  version, so the dashboard mislabeled itself. Synced both to `0.15.0`
  (`api.py` module → `0.4.0`).
- Verified live against Alpaca paper `PA000000000000`: `/health` connected,
  `/status` returns account+positions (LLY) with live prices, `/trades` 777 fills.
  `get_classification` (IBKR-only) degrades to null sector/industry via the
  existing try/except — no crash.

### Added — `make install` installs the equity-snapshot crontab entry
- **Why.** `bin/aitrader-snapshot` was already installed to `~/.local/bin`, but its
  crontab entry was a manual host step that got forgotten on new nodes — so
  `/portfolio_history` stayed empty (the Alpaca node equity chart was flat). The
  recorder reads `/status` over HTTP, so once the API was fixed it works on any
  backend; only the cron was missing.
- New `install-cron` Make target (folded into `install`, also standalone):
  idempotently appends `*/15 … aitrader-snapshot >> …/logs/snapshot.log` for the
  running user (paths from `$(LOCAL_BIN)`/`$(STATE_DIR)` → correct per-user) only
  if no `aitrader-snapshot` line exists, and `mkdir -p`s the logs dir.

## [0.14.0] — 2026-06-18 — `/review` serves the agent's recorded rationale

### Added — UI "why was this bought" now backed by the journal
- **Why.** The trader-ui's click-a-symbol review panel hit `GET /review`, which
  aitrader stubbed to a flat `404` — a leftover from gutting `/src/trader`'s
  reviewer (the cognition we reject). The "why" data already existed in the
  journal; nothing surfaced it. No new journal tool was needed.
- `api.py` `/review?symbol=` now assembles a read-only rationale from the
  existing durable stores: the **position-of-record** (`entry_rationale`,
  `thesis`, `planned_exit`, status/opened) plus that symbol's **journal
  entries** (chronological log). Returns the UI's `ReviewData` (`content` as a
  preformatted log, `format: "text"`); still `404` when the agent recorded
  nothing. Matches crypto under either slash/no-slash keying.
- Pure infra: surfaces only what the agent itself wrote — no scoring, no
  reviewer. Populating it is the agent's job (see prompt note below).

## [0.13.1] — 2026-06-18 — fix: Alpaca TIF case-insensitive

### Fixed — uppercase crypto TIF no longer silently breaks
- **Why.** `tif_enum()` keyed only on lowercase strings and `.get(tif,
  TimeInForce.DAY)` fell back to DAY on any miss. An uppercase `"GTC"` (or any
  unrecognized value) therefore became `DAY`, which Alpaca rejects for crypto →
  cryptic broker-side "invalid crypto time_in_force" error with no local clue.
  This is a faithful port of `/src/trader`'s identical latent bug — it was never
  exercised there with an uppercase crypto TIF.
- `brokers/alpaca.py` `tif_enum()` now lowercases/strips input (so `"GTC"` ==
  `"gtc"`), keeps DAY only for empty/None, and raises a clear `ValueError` naming
  the bad value + valid set instead of silently masking a typo as DAY.

### Fixed — `side_enum` wrong-direction footgun (same root cause)
- **Why.** `side_enum` was `OrderSide.BUY if side == "buy" else OrderSide.SELL`,
  so any non-exact match (`"BUY"`, `"Buy"`) fell to the `else` and silently
  placed a **SELL** — a wrong-direction trade, far worse than a bad TIF.
- Now case-insensitive (`str(side).strip().lower()`), matches buy/sell
  explicitly, and raises `ValueError` on anything else instead of defaulting to
  SELL. Same latent bug exists in `/src/trader`'s `side_enum`.

## [0.13.0] — 2026-06-17 — selectable execution backend (ibkr | alpaca | myse)

### Added — /src/trader's broker-factory model: pick the EXECUTION backend
- **Why.** A pure-Alpaca deployment couldn't run: `broker()` hardcoded IBKR
  execution and `AlpacaBroker` was data-only (every order/account method raised).
  This ports `/src/trader`'s broker selector so execution can be IBKR, Alpaca, or
  MYSE — independent of the optional data feed.
- `settings.broker` ∈ {ibkr (default), alpaca, myse} selects execution;
  `broker_server.build_execution_broker()` constructs it (IBKR keeps the clientId
  flock lease; alpaca/myse just connect). `broker()` returns the same
  `BrokerRouter` on top, so the data_broker split is unchanged. With NO data
  broker, the execution broker serves data too (the pure-Alpaca case).
- `brokers/alpaca.py` — replaced the data-only `_refuse()` stubs with full
  execution ported from `/src/trader` (account/positions/portfolio_history; place
  market/limit/stop/stop-limit/bracket; modify/cancel/global_cancel/order
  queries; close_position; wait_for_fill; fills). Adapted for aitrader: accepts
  `client_tag` → Alpaca `client_order_id`, surfaced back as `order_ref` for
  idempotent reconcile; signatures match the MCP tool calls.
- `brokers/myse.py` — NEW: MYSE REST execution backend (stocks only, 24/7 sim
  exchange at localhost:7777). `load_myse_credentials` + `requests` dep added.
- Paper-only fuse per backend: IBKR refuses non-DU/DF; Alpaca connects with
  `paper=(not allow_live)`.
- **Divergence from /src/trader (both backends):** no long-only enforcement
  (`check_no_short` dropped) — the agent owns sizing/direction (CLAUDE.md §2),
  matching the IBKR backend. Options + Alpaca/MYSE bracket raise a clear
  `NotImplementedError` instead of `AttributeError`.
- **Not ported:** the `sim` backtester (1833 lines, parquet-driven, off the live
  path) — the 4th `/src/trader` backend, left out as the non-live one.

### Verified — live Alpaca paper execution, no mocks (2026-06-17)
Real paper account `PA000000000000`: `get_account`/`get_positions`; placed an AAPL
buy-limit @ $10 with a `client_tag` → returned `order_ref=client_tag`
(idempotency), found in `get_open_orders_for_symbol`, then `cancel_order` →
`canceled`. aitrader itself stays `broker=ibkr` (live agent untouched).

## [0.12.0] — 2026-06-17 — remove the HALT-file kill switch

### Removed — the soft kill-switch fuse (operator request)
- **Why.** The operator runs the trader interactively (ccloop in tmux) and kills
  it by exiting the session (escape → exit) or `systemctl stop aitrader`; never
  via `claude -p`. The HALT-file sentinel was a second, redundant kill path that
  added surface for no benefit. The HARD kill (`systemctl stop` / exit) is
  unchanged.
- Removed `kill_switch_active/reason/engage/clear` from `fuses.py` (paper-only
  enforcement remains — it's now the ONLY fuse), `KILL_SWITCH` from `paths.py`,
  the `kill_switch` setting + property from `config.py`, the kill-switch check in
  `scheduler_server._sleep_until` (the chunked-wait loop stays — it's the hook
  point for the future broker-event early wake), and the three `/kill_switch`
  endpoints from the dashboard API.
- Docs synced: `CLAUDE.md` §3 fuses row, `docs/api.md`, `docs/scheduler-mcp.md`,
  `state.md`. Kept every "kill = `systemctl stop` / exit the session" reference —
  those remain true.
- **Heads-up:** trader-ui's kill-switch button now 404s (backend endpoints gone);
  remove it from the UI separately if desired.

## [0.11.0] — 2026-06-17 — market-DATA feed (Alpaca) in front of IBKR execution

### Added — the §A.3 data/execution split (restores /src/trader's data_broker)
- **Why.** IBKR's *paper* market data returns nothing pre-open, so the agent kept
  hitting "DATA FEED DEAD PRE-MARKET" — empty bars/snapshots with no informed
  open decision. `/src/trader` solved this with `broker=ibkr` + `data_broker=alpaca`
  (stock/crypto data from Alpaca's pre/after-hours tape, execution on IBKR). That
  split was always part of aitrader's design (the `Broker` ABC names both drivers)
  but had not been ported. This ports it.
- `aitrader/brokers/alpaca.py` — `AlpacaBroker`, **data-only** adapter (alpaca-py).
  Ports the data-method bodies from `/src/trader` (bars/snapshots/tradeable list +
  pure time facts), normalized to the SAME dict shapes `IBKRBroker` returns so
  routing is invisible to the agent. **Every execution/account method raises** —
  Alpaca's paper account is a different account; aitrader executes only on IBKR.
- `aitrader/brokers/router.py` — `BrokerRouter`: holds execution + optional data
  broker, proxies each call. `DATA_METHODS` (get_bars/get_snapshot/get_snapshots/
  get_tradeable_assets) with an explicit stock/crypto `asset_type` → Alpaca;
  account/orders/fills + any no-/non-stock-crypto-`asset_type` call → IBKR.
- `broker()` (broker MCP) now returns the router; a dead data feed degrades to
  IBKR-for-data (logged), never stopping execution. `broker_status` reports
  `data_feed`. Data-tool docstrings note the source split.
- Config: `settings.data_broker` (default unset → IBKR data) + `data_broker_types`
  (default `["stock","crypto"]`); `load_alpaca_credentials()`; `alpaca-py>=0.30.0`
  base dep. secrets.toml/settings.toml wired; settings.toml.example documented.

### Divergences from a literal /src/trader mirror (both safety-driven)
- **No-`asset_type` data calls go to IBKR, not the data broker.** IBKR prices every
  asset class; Alpaca only stock/crypto — so an omitted `asset_type` must not be
  silently mis-served by Alpaca. The data feed is reached only on an *explicit*
  stock/crypto `asset_type`.
- **`get_fill_activities` stays on IBKR** (it's NOT in `DATA_METHODS`). Fills are
  account-of-record data and aitrader's account lives on IBKR; routing them to
  Alpaca's separate paper account would corrupt reconcile.

### Verified — live Alpaca, no mocks (2026-06-17 08:42 ET, pre-market)
`get_snapshot('AAPL', stock)` → live `latestTrade.p=299.26` (IBKR returns empty
pre-open); AAPL daily SIP bars, BTC/USD 1h bars, 73-coin crypto universe all
populate; router resolution + Alpaca execution refusals pass; full MCP build path
(`build_data_broker()` → router → routed call) green. See `docs/broker-data-feed.md`.

## [0.10.1] — 2026-06-17 — harden the client-id lease (agent pins 40; no leak)

### Fixed — two robustness holes in the 0.10.0 lease
- **Lease leak on connect failure.** `broker()` leased a base then connected; if
  the connect raised, the flock fd stayed held (in `_held_fds`) but unused, and a
  retry leased a *different* base — so failed connects accumulated dead leases
  and pushed everyone to higher ids. Now `acquire_client_id()` returns `(base,
  fd)` and `broker()` calls `release(fd)` on connect failure, `hold(fd)` only on
  success. (Verified: acquire→release→reacquire reclaims the same base.)
- **Agent could lose its stable id.** With everyone leasing the same pool, a race
  (or the leak above) let an interactive session grab 40, forcing the agent onto
  110 — which breaks its ability to cancel/modify its own resting orders (IBKR
  ties those rights to the placing clientId). Now the **agent pins 40** and
  interactive/ad-hoc brokers lease **110+** and never touch it. The agent is
  detected by cwd = the run dir (its broker MCP runs there; interactive sessions
  don't) — no env var, no arg, deterministic.
- `clientid_lease.py`: `AGENT_CLIENT_ID=40` + `INTERACTIVE_BASES=[110,140,…]`;
  `acquire_client_id()/hold()/release()`. Tested: role split (agent→40,
  interactive→110), leak-fix reclaim, and concurrent distinct bases all pass.

## [0.10.0] — 2026-06-16 — broker MCP leases a unique client-id (coexists with agent + API)

### Added — cross-process IBKR client-id lease (`brokers/clientid_lease.py`)
- **Problem:** every `aitrader-broker-mcp` instance read the same fixed
  `ibkr_client_id=40` from secrets (the registration passes no args/env), so a
  *second* broker MCP (an interactive/ad-hoc session alongside the running
  agent) collided on IBKR error 326 — "pools failed to become ready." The
  gateway offers no way to query which client-ids are in use, so the server
  couldn't just pick a free one.
- **Fix:** `broker_server.broker()` now claims a unique client-id *base* via a
  cross-process **flock** lease. Each candidate base (`40, 110, 140, …`, spaced
  30 so each owns a full pool slot; 80-100 reserved for the API) has a lock file
  under `STATE_DIR/ibkr-clientids/`; a process flock()s the first free one and
  holds the fd for its lifetime. The kernel releases the lock the instant the
  holder dies (clean exit, crash, kill -9), so a lease **can't go stale** — no
  PID bookkeeping, no reclaim sweep, no PID-reuse race.
- **Result:** first broker up keeps 40 (the agent), the API keeps 80, any
  interactive session auto-takes 110/140/…, freed instantly on exit. N brokers
  coexist on the one gateway with zero per-launch config.
- Tested: concurrent processes get distinct bases; killing a holder frees its
  base immediately; a held base is skipped and the next is connected live.
- **Boundary:** pure connection plumbing (§A.3) — no trading logic.
- *(Reverted a first attempt that auto-bumped client-ids by colliding against
  the gateway and catching 326 — slow and log-spammy; the flock lease is the
  clean, deterministic replacement. `ibkr.py` is back to its original.)*

## [0.9.0] — 2026-06-16 — `/status` reports heat (risk-at-stop) for the shared UI

### Added — top-level `heat` aggregate + real per-position `heat`
- The shared trader-ui HeatPanel rendered `0.0%` across every row for the aitrader
  engine (:7099) because `/status` emitted no `heat` object and hardcoded each
  position's `heat` to 0 (a leftover stub from when those were risk-engine fields).
  The trader engine (:7000/:7001) populates the same panel from its risk engine;
  the UI is shared between both, so the fix belongs in *each* engine's `/status`
  rather than in engine-specific UI branching.
- New `enrich_positions_with_heat(positions, equity)` computes **risk-at-stop as a
  fraction of equity**, per position and aggregated per asset class + total
  (`total_heat`/`stock_heat`/`crypto_heat`/`forex_heat`/`futures_heat`/`position_count`).
  Dollars at risk = `|market_value|` when a position has no live protective stop
  (full downside; `market_value` already embeds the futures multiplier, so it's
  true notional across asset classes — no stop = max heat), or the loss-if-stopped
  (`|market_value| × max(0, distance_to_stop)/current`, floored at 0 so a stop
  locked in profit reads as zero downside risk) when a live broker stop exists.
  Stops are sourced from `enrich_positions_with_protective_orders`; classes from
  `asset_types.classify_symbol`. The disconnected branch returns a zeroed `heat`
  object so the response shape is stable.
- **Boundary (CLAUDE.md §2):** this is display-only observability derived from
  broker truth — the same mechanical class as the existing `to_stp` distance.
  It is NOT a heat *budget*, cap, or gate: nothing here constrains a decision, and
  the agent never reads this API (it acts through MCP tools). It does not port the
  rejected risk engine (§8) — only the dollars-at-risk arithmetic, which is factual,
  not an opinion. The agent still owns all sizing and risk. See memory
  `heat-observability`.

## [0.8.1] — 2026-06-16 — `/status` positions carry their sector/industry

### Fixed — equity positions no longer all bucket as "Unclassified"
- `map_position` hardcoded `sector`/`industry` to null (the old risk engine was
  their source and it's gone), so trader-ui's allocation "by sector" view dropped
  every position into a single **Unclassified** slice.
- `/status` now enriches each `us_equity` position with its sector/industry from
  the broker's IBKR contract classification (new `IBKRBroker.get_classification`:
  `reqContractDetails` industry → sector, category → industry). ETFs/funds carry
  no single industry, so their `stockType` ("ETF"/"FUND") becomes the sector
  (QQQ/SMH → "ETF") instead of "Unclassified". Forex/crypto/futures carry no
  classification and stay null (honest — a currency has no equity sector).
- Classifications are cached process-wide (static reference data); definitive
  answers — including "no classification" — are cached, transient broker failures
  are not, so they retry on the next fetch.
- **Boundary:** this is a factual reference lookup of a security's published
  classification — like `asset_class`. It is NOT a screen, score, ranking, or
  opinion, so it stays on the infra side of the hard boundary.

## [0.8.0] — 2026-06-16 — `GET /journal` — the agent's notebook as a shared feed

### Added — normalized `/journal` endpoint for trader-ui
- New `GET /journal?limit=&kind=&symbol=&since=` projects the journal table into a
  backend-agnostic feed: `{ entries: [{id, time, kind, symbol, text, tags, meta}] }`.
  aitrader rows map `ts→time` (re-emitted as ISO-8601 UTC), `kind→kind`,
  `body→text`, `tags→tags`; `meta` is `{}` (no per-entry structured context here,
  unlike trader's risk-check fields). Newest-first, capped at `limit`.
- **Why:** the dashboard's bottom panel is moving from a Trades table to a Journal
  feed. The IBKR broker has no durable trade history (confirmed: `reqExecutions`
  and `ib.fills()` both return 0 for any prior day — IBKR keeps current-day
  executions only), and the API's client never even sees the agent's fills. The
  agent's journal, by contrast, already records every action in prose at trade
  time (entry/exit/cycle entries carry symbol/qty/price/rationale). So the journal
  — not an ephemeral broker poll — is the right durable source to surface.
- **Shared contract:** the trader API (`/src/trader`) implements the identical
  envelope + field names against its `decisions` table (converting its naive-UTC
  `decided_at` to ISO-8601 UTC), so one trader-ui `JournalFeed` component renders
  both. `api` 0.1.2 → 0.2.0.
- Pure infra: read-only projection, no logic/cognition (CLAUDE.md §2).

## [0.7.1] — 2026-06-16 — Fix: `/portfolio_history` honors `period` (every chart range was identical)

### Fixed — the endpoint ignored `period`/`timeframe`; all ranges returned the same curve
- `/portfolio_history` accepted `period` + `timeframe` and discarded both, always
  returning `equity_read(limit=5000)` (the last ≤5000 raw snapshots). So 1D, 1W,
  1M, 3M, 1Y all rendered the **same** curve in trader-ui's header chart (which
  plots the returned series as-is, only trimming leading zeros), and the `LIMIT
  5000` was a hard ceiling on lookback (~52 days at the recorder's 15-min cadence —
  1Y could never be shown).
- **Fix:** ported the trader API's approach (`/src/trader/trader/api.py`
  `get_portfolio_history`, which sources the same `equity_snapshots`): resolve each
  period to a **date-window lower bound** and filter `ts >= since` instead of
  capping by row count. `portfolio_since()` is ET-aware to match the display
  calendar — 1D = since ET midnight (consistent with `day_pl`), YTD = since ET
  Jan 1, the rest are rolling N-day windows (`1A`/1Y = 365). `ALL` = no bound.
- **Consequence:** lookback is now bounded by the window, not by cadence — the
  `LIMIT 5000` artifact (not the snapshot cadence) was the only thing limiting
  history. `timeframe` is passed through; server-side downsampling for long ranges
  (daily buckets) is a noted follow-up, not yet implemented. `api` 0.1.1 → 0.1.2.
- Verified on live data: 1D → 102 snapshots (today only, base 50790.34) vs
  1W/1M/1Y/ALL → 105 (base 50888.65, back to the earliest snapshot 06/15).

## [0.7.0] — 2026-06-16 — Fixed-cadence equity snapshot recorder (`bin/aitrader-snapshot`)

### Added — cron-driven equity telemetry so `day_pl` / the equity curve aren't agent-dependent
- New `bin/aitrader-snapshot`: reads account equity from the already-running
  dashboard API (`GET 127.0.0.1:<api_port>/status`) and writes ONE equity snapshot
  to the journal. Installed to `~/.local/bin` by `make install` (LOCAL disk).
- Wired into the `aitrader` user crontab every 15 min, 24/7:
  `*/15 * * * * ~/.local/bin/aitrader-snapshot >> ~/.local/state/aitrader/logs/snapshot.log 2>&1`
  (15 not 5: the real cost is the live broker round-trip behind each `/status`,
  not disk — ~4 IBKR calls 24/7 incl. overnight when equity is static and the
  gateway has thrown Error 322 on account-summary churn. day_pl needs only one
  snapshot after ET midnight; intraday resolution only matters during RTH. 15-min
  ≈ 1/4 the broker load and ~3× the visible history window.)
- **Why:** equity snapshots were written *only* by the agent (journal MCP
  `equity_snapshot_write`) when it chose to — so they were sparse and irregular
  (observed: 3 points across a whole day, none after it went to sleep). `day_pl`
  baselines off the first snapshot of the current ET day, so right after ET
  midnight — and all through the agent's ~11h overnight blocking-scheduler sleep —
  there was no snapshot and day_pl read 0, and the equity curve was gappy. A fixed
  cadence guarantees a fresh baseline within 15 min of any ET-day rollover.
- **Boundary (CLAUDE.md §2):** recording equity on a clock is mechanical telemetry
  — no threshold, ranking, or decision; it biases no trade. The agent still writes
  its own *annotated* snapshots whenever it wants; the recorder only guarantees the
  baseline underneath. Reads over HTTP from the API (broker client_id 80) so it
  opens NO broker connection of its own — no extra IBKR client id, no Error 322/326
  risk.
- **Never records fake data:** if the API is unreachable or the broker is
  disconnected (or equity is missing/0), it writes nothing and exits non-zero.
- See `docs/snapshot-recorder.md`.

## [0.6.3] — 2026-06-15 — Fix: `/status` day P&L baselines on the ET day, not the UTC day

### Fixed — `api.day_pl` mis-anchored the daily baseline at the UTC midnight edge
- `day_pl()` selected the first equity snapshot of "today" via `utcnow().date()`
  (a **UTC** calendar date), but the dashboard displays in **ET** (CLAUDE.md §6:
  all times UTC internally, display ET) and the trading day is an ET day. The two
  calendars disagree near midnight, so the baseline was picked from the wrong day.
- Concretely: during the ET evening (e.g. 22:00 ET = 02:00 UTC the next day), the
  old code's "today" was already the *next* UTC date, so it baselined off a
  late-session snapshot and reported **day P&L ≈ 0** even though equity had moved
  all day. Verified against the real `journal_db`: equity 1010→1025 over an ET day
  read `+0.00` under the UTC filter vs the correct `+15.00` under the ET filter.
- **Fix:** compute ET midnight of the current ET day and convert it back to a UTC
  instant for the `since` filter, so the selection calendar matches the display
  calendar. Snapshots stay stored as UTC ISO strings (storage invariant unchanged);
  only the boundary computation moved into the display tz. `api` 0.1.0 → 0.1.1.
- **Scope note:** the `/trades` endpoint does **not** date-filter at all (it accepts
  `period` and returns all broker fills), so the trader-side `/trades` window bug
  has no analog here — `day_pl` was the only UTC-date-vs-ET-display selection.

## [0.6.2] — 2026-06-15 — Gateway readiness gate (fixes post-reboot broker 326 storm)

### Added — `ibgateway-ready.service` + `bin/aitrader-gateway-wait`
- New oneshot user unit that blocks until the IB Gateway API actually accepts a
  login (real handshake: connect on throwaway client 199 → `managedAccounts`),
  `RemainAfterExit=yes`, retries up to 300s. `aitrader` and `aitrader-api` now
  `After=ibgateway-ready.service` + `Wants=` it.
- **Why:** `ibgateway.service` is `Type=simple`, so `After=ibgateway.service`
  only waits for the gateway *process* (~13s post-boot), but its login takes
  ~10-90s longer. The API/agent connect early; connecting during that window
  leaves the broker pool in an `Error 326` ("clientId already in use") reconnect
  storm that wedges the dashboard / agent until a manual restart (observed after
  a power-loss reboot — blank UI, `positions` CLI timeout). The gate makes
  startup wait for genuine readiness.
- `Wants=` (not `Requires=`): if the gate ever times out, dependents still start
  (degraded, own reconnect takes over) rather than the trader being blocked
  forever. The probe reads host/port from secrets.toml — no hardcoded port
  (same "never guess a port → could be LIVE" rule as the broker).
- `make install-service` now installs the new unit; `bin/*` already installs the
  probe. Validated: probe exits 0 in 0s when ready; API restart through the gate
  reconnects clean (`connected: True`, 9 positions).

## [0.6.1] — 2026-06-15 — Fix: service `Environment=PATH` so ccloop/claude resolve

### Fixed — `aitrader.service` crash-looped on start (and after reboot)
- Added `Environment=PATH=/home/aitrader/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`
  to the unit. systemd's user-manager PATH omits `~/.local/bin`, so the launcher's
  `os.execvp("ccloop", …)` failed with *"ccloop not found on PATH"* → exit 1 → the
  tmux window died → `Restart=always` looped every 15s (so `tmux -L aitrader attach`
  hit "no sessions" between restarts). Worked from a terminal only because the login
  shell's PATH includes `~/.local/bin`.
- **Why it surfaced now:** a power-loss reboot killed the interactive agent; bringing
  the trader back via the *service* (not a terminal) exposed the PATH gap.
- Also this session: enabled `aitrader` / `aitrader-api` / `aitrader-ui` user services
  (boot-start; lingering already on) so the stack recovers automatically after a reboot.

## [0.6.0] — 2026-06-15 — Service runs ccloop in tmux (interactive/subscription, never headless `-p`)

### Changed — `systemd/aitrader.service` now launches ccloop inside a tmux session
- `ExecStart` is now `tmux -L aitrader new-session -d -s main .../aitrader` (was a
  bare `Type=simple` exec). `Type=forking`; `ExecStop=tmux -L aitrader kill-server`.
- **Why:** Anthropic is moving headless `claude -p` / Agent-SDK usage off the
  subscription onto a metered API credit. ccloop 0.5.0 enforces this — it never
  picks headless `-p` implicitly (requires `--headless --accept-api-cost`) and
  **refuses to start with no TTY**. The old unit ran with no TTY, so under 0.5.0
  it would either refuse (crash-loop) or, pre-0.5.0, silently meter `-p`. Running
  ccloop inside tmux supplies a real PTY → ccloop auto-selects the interactive TUI
  → draws on the **subscription**. Verified: inside the `-L aitrader` socket,
  `sys.stdin.isatty()` and `sys.stdout.isatty()` are both true.
- Dedicated tmux socket (`-L aitrader`) → fresh server per start, reliably tracked
  by systemd, isolated from any other tmux. Attach: `tmux -L aitrader attach -t main`.
- **Caveat (ccloop-side):** in interactive mode an abnormal (non-relay) session exit
  triggers ccloop's `_confirm_relaunch()` Y/n prompt; inside a detached tmux with no
  human it blocks rather than auto-relaunching. Normal context-fill relays are
  unaffected. Consider a ccloop auto-relaunch-when-unattended option for full autonomy.
- Docs synced: `state.md`, service unit header. Backups: `*.service.backup`.

## [0.5.0] — 2026-06-15 — MCP servers registered at USER scope (no run-dir `.mcp.json`)

### Changed — MCP server registration moved from project scope to user scope
- `make run-dir` (and thus `make install`) now **merges** the broker / scheduler /
  journal MCP servers into `~/.claude.json` at **user scope** instead of writing a
  project-scoped `<run_dir>/.mcp.json`. The merge is idempotent (updates the three
  keys in place, preserves all other `.claude.json` state) and the stale run-dir
  `.mcp.json` is removed.
- **Why:** project-scoped `.mcp.json` only attaches when `claude` runs *inside the
  run dir*, which forced a `cd ~/.local/share/aitrader/run` before launching an
  interactive session. The `aitrader` user exists solely to trade, so the servers
  should be available in every session regardless of cwd. The launcher still chdirs
  to the run dir for `CLAUDE.md` + `.claude/settings.json`; only MCP discovery
  changed.
- Docs synced: project `CLAUDE.md`, `SETUP.md`, `docs/runtime.md`, `state.md`,
  `launch.py`, `config.py`.

## [0.4.0] — 2026-06-15 — `aitrader` launcher (resume-aware), settings-driven run, fully open-ended

### Added — `aitrader` launcher (config-driven, resume-aware)
- `aitrader/launch.py` (console script): reads `criteria` + `task` + `ccloop_cutoff`
  + `run_dir` from `settings.toml`, chdirs to the run dir, and execs ccloop. With
  no args it **scans `<run_dir>/.ccloop/runs/` and `--resume-run`s the latest run**
  if one exists (so a reboot / `systemctl restart` CONTINUES the run instead of
  starting over); fresh only when there's no prior run. `aitrader "<criteria>"
  "<task>"` = ad-hoc fresh run. Replaced the bash wrapper; service is
  `ExecStart=.../aitrader`.
- `ccloop` invocation moved into config: `criteria` + `task` (ccloop's two args,
  text in `settings.toml` — `task` is session-1-only, everything persistent lives
  in the run-dir CLAUDE.md) + `ccloop_cutoff` (default 500 → `--cutoff=500`).
- `make full` / `make install-service` / `make restart` added.

### Removed — all biasing of the agent's decisions (open-ended by design)
- **Skills dropped.** The brief's "how to think" prose playbooks
  (morning-routine / exit-thinking / journaling) and the constitution's "read
  your skills" reference are gone — they pre-loaded heuristics that would taint an
  open-ended experiment. (Source `skills/` kept, unreferenced.) Memory
  `skills-disabled`.
- **Constitution stripped to operational mechanics only.** Removed the
  "Disposition" section and all trading guidance (skepticism, "flat is a
  position," "the right trade is usually no trade," thesis/falsifier, prefer-
  fewer-positions, risk/sizing coaching, cadence advice, anti-systematic
  editorializing). What remains: you-are-the-decider, the tools, broker=truth /
  journal=memory, relay + reconcile-before-acting, idempotency, the fuses — plus
  an explicit "no guidance encoded here, by design" note. Every trading decision
  (including blowing up the account) is the model's, unguided. Memory
  `no-biasing`.

## [0.3.0] — 2026-06-15 — ccloop runtime, settings.toml config, ~/.local install

Three architecture changes driven by user direction:

### Runtime is now ccloop (custom harness deleted)
- Deleted `aitrader/harness/` (`loop.py` + the `aitrader-harness` entry point)
  and all loop-era prompts (wake/stub/smoke). The runtime is **ccloop**
  (`/src/ccenv/ccloop`): never-stop via its `Stop` hook (vs. flimsy prompt
  prose), and FRESH-session relay on context-fill (vs. lossy compaction).
- ccloop runs `claude` in a **run dir** `~/.local/share/aitrader/run/`, which
  natively loads `CLAUDE.md` (constitution), `.mcp.json` (the 3 MCP servers), and
  `.claude/settings.json` (model). Scheduler MCP still provides sleep/cadence;
  journal+broker reconcile provide cross-relay state.
- New **`aitrader` launcher** (`aitrader/launch.py`, console script): reads
  `criteria` + `task` + `ccloop_cutoff` from `settings.toml`, chdirs to the run
  dir, and execs `ccloop --cutoff=N`. **Resume-aware:** with no args it
  `--resume-run`s the latest run under `<run_dir>/.ccloop/runs/` (so reboot/
  restart continues, not restarts); fresh only when no prior run. `aitrader
  "<criteria>" "<task>"` = ad-hoc fresh run.
- New `systemd/aitrader.service` = `ExecStart=.../aitrader` (no args), replaces
  the harness unit. Kill switch = `systemctl stop aitrader`. `make full` /
  `make install-service` / `make restart` added. Memory `runtime-ccloop`.

### Config: settings.toml only, NO environment variables
- New `aitrader/config.py` — single source of truth: XDG defaults, overridable
  in `~/.config/aitrader/settings.toml`. Ripped every `AITRADER_*`/`os.environ`
  config read out of `paths.py`, `credentials.py`, broker/scheduler servers.
  MCP servers each load `settings.toml` themselves (no env passthrough). Only
  remaining env use is building the spawned-subprocess environment. `model`
  moved to the run dir's `.claude/settings.json` (a Claude concern under ccloop);
  `settings.toml` keeps `wake_floor_seconds`, `allow_live`, paths. Memory
  `config-no-env-vars`.

### Install to ~/.local (LOCAL disk) — never run from /src (NFS)
- `/src` is an NFS mount; running from it means an outage kills the trader.
  Deleted the errant venv. New `Makefile`: `make build` (wheel) → `make install`
  (`pip install --user --break-system-packages "<wheel>[ibkr,calendar,sandbox]"`
  → `~/.local/bin` + `~/.local/lib`), prompts/skills/run-dir to
  `~/.local/share/aitrader`. Verified: package + MCP servers run from `~/.local`
  with cwd=`$HOME`, source off the path.

### Verified
- All 3 MCP servers handshake from the installed `~/.local/bin` scripts.
- `config.py` resolves XDG defaults + file overrides with zero env.
- Run dir, wrapper, and service unit in place. (ccloop end-to-end smoke + first
  light pending — see state.md.)

## [0.2.2] — 2026-06-15 — Phase-0 exit run + clean slate + crash-recovery fix

### Phase-0 exit criterion (§A.5) — DEMONSTRATED
- Ran `aitrader-harness --stub` unattended against the live paper account: the
  agent looped on its own — reconcile (broker_status/get_account/get_positions/
  get_orders) → journal → `wait_seconds(20)` → repeat — accumulating reconcile
  entries across multiple cycles with no human input.
- **Restart survival:** killed the agent mid-loop and relaunched; it reconciled
  from broker truth + read its journal and continued seamlessly (journal entry
  count grew across the crash). The journal + broker-reconcile safety invariant
  holds. A full multi-hour soak is left to operations; the mechanism is proven.

### Fixed — crash-recovery session-id persistence
- The harness saved the session id only AFTER the agent process exited. In the
  long-lived model the agent never exits on its own, so killing the HARNESS
  itself (systemd restart / OOM) mid-cycle lost the id, and the relaunch started
  a fresh session instead of `--resume`. Now `stream_events` persists the id the
  instant it arrives in the init event. Verified: `harness.json` is written while
  the process is still running and survives a `kill -9` of the harness.
  (Continuity was always safe via journal+reconcile; this restores in-context
  session resume too.)

### Account — clean slate
- Flattened the inherited forex residue (CAD/CHF/GBP ≈ $5.9k) back to USD via
  `flatten_all_residual_currencies`. Account now flat USD, only sub-$1
  untradeable dust remaining. aitrader starts effectively flat.

## [0.2.1] — 2026-06-15 — Live paper connection (gateway co-located) + capstone

### Operational — IB Gateway co-located on this node (clyde)
- Moved the IBKR **paper** gateway off the underpowered `infra` QNAP VM onto this
  node, alongside aitrader (one failure domain, localhost API, no LAN dep).
  - Replicated infra's proven install via rsync: IB Gateway **1044** (`~/Jts`),
    its bundled Zulu-17 JRE (`~/.local/share/i4j_jres/Oda-…`), and **IBC 3.23.0**
    (`~/ibc`); rewrote 5 install4j path files `/home/trader` → `/home/aitrader`.
  - `systemd/ibgateway.service` (system unit) runs it headless under Xvfb,
    `Restart=always`. Installed deps: xvfb + X libs.
  - Stopped + disabled `ibgateway.service` on `infra` (was the autostart). `infra`
    is out of the trading path.
  - `secrets.toml`: host `127.0.0.1`, port 4002, `client_id=40`, account `DU0000000`.

### Fixed
- **`IBKRBroker.get_account`** now includes the `account` id (from
  `summary.account` / `managedAccounts`). Previously omitted, so the broker MCP's
  `broker_status` reported `account: null, paper: false` despite the connection's
  paper fuse correctly identifying `DU0000000`. Now `broker_status` →
  `{connected: true, account: 'DU0000000', paper: true}`.

### Verified — LIVE against the paper account
- Direct: broker MCP connected to the co-located gateway; paper fuse confirmed
  `DU0000000`; equity/cash/buying-power, `available_types` (stock/crypto/forex/
  futures all true), `market_session=regular` all returned.
- **Capstone (full loop):** the harness drove `claude -p` through the broker +
  journal MCP — reconciled account/positions/orders from the live paper account,
  wrote a journal reconcile + equity snapshot, exited rc=0. harness → Claude →
  live broker → journal is proven.

### Note — inherited state
- The paper account carries **3 open positions** (~$50.9k equity) left by the old
  movers engine, with NO positions-of-record. aitrader's first real reconcile
  will see positions it has no thesis for — a deliberate decision point for the
  agent (adopt or flatten). Consider flattening before first live run if a clean
  slate is wanted.

## [0.2.0] — 2026-06-15 — Phase 0 code-complete + Phase 1 (constitution & skills)

### Added — infrastructure tool servers (all pure plumbing, zero cognition)
- **broker MCP** (`aitrader/mcp/broker_server.py`, 31 tools). Owns the IBKR
  connection (§A.3). Driver `aitrader/brokers/{ibkr,ibkr_connection,ibkr_pool}.py`
  + `futures.py` ported from the old system: `Broker` ABC method bodies reused
  as-is; each connection pool runs its own thread + asyncio ib_async pump;
  `client_tag`→`Order.orderRef` idempotency on every order; lazy connect with
  graceful no-gateway errors. Cognition stripped (ranked scanner, news, DB-forex
  → live reconstruction). `docs/broker-ibkr.md`, `docs/broker-mcp.md`.
- **scheduler MCP** (`aitrader/mcp/scheduler_server.py`, 6 tools). Pure
  blocking-wait mechanism over `market_calendar`. Chunked, kill-switch-
  interruptible waits; `wait_seconds` floor-clamped (cadence fuse).
  `wait_for_fill` intentionally placed in the broker MCP (owns the connection),
  not here. `docs/scheduler-mcp.md`.
- **`aitrader/market_calendar.py`.** Clean-room multi-tier NYSE close/open
  resolver (broker → pandas_market_calendars → hardcoded), clock dep swapped to
  `timeutil`.
- **`aitrader/fuses.py`.** Kill switch (HALT file) + paper-only helper (DU/DF).

### Added — runtime harness
- **`aitrader/harness/loop.py`** (`aitrader-harness`). Perpetual act-loop driving
  `claude -p` exactly like the old `opus_reviewer`
  (`--output-format stream-json --permission-mode bypassPermissions
  --append-system-prompt --mcp-config`, `CLAUDECODE` popped). Long-lived resumed
  session: relaunch-with-`--resume` on crash, session-id persistence,
  reconcile-from-truth via the wake prompt, kill-switch gating. `--stub`,
  `--once`, `--no-broker`, `--no-resume`. `docs/harness.md`, `systemd/`.

### Added — the agent's mandate (Phase 1; prose, not logic)
- **`prompts/constitution.md`** — the trader's constitution: the hard boundary,
  the cycle, broker-is-truth/journal-is-why, always-on/never-end-turn,
  idempotency, sizing-is-yours, disposition. Plus `stub_agent.md`, `wake_prompt.md`,
  and bounded `smoke_*` prompts.
- **`skills/`** — three judgment playbooks (morning routine, exit thinking,
  journaling & idempotency) + README. Guidance, no rules/thresholds.

### Verified
- All 3 MCP servers launch + complete the MCP handshake over stdio (49 tools).
- Journal layer unit-tested. Scheduler floor fuse + calendar tested. Paper fuse
  + parse_asset_type tested. Driver imports clean (all ABC methods implemented).
- **Live end-to-end:** the harness drove `claude -p` through the scheduler +
  journal MCP tools and persisted a journal entry, exiting rc=0 (bounded smoke
  test, ~$0.40). The harness↔Claude↔MCP bridge works.

### Pending (not deferrable in code — needs hardware)
- Live IBKR broker connection + the Phase-0 §A.5 exit run require a reachable IB
  Gateway/TWS paper instance, absent in this environment. See `SETUP.md`.

### Rationale notes
- `wait_for_fill` in broker MCP not scheduler: two processes can't share one
  IBKR socket; polling belongs where the connection lives.
- Single frontier model, agent-chosen cadence with a 5s floor + wake-at-open
  (locked §10). Paper-only + kill-switch are the ONLY fuses; agent owns sizing.

## [0.1.0] — 2026-06-15 — Project genesis + Phase-0 scaffold

### Added
- **Founding docs.** `BRIEF.md` (canonical founding mandate) and `CLAUDE.md`
  (operational constitution distilling it). The hard boundary between
  infrastructure and cognition is load-bearing and recorded in both.
- **`pyproject.toml`.** Package `aitrader` 0.1.0. Deps: `mcp` (official SDK,
  replacing the old hand-rolled JSON-RPC server), `tzdata`. Extras: `ibkr`
  (`ib_async`), `calendar` (`pandas_market_calendars`), `sandbox` (pandas/numpy),
  `dev`. Console scripts for the three MCP servers + harness.
- **Core package primitives.** `paths.py` (clean-room XDG layout, `AITRADER_*`
  env overrides, kill-switch path), `credentials.py` (IBKR secrets loader,
  refuses to default the port so it can't silently hit a live gateway),
  `asset_types.py` + `broker.py` (clean-copied verbatim from `/src/trader` —
  pure primitives, imports renamed to `aitrader.*`; broker.py docstring updated
  to say the broker MCP owns the connection).

### Decisions (§10 of the brief)
- Persistence = long-lived resumed session; asset scope = multi-asset; fuses =
  kill switch + paper-only (no notional/BP caps — agent owns all sizing); broker
  = IBKR paper, reuse ABC + method bodies, clean-room the connection; single
  frontier model; agent-chosen cadence with a 5s floor and wake-at-open.

### Rationale
- **Official `mcp` SDK over the old hand-rolled JSON-RPC.** The old `mcp.py` was
  a stdio JSON-RPC shim that HTTP-proxied the engine; useless standalone. The
  SDK gives stdio servers with far less boilerplate and is the Claude Code
  standard.
- **Clean-room `paths.py`** rather than porting the old one — the old file was
  saturated with buy/sell/review/screener paths that encode the rejected design.

### Added (journal MCP — first working subsystem)
- **`timeutil.py`.** UTC-internal / ET-display helpers over `zoneinfo` (real tz
  lib per the invariant; `tzdata` dep covers minimal containers).
- **`journal_db.py`.** Clean-room sqlite layer (WAL, locked-retry): four record
  kinds — `journal` (notebook), `positions_of_record` (the "why"),
  `equity_snapshots`, `orders_of_record` (idempotency). Partial-update upserts.
- **`aitrader/mcp/journal_server.py`.** FastMCP stdio server exposing 12 tools.
  Unit-tested without a broker: DB CRUD + partial-update semantics + tool
  registration all verified. `docs/journal-mcp.md` written.
- **venv + editable install** working (`mcp`, `tzdata`).

### Not ported (deliberately)
- `risk.py` / `check_risk_limits`, `compute_order_prices`, screeners, scoring,
  strategies, reviewers, indicator-gates. They invert this project's mandate.
