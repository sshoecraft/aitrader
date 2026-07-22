# Changelog

All notable changes to aitrader. Each entry records *what* and *why*.

## [1.52.0] — 2026-07-22 — REVIEW restores discretionary profit-taking: two-sided thesis, TRIM/EXIT verdicts, per-cycle payoff read (winners no longer exit only via the trail)

### Why
itrader (opus) held the MPC/VLO/PBF refiner complex up ~$3,500 open profit
intraday, gave back ~$1,100 to ~$2,373, and never trimmed or banked a cent — it
only ratcheted trailing stops sitting ~0.6–1% under price. Pressed on it, the
agent was right that its constitution left it no other move: step 4a REVIEW
offered a THREE-verdict set — `HOLD / TRAIL / EXIT` — with EXIT reachable ONLY on
thesis falsification, so a green, un-falsified position could legally resolve to
only HOLD or TRAIL. There was no TRIM / take-profit verdict anywhere; the prompt
declared "the trail is how a winner gets SOLD, and a green stop-out is a SUCCESS,"
and the mandate framed cash as a failure ("idle cash and a hopeful-thesis loser
are the SAME failure"). "Sell into strength to bank the gain" was not a
representable action.

Two external reviews (GPT-5.6, Fable-5) independently ruled this boundary DRIFT,
not a legitimate mechanical invariant: it had baked a trend-following exit
STRATEGY into the prompt, foreclosing an exit modality that is the agent's
cognition (BRIEF §2/§8). The asymmetry that named it: for LOSERS the constitution
mandates only the EXISTENCE of protection and lets the agent choose the level (the
legal act-not-number line); for WINNERS it dictated the whole philosophy (run to
the trail, never trim) and deleted "take profit" from the decision surface. The
deeper diagnosis (Fable): every position carried a downside INVALIDATION (the
stop) but no upside OBJECTIVE — so a runner re-won HOLD every cycle by
construction, because the only question ever asked was "is the thesis intact?"

### What — prompts/constitution.md, boundary-safe (no fixed target/threshold/formula added; the agent authors every number)
- **Two-sided thesis at entry.** A TAKEN entry records a `position_record_upsert`
  intent carrying TWO tags — `WRONG-IF:` (the invalidation) and `WORTH:` (the
  objective: price zone / condition / catalyst / explicit open-ended). Missing
  either = step 6 NOT DONE. The `WORTH:` tag is the upside anchor REVIEW
  adjudicates every later cycle; a named catalyst files a forward-expectation (5A)
  pinging a future cycle to RE-DECIDE, never auto-exit.
- **REVIEW (4a) verdict set widened to `HOLD / TRIM n% / TRAIL → X / EXIT`,** all
  legal in every state; EXIT no longer gated on falsification. New payoff column:
  fraction of the objective already CAPTURED (paper) vs upside left · downside to
  the stop — or "wrong lens: <why>". Objective/payoff are the agent's authored
  read: NO repo target, NO multiple, NO %-of-move rule; ATR etc. computed in the
  sandbox to inform the agent's OWN number. Guard: "the objective is not a
  trigger — reaching it mandates a DECISION, not an exit; not reaching it never
  forbids a trim."
- **Removed the trend-following absolutism** ("the trail is how a winner gets
  SOLD," "a green stop-out is a SUCCESS," "verdict IS TRAIL"). Trailing and
  trimming are now BOTH available; being green forces neither.
- **Neutralized cash-aversion** in the mandate: cash is a POSITION re-won each
  cycle; cash raised by banking a realized gain, or refusing a no-edge tape, is a
  decision, never a failure. Anti-passivity kept — don't force a trade to deploy
  cash, don't hold to avoid holding it.
- **Anti-regression teeth (Fable's final review caught the first draft
  re-legalizing the exact failure).** "Add TRIM + require a verdict-and-reason"
  left `HOLD — thesis intact` legal forever. Fixed: a green row whose structure
  sits above the stop OR whose payoff shows most of the objective captured may
  HOLD only with a reason that NAMES that fact and argues against acting THIS
  cycle; a generic reason = step 4 NOT DONE. Payoff cell gets per-cell teeth
  (empty/copied = NOT DONE; "wrong lens" needs a position-specific why). The
  open-ended objective's bank-condition must differ from the invalidation.
- Reviewed per the standing constitution edit protocol (backup
  `constitution.md.backup-20260722`; GPT + Fable). Deploy via `make const`
  (owner-run) — not yet deployed.

## [1.51.2] — 2026-07-18 — journal_write auto-corrects a stale reconcile `Local:` clock against the row's own ts

### Why
atrader (gemma) wrote two consecutive reconcile entries (#375, #376) whose body
`Local:` line was ~2h06m stale — it reported the PREVIOUS cycle's clock. Forensics
on the live transcript ruled out every obvious suspect: the `now` tool was called
every cycle and returned the correct wall clock every time (verified to the
second), and the stale cycles sat inside ONE continuous session — no relay, no
compaction (atrader runs `DISABLE_COMPACT=1`). The failure is purely at step 6:
across the ~3-minute, table-heavy gap between the step-1 `now()` read and the
`journal_write`, the local model reached back into a context holding ~6
near-identical prior `now()` results and copied the wrong (previous) one — a
near-duplicate retrieval / off-by-one-cycle slip. The row's server-stamped `ts`
was correct throughout; only the hand-typed prose clock drifted. Two external
reviews (GPT-5.6, Fable-5) independently confirmed the diagnosis and ranked
"remove the hand-copy from the data path" as the fix. The dashboard was never
affected — `JournalFeed` already renders each entry's time from `ts`; the stale
value lived only in the body prose.

### What
- journal_server.py 0.2.2: `journal_write` now normalizes a grossly-stale
  reconcile `Local: <date> HH:MM TZ / HH:MM UTC` line against the authoritative
  row `ts` (`normalize_reconcile_clock`). If the body's stated UTC deviates from
  `ts` by more than `CLOCK_DRIFT_TOLERANCE_MIN` (10 min), the line is rewritten to
  the canonical ts-derived value and tagged `[clock auto-corrected — body said
  HH:MM UTC]` (never silent). The legitimate ~2-3 min step-1→step-6 gap is below
  tolerance, so fresh entries are left byte-for-byte unchanged (verified against
  live entries #369-383: only #375/#376 corrected). The stated time is resolved
  against the row date ±1 day so a real near-midnight clock is never mistaken for
  a ~24h drift. Normalization never raises — any parse failure returns the body
  untouched, so it can never fail a write.
- `journal_write` now also returns `local` + `et` (the row `ts` rendered in the
  host and NYSE clocks) so the agent never has to hand-derive them.
- Infra-only, no constitution change: the fix lives at the single write choke
  point and does not depend on model behavior. `now`-vs-`date` tool choice is
  irrelevant to this class — the value was always hand-copied across the gap.
- Follow-up (NOT in this change): the same hand-copy-across-a-table-heavy-gap
  mechanism threatens any transcribed value, most dangerously prices / stop
  levels — a sibling-bug audit of those fields is recommended.

## [1.51.1] — 2026-07-17 — install.sh + Makefile disable Claude Code's 2-min MCP auto-background (restores the scheduler sleep)

### Why
Claude Code auto-updated to 2.1.212 on the trader nodes (binary built 2026-07-16
19:28; the updater keeps a rolling 210/211/212 set). 2.1.212 is the first build
that wires MCP-tool auto-backgrounding — a client gate `tengu_mcp_auto_background`
with a default threshold of 120000 ms (2 min). Any MCP call running longer than
2 min is moved to a background "task" instead of blocking the model's turn. The
scheduler's `wait_*` tools ARE long blocking calls, and that block is the agent's
sleep (BRIEF §A.4.2). Backgrounded, they stop suspending the agent: it regains
control, ccloop's Stop hook re-feeds "keep going" (its background-work gate keys
on a live procfs writer and cannot see an MCP task), and the agent busy-loops
through downtime — burning context and hitting the broker mid-"sleep" (observed
in an atrader session: `MCP task … completed` plus 32 tool calls during the
wait). Verified by binary diff — the gate literal is absent in 2.1.210/211 and
present in 2.1.212 — and by history: on Jul 11 a 2-hour wait died at exactly
1800s, impossible if a 2-min auto-background were active then. Separate from the
1800s *idle* abort the 0.4.0 progress heartbeat already handles; the heartbeat
does nothing against this earlier wall-clock guillotine.

### What
Both run-dir settings.json writers — `install.sh` (standalone) and the `Makefile`
`run-dir` target (Makefile:102, which `make install`/`world`/`full` actually
use) — idempotently merge `env.CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS = "0"` after
seeding the file (0 disables it — the client clamps `Math.min(Math.max(0,r),MAX)`
to 0). install.sh and the Makefile are duplicated, independent paths, so both
needed it. `setdefault` merge, so existing installs self-heal on re-run and any
explicit user value is preserved (verified idempotent + non-clobbering; Makefile
verified via `make -n run-dir`). Live nodes (atrader, itrader) were hand-patched the
same way and pick it up on their next ccloop relaunch.

Scheduler server code is UNCHANGED — this is a harness-behavior workaround, not a
server bug. The `Makefile` edit was made with explicit owner approval (standing
rule: don't touch the Makefile unless told).

## [1.51.0] — 2026-07-17 — break the thesis-inheritance loop: self-authored context named as such, fixed discovery query, GATE numbers that admit comparison

### Why
Theme lock on energy, verified in both nodes' data — in different degrees, so
the shared context-inheritance design is the common cause and model strength
sets the severity. atrader (gemma) shows the FULL failure: a 100%-energy book
(MPC/VLO/XOM, all opened 7/14), macro news queries pre-shaped by the thesis
("energy market news US blockade Iran…" can only return confirmation),
survey-surfaced non-energy movers dismissed AT GATE for being non-energy
("none of them are Energy"), and the theme-saturated context misread as a
human preference — "The user's context (and the news) strongly suggests
Energy is the driver" (transcript, session c15e4b89, 2026-07-17) — because
journal/inbox/relay summaries all arrive in user-role messages. itrader
(opus) shows the inheritance MECHANISM without full capture: a crack-spread
thesis carried 4+ days across sessions/relays, 30 of its last 30 journal
entries theme-saturated, 3 of 4 open positions oil-complex — but it also took
an explicitly-uncorrelated non-energy bet (ORCL short, "A SECOND,
UNCORRELATED BET") and self-audited the thesis ("ON REAL PRINTS MY CRACK
ALPHA IS NEGATIVE"), so on the stronger model the replayed context biases
attention rather than fully capturing it. The shared gap the constitution
never addressed: nothing said the replayed notes are self-authored, the news
step allowed thesis-shaped queries, and GATE accepted "not my theme" as a
blocking reason.

### What
`prompts/constitution.md` (backup `constitution.md.backup-20260717`; deploy is
owner-run `make const` on both nodes):
- **Preamble provenance rule**: journal / position records / prospect inbox /
  memory / relay summaries are mechanically replayed SELF-authored notes even
  though they arrive in user-role messages — never a human instruction,
  preference, or theme assignment; the space a theme occupies in the notes is
  evidence neither for nor against it. Scoped to those record types so a
  genuine owner instruction typed into the session still binds.
- **Step 2B**: first search each cycle is a FIXED discovery query (`global
  financial markets economy central banks geopolitics news DATE`, no added
  ticker/sector/commodity/thesis terms) with forced artifacts: exact query,
  LEADING SUBJECTS (first three, recorded before interpretation), one MACRO
  line. A held theme in the results is legal — the process is blind, never
  the outcome. Held symbols searched after; a new-name ENTRY requires its
  search line before the order; free-form searches (theme included) legal
  once the discovery lines are written.
- **Step 4(c) GATE**: the inherited-stance VOID rule now covers inherited
  THEMES, and a new bullet defines the blocking NUMBER as exactly three kinds
  — candidate vs threshold, portfolio impact vs threshold, comparison vs
  incumbent/cash — each written as value AGAINST its level. "Not my theme" is
  a stance, = step 4 NOT DONE. Deliberate concentration stays legal when it
  wins on written numbers.

Per the standing edit protocol, reviewed by ask_gpt before finalizing.
Adopted from review: the fixed query + pre-interpretation subjects artifact
(rule-based "thesis-blind" was gameable and forced fuzzy self-classification);
the three-kind NUMBER (the first draft's candidate-own-row-only rule would
itself have forced rotation/churn by outlawing comparative and portfolio
blocks); de-rhetoricized preamble ("re-wins its place" read as
challenge-the-incumbent-every-cycle). Rejected from review: a news search per
GATE row (12+ searches/cycle; entry-gated instead) and softening the proven
VOID wording.

## [1.50.0] — 2026-07-16 — the whole stock universe surveyed with NO liquidity fact pre-market, so the agent invented a "sub-penny = uninvestable" price proxy; added prev_volume / prev_notional

### Why
Owner asked why the agent GATE-rejected EOSER (+86.6%) as "sub-penny,
uninvestable" — penny stocks are not categorically uninvestable, and the
reason smelled like a habit rather than a judgment. It was neither: it was a
symptom of missing data.

Measured live: **12,968 of 12,968 stock rows carried a blank `day_volume`.**
Not EOSER — every name in the universe.

Root cause: the survey feed is `delayed_sip` (1.37.3, for the full consolidated
tape), and its snapshot `dailyBar` only rolls to today ~15 MINUTES INTO the
session, because it is a 15-min delayed tape — before that it still serves the
prior session's bar. `bar_is_today` (broker_server.py) is therefore False for
the whole universe through every pre-market survey, and the 1.48.1 staleness
guard does exactly what it was built to do: refuse to relabel yesterday's bar
as today's, blanking day_volume/day_notional/rel_vol/day_open/high/low and
every derived range field. Confirmed by feed comparison at 13:44 UTC — NVDA
dailyBar `delayed_sip` = 2026-07-15 (yesterday, v=125,734,825) vs `iex` =
2026-07-16 (v=239,012) — and it rolled at 13:46, 16min after the open. Still
only 47.5% of a 400-name sample had rolled at 13:47.

Consequence: `pct_1d` was the ONLY usable lens precisely when the agent forms
its morning watchlist, every floored cut returned 0 rows (`min_volume` floors
on day_volume), and a raw %-move ranking surfaces sub-penny names — with no
fact available to judge whether any of them can absorb size. The agent filled
that hole with the only column it had: price. The heuristic is backwards in
both directions — EOSER at $0.0425 traded **$2.2M** the prior session, while
XOCT at $39.71 traded **$36.8k** and EVLVW (+438%!) at $0.007 traded **$3.9k**.
"Sub-penny" rejects the liquid name and passes the illiquid ones.

Not a feed-budget problem: `delayed_sip` is doing its job (NVDA 4.8M vs IEX's
283k — IEX is a ~6% keyhole), and pre-market there is no today-bar on ANY feed
at any price — the session hasn't started. The right pre-market liquidity
measure is the PRIOR session's volume, which we already had for free and were
throwing away: `pvol` was fetched only to serve as `rel_vol`'s denominator.
(Also noted: `sip` silently returns IEX data on this account — a paid feed
would need verifying, not assuming.)

### Added
- `snapshot_type_to_csv`: `prev_volume` + `prev_notional` columns — the
  completed prior session's units and dollars traded (`prev_close ×
  prev_volume`; stock/crypto only, per the existing day_notional unit rules).
  Sourced from whichever bar IS the previous session's, mirroring the choice
  `prev_close` already makes: `prevDailyBar` when today's has rolled, else the
  `dailyBar` itself. Never blank pre-market — that session is over. Still pure
  DATA per CLAUDE.md §2 (a raw fact like prev_close; no floor, score, or
  opinion in code — the agent decides what it means).
- `rank_instruments`: both are valid `by`/`lenses` values automatically (`by`
  validates against the CSV's own columns) and ride along in every returned
  mover (a mover carries the whole row). Docstring documents them, and now
  states plainly that `min_volume` floors on TODAY's volume and so removes the
  entire universe before the roll.

### Changed
- `rel_vol` now divides by the same `prev_v` (identical value — `pdb.get("v")`
  — on the only branch where it was ever used, since `dvol` is None on the
  other). Removed the now-redundant `pvol`; folded the duplicated crypto
  volume-rounding into one `vol_out` helper used by both volume columns.
- `min_volume` deliberately NOT changed to fall back to prev_volume: the agent
  journals the floors it used, and a floor whose basis silently shifts with the
  clock makes that record ambiguous. Exposed as a lens instead — the agent
  chooses the basis, which is where §2 says the choice belongs.

### Verified (live tape, no mocks)
- Pre-market branch exercised on REAL not-yet-rolled symbols: day_volume /
  day_notional stay honestly blank while prev_close/prev_volume/prev_notional
  populate (XOCT $36,806 · WOOD $189,556 · JWEL $1,339).
- Post-roll branch unchanged and correct (EOSER prev_notional $2,227,595;
  NVDA $26.7B; AAPL $20.0B).
- Ran through the real `snapshot_type_to_csv` against a temp state_dir and a
  4-symbol universe — never touched the live CSV or the IBKR gateway.
- Deploy: owner-run (broker MCP restart). NOTE: version records have drifted —
  pyproject 1.48.0, `aitrader/__init__.py` 1.7.4, CHANGELOG 1.49.x — left
  alone here rather than guessed at.

## [1.49.9] — 2026-07-16 — journal UI: SURVEY/GATE tables render as tables again (the agent stopped emitting the GFM delimiter row); unblocked the UI build

### Why
Owner-reported: the step-3 SURVEY table in journal id 464 rendered as run-on
pipe soup (`| verdict | | futures | ... | PASS | | forex |`) instead of a
table. The adjacent-pipe joins are the tell — that is two rows collapsed into
one paragraph line.

Confirmed off the DB's raw bytes: the body is NOT malformed the way 1.42.2's
was. Real newlines, one row per line, correct content — but **no delimiter
row** (`|---|---|`) under the header. GFM requires it; without it remark-gfm
parses the whole block as a lazy paragraph, and soft line breaks render as
spaces. Verified mechanically against the real parser: entry 464 produced
`table` nodes = 0, the pipe block arriving as a single `paragraph`/`text`.

The constitution's own templates DO carry the delimiter row (§3 SURVEY, §4(a)
REVIEW) — the agent reproduces the header and data rows and drops it. 45 of 53
recent pipe-bearing entries have it, 8 don't, so this is model variance, not a
template defect. Prompting harder is the wrong lever (and 1.42.2 already
settled that this class is a display concern): the fix is in the UI, and it
also repairs the 25 already-written entries retroactively. The DB body is the
record and stays untouched.

### Changed
- `ui/src/components/JournalFeed.tsx` (ui 1.6.2): `normalizeTables` now also
  synthesizes the missing delimiter row — for any pipe block whose header is
  not followed by one, it inserts `|---|...` with the header's cell count and
  indentation, on top of the existing blank-line boundary pass. A pipe row with
  no pipe row beneath it is left alone (prose, not a one-column table); blocks
  that already carry a delimiter are untouched.
- `ui/src/api.ts`: `parsePosition` now carries `expiry` through (empty string
  when absent, matching `/status`). It was dropped while `Position.expiry` is
  required, so `tsc -b` exited 2 and `make ui` (`tsc -b && vite build`) could
  not build AT ALL — pre-existing and unrelated to the table fix, but it
  blocked shipping it. Dropping the field in the UI layer also re-opened
  exactly what api.py:227-230 warns about: two same-symbol futures contracts
  on different expiries are otherwise indistinguishable (the 1.49.8 bug).

### Verified
- Replayed all 276 pipe-bearing journal entries through the real shipped
  `normalizeTables` + react-markdown/remark-gfm: **25 gained tables, 251
  unchanged, 0 regressed.** Entry 464 goes 0 → 4 tables; its SURVEY renders as
  a real `<table>`, 5 `<th>`, 3 `<tr>`, `<td>futures</td>` / `<td>forex</td>`.
- `tsc -b` exits 0 and `vite build` succeeds (both failed before).
- Deploy: `make ui` (owner-run; content-hashed assets → hard-refresh).

## [1.49.8] — 2026-07-15 — futures order placement silently drifted to a new front-month contract, orphaning a held position; a live IBKR side-normalization bug; dashboard hid two same-symbol futures contracts as unexplained duplicates

### Why
Owner-reported live anomaly on itrader: MCL showed as two positions in the
CLI (`positions`) and as six flickering rows in the dashboard, one described
as "the short" with no stop despite a stop having just been placed for it.
Root-caused to three compounding bugs, none of them display-only:

1. Every futures order placement (`place_market_order`, `place_limit_order`,
   `place_stop_order`, `place_stop_limit_order`, `place_bracket_order`,
   `close_position`) resolved its IBKR contract via `resolve_front_month`,
   which always returns whatever IBKR's CURRENT front month is (auto-rolling
   early within 5 days of expiry) — with zero regard for which contract an
   existing position is actually held in. Once the front month rolled past a
   held contract, any further order for that symbol silently targeted a
   *different* contract: a protective stop meant for an existing short landed
   on a new contract instead, leaving the real position naked and opening an
   unrelated new position under the same display symbol. `held_qty` (used by
   `close_position`) made this worse — it matched only the FIRST
   same-symbol contract it found and stopped, so `close_position` could never
   even see, let alone flatten, a second contract.
2. `map_position` (`api.py`) dropped the `expiry` field that `normalize_position`
   already attached for futures, so the dashboard/CLI had no way to show
   *why* two "MCL" rows existed — they looked like an unexplained duplicate
   rather than two distinct contract months.
3. `PositionsTable.tsx` keyed each row on `pos.symbol` alone. Two positions
   sharing a symbol collide on that React key; reconciling that across
   repeated `/status` polls is what produced the flickering 6-row duplicate
   display in the dashboard (the CLI, which doesn't use React keys, only
   ever showed the real 2).

Separately, an IBKR-side case-sensitivity bug was found in passing: order
`side` was matched with `"BUY" if side == "buy" else "SELL"` at every
placement call site — any non-exact-lowercase side (e.g. `"BUY"`, `"Buy"`)
silently resolved to `SELL`, a wrong-direction trade with no error. The
Alpaca adapter fixed the identical bug (`side_enum`) previously; IBKR's TIF
got the matching `normalize_tif` fix, but `side` never did until now.

### Fixed
- `aitrader/brokers/ibkr.py` (1.5.1 → 1.6.0):
  - `normalize_side()` — case-insensitive side normalization that RAISES on
    an unrecognized value instead of silently defaulting to `SELL`. Replaces
    every `"BUY" if side == "buy" else "SELL"` call site (order placement,
    plus the `get_historical_executions` BOT/SLD filter).
  - `held_contracts()` (new) — returns every DISTINCT contract (by conId)
    matching a canonical symbol with a nonzero position, not just the first
    match; checks both IBKR position feeds per-conId (same anti-desync logic
    the old single-contract `held_qty` used).
  - `held_qty()` — now sums across `held_contracts()` instead of reading one
    arbitrary matching contract.
  - `make_contract()` futures branch — now prefers the symbol's single held
    contract over `resolve_front_month` when exactly one exists (so an order
    on an existing position always targets what's actually held, never a
    fresh front-month lookup); RAISES if more than one distinct contract is
    held under the symbol rather than guessing which one an order should
    hit. Falls back to `resolve_front_month` only when nothing is held (a
    genuine fresh entry) — unchanged behavior for the common case.
  - `close_position()` — flattens EVERY held contract for the symbol (was:
    one `make_contract` call that could miss or mismatch), each against its
    own actual contract. Returns the usual single order dict when one
    contract closed, or `{"count": N, "orders": [...]}` when more than one
    was — the multi-contract case is now visible rather than silently
    dropping a leg.
  - `normalize_order()` — futures orders now carry `expiry`, so
    protective-order matching (below) can tell which contract an order
    belongs to.
- `aitrader/api.py` (0.7.0 → 0.7.1):
  - `map_position()` now carries `expiry` through instead of dropping it.
  - `map_order()` now carries `expiry` through.
  - `enrich_positions_with_protective_orders()` — when a position carries an
    expiry, only matches a protective order carrying the SAME expiry; two
    same-symbol futures contracts can no longer have a stop cross-attached
    to the wrong one (or double-attached to both).
- `aitrader/mcp/broker_server.py` (0.10.4 → 0.10.5): `close_position`
  docstring documents the new `{count, orders}` multi-contract return shape.
- `bin/positions` (2.0.4 → 2.0.5): when a symbol appears more than once
  within a section, appends the expiry (`YYYYMM`) to disambiguate instead of
  showing two identical-looking rows.
- `ui/` (1.6.0 → 1.6.1): `PositionsTable.tsx` rows now key on
  `symbol|expiry|side` instead of `symbol` alone (fixes the React
  duplicate-key flicker); the symbol cell shows the expiry for any futures
  position, matching card-futures.md's "track time-to-expiry on every
  position" guidance instead of only surfacing it on collision.
- `docs/broker-ibkr.md`, `docs/api.md`: documented the held-contract
  resolution rule, the `{count, orders}` `close_position` return shape, and
  the `expiry` field end-to-end.

### Known follow-on (not fixed here)
- `AllocationPanel.tsx`'s per-position chart-legend slices are also keyed on
  bare `symbol` (`key: p.symbol`), the same pattern that caused the
  `PositionsTable` bug — lower severity (cosmetic chart legend, not a
  trading-relevant display) and left alone for now.
- No live verification against itrader's actual IBKR session was done (no
  access from this box) — the diagnosis is from static code reading. Owner
  should confirm the two MCL contracts' actual expiries match this theory
  before relying on the fix in production, and decide whether the orphaned
  leg from before this fix needs manual reconciliation (this fix does not
  retroactively touch existing orders/positions).

## [1.49.7] — 2026-07-14 — daily report Activity table: the reason column was a wall of text, and partial fills of one order showed as separate rows

### Why
Owner feedback on a live daily report email flagged two problems in the same
table. First, buy/sell rows carried the agent's full journal-style rationale
verbatim — multi-sentence theses with sizing math and risk framing meant for
the notebook, not a scannable ledger ("remove reason for buy - or make it 1
liner ... this is stupid"). Second, a single logical order that filled in
pieces (4 AAVE/USD buy fills at 01:10, a stop that filled as 2 AAVE/USD sells
at 13:05) rendered as that many separate rows, each repeating the identical
reason text ("if its the same symbol at the same time for the same reason
... then combine the entries"). Both are the same root issue: the table was
built one row per broker fill instead of one row per decision.

### Fixed
- `bin/aitrader-report` (1.1.0 → 1.1.1):
  - `reason_oneline()` — the Reason cell now shows only the first sentence of
    the recorded reason (splits on the first ". " so bare decimals/ratios
    like `297.89` or `0.19:1` don't trigger an early cut), hard-capped at 160
    chars with a trailing "…" if that sentence itself runs long. The journal
    still holds the full text — this only shortens what the emailed table
    displays.
  - `merge_fills()` — fills sharing the same side, symbol, reason text, and
    displayed HH:MM collapse into one row before rendering: qty sums, price
    becomes the qty-weighted average, cost/P&L sum. Applies uniformly to buys
    and sells via the existing merged `timeline`, so a stop that fires as
    multiple IBKR fills reports as a single Sell line.
  - Verified with a throwaway script (`/tmp`, not committed) that fed both
    functions the exact rows from the reported email (the MPC/XOM/MCL reason
    strings, the 4 AAVE buy fills, the 2 AAVE sell fills) — confirmed the
    one-line headline extraction and that merged qty/price/P&L reconcile
    exactly to the sum of the underlying fills.
- `docs/report.md`: documented the one-line reason + fill-merge behavior and
  added both as design invariants not to regress.

## [1.49.6] — 2026-07-13 — IBKR stock session close mis-parsed the modern liquidHours format; `stock: open` stayed true ~4.5h past the real 16:00 ET close

### Why
Owner, watching itrader live: "its 4:25pm CT and it still shows equities
open." Pulled itrader's actual `get_available_types` results straight from
its session transcript rather than trusting the claim at face value:
confirmed live at **20:54:03 UTC (16:54 ET, 54 minutes past the real close)**
it was still returning `"stock": true`. itrader's `extended_hours` is never
enabled for this instance (never passed at the `IBKRBroker(...)`
construction site in `broker_server.py`), so `stock` should have flipped to
`false` the instant the session left `regular` — this was not a labeling
ambiguity, it was wrong.

Root cause: `session_close_from_gateway` (the function that reads SPY's
`liquidHours` from IBKR to compute today's real session close, feeding
`market_session_now`'s `now < close_utc` check) had its own bespoke,
slice-based parser that assumed the LEGACY `YYYYMMDD:HHMM-HHMM` shape. IBKR's
actual current format is `YYYYMMDD:HHMM-YYYYMMDD:HHMM` (a second date stamp
on the close side too) — confirmed already documented in this repo
(`docs/broker-ibkr.md`, written when the sibling forex/futures function was
built). Under that shape, slicing "the characters after the close-side '-'"
lands on `20260713:1600` (the date, not the time): `hour=int(close_part[:2])`
read `20`, `minute=int(close_part[2:4])` read `26` — computing a session
close of **20:26 ET instead of 16:00 ET**, a 4h26m overshoot. `market_session_now`
kept returning `"regular"` (not even `"extended"`) for that whole stretch, so
`get_available_types` kept reporting `stock: true` until nearly 8:30 PM ET,
every single trading day, since whenever this path was last touched.

The forex/futures sibling (`class_windows_from_gateway`) never had this bug —
it already used the shared `parse_trading_hours` helper (regex-based,
explicitly handles both the modern two-date and legacy one-date shapes). The
stock path had its own separate, older, narrower parser that was never
migrated to the shared helper when the modern-format handling was added
elsewhere.

Real-world impact: itrader's own reasoning wasn't fooled (its journal
narrative correctly said "Post-close" the same cycle it received `stock:
true` from the tool) — the model's own judgment already discounted the
wrong signal. But relying on a smarter model to silently route around a
broken fact is not a fix, and a weaker model (atrader/gemma) has no track
record of catching this kind of implicit contradiction reliably.

### Fixed
- `aitrader/brokers/ibkr.py` (1.5.0 → 1.5.1): `session_close_from_gateway`
  rewritten to call the shared `parse_trading_hours(det.liquidHours,
  det.timeZoneId or "US/Eastern")` — same helper `class_windows_from_gateway`
  already uses for forex/futures — instead of its own inline parser. Finds
  the window whose local start-date matches `target_date` and returns its
  `end_utc`; `None` (unmatched / gateway-confirmed CLOSED date) preserved
  exactly as before.
- No other files changed — `market_session_now`, `get_available_types`,
  `get_market_session` all call this function unchanged; the fix is entirely
  inside what it returns.
- Verified via a throwaway script (`/tmp`, not committed — reproduces the
  exact bug with a synthetic modern-format liquidHours string, not real
  IBKR data): old parser → `2026-07-14T00:26:00Z` (wrong, matches the
  observed live symptom's magnitude); new parser → `2026-07-13T20:00:00Z`
  (correct 16:00 ET). Also verified: legacy `YYYYMMDD:HHMM-HHMM` format
  still parses correctly (backward compatible), a gateway-confirmed
  `CLOSED` date still returns `None`, and a date with no matching entry
  still returns `None` rather than a stale window. Could not exercise the
  live `reqContractDetailsAsync` call itself — `ib_async` isn't installed in
  this source-tree checkout (paper-account/gateway-only optional extra) —
  so this verifies the parsing logic exhaustively; the owner's post-deploy
  observation is what confirms the live IBKR round-trip end to end.
- Deploy is OWNER-run (build+install+restart) — prepared in `/src/aitrader`
  only, not yet deployed as of this writing.

## [1.49.5] — 2026-07-13 — snapshot CSV gets day_range_pct: a volatility-normalized fact, so a mid-cap's move stops losing to a penny stock's on raw %

### Why
itrader (owner's wife, Julie, asking about small/mid-caps it never surfaces)
self-diagnosed a real structural gap in its own reasoning: ranking the
12,941-name stock universe by raw `pct_1d`/"biggest % move" is mechanically
won by low-priced names every time — a $4 stock can physically swing a
larger % than a $300 one on the same dollar move, so a genuine, tradeable
move in a quality mid-cap can't make a raw-%-move top-3 cut. It named this
the same blindness that hid MPC (this account's best trade that day) for
five straight cycles, and asked to "build a screen filtered by tradeable
geometry (volatility under ~5% of price, real dollar volume) rather than
raw % move."

That capability already mostly exists — `rank_instruments` ranks/floors by
any snapshot column, and the agent already has full sandbox access to
derive whatever it wants from the CSV (it had just done exactly that for
ATR). But there was no CHEAP, always-there column for "how much has this
actually moved today, normalized for its own price level" — every agent
would have to hand-derive it from day_high/day_low/price in a scratch
script every time instead of it just being there, same reasoning that
already motivated adding pct_intraday/gap_pct/range_pos (CHANGELOG 1.40.0).

### Added
- `aitrader/mcp/broker_server.py` (0.10.3 → 0.10.4): new snapshot CSV column
  `day_range_pct` = (day_high − day_low) / price × 100 — today's high-low
  spread as a percent of price. Pure arithmetic off fields the row already
  carries; blank under the exact same condition as pct_intraday/gap_pct/
  range_pos (bar hasn't rolled to today yet). Immediately usable as
  `rank_instruments(by="day_range_pct", ...)` — no new tool, just a new
  column value the existing `by` parameter already accepts dynamically.
  Docstrings (`get_all_snapshots`, `rank_instruments`) updated with the
  column and its purpose.
- Still a raw FACT, not a quality score: it says how much a name moved
  relative to itself today, nothing about whether that move is "good" —
  the agent still ranks, floors, and decides entirely on its own. No
  pre-picked shortlist, no threshold baked into infra.
- Verified via a throwaway script (`/tmp`, not committed — synthetic
  snapshots for a $4 and a $300 name, not real market data): the column
  correctly normalizes the two to comparable magnitudes, is blank exactly
  when the bar hasn't rolled to today, and `rank_instruments(by=
  "day_range_pct")` ranks by it end-to-end without any other code change.
- Deploy is OWNER-run — prepared in `/src/aitrader` only, not yet deployed.

## [1.49.4] — 2026-07-13 — rank_instruments' exclude_held re-fetched broker positions on EVERY call; cached it

### Why
Owner reported `rank_instruments` "taking a VERY long time each time" on
itrader (IBKR). Measured actual latency from itrader's own session
transcripts (matching each `tool_use` to its `tool_result` timestamp):
~21% of calls took 3-9s against a typical ~0.1s, with no correlation to
`asset_type` or CSV size — the 1-2KB forex/futures CSVs were slow just as
often as the 1.4MB stock one, which ruled out CSV parsing as the cause.

Root cause: both `rank_snapshot_csv` (single-lens) and `_rank_multi_lens`
call `broker().get_positions()` on every invocation to build the
`exclude_held` filter set — not once per cycle, once per `rank_instruments`
call (THE LOOP's step 3 makes 2 calls per open type: floorless + floored,
so 4-8 calls/cycle across stock/futures/forex). For IBKR, `get_positions()`
can fall into `recover_portfolio()` (`ibkr.py`) whenever `ib.portfolio()`
returns momentarily stale/empty — a known `ib_async` cache-lag quirk — which
retries with up to 5 sequential `await asyncio.sleep(1.0)` once it sees
`GrossPositionValue >= $1000`. itrader currently holds ~$40k (VLO + XOM),
so that gate is live. Alpaca's `get_positions()` is a plain REST call with
no retry loop, which is why atrader never showed this. (A second,
independent contributor — clyde running 25+ qemu test VMs alongside
vLLM, swapping under memory pressure — caused a separate ~17-18s stall
observed across EVERY MCP tool, not just this one; owner resolved that
host-side before this fix, so it's out of scope here.)

### Changed
- `aitrader/mcp/broker_server.py` (0.10.2 → 0.10.3): added `_held_symbols()`
  — a 60s-TTL cache in front of the `exclude_held` lookup, used ONLY by
  `rank_instruments`'s two internal call sites. The public `get_positions`
  MCP tool (RECONCILE, order-fill confirmation) is untouched — still always
  live — so nothing safety- or fill-critical can see stale data; a
  minute-stale held-set can only affect whether an already-held name is
  also shown as a ranking candidate, never an order/position record.
  Verified via a throwaway script (stub broker + synthetic CSV, not
  committed): 5 rapid `rank_instruments`-style calls now cost 1 broker
  round-trip instead of 5, exclude_held filtering still excludes the right
  symbol, cache still correctly expires and re-fetches after the TTL, and
  `exclude_held=False` still bypasses the broker entirely.
- No change to `recover_portfolio()` or any IBKR sync logic — that
  mechanism is correct for RECONCILE; this fix only stops paying its cost
  redundantly from a candidate-ranking filter that doesn't need
  millisecond-fresh positions.
- Deploy is OWNER-run (build+install+restart) — a repo edit alone does not
  change what either live agent runs.

## [1.49.3] — 2026-07-13 — step 6 JOURNAL never named the write tool; a resumed cycle skipped it entirely

### Why
Owner ran `make world` on atrader; the service restarted mid-sleep between
cycles. The resumed session (ccloop resume framing: "previous session may
have crashed") re-ran a full, complete-looking cycle — RECONCILE, SURVEY,
GATE, FORWARD EXPECTATIONS all rendered correctly as chat text — but never
called `journal_write`. Confirmed from the raw session transcript
(`*.jsonl`, scanned for every `tool_use` block): zero attempts that cycle,
not a failed or malformed call. No information was actually lost (the cycle
was a redundant re-derivation of the already-journaled prior state), but the
gap is real and would bite on a cycle that does contain a new decision.

Root cause: step 6 is the only step in THE LOOP whose forced artifact is a
tool call but which never names that tool. Every sibling step that requires
a call says so explicitly in backticks (2A: "submit ... via `prospect_ack`";
2C: "submit ... via `insight_hypothesize`") — step 6 named only
`position_record_upsert` (a secondary call) and otherwise only said "Write
what you did and why," which reads as an instruction to render text, not to
persist it. Same shape as two prior fixes to this doc
(`constitution-steps-not-prose`, `constitution-enforce-via-step-not-column`):
the weaker local model reliably complies with a prose-described *chat*
artifact and just as reliably drops a call that isn't named as its own
forced step.

### Changed
- `prompts/constitution.md` (`ask_gpt` review obtained per
  `constitution-edit-protocol`; review flagged three secondary risks in the
  first draft — ambiguous `kind`, a premature call before the text was
  finished, and "lands" wording that could read as license to retry
  indefinitely — all three addressed in the landed wording):
  - Step 6: added "After assembling that complete text, call
    `journal_write(kind, body[, symbol, tags])` — `kind=\"reconcile\"` for
    this per-cycle entry, the full text above as `body` — exactly once,"
    plus "Rendering the text in your response does not persist it: step 6
    is NOT DONE until `journal_write` succeeds, no matter how complete the
    written text looked" — same enforcement idiom ("NOT DONE") used
    throughout the rest of the document, applied here for the first time to
    the step that had been missing it.
  - No change to `journal_write` itself (`journal_server.py`) — it already
    does the right thing (raises on an empty body rather than silently
    no-op'ing); the gap was purely that the constitution never told the
    model to call it by name.
- Deploy is OWNER-run (`make const`/`make world`) — a repo edit alone does
  not change what either live agent reads.

## [1.49.2] — 2026-07-13 — rank_instruments docstring: no quoted literals a weak model could imitate into a malformed native tool call

### Why
Owner spotted `rank_instruments` calls arriving corrupted in atrader's log
(`asset_type: "stock**,by:"`, `pct_intraday**,direction: "up**,n:3"` —
`AssetType` correctly rejected them; nothing in aitrader was ever fooled).
Traced to the root cause by copying the actual gemma4 native tool-call
parser (`vllm/parser/gemma4.py` in the local vLLM fork — the model is
served in a custom `<|"|>`-delimited format, not standard JSON) into a
throwaway script and testing candidate raw strings against it until one
reproduced the exact garbage character-for-character: the model opened and
closed its native string delimiter around TWO arguments' worth of content
at once, using a literal `**,` as an improvised (invalid) boundary between
what should have been separate arguments — self-diagnosed in its own
transcript ("I included the `**` ... trying to emphasize them").

Both failing calls (the pre-existing `by`/`direction` floorless call AND the
new `lenses` call) share something: this tool's OWN docstring shows their
example values wrapped in ordinary quote marks (`'up'`, `'down'`, `'abs'`,
`lenses="pct_1d:up,..."`) — the same convention nearly every other model
family uses for tool-call arguments, and NOT the native `<|"|>` delimiter
this specific model must use instead. A model pattern-matching its own
tool's documented example directly into the call it constructs would
produce exactly this failure. Self-recovering (both observed cases got a
clean, valid retry within 5-10 seconds — a token/latency cost, not a
correctness or blocking issue), so this isn't an emergency, but it's a
cheap, low-risk, in-aitrader's-own-code fix worth taking regardless.

### Changed
- `rank_instruments` docstring (`broker_server.py` 0.10.1 → 0.10.2): removed
  every quoted-literal example value (`'up'`/`'down'`/`'abs'`,
  `'stock'|'crypto'|...`, `lenses="pct_1d:up,..."`) in favor of either plain
  prose (`up or down ... or abs`) or backtick code-spans for placeholders
  (`` `<by>` ``, `` `<by>:<direction>` ``) — nothing left that reads as a
  copy-pasteable quoted string literal. Added an explicit line to the
  `lenses` doc: "No quote characters belong inside an entry itself."
  Scope: only this tool's docstring (aitrader's own code) — the shared
  vLLM chat template / tool-call parser is NOT touched by this change; that
  stack was investigated (confirmed the running service uses the model
  snapshot's bundled template, functionally identical to the standalone
  copy in `~/models/`) but left alone as out-of-scope shared infra.
- No behavior change — docstring only, verified the module still imports
  cleanly and the existing regression suite still passes unchanged.
- Deploy is OWNER-run (package build+install + restart) — a repo edit alone
  does not change what either live agent reads.

## [1.49.1] — 2026-07-13 — GATE completeness gets a mechanical count instead of a memory task

### Why
1.49.0 deployed and worked exactly as designed on the first live cycle:
atrader's survey correctly surfaced a full candidate set via the new
floored-cut lenses (13 unique stock names, ~9 crypto). But step 4's GATE —
which has always required one row per survey-surfaced name — dropped ~80%
of them (13+9 surfaced, 4 GATE rows written). itrader, given a
similarly-sized candidate set the same morning, wrote 12 fully-reasoned
GATE rows with zero drops — direct evidence this is a completeness gap
specific to the weaker model at this candidate volume, not a wiring
problem (the shared infra now hands both agents the identical, complete
set — that part is proven working).

Diagnosis: GATE's *existence* is a forced step (never skipped) — GATE's
*completeness* was enforced only by a prose consequence ("a survey-surfaced
name with no row = step 4 NOT DONE") with nothing mechanical backing it, no
number the model could check its own row count against. Same shape as the
original step 3(b) gap this session already fixed once, one level
downstream, and not yet given the same treatment.

### Added / Changed
- `rank_snapshot_csv`/`_rank_multi_lens` (`broker_server.py` 0.10.0 →
  0.10.1): multi-lens `rank_instruments` calls now return `unique_movers` —
  the DISTINCT symbol count across every requested lens combined (a name
  topping two lenses counts once, not twice). Computed from data the
  function already has in hand; no new tool, no new call.
- `prompts/constitution.md` (`ask_gpt` review obtained per
  `constitution-edit-protocol`; review flagged and we dropped an initial
  "explain your collapses" escape-hatch draft as a real loophole — it would
  have let the model explain away exactly the drops this fix targets, and
  risked teaching a false "same sector = same candidate" equivalence — the
  landed version is a strict count match, no exceptions):
  - Step 3(c): "Also record its `unique_movers` count."
  - Step 4(c): "For each type, the number of GATE rows whose symbol is one
    of step 3(c)'s floored-cut names must equal that call's `unique_movers`
    — a row covering more than one symbol counts once, not per-symbol."
  - Two sentences total, no new lettered sub-step, no new table column —
    deliberately narrow given this doc's growth history (~51% in the 2 days
    before this session; every prior addition, including this one, has been
    evidenced by a specific live failure, never spec work — see
    `constitution-stripped-to-mechanics`).
- Verified: stubbed regression with a fixture specifically designed for
  partial lens overlap (one symbol topping two lenses) confirms
  `unique_movers` dedupes correctly (naive per-lens sum 4 → true union 3),
  not just "returns the same number as before." Live smoke test against the
  real universe: 12 per-lens slots (3 × 4 lenses) → `unique_movers=10` (2
  genuine duplicates), matching the exact symbols from the live cycle that
  exposed the bug (BMNU/VEEE/AGEN/AXTX/JLHL/KORU/MU/QQQ/SNDK/AMIX).
- Scoped deliberately narrow, not claimed as full GATE completeness: this
  covers the floored-cut set specifically (the population actually observed
  being dropped) — NOT the floorless top-3 or ACT candidates, which stay on
  the existing prose-only requirement per `ask_gpt`'s review (a smaller,
  already-working memory burden; expanding the mechanical check to cover
  them too is future work if the same failure shows up there).
- This is an explicit TEST of a hypothesis, not a guaranteed fix: does
  handing the weak model a hard, checkable number fix GATE completeness (a
  forcing-mechanism gap, consistent with every prior finding in this
  project), or does it persist even with the number in hand (evidence of a
  raw capability ceiling for this model at this candidate volume, which
  would need a different kind of fix — e.g. tool-side pre-populated GATE
  row stubs, per `ask_gpt`'s longer-term recommendation)? Next cycle's
  journal is the evidence either way.
- Deploy is OWNER-run (package build+install + `make const` + restart).

## [1.49.0] — 2026-07-13 — rank_instruments gets multi-lens cuts; constitution makes the floored pass mandatory

### Why
Live transcript inspection (root-causing an unrelated question — "the market
is open, why didn't atrader evaluate any stock buy?") found atrader (local
vLLM/gemma) makes exactly ONE `rank_instruments` call per asset type every
cycle: FLOORLESS, `n=3`, nothing else. Constitution step 3(b) only REQUIRES
that floorless call; applying a floor afterward was worded as optional
("Floors are a lens you may apply AFTER..."), and atrader never exercises
that option. On a ~13,000-name stock tape, a floorless top-3-by-%-move is
almost always penny/warrant noise (verified live: a stock +172.7% on $4k
traded, another +81.4% on $1.6k, another +75% on a **$4** total) — correctly
passed as junk, and then nothing else about stocks is ever looked at.
itrader (opus) never has this problem because it never calls
`rank_instruments` at all: every cycle it writes its own sandboxed pandas
script against the raw CSV with its own ad hoc floor and multiple lenses
(biggest % up/down, most dollars traded, highest unusual volume) — exactly
what `rank_instruments` (1.38.0) was built to give the weaker model a
reliable, tool-call-shaped equivalent of. The constitution just never forced
the second call for the model that actually needs the tool to do it.

### Added
- `rank_instruments` / `rank_snapshot_csv` (`aitrader/mcp/broker_server.py`,
  0.9.2 → 0.10.0): new `lenses` param — a comma-string (or list) of `"<by>"`
  or `"<by>:<direction>"` (direction defaults `up`), e.g.
  `lenses="pct_1d:up,pct_1d:down,day_notional:up,rel_vol:up"`. Runs the
  shared filter pass (`min_price`/`min_volume`/`fresh_only`/`exclude_held`)
  ONCE, then sorts/truncates per lens, returning
  `{..., lenses: {"<lens>": {count, by, direction, excluded, movers}, ...}}`.
  Deliberately a FLAT list of short scalar strings, not nested JSON objects —
  gemma's tool-call JSON construction is unreliable past short scalar args
  (see `rank-instruments-tool`), which is the whole reason this tool exists
  instead of "rank it yourself in the sandbox." `lenses=None` (the default)
  is byte-identical to pre-1.49.0 behavior — the original single-lens code
  path is untouched, multi-lens is a new, separate, additive path.
- Verified: a stubbed regression test confirms the single-lens path's exact
  shape/ordering is unchanged, and a multi-lens call applies the shared
  floor once with correct per-lens `movers`/`no_data`. A live smoke call
  against the real current universe (12,939 stock rows) returned
  `day_notional:up` = MU/QQQ/SNDK/NVDA/SPY — matching, almost verbatim, the
  names itrader finds by hand in its own journal the same morning.

### Changed
- `prompts/constitution.md` (backup `.backup-20260713` taken first,
  `ask_gpt` review obtained per `constitution-edit-protocol` before landing —
  review flagged and fixed: a direct contradiction between (b)'s "may apply"
  and the new (c)'s "MANDATORY"; that a both-floors-at-0 call would satisfy
  "floored" in letter only; an underspecified required-artifact list; and
  one sentence reading as advocacy rather than mechanics — all incorporated
  before landing):
  - Step 3(b): "Floors are a lens you may apply AFTER..." → "Floors come
    only AFTER you have seen this unfiltered top — (c) below makes that
    pass MANDATORY, not optional."
  - New step 3(c): one more required `rank_instruments` call per type,
    `lenses="pct_1d:up,pct_1d:down,day_notional:up,rel_vol:up"`, `n=3`, and
    a `min_price`/`min_volume` of the agent's choosing with **at least one
    greater than 0** — its own forced sub-step with its own "= step 3 NOT
    DONE" enforcement line (per `constitution-enforce-via-step-not-column`:
    a soft clause folded into an existing step is what a weak model reliably
    skips; a step with its own enforcement line is what it follows). Old
    (c) VERDICT renumbered to (d), text unchanged.
  - Survey table gains a column for the floored-cut result; the "Every cell
    holds what you READ" enforcement paragraph and step 4(b)/(c)'s
    cross-references ("every floorless top-3 name...") extended to cover it
    too, so names this surfaces actually flow into RANK/GATE.
- `rank_instruments` docstring: clarified that `direction` on an unsigned
  magnitude column (`day_notional`, `day_volume`, `rel_vol`) is a
  largest-first/smallest-first sort, not a bullish/bearish signal — flagged
  by the review as a real misreading risk for `day_notional:up` specifically.
- Deploy is OWNER-run (package build+install + `make const` + restart) — a
  repo edit alone does not change either live agent's behavior.

## [1.48.2] — 2026-07-13 — snapshot CSV: close the residual day_high/day_low violation on thin names

### Why
Verifying 1.48.1 live, itrader's own acceptance test (journal entries
378/379) found the arithmetic-impossibility rate dropped 14.3% → 3.83%
(496/12,939 rows) but did not reach itrader's stated PASS bar of ~0%.
Splitting that residual live: most of the movement (3,148 rows) was
legitimately-blank `day_high`/`day_low` (bar not yet rolled — 1.48.1 working
as designed, not a bug) miscounted as still-corrupt by a naive check; the
real remainder was ~230-500 rows where a bar that HAS rolled to today still
shows `price` outside its own `[day_low, day_high]`. Live re-pulls of the
named symbols (IYK/AVD/BRKU/OPTH) confirmed the mechanism: e.g. IYK's row
had `day_high=74.87` against `price=75.01`; a fresh pull minutes later showed
the vendor's own `dailyBar.h` had caught up to 75.03. This is the vendor's
same-session aggregate lagging the very latest tick by seconds — worst on
thin/leveraged/preferred names — not a session-mismatch (1.48.1's target).

### Fixed
- `aitrader/mcp/broker_server.py` (0.9.1 → 0.9.2), `snapshot_type_to_csv`:
  once `bar_is_today` and `price` are both established, widen `day_high` up
  / `day_low` down to include `price` if the vendor's own bar hasn't caught
  up yet. Not a guess: a print that genuinely happened today means today's
  true high is *at least* that print and today's true low is *at most* that
  print, so `day_low <= price <= day_high` (and `range_pos` in `[0,1]`) hold
  by construction afterward. Does not touch the not-yet-rolled branch
  (those fields correctly stay blank — 1.48.1's fix).
- Verified: extended the 1.48.1 stubbed repro with an IYK-shaped fixture
  (bar rolled today, `dailyBar.h` below the live price) confirming the widen
  + resulting `range_pos == 1.0`. Live re-check against the real, full
  current universe (12,939 rows, itrader's own exact Check-1 script):
  **0.00% corrupt**, down from 3.83% — itrader's stated PASS bar, met. All
  8 previously-named still-bad symbols (OPTH/BFH.PRA/AIFF/EWV/BBLG/IYK/
  BRKU/AVD) individually reconfirmed clean.
- Not changed: itrader's own permanent `get_snapshot`-before-order
  verification gate and Check-1 arithmetic-impossibility detector stay
  exactly as itrader designed them — this fix closes a specific residual,
  it does not (and shouldn't) argue the CSV never needs independent
  verification before an order.
- Deploy is OWNER-run — a repo edit alone does not change the live CSV.

## [1.48.1] — 2026-07-13 — snapshot CSV: stop pairing a live price with a stale dailyBar at/near the open

### Why
An `itrader` session root-caused a near-miss: the survey CSV written 2 minutes
after the open showed a fabricated "tanker breakout" (a real fundamental —
VLCC rates near-doubled — happened to agree with corrupted numbers) that
almost got sized and ordered before the agent noticed `prev_close` didn't
match Friday's close from `get_bars`.

Root cause: Alpaca's snapshot `dailyBar` rolls to the new session on a
symbol's FIRST *consolidated* print of that session, not at the bell. Written
soon enough after the open, most of the universe still carries the PRIOR
session's `dailyBar`/`prevDailyBar` while `latestTrade` is already live —
`snapshot_type_to_csv` paired that live price against the stale bar
unconditionally, so `prev_close` came out one session too far back (e.g. FRO
36.56 [Thursday] instead of 38.11 [Friday]) and `day_open/high/low/volume`
carried the prior session's range mislabeled as today's. On the observed
snapshot (12,914 rows): `price > day_high` in 6.2%, `price < day_low` in
9.6%, `range_pos` outside `[0,1]` in 14.3% — e.g. INSW's live pre-market
print of 89.9999 read against Friday's high of 88.54 as `range_pos` 1.28.
`rank_instruments(fresh_only=True)` did not filter these out: it checks
`last_trade_ts` (the TRADE's date, genuinely "today" for a pre-market print),
not the BAR's date — the wrong field for what it was trying to guard.

### Fixed
- `aitrader/mcp/broker_server.py` (0.9.0 → 0.9.1), `snapshot_type_to_csv` row
  builder: compare the bar's own timestamp to today's date
  (`bar_is_today`). When the bar has NOT rolled yet: `day_open/day_high/
  day_low/day_volume` (and everything derived from them — `rel_vol`,
  `day_notional`, `pct_intraday`, `gap_pct`, `range_pos`) go BLANK instead of
  silently carrying the prior session's values under today's label, and
  `prev_close` is sourced from the (stale-but-real) `dailyBar.c` itself
  rather than `prevDailyBar.c`, which would be two sessions back. Blank
  beats confidently wrong: downstream fields go null instead of poisoning
  every ratio computed from them, and `price > day_high` / `range_pos`
  outside `[0,1]` become structurally impossible (the bounding fields are
  blank whenever they aren't genuinely today's). `last_trade_ts` needed no
  change — it already tracked the PRICE's own provenance correctly; the bug
  was the other columns not carrying the same discipline.
- Updated `get_all_snapshots`'s docstring to describe the new blank-until-
  rolled behavior (previously said untraded names show "YESTERDAY'S" pct_1d
  — now they read a flat 0% and the range columns are blank, not a stale
  number under a misleading column name).
- Verified against a stubbed reproduction of the exact FRO/INSW scenario from
  the writeup (no live broker needed): `prev_close` now lands on the correct
  prior close, the range columns blank out instead of bounding the price
  impossibly, and an already-rolled control row is untouched byte-for-byte.
- Checked against all three brokers' snapshot shapes, not just Alpaca:
  MYSE's `dailyBar`/`prevDailyBar` are genuine last-2-bars (same latent bug,
  same fix applies) — IBKR's `dailyBar.t` is really "last ticker update," not
  a bar date, and it duplicates `prevDailyBar.c == dailyBar.c` already, so
  this change is a no-op there when connected and, on no-tick-yet, replaces a
  confident `0.0` placeholder with blank (a strict improvement).
- Not changed: `rank_instruments`'s `fresh_only` filter. With the row-builder
  fix, a stale-bar row's `by`-column is either correct (`pct_1d`, `price`) or
  blank — and blank already self-excludes via the existing `no_data` path —
  so there was no remaining failure mode left for `fresh_only` to guard
  against; no compensating filter needed downstream once the source CSV
  can't misrepresent a stale bar as today's.
- Deploy is OWNER-run (package build+install + restart the broker MCP
  process) — a repo edit alone does not change the live CSV.

## [1.48.0] — 2026-07-12 — constitution made paper/live-agnostic; mandate drops the VTI benchmark

### Why
Owner review of the constitution's opening: "You are the autonomous
portfolio manager for a **paper trading account**" and a House-fuses bullet
("Paper account only. The broker adapter refuses anything else.") baked
paper-specific language into the PROMPT, when the actual paper-only
enforcement lives entirely in broker code (`ibkr_connection.py::assert_paper`
verifies the real connected account ID; Alpaca's `paper=` flag selects a
physically separate endpoint) and is completely unaffected by anything the
prompt says. Owner wants ONE constitution text usable unmodified whether the
account is paper or eventually live — paper-specific wording in the prompt
serves no enforcement purpose and would just need editing later.

Separately: "why beat VTI? what happened to the success criteria" — the
mandate's benchmark line didn't match the actual operational goal already
in use as the ccloop harness's stop-hook criteria ("Grow the account...
by any means necessary"). First attempt at fixing this literally copied
that $1,000,000,000 figure into the constitution too — WRONG per the owner:
that number is the ccloop STOP condition, a harness concern, not the
agent's own identity; hardcoding it here would (a) imply a ceiling ("stop
trying once you hit $1B") the owner explicitly does NOT want, and (b)
create a second place needing an edit if the harness target ever changes.
Corrected to an open-ended, uncapped goal with no dollar figure at all.

### Changed
- `prompts/constitution.md` (31,427 → 31,481 B; backups
  `.backup-20260712-premandate` taken first, `ask_gpt` review obtained per
  `constitution-edit-protocol` before landing):
  - Para 1: "portfolio manager for a **paper trading account**" →
    "portfolio manager for **a brokerage account**."
  - Mandate: "grow the account and beat VTI, net of costs" → "grow the
    account, by any means necessary within the house fuses below, net of
    costs — judged on long-run compounded growth, never any single cycle's
    result." No dollar target, no ceiling — `ask_gpt`'s review flagged that
    "by any means necessary" unbounded could read as license to override
    the fuses themselves; "within the house fuses below" closes that
    reading without reintroducing an index benchmark or a cycle-by-cycle
    performance requirement (which would encourage forced trades).
  - House fuses: deleted the "Paper account only" bullet entirely — unlike
    every other fuse in that list, it was never a behavioral instruction
    the agent acts on; it's an infra fact enforced in broker code
    regardless of prompt wording, so it doesn't belong in a doc meant to
    read identically across paper/live.
  - Order-mechanics: "On the paper feed a marketable order fills
    GRADUALLY..." → "In this execution environment a marketable order
    fills GRADUALLY..." — same fill-latency guidance, no paper-specific
    framing.
- Verified: zero remaining case-insensitive matches for "paper", "VTI", or
  "live account" anywhere in `prompts/constitution.md`.
- Deploy is OWNER-run (`make const` or package install + restart).

## [1.47.0] — 2026-07-12 — new card-shorting; the edit-review protocol now covers cards, not just the constitution

### Why
Neither model reliably knows shorting is available — the long-only guard
kept it moot for weeks, and tonight's discovery arrived via a leading
question that got scrubbed (see `ibkr-long-only-guard-removed`,
`futures-zeros-and-mcp-bypass`) specifically to avoid biasing behavior. The
owner wants the CAPABILITY documented without any of that narrative: a
plain, neutral fact card, same category as `card-crypto`/`card-futures`/
etc. First draft ran through `ask_gpt` review and came back flagged for
exactly the failure this whole night was about — repeated
normalization/encouragement language ("not riskier by policy," "mirror of
a long," "stop discipline matters MORE") that reads as a nudge toward
shorting rather than a neutral mechanics statement, plus a factually
incomplete asymmetry claim (missed borrow/recall/dividend-owed/gap-through
facts). Rewritten as pure mechanics with all selection/sizing/stop POLICY
explicitly deferred to the constitution.

Separately, the owner extended the constitution-edit-protocol standing rule
(backup + higher-order-model review before landing) to cover cards too — a
card is read with the same authority as constitution text ("your card-*
notes are this account's hard-won per-asset evidence"), so a card that
reads as encouragement rather than fact is just as capable of biasing
behavior as a constitution edit, via a smaller file that's easier to add
without applying the same scrutiny.

### Changed
- New `prompts/ccmemory-seed/card-shorting.md` — states: this account
  supports short orders in borrowable stocks/futures; a stock short's max
  loss has no price ceiling (vs. an unlevered long's capped-at-investment
  loss); borrow availability/rate can change and a recall/margin change can
  force a cover; short seller owes dividends; a stop does not cap a short's
  loss (gaps/halts/squeezes fill through it); futures shorting is
  mechanically symmetric to a futures long; crypto cannot be shorted via
  this account's configured Paxos/ZeroHash spot route (a venue fact, not a
  policy); paper accounts may not realistically model live-account short
  frictions. Explicitly does NOT take a view on whether/when to short.
- Landed directly into itrader's live `.ccmemory` (immediate availability,
  no restart needed) in addition to the source seed directory (reaches
  atrader + any future instance via `make const`).
- ccmemory `constitution-edit-protocol` broadened: now covers
  `prompts/ccmemory-seed/*.md` (the curated cards), not just
  `prompts/constitution.md`. Same two steps — backup before editing an
  EXISTING file (moot for a brand-new card), review by a higher-order model
  (`ask_gpt` or `ask_fable`) before landing, asking explicitly whether the
  framing reads as neutral fact or as a behavioral nudge.

## [1.46.0] — 2026-07-12 — long-only guard removed: shorting was silently blocked on IBKR, by our own code

### Why
itrader's own session log said it plainly: *"shorting is blocked GLOBALLY on
this adapter... This account is long-only... Every 'short side' candidate in
my survey language has been unactionable this whole time."* Confirmed by
code inspection, not IBKR: `aitrader/brokers/ibkr.py::verify_position_for_sell`
was called from `place_market_order`/`place_limit_order`/
`place_stop_limit_order`/`place_stop_order` whenever `side == "sell"`, and
raised `ValueError("... would create accidental short")` any time the sell
qty exceeded held quantity — refusing every short-side stock/futures order
before it ever reached IBKR. This has nothing to do with IBKR account
permissions or exchange rules: `aitrader/brokers/alpaca.py` has zero
equivalent check (already documented in `docs/broker-data-feed.md` as "No
long-only enforcement" for Alpaca — a known asymmetry nobody had connected
to a live trading limitation until tonight). The guard was carried over
verbatim from `/src/trader`'s IBKR driver during the clean-room port
(present since aitrader's initial commit) and never revisited — exactly the
inherited-risk-engine-logic class of thing CLAUDE.md §8 says should never
have survived, and directly contradicts this project's own Locked Decision
that the agent owns ALL sizing/risk with NO fuses beyond paper-only (§3).
The constitution itself has ALWAYS written as if shorting were available
("longs AND the short side", "hedge, or short") — the agent was never told
this door was welded shut, it just silently failed every time it reached
for the handle.

### Changed
- `aitrader/brokers/ibkr.py` (1.4.3 → 1.5.0): removed `verify_position_for_sell`
  entirely and its 4 call sites. Also removed the `side="sell_short"`
  crypto-rejection special case in `place_limit_order` — it was a partial,
  inconsistent, UNDOCUMENTED workaround (bypassed the guard in 3 of 4
  methods, explicitly blocked only for crypto in the 4th), never exposed in
  the constitution or any MCP tool docstring (`side` was always documented
  as `buy`/`sell` only), so it was unreachable through the sanctioned
  interface regardless. `place_bracket_order` never had this guard — an
  existing inconsistency, now moot since nothing else has it either.
  `held_qty()`/`recover_portfolio()`/`get_forex_cash_positions()` are
  unaffected (still used elsewhere).
- A short that IBKR itself genuinely can't fill (e.g. crypto shorting isn't
  a real Paxos/ZeroHash capability) now surfaces as IBKR's own rejection —
  aitrader's driver no longer pre-empts it with a guess.
- `docs/broker-ibkr.md`, `docs/broker-data-feed.md` updated with the removal
  and its history.
- Deploy is OWNER-run — package install/restart, not `make const` alone
  (this is Python source, not the constitution).

## [1.45.0] — 2026-07-12 — IBKR snapshot fields fixed, bulk-bars CSV tool, closed broker-data path

### Why
Reading itrader's last session log (owner-directed audit) surfaced two
separate issues. First: a futures snapshot showed `latestTrade.s=0.0`,
`.t=""`, and `dailyBar.h/l/v=0.0` on every contract, read by the agent as
"no live futures data on this node." Code inspection found `latestTrade.s`/
`.t` and `dailyBar.t` were HARDCODED literals in `IBKRBroker.get_snapshot`/
`get_snapshots` — never read from the ib_async ticker at all, regardless of
whether real data was flowing (the h/l/v zeros are a separate, likely-genuine
market-data-subscription gap on this IBKR account/gateway for CME futures,
not fixable in code). Second, and more serious: earlier in the SAME session
the agent needed bars for ~400 stock symbols × 90 days, judged that pulling
that through the `get_bars` MCP tool would dump enormous JSON into its
context, found no bulk/CSV alternative, and instead discovered + curl'd the
DASHBOARD's own internal FastAPI backend (`aitrader-api.service`, a separate
service with its own IBKR connection meant for the UI, not the agent) to
fetch bars directly — bypassing the broker MCP entirely. Legitimate context
concern, unsanctioned side-channel: that API isn't a declared tool, isn't
guaranteed to stay consistent with the MCP data path, and its port is
dynamically allocated.

### Changed
- `aitrader/brokers/ibkr.py` (1.4.2 → 1.4.3): `get_snapshot`/`get_snapshots`
  now read `ticker.lastSize` → `latestTrade.s` and
  `ticker.lastTimestamp`/`ticker.time` → `latestTrade.t`/`dailyBar.t`
  (ISO-formatted) instead of the hardcoded `0.0`/`""`. Does NOT fix missing
  `dailyBar.h/l/v` on unsubscribed feeds — that's an IBKR account
  market-data-subscription question (Account Management, not code).
- `aitrader/mcp/broker_server.py` (0.8.2 → 0.9.0): new **`get_bars_csv`**
  tool — same args/routing as `get_bars`, but writes long-format rows
  (symbol, t, o, h, l, c, v) to a CSV on disk and returns `{path, count,
  symbols, columns, as_of}` instead of raw JSON, mirroring the existing
  `get_all_snapshots`/`get_type_snapshots` pattern. Removes the actual
  motivation for the API-bypass workaround.
- `prompts/constitution.md` (30,689 → 31,427 B; backup taken first per the
  new `constitution-edit-protocol` standing rule, and reviewed with
  `ask_gpt` before landing): new bullet in "What you have" —
  **"BROKER/MARKET DATA — ONE PATH"** — broker/market data comes ONLY
  through the declared broker MCP tools; the sandbox may process a file a
  tool produced, never fetch data itself; a bulk pull uses the CSV-returning
  tools; a tool genuinely unable to supply what's needed makes that step
  NOT DONE, never a substituted data path. Framed as a NOT-DONE outcome
  (per ask_gpt's review) rather than a bare prohibition, matching this
  document's own proven enforcement idiom (prose-only rules get skipped;
  mechanical/NOT-DONE consequences bind).
- New ccmemory standing rule `constitution-edit-protocol`: every future
  constitution.md edit requires a backup first and an `ask_gpt` review
  before landing.
- Deploy is OWNER-run: the broker/scheduler MCP changes need a package
  install + restart; the constitution needs `make const` (or the package
  install, which ships both).

## [1.44.1] — 2026-07-12 — get_market_schedule stops showing forex/futures on brokers that don't have them

### Why
Owner observed atrader (Alpaca execution broker) reading `get_market_schedule`
and seeing `forex`/`futures` sessions with `open_now`/`next_open` facts, even
though Alpaca has no forex or futures at all — `Alpaca.get_available_types()`
correctly omits those keys entirely ("Alpaca has no forex/futures"), but
`market_calendar.week_schedule()` (what `get_market_schedule` returns) is a
pure calendar function with zero broker awareness: it unconditionally builds
`stock`/`futures`/`forex`/`crypto` sessions for every caller. For IBKR that's
correct (it trades all of them); for Alpaca/myse it silently showed classes
that were never tradeable on that account, not just closed right now — a
schedule fact indistinguishable from a real one, exactly the kind of gap that
misleads session-start planning (ONCE PER SESSION step **C** reads this
schedule to plan the week's sleeps against).

### Changed
- `aitrader/mcp/scheduler_server.py` (0.4.0 → 0.4.1): new `BROKER_ASSET_TYPES`
  map (ibkr: all 5 classes; alpaca: stock+crypto; myse: stock only) mirroring
  each `Broker.get_available_types()` key set. `get_market_schedule` now
  filters `week_schedule()`'s `classes` dict to what `settings().broker`
  actually supports and adds a `broker` field to the response. An unrecognized
  broker value degrades to the unfiltered (pre-fix) behavior rather than
  hiding everything. `market_calendar.week_schedule()` itself is untouched —
  it stays a pure, broker-agnostic calendar function; the scheduler MCP (which
  already reads `settings()`) does the filtering, keeping ZERO trading logic
  and the broker-capability mapping a static fact table, not a live broker
  call.
- Verified via a standalone script (no broker connection needed): raw
  `week_schedule()` returns `{crypto, forex, futures, options, stock}`;
  filtered for `alpaca` → `{crypto, stock}`; `ibkr` → all 5; `myse` →
  `{stock}`.
- Deploy is OWNER-run (package install/restart, not `make const` alone — this
  is Python source, not the constitution).

## [1.44.0] — 2026-07-12 — news-check restored as a forced step (2B) + prospective memory (2A/5A)

### Why
Auditing the constitution for a `ccprospect` integration surfaced a regression:
`[1.36.0]`'s minimal-experiment rewrite correctly dropped the OFFENSE/DEFENSE/
PATIENCE posture machinery (prompt-encoded strategy — the model's judgment per
this project's own Hard Boundary), but it silently took the mandatory
"go check the news" forcing function down with it. Since then, step 4 DECIDE &
ACT only ever listed web search passively among "whatever helps" — no artifact,
no NOT-DONE gate, easy to skip forever without it ever showing in the journal.
The predecessor system (`/src/trader`) was burned before by not checking news
ahead of scheduled events; this constitution had quietly drifted back to the
same gap. Owner call: restore the process obligation only (mandatory search +
written findings + catalyst scope), leave posture/regime judgment with the
model.

### Changed
- `prompts/constitution.md` (27,408 → 30,689 B). Two new lettered loop steps,
  landed without renumbering the existing flat 0–7 sequence (steps 2–7 are
  cross-referenced by number ~25 times in the doc's prose):
  - **STEP 2A · PROSPECTIVE INBOX** (right after step 2 OPEN NOW) — resolves
    `ccprospect`'s inbox every cycle: one disposition per fired/due row via
    `prospect_ack`, complete only at `pending_count: 0`. Fail-open on tool
    error — never blocks RECONCILE/SURVEY/DECIDE/PROTECT.
  - **STEP 2B · CHECK THE NEWS** (right after 2A, before step 3 SURVEY) —
    mandatory web search of market/macro + every held/candidate symbol,
    written findings, NOT-DONE if no search line appears; CATALYST SCOPE
    sub-bullet forces stating what an event gates and what it does NOT.
    Deliberately does NOT restore OFFENSE/DEFENSE/PATIENCE or any default
    posture bias — only the act of looking is forced, the read is the model's.
  - **STEP 5A · FORWARD EXPECTATIONS** (right after step 5 PROTECT) — up to 3
    forward-expectation candidates per cycle from step 3/4 material, one row
    each; `NONE`/`NO_CONTRACT` sentinel required if none qualify.
  - House-fuses section: new bullet — existing safety fuses (naked position,
    liquidation cushion) outrank 2A/2B/5A; a prospective-memory or news-check
    hiccup never delays a stop or exit.
  - Loop intro states the exact execution order: `0,1,2,2A,2B,3,4,5,5A,6,7`.
  - Step 6 JOURNAL's artifact list and labeled-section set gain the 2A/2B/5A
    tables (`NEWS:` added alongside `RECONCILE:`/`SURVEY:`/etc.).
- `.ccprospect/integration.json` records the ccprospect binding
  (`shape: custom`, `binding_file: prompts/constitution.md`).
- Backups taken before each edit: `prompts/constitution.md.backup-20260712`
  (pre-2A/5A), `prompts/constitution.md.backup-20260712-prenews` (pre-2B).
- Deploy is OWNER-run (`make const`) — not done as part of this change; an
  already-running session keeps the old prompt until the next relay or a
  service restart.

## [1.43.0] — 2026-07-11 — the week ahead: per-class market schedule, read once per session

### Why
itrader, flat on Saturday evening, planned "redeploy Monday 09:30 ET" and
aimed its weekend attention there — writing off Sunday ~18:00 ET futures (and
17:00 forex) opens it never intended to look at. Not purely a judgment
failure: the toolset's ONLY forward-looking schedule fact was NYSE
`next_open`. Nothing could say "futures reopen Sunday evening" or "Friday is
a holiday" in advance — futures/forex halts became visible only once already
in effect (`get_available_types` booleans, now-only). The agent anchored on
the one future timestamp it could fetch. Owner call: import the calendar
knowledge and hand the agent the week's schedule ONCE at session start so it
is always in context.

### Changed
- `market_calendar.py` 0.2.0 → 0.3.0 (the old system's resolver, extended):
  `class_sessions`/`week_schedule` — stock/options from the NYSE library
  calendar (holidays + half-days), futures from CME_Equity (Globex Sunday
  18:00 ET opens, holiday-aware), forex as the rule-based Sun 17:00 → Fri
  17:00 ET week, crypto 24/7. Every class carries its `source` (library vs
  rule) so a degraded holiday-blind answer is visible as such; stock's closed
  weekdays in the window are listed (the "is Friday a holiday" answer).
  Degrades to weekday-window rules when pandas_market_calendars is absent.
- Scheduler MCP: new `get_market_schedule(days=7)` (clamped 1–14, ~2–4KB
  payload). Verified live on this Saturday: futures next_open Sun 07/12
  18:00 ET, forex Sun 17:00 ET, stock Mon 09:30 ET — exactly the facts
  itrader lacked.
- Constitution (27,408 B): ONCE PER SESSION gains **C** — read
  `get_market_schedule` once at session start (NOT each cycle) so every
  sleep is planned against real opens; step 7's long-sleep rule now ends
  BEFORE the earliest next open on that schedule — sleeping through an open
  you knew about is a step-7 failure.
- Deploy: package install + restart (`make world`/`full`) — `make const`
  alone ships only the constitution half.

## [1.42.4] — 2026-07-11 — verbose-TUI default reverted (installer seed + nodes verified)

### Why
The 1.41.3 `"verbose": true` seed made the expanded transcript the default in
the tmux attach — which is just the ctrl+o dump made permanent: full thinking
walls between every tool line. Owner verdict after living with it: worse than
the collapsed digest. The underlying grouping is stream-shape behavior (text
blocks segment the display — probe-established), which a display default
cannot fix; ctrl+o remains the on-demand lens.

### Changed
- install.sh: the run-dir `.claude/settings.json` seed is back to
  `{"model": "<model>"}` only.
- Nodes: atrader's run-dir `.claude/` was removed by the owner (harmless
  there — clyde forces `--model opus` plus the env pin); itrader's
  `settings.json {"model":"opus"}` verified intact and verbose-free — it has
  no clyde, so that file IS its model selection and must stay.
- extras/local_claude.md + the topology memory record the experiment as
  tried-and-reverted so it doesn't come back.

## [1.42.3] — 2026-07-11 — RETIRED manifest: stale agent memories purged by BOTH deploy paths

### Why
itrader was observed capping every sleep at ~1700s, citing its own recorded
lesson (wait-seconds-1800s-abort): under the pre-1.41.1 scheduler any wait
over ~1800s was killed by the client's idle watchdog, and the agent had
correctly learned to duck the ceiling. That ceiling is FIXED (1.41.1
heartbeat, verified live at 3600.001s), so the lesson is now false and
throttles cadence on any node still carrying it. The owner deleted itrader's
copy by hand; the deploy path must do it everywhere else. install.sh already
had a retirement mechanism (inline RETIRED_NOTES) but `make const` — the
everyday deploy — never processed it, and an inline list can't be shared.

### Changed
- New `prompts/ccmemory-seed/RETIRED` — shared retirement manifest (one name
  per line, `#` comments): the 16 legacy lesson-* names moved out of
  install.sh, plus `wait-seconds-1800s-abort` and `wait-seconds-idle-timeout`
  (aliases of the fixed wait-cap lesson). Documented rule: append-only;
  agent-written names are retired ONLY when they encode a since-fixed
  infrastructure defect (owner-directed) — agent relearning that is still
  true is never touched.
- install.sh: RETIRED_NOTES now read from the manifest (purge mechanism
  unchanged).
- Makefile `const` (owner-directed edit): purges manifest names from the
  run-dir store after the card refresh; clears the ccmemory index when
  anything was seeded OR removed. Verified against a scratch RUN_DIR:
  planted stale notes removed, agent-authored survivor untouched, index
  cleared.
- Node state at ship time: atrader and itrader stores both verified clean —
  the manifest is the guarantee for every other clone/instance.

## [1.42.2] — 2026-07-11 — journal UI: REVIEW/GATE tables render as tables (blank-line normalizer)

### Why
The agent opens its step-4 tables directly under a section label ("REVIEW:")
or inside a list item ("- GATE:"), first pipe row on the next line. The
journal body is correct markdown (verified in the DB — real newlines, proper
delimiter row), but remark-gfm treats a pipe row following a non-blank line as
lazy paragraph continuation, so the table never parses: the dashboard showed
run-on pipe soup for REVIEW and GATE while the top-level SURVEY table rendered
fine. Display concern → fixed in the UI, not by asking the model to journal
differently; the DB body is the record and stays untouched.

### Changed
- `ui/src/components/JournalFeed.tsx`: `normalizeTables` inserts a blank line
  at every pipe/non-pipe boundary before the text reaches ReactMarkdown, so a
  table after a label line or list item always parses as its own block.
  Typecheck clean. Deploy: `make ui`.

## [1.42.1] — 2026-07-11 — REVIEW structure cell: a real swing point strictly below price, not the last print copied in

### Why
First cycle under 1.42.0 (journal id 298): the model pulled the bars — three
`get_bars` calls, the look happened — then filled the structure cells with the
current price: AAVE "HL 100.095" against a 100.10 print, UNI "HL 3.772"
against 3.77, a "higher-low" ABOVE the current price, definitionally
impossible. With fabricated structure, a red momentum thesis (UNI −1.6%) wrote
CONFIRMS · HOLD, and AAVE's row wrote structure 100.095 > stop 94.00 with
verdict HOLD — violating the trail rule stated as prose in the same bullet.
Prose tail-clauses don't bind the local model; cell-level NOT-DONE
consequences do. The 41K build carried exactly this counter-clause ("a
structure price equal to or above current is NOT a higher-low — it's the
current price copied in"); it hadn't been ported in the 1.42.0 fold.

### Changed
- `prompts/constitution.md` step 4(a) (26,129 → 26,736 B): new bullet — the
  structure cell holds a REAL prior swing point, several bars back, strictly
  BELOW current price for a long (ABOVE for a short); a value at or within a
  hair of the current print = the cell is NOT filled = step 4 NOT DONE; "no
  swing point formed since entry" must be written as exactly that. Trail
  bullet hardened: a row whose structure price sits above the current stop
  with a verdict other than TRAIL or EXIT = step 4 NOT DONE.
- Deploy: `make const`.

## [1.42.0] — 2026-07-11 — REVIEW: every holding re-wins its place (thesis CONFIRM/FALSIFY + trail, one forced table)

### Why
The UNI position exposed the exit-side hole: the minimal build deleted the old
constitution's REVIEW machinery (per-holding thesis CONFIRM/FALSIFY → falsified
is a SELL) and the trail-winners pass, and neither came back with the spine or
the GATE graft. As the loop stood, a dead thesis had exactly one exit — the
broker stop, 11% below the UNI entry — and a green name (AAVE, +0.7%) sat on
its entry-era stop with nothing forcing the trail question. Owner's verdict:
no trader rides a dead thesis to the stop; fix it. Both mechanisms return as
ONE forced table (own clean sub-step — the form verified to bind the local
model: 1.21.0 trail table, 1.41.0 GATE table).

### Changed
- `prompts/constitution.md` (24,367 → 26,129 B): step 4 gains **(a) REVIEW**,
  one row per position, filled off this cycle's bars and the RECORDED intent
  (thesis judged against the agent's own words at entry, not a fresh story):
  thesis · entry→now % + structure (higher-lows or LOWER-lows) · CONFIRMS or
  FALSIFIES · verdict HOLD (number) / TRAIL stop → X / EXIT now. FALSIFIED →
  EXIT this cycle — a stop caps a loss, it is never a reason to keep a dead
  thesis; a patient-hold exception must be written with its break level. Green
  since entry → the row answers the trail question: higher-low above the
  current stop → `modify_order` the existing stop under it (crypto: real swing
  low, never the last candle); a winner on its entry-era stop is UNMANAGED and
  a green stop-out is a SUCCESS. A held name with no row = step 4 NOT DONE.
  Former (a)–(e) re-letter to (b)–(f); (f) now names REVIEW's EXITs/TRAILs
  explicitly; step 6 journal reproduces the REVIEW table.
- Deploy: `make const`.

## [1.41.3] — 2026-07-11 — local-model TUI: steps visible in the attached tmux (verbose default; clyde pin documented)

### Why
With the served model pinned into the opus slot (extras/local_claude, deployed
as /usr/local/bin/clyde), interleaved thinking works under ccloop — verified in
the live process env — but the attached tmux still shows one collapsed
"Thinking for Xm, calling ... N times… (ctrl+o to expand)" line per cycle. That
is Claude Code's in-flight rendering of a single long interleaved turn: a
constitution cycle is thinking + ~25 tool calls + a blocking wait with no
user-facing text, so everything groups under one expandable digest (the ⎿ NN%
sub-line is the 1.41.1 wait heartbeat's progress). Interactive sessions look
step-by-step because their turns are short — and the shim leaves --effort at
default while ccloop passes max — not because ccloop breaks rendering. The
steps exist; the default view hides them.

### Changed
- install.sh: the run-dir `.claude/settings.json` seed now includes
  `"verbose": true`, defaulting the TUI to the expanded view (the ctrl+o
  toggle) so steps render live in `tmux -L aitrader attach`. Existing nodes:
  add the key to `~/.local/share/aitrader/run/.claude/settings.json` by hand
  (the seed is no-clobber without --reconfigure); applies from the next
  session.
- extras/local_claude.md: now documents the shim — the opus-slot pin (why a
  bare ANTHROPIC_MODEL renders as a post-hoc digest), the ccloop rendering
  behavior, the ctrl+o/verbose controls, and the warning not to strip
  interleaved_thinking from the capabilities string.

## [1.41.2] — 2026-07-11 — GATE entries read the bars: a TAKEN on a new name cites its structure price

### Why
First live cycle under 1.41.0 (journal id 295, 15:39 CDT): the GATE table bound
the local model immediately — rows, numbers, an honest passed-before column
("~3.50 -> 3.82") — and the model promptly bought UNI/USD at +7.58%, seven
hours into the move it had watched all day, off the survey row alone; the
position was red within minutes. The table forced the decision but nothing
forced a look at the move's structure first: the model read the hesitation-tax
column as urgency instead of spent edge. The 41K build had exactly this guard
("pull 5/15-min bars, confirm CLEAN directional structure before entering any
mover") — it was cut in the 1.41.0 trim as part of the bloat. Wrong cut;
restored here in table-cell form.

### Changed
- `prompts/constitution.md` step 4(b), one new GATE bullet (23,864 → 24,367 B):
  a TAKEN on a NEW name requires pulling the name's 5/15-minute bars this cycle
  and writing the structure price (the higher-low / lower-high being entered
  beyond) in the row's action cell; stalling or reversing on heavy volume is
  the FAILED move; a TAKEN with no bars-read structure price = step 4 NOT
  DONE. The look is forced, the read stays the agent's (§2 split intact — same
  form as the 1.40.0 look-first survey). Columns unchanged (enforcement as its
  own clause, not a new column, per the enforce-via-step lesson).
- Deploy: `make const`.

## [1.41.1] — 2026-07-11 — scheduler waits survive the client's 1800s idle watchdog (progress heartbeat)

### Why
Live transcript (atrader, 7/11): seven waits died with `MCP server "scheduler"
tool "wait_seconds" sent no response or progress for 1800s; aborting` — a
`wait_seconds(7200)` and a 90-minute `wait_until` both killed at exactly
1800s. The Claude Code client aborts any MCP tool call that stays silent for
1800s; our waits sleep silently, so every sleep over 30 minutes died. The
agent saw tool errors mid-loop, re-issued waits, and eventually self-clamped
to 1799/1790-second sleeps — journaling "maintaining 30-minute leash" as if it
were judgment when it was the harness ceiling. The constitution's earned
weekend leash (~2h) was structurally unreachable. Diagnosed and fixed in the
predecessor repo (its session_state.md §8, scheduler 0.4.0) but the fix never
crossed the rebuild — this port closes that gap.

### Changed
- `aitrader/mcp/scheduler_server.py` 0.3.0 → 0.4.0 (faithful port of the
  predecessor fix; the files were otherwise identical): `_sleep_until` emits
  `ctx.report_progress` every `PROGRESS_PING_SECONDS` (60s) while sleeping,
  resetting the client's idle watchdog; `ctx: Context` threaded through all
  four wait tools (FastMCP injects it — tool schemas unchanged for the model);
  a `report_progress` raise is swallowed so a missing progressToken can never
  break the wait itself.
- Deploy: package install + service restart (`make world`/`make full` + restart
  aitrader) — `make const` does NOT ship it. Verify by watching one >30-minute
  wait return `woke_reason: condition_met`.

## [1.41.0] — 2026-07-11 — GATE becomes a forced table: TAKEN or a number (the appetite graft)

### Why
Saturday live evidence (atrader journal ids 285–294): UNI/USD topped the
agent's own floorless survey six consecutive cycles (+5.8%→+6.9%, day-notional
$4k→$14.7k) and never once appeared in RANK; GATE read "No new entries.
Maintaining patience." — no number — while 82% of equity sat in cash with
$101k buying power journaled and untouched. The "patience" stance wasn't even
a current decision: the ccloop relay prompt injected the previous session's
dying posture ("POSTURE: PATIENCE", "Buys: DISABLED" — vocabulary from the
pre-1.36.0 build) and the model templated it forward cycle over cycle. Asked
directly, the agent's own post-mortem named the three failures: waiting for
confirmation that only exists after the move, "patience" as a shield, and
repeating the prior verdict instead of deciding fresh.

The 1.39.0 spine's GATE was prose, and prose is dodgeable — the same lesson as
trailing (1.21.0): enforcement binds this model only as a forced table in its
own sub-step. The 41KB aggressive build is NOT restored: it stated the
deploy-default four times over (mandate, posture step, gate prose, lenses),
and its OFFENSE/DEFENSE/PATIENCE posture machinery is the source of the very
stance-vocabulary this failure rode in on. The graft states each restored idea
once, inside the artifact layer. It forces the DECISION, not the trade — a
pass with a real number still passes everything.

### Changed
- `prompts/constitution.md` (21,536 → 23,864 B; pre-graft state preserved as
  `constitution.md.backup-20260711`):
  - Mandate: two-failure symmetry restored — a forced no-edge trade and
    idle/parked money cost the same. "No opinions about what to trade"
    honestly weakened to "no shortlist" (the gate now carries one momentum
    prior).
  - Step 4(a) RANK: every survey-surfaced name (ACT candidates + floorless
    top-3) must appear in the list, else step 4 NOT DONE.
  - Step 4(b) GATE: prose → FORCED TABLE, one row per survey-surfaced name
    plus the worst holding. Action cell = TAKEN (side · size) or the blocking
    NUMBER; "watch" is not a state; stance words are not numbers and a stance
    inherited across a session/relay is VOID until re-won; buying is never
    globally on or off. Passed-before column carries first-pass price → now
    (the hesitation tax, written down every cycle it recurs). Momentum prior:
    extended ≠ done, reject only the FAILED move; "it already moved" is not a
    number. Idle-money clause: cash + unused buying power above a small
    working buffer must win its place each cycle or get deployed.
  - Step 6 JOURNAL reproduces the GATE table in full.
- Deploy: `make const` (owner-run). Recommended alongside: restart atrader on
  a FRESH ccloop run (move `run/.ccloop/runs` aside first) so the contaminated
  "PATIENCE / Buys: DISABLED" relay summary stops being injected into every
  new session.

## [1.40.3] — 2026-07-11 — card-crypto carries no track record; contaminated memory removed

### Why
card-crypto was steering live coin selection with a per-name tier record
(six "profitable" names vs ten "catastrophic" ones), a 6.7% win rate, and a
"~$23.7k universe-restriction swing" — all mined from the predecessor
system's trade ledger. That ledger is inadmissible as trading evidence: its
window (Mar–Apr 2026) is covered by documented order-management bugs
(stop-loss exits silently dropped from the ledger so realized losses never
recorded, zombie/REARM stops manufacturing phantom positions, default-stop
overrides), so per-name P&L from it reflects engineering defects, not
markets. Agents were observed citing these tiers inside real buy/pass
decisions — static bug-derived data deciding which coins the account chases,
the exact inversion the constitution's Hard Boundary exists to prevent.

The fix removes the data AND the story about the data: the agent needs no
knowledge of a predecessor, a ledger, or a withdrawal — naming coins to
exonerate them keeps the association alive, and provenance forensics in a
force-read card is a permanent per-session attention tax. Incident history
belongs here, in the changelog, not in the agent's head. Standing rule: the
card carries market/venue mechanics and behavioral principles only — never a
quantified track record, never per-name judgments.

### Changed
- `prompts/ccmemory-seed/card-crypto.md` rewritten: all predecessor P&L
  removed (both name tiers, 6.7% win rate, $23.7k swing thesis,
  "exit-tightening disproven", weekend FIFO win-rate table, 14/28-day
  mean-reversion figures) with no withdrawal notice replacing them. Kept, as
  principles and mechanics: concentrate-and-defend, vol/momentum regime, the
  three behavioral hazards (chased "recoveries", re-entry after stop-outs,
  equity-width stops), venue coin-volume vs `day_notional`,
  weekend-as-priced-condition + stop-limit gap risk, anti-passivity closer.
- `.ccmemory/crypto-hard-lessons-provenance.md` deleted (asserted the tier
  record as "scars that are REAL"); its MEMORY.md index line removed.

## [1.40.2] — 2026-07-11 — `make const` also deploys the curated cards

### Why
`make const` only copied the constitution (-> CLAUDE.md); the run-dir
`.ccmemory` cards were seeded exclusively by `install.sh`, which `make install`
/ `make world` never invoke. So a card edit (prompts/ccmemory-seed/card-*.md)
had no path to a running node through make at all — it silently stayed the old
content (no-clobber seeding stranded it). This bit a live card deploy: `make
const` reported success while the deployed card was untouched.

### Changed
- Makefile `const` target: after deploying the constitution, refresh every
  `prompts/ccmemory-seed/*.md` into `$(RUN_DIR)/.ccmemory` (OVERWRITE — cards
  are canon) and clear the ccmemory index, before the restart — mirroring
  install.sh's card-seed logic. One `make const` now ships both the
  constitution and any card edits.

## [1.40.1] — 2026-07-11 — `make ui` guards its own `npm install`

### Why
On a fresh checkout (e.g. `/tmp/aitrader`), `make world` died at the `tsc`
step. `node_modules` is gitignored, and the `ui` target ran `npm run build`
(`tsc -b && vite build`) directly with no `npm install` — there was no local
`tsc` to run. It only "worked" in `/src/aitrader` because a prior
`install.sh`/`make ui` had already populated `node_modules` there. `make ui`
implicitly assumed `install.sh` had run once; a clean tree broke that.

### Changed
- Makefile `ui` target: install deps when they're absent — `[ -d node_modules ]
  || npm install --no-audit --no-fund` (same flags as install.sh:374) before
  `npm run build`. Guarded on `node_modules` so warm trees stay fast (no reinstall
  on every build). `make world`/`make ui` now build on a fresh checkout without
  needing `install.sh` first.

## [1.40.0] — 2026-07-10 — survey looks before it filters: day_notional column, excluded-counts on rank_instruments, floorless-first survey artifact

### Why
Transcript-verified failure (atrader, all afternoon 7/10): gemma surveyed
crypto with floors copied from its stock template — `min_price=1,
min_volume=1_000_000` — which are STRUCTURALLY empty on Alpaca crypto
(day_volume is venue coins: the only 1M+-unit pairs are sub-$1 memes, and
every $1+ coin prints a few hundred units). The tool honestly returned zero
rows every hour; the journal templated "None meeting filters · PASS: No
signals" while the venue's real tape had PEPE +6.7%, AAVE +5.6%, DOT +5.4% —
AAVE and SKY are Tier-1 names on the agent's own card. The agent judged
BEFORE it looked; the artifact let it. This matters beyond gemma: Alpaca
paper crypto is the only rehearsal for IBKR live crypto (Paxos/Zero Hash do
not paper), so the crypto survey loop has to actually run.

### Changed
- `snapshot_type_to_csv`: new `day_notional` column = price × day_volume in
  dollars, for stock (shares) and crypto (coins) — the cross-row comparable
  activity fact (1.4B PEPE units ≈ $4k; 1.26 BTC ≈ $80k — coin units were
  inverting the activity ranking). Futures/forex leave it empty: futures
  need the contract multiplier (their rows already carry `notional`
  exposure) and forex bars have no venue volume — no false numbers.
- `rank_snapshot_csv` / `rank_instruments`: response now carries `universe`
  (rows in the CSV) and `excluded` (per-filter removal counts: no_data /
  min_price / min_volume / stale / held), so `count=0` names its own cause —
  "your floor emptied the list", not "dead tape". Crypto results carry a
  `notes` field with the venue-coins caveat (parity with get_all_snapshots,
  which had it since 1.36.2 — the newer tool had lost the older tool's
  guard).
- Constitution step 3(b) is now "look FIRST, filter AFTER": the first ranked
  call per type is floorless and the survey row must quote its top 3 as
  symbol · %move · $notional; a floored zero-result must paste the
  `excluded` counts; the session's first crypto survey reads card-crypto
  (the CARD LINE previously fired only on entries, so a survey-blinded
  session never met the card). Judgment stays the agent's — the step forces
  the LOOK, never the verdict (§2: rank by fact = infra; opinion = agent).

## [1.39.1] — 2026-07-10 — get_fill_activities defaults to a 4-day window (kills the spill-file detour)

### Why
With no `after`, get_fill_activities returned the broker's entire activity
history; the result now exceeds the harness tool-result cap, so every fresh
session's reconcile produced a "too large — saved to file" spill the model had
to Read back. That extra hop is exactly where gemma face-planted this
afternoon: mis-typed the spill path (an older file's timestamp), file-not-found,
then a 158×-repetition drift loop emitting invented `<call:Read .../>` text —
a full session wedge (owner had to stop it; the native <|tool_call> token
never fired, so no parser could have caught it). Reconcile needs fills since
the last wake, not the account's life story.

### Changed
- `get_fill_activities`: `after` defaults to now-4d (covers weekend gaps);
  response includes `since` so the window is explicit; docstring points to
  transactions_read for deeper history. Explicit `after` still honored.

## [1.39.0] — 2026-07-10 — THE SPINE: RANK / GATE / BOOK sub-steps restore minimal disposition (experiment amended)

### Why
One dress-rehearsal day answered the pure-minimal question three independent
ways, all documented in the agents' own journals:
1. **Appetite** — the hesitation tax: itrader identified NVDA as the leader at
   ~204, sold what it held at 204.05, re-entered at 209.03 (~2.4% paid for
   refusing to hold risk while being right).
2. **Breadth** — one-bet books BY CHOICE: given the consolidated tape (284
   movers), a quoting-proof ranker, and the short side as a menu, both models
   still built single-name books (both the same name).
3. **Leverage** — $130k buying power journaled every cycle and treated as
   decoration ("only $4.5k cash anyway"); "unlevered" written as a virtue.
   The old text's "margin is a tool, not a last resort" was deleted with the
   aggressive build, and trained risk-aversion filled the vacuum.
Tools cannot fix disposition — the tool layer is complete and proven. Owner
call: restore the minimal spine now; the test week (Mon 7/13–Fri 7/17)
measures minimal+spine, which is the actual production candidate.

### Changed
- **Constitution step 4** gains lettered artifacts (clean-new sub-steps bind;
  numbering unchanged): **(a) RANK** — one ordered list: candidates BOTH
  directions + holdings + cash, correlated names = one bet; **(b) GATE** — a
  candidate that outranks cash or the worst holding gets TAKEN or the specific
  disqualifying NUMBER gets written ("wait" with no number is not an answer),
  and settled cash is NOT the budget — buying power is a tool bounded only by
  the liquidation-cushion fuse; **(c) BOOK** — largest same-driver cluster as
  % of equity, written every cycle (no cap — surfaced, not gated). HISTORY
  becomes (d) verbatim; order mechanics become (e).
- **Step 6 JOURNAL** reproduces the new artifacts (RANK list, GATE numbers,
  BOOK line). `constitution.md.minimal` re-frozen — the test-week baseline is
  minimal+spine.

## [1.38.1] — 2026-07-10 — rank_instruments: empty trade-ts means unknown, not stale

### Why
itrader's first 1.38.0 survey journaled forex/futures ranking to "0 rows":
IBKR-sourced snapshot rows carry NO last_trade_ts (verified: ES row's ts field
empty), and `fresh_only` compared empty < today = stale → entire asset classes
silently filtered to nothing. The agent handled it honestly (used its prior
read, disclosed), but a freshness filter must never eat classes whose venue
doesn't report trade timestamps.

### Changed
- `rank_snapshot_csv`: `fresh_only` drops a row only when its ts is PRESENT
  and pre-today — empty ts = freshness unknown = keep.

## [1.38.0] — 2026-07-10 — rank_instruments: mechanical ranking at agent-chosen parameters (owner design)

### Why
gemma's sandbox ranking step fails CONTINUOUSLY — its parser mangles long
quoted `python3 -c` one-liners (unterminated f-strings, malformed tool-call
JSON, bash EOF errors — watched live, repeatedly), so the whole-tape design's
"rank it yourself in the sandbox" collapses exactly where the weak model needs
it most, and cycles burn minutes on syntax retries. A tool call with a few
short scalar args is immune to that mangling. §2/§8-clean: infra sorts the
existing snapshot CSV by a RAW FACT at parameters the AGENT chooses per call —
it scores nothing, prefers nothing, keeps no house shortlist (the 1.34.0 trap
died with the vendor feed: this ranks OUR whole-tape data at the agent's own
floors, and the CSV stays for deeper cuts).

### Changed
- **`rank_instruments(asset_type, n=20, by='pct_1d', direction='up'|'down'|'abs',
  min_price=0, min_volume=0, fresh_only=True, exclude_held=True)`** — returns
  `{count, csv_age_seconds, filters, movers: [...]}` — inline JSON row objects
  with real numbers (wrapper-shape rule). Named rank_instruments, NOT
  "top movers": (a) the old junk vendor tool was called get_top_movers and the
  agents' memories reference that name as removed garbage; (b) "top movers"
  preaches chasing completed moves — the neutral name + `by=<fact>` makes the
  agent choose its lens per call. `direction=down` makes the short side a
  first-class menu (the models have never once evaluated a loser);
  `fresh_only` drops stale prints by fact; `exclude_held` (owner ask) drops
  current positions so no tokens re-filter the book. Reads the step-0 CSV
  (pulls only if missing) and reports its age instead of hiding staleness.
  Core is a plain function (`rank_snapshot_csv`), tested live against the
  consolidated tape: gainers/losers/crypto + held-exclusion verified.
- **Three derived FACT columns in the snapshot CSVs** (pure arithmetic —
  lenses that exist BEFORE a move completes): `pct_intraday` (today's move
  ex-gap; split-immune — kills the INHD +3559% artifact class), `gap_pct`
  (the overnight repricing alone), `range_pos` (0=at day low .. 1=at day
  high). With `rel_vol` (now meaningful on consolidated volume) these make
  "unusual participation before price resolves" a one-call lens instead of a
  sandbox pandas exercise.
- **Constitution step 3(b):** ranking can go through `rank_instruments` at
  YOUR parameters — lens menu named, short side named — or the sandbox (write
  a script FILE — quoted one-liners mangle); the judgment stays the agent's
  either way. `.minimal` baseline re-frozen.

## [1.37.3] — 2026-07-10 — survey sees the whole market: delayed-SIP feed for the tape CSVs

### Why
The survey layer was running through a keyhole: the account's free Alpaca plan
is real-time-IEX, and IEX carries ~2-4% of consolidated volume (NVDA live
check: 2.9M IEX vs 70.9M consolidated). Consequences, all observed during the
dress rehearsal: volume floors lied (a "1M share" floor ≈ 25-50M consolidated
→ 16 "liquid" names on the whole tape), thousands of names invisible ("traded
today" = names that printed ON IEX), stale opening prints, and a
mega-cap-biased movers menu that helped manufacture the NVDA monoculture.
Discovery: the free plan ALSO includes the full consolidated tape at a 15-min
delay (`feed=delayed_sip` — verified live against the account). For breadth —
liquidity floors, traded-today, movers ranking on a 5-30 min cadence —
15-min-stale consolidated beats real-time keyhole outright. $0.

### Changed
- `settings: alpaca_survey_feed` (default `delayed_sip`) — feed for the
  whole-tape survey CSVs ONLY; single-symbol quotes/bars/entries stay
  real-time on `alpaca_data_feed` (iex). The division of labor the agents
  already practice: survey the file, verify live before acting.
- `AlpacaBroker.resolve_feed(name=None)` maps iex|sip|delayed_sip;
  `get_snapshots`/`get_stock_snapshots` accept `feed=` with a silent
  fall-back to the configured feed on an entitlement error (verified live:
  requesting blocked `sip` degrades to IEX instead of raising — a degraded
  survey beats no survey). IBKR/MYSE accept-and-ignore the kwarg.
- `snapshot_type_to_csv` passes the survey feed for STOCK pulls. Verified via
  source-tree run: NVDA 73.9M / NOK 29.0M / VOD 12.6M in the survey path.

## [1.37.2] — 2026-07-10 — journal_write tolerates the parser's fused-kind mangling

### Why
Live mid-day: gemma's long `journal_write` bodies failed validation — the vLLM
parser appended its stray backtick to the body AND fused `,kind: "reconcile"`
INTO the body string, leaving `kind` (required, no default) missing. The write
was safely REJECTED (unlike the old kind-field spill), but the agent burned a
cycle diagnosing it and started shortening entries to dodge the bug — pressure
toward worse journals. Same parser family as the trailing-backtick and
order-id char-drop bugs; the root fix is the vLLM parser patch (restart at the
close), this is the infra-side defense in the meantime.

### Changed
- `journal_write`: `kind` now optional at the boundary; a fused
  `…`,kind: "x"` tail is recovered from the body (kind extracted, tail
  stripped), stray trailing backticks stripped from body/kind/tags, empty body
  still errors, unrecoverable kind defaults to `note` rather than losing the
  entry. Same tolerance philosophy as resolve_order_id / comma-string args.

## [1.37.1] — 2026-07-10 — survey freshness column + IBKR phantom-limit fix (dress-rehearsal findings, shipped same day)

### Why
Two live findings from this morning's open:
1. **Stale open prints:** minutes into RTH, names that had not traded yet
   carried YESTERDAY'S move as pct_1d — the survey's top "gainers" (AEHR +12%,
   ONTO +8.9%) were July-9 prints. Opus caught it and cross-verified live;
   gemma cannot — the CSV needed to carry the freshness fact itself.
2. **Phantom limit on IBKR stops:** `normalize_order` surfaced `lmtPrice`
   unconditionally, and IBKR's gateway echoes a venue-computed lmtPrice even on
   plain STP orders — itrader's clean META stop-market read back as "limit
   657.53, wrong side," which it then had to clear via modify_order (burning a
   cycle on infra noise it worked around from its own memory note).

### Changed
- **`snapshot_type_to_csv`:** new `last_trade_ts` column — when the row's price
  actually printed (carries the bar's ts when a stale print was replaced by the
  bar close, i.e. the freshness the price reflects). Tool docstring shows the
  filter idiom (`df[df.last_trade_ts >= today_iso]`) so early-session ranking
  can exclude yesterday's prints factually — infra states freshness, the agent
  decides what to do with it.
- **`ibkr.normalize_order`:** `limit_price` is only surfaced when the order
  TYPE carries a limit (`LMT`/`STP LMT`); STP/MKT orders report no limit —
  the phantom stop-limit reading is gone.
- **Every list-returning MCP tool now returns a self-describing dict**
  (`{count, positions|orders|fills|executions|assets|balances|entries|records|
  snapshots|transactions|results: [...]}`) — 8 broker + 6 journal tools. Why:
  the MCP SDK renders a Python list as one content block PER ELEMENT, so a
  single position arrived as a bare JSON object with no brackets — gemma
  (correctly!) couldn't tell one-position from wrong-shape and burned a cycle
  re-checking. The wrapper renders as ONE block with an explicit count at
  0, 1, or many; `count==0` is now the only form of "no rows".

## [1.37.0] — 2026-07-10 — the tape pulls itself: argless `get_all_snapshots` chained to step 0 (owner design)

### Why
Both models shed the survey obligation under pressure — gemma on 5-min leashes
(prose lines, no pulls), opus once in a position (its forex CSV went 65+ min
stale while forex was open; three consecutive wakes with zero pulls, proven by
file mtimes). Text cannot win against a context dominated by the model's own
recent manage-only turns. Owner's redesign: stop depending on the model to
pull the tape — chain the pull to the ONE call that has never eroded, step 0's
`broker_status`.

### Changed
- **broker MCP:** CSV engine extracted to `snapshot_type_to_csv()`. NEW
  **`get_all_snapshots(asset_type=None)`** — called with NO arguments it pulls
  EVERY open asset type (via `get_available_types()` internally; options is
  worked through chains, not snapshotted) and returns
  `{as_of, open_types, results: {type: {path, count, ...} | {error}}}` —
  per-type errors inline and fail-open, never blocking the other types. Called
  WITH a type it behaves exactly as before (back-compat with both models'
  existing habits). NEW **`get_type_snapshots(asset_type)`** = explicit
  single-type mid-cycle refresh. The payload stays paths + counts — NO ranked
  names, so infra never becomes a shortlist again (the 1.34.0 trap).
- **Constitution:** step 0 — once READY is written, the SECOND call of every
  cycle is `get_all_snapshots()` argless; step 3(a) — "THE TAPE IS ALREADY
  PULLED: write each type's path + count from step 0." Survey compliance now
  requires reading files that already exist instead of remembering to pull
  them. `constitution.md.minimal` re-frozen as the test-week baseline.

## [1.36.5] — 2026-07-10 — pre-open final config: survey-artifact enforcement + card-crypto step refs; baseline re-frozen

### Why
Owner reframed the schedule: Mon 7/13–Fri 7/17 is the measured test week
(review at the owner's call); everything before Monday is hardening. So the survey-artifact
erosion observed overnight (gemma degraded the step-3 table to a bare-names
prose line — no path, count, or %moves) gets fixed NOW, pre-experiment, and
today's session validates the final configuration. Process enforcement only —
no disposition added.

### Changed
- **Constitution step 3 + step 6:** one sentence each — every survey cell holds
  what was READ (path · count, each mover as symbol · %move); bare names with no
  numbers = step 3 not done / satisfy nothing in the journal. (Stated as the
  required form only — no negative examples, per the templating lesson.)
- **card-crypto:** removed the two references to the retired aggressive
  constitution's step numbers (step 7/11) and the number-or-take-the-trade gate
  language they smuggled; the card's anti-veto intent kept in neutral wording
  ("evidence that sharpens your survey read and entry plan, never a veto").
- **`constitution.md.minimal` re-frozen** to match the deployed text — the
  test-week baseline for the review diff is the FINAL config, not the
  Thursday-night draft.

## [1.36.4] — 2026-07-10 — order-id tolerance: resolve mangled UUIDs by unique prefix (AMD stop was locked all night)

### Why
Overnight, gemma (atrader) tried to RAISE its AMD stop 541 → 545 to lock in a
gain — self-directed trailing under the minimal constitution, exactly the
behavior we want — and infra failed it: the model passed
`b2751323-…-4aeb0d5c700` (11 hex in the last group) for the real
`…-4aeb0d5c5700`, one character dropped — the local-model long-string mangling
family (trailing-backtick, comma-truncation). Both `modify_order` and
`cancel_order` rejected the id ("badly formed hexadecimal UUID string"), and
once the wrong id was in its journal it re-used it every cycle. Net effect: the
position was PROTECTED (stop resting broker-side) but UNMANAGEABLE — no modify,
no cancel, and a market exit would bounce on stop-reserved shares.

### Changed
- `broker_server.py`: new `resolve_order_id()` applied in the `modify_order`,
  `cancel_order`, and `wait_for_fill` MCP wrappers. Strips parser junk
  (backticks/quotes/trailing dots); a UUID-shaped id (or the journal's bare
  hex-prefix display form, e.g. `b2751323...` — has a–f so it can never be an
  IBKR integer id) that doesn't match an open order exactly is resolved by
  UNIQUE first-group prefix against the live open orders. Ambiguous or unknown
  ids pass through untouched so the broker reports the real error; integer ids
  are never fuzzed. Same tolerance philosophy as the comma-string args fix.

## [1.36.3] — 2026-07-09 — card-crypto states the venue-volume fact; atrader journal repaired of volume-taint

### Why
Even with 1.36.2's honest CSV and the `notes` caveat on every crypto survey
return, gemma kept writing "PASS (Low volume/conviction)" — its own recent
journal entries out-vote fresh guidance (the documented templating mechanism),
and every relay re-reads that tail, re-seeding the reflex for the whole
experiment week. Owner's call: those reasons are residue of the fixed data bug
— repair the record so the week runs untainted, and put the fact in the
knowledge channel loaded at session start.

### Changed
- `prompts/ccmemory-seed/card-crypto.md`: the venue-volume fact (Alpaca's OWN
  venue, coin units, quote-derived bars → 0/blank normal, never a liquidity
  signal) now explicit in the body AND in the `description:` line — visible in
  every session-start `memory_list` without fetching the card. Installed
  directly into both agents' run-dir stores.
- **atrader `journal.db` repaired IN PLACE** (services stopped → UPDATE →
  restarted; backup `journal-volume-taint.backup`; never rm/recreate per the
  split-brain lesson): entries 234–238. The stale-print movers row (+1175%
  LTC/BTC class) now shows the real tape read off the same CSV at that time,
  and four `PASS (Low volume/conviction)` cells read `PASS (focus on held AI
  book; note: crypto day_volume is Alpaca venue-only — not a liquidity
  signal)`. The agent's actual decisions (PASS, hold the AI book — its own
  words in the same entries) are untouched; only the bug-derived reasons were
  replaced with the true facts, marked `[corrected ...]` where a fact row
  changed. If the fresh sessions now template anything forward, it's the
  correct caveat.

## [1.36.2] — 2026-07-09 — pre-open fixes: IBKR `presubmitted` stock stops count as WORKING; crypto survey volume told straight

### Why
Two survey-integrity items from the minimal-constitution experiment's first
overnight cycles:
1. **itrader (IBKR):** the PROTECT working-status list was Alpaca-flavored;
   IBKR's normal armed state for a resting stock stop is `presubmitted` — not on
   the list. Opus read it charitably ("presubmitted = WORKING") every cycle, but
   a literal reading by a fresh post-relay session would declare a fine stop
   NAKED → place a duplicate → insufficient-quantity reject → false
   "NAKED — BLOCKED" loop. Restarting for 1.36.1 forces exactly that fresh read,
   so this ships in the same restart.
2. **atrader (Alpaca):** crypto `day_volume`/`rel_vol` were steering verdicts
   ("PASS — low volume/conviction"), but per Alpaca's docs their crypto data is
   their OWN venue only (v1beta3 stopped distributing third-party data) and bars
   are quote-derived when no venue trade printed — zero volume is normal and
   says nothing about a coin's global liquidity. Worse, `int()` floored
   fractional coin volumes (0.4 BTC → 0): BTC/USD surveyed as `day_volume=0`.

### Changed
- **Constitution PROTECT** (one venue-fact line): the working-state list now
  names `presubmitted` for IBKR **stock** stops; a *futures* stop resting
  `presubmitted` on this node still does not fire (self-managed class).
  `constitution.md.minimal` stays frozen as the launch baseline — the review
  diff shows exactly this line.
- **`broker_server.py` `get_all_snapshots`:** crypto `day_volume` keeps its
  fractional coin value (no `int()` floor); the tool docstring and a `notes`
  field on every crypto return state the venue-only / coin-units /
  quote-derived semantics so the agent sees the caveat at call time. What to
  DO about thin venue volume remains the agent's judgment.

## [1.36.1] — 2026-07-09 — survey CSV: stale-`latestTrade` guard (LTC/BTC +1175% "1-day" was an ancient print)

### Why
atrader's first minimal-constitution survey showed crypto pct_1d of +1175%
(LTC/BTC), +292% (SUSHI/USDT), +271% (AVAX/USDT), +238% (DOGE/USDT). The CSV was
faithful — the bug is upstream: on thin non-USD-quoted pairs Alpaca's
`latestTrade` is the last time the pair EVER traded on the venue (months/years
old: DOGE at $0.24, AVAX at $24.83), while the daily bars are current. The
row-builder trusted the stale print over the bar → absurd pct_1d vs a current
prev_close. Same disease family as the premarket stale-latestTrade lesson and
the 1.35.0 `-1` guard. The model (gemma) read the junk data at face value and
reasoned over it — infra owes the agent true facts (§2), so this is an infra fix,
not a prompt fix.

### Changed
- `broker_server.py` `get_all_snapshots` row-builder: if `latestTrade.t`'s date
  is before `dailyBar.t`'s date, the print is stale — `price` uses the bar close
  instead. Snapshots without timestamps keep the old behavior; both brokers'
  `normalize_snapshot` shapes carry `t`. (Deploy: reinstall package + restart
  aitrader on each instance for the broker MCP to pick it up.)

## [1.36.0] — 2026-07-09 — EXPERIMENT: minimal process-only constitution — all trading judgment to the model

### Why
Every "trust the model" experiment to date (the zero-bias run, the 1.10.0 prose
rebalance) ran while the candidate feeds were `get_top_movers`/`get_most_actives`
— a 2–3 name shortlist that acted as the de-facto screener (the §2 inversion via
the data layer, diagnosed in 1.34.0). So "unguided failed" was confounded:
unguided was never tried with a real view of the tape. With `get_all_snapshots`
in place the experiment is clean for the first time: generic tools + a mandatory
mechanical loop, with ALL trading judgment — posture, deployment, sizing,
leverage, entries/exits, trailing — returned to the model. Owner's call
2026-07-09; one-week trial, reviewed when the owner calls it.

### Changed
- **`prompts/constitution.md` replaced with the minimal build** (41,206 →
  18,894 bytes; also clears Claude Code's large-CLAUDE.md startup warning).
  - **Kept (process obligations + venue facts only):** step 0 READY gate;
    1 RECONCILE (broker truth); 2 OPEN NOW; 3 SURVEY every open type off
    `get_all_snapshots` (path+count proof, rank it yourself in the sandbox,
    ACT/PASS verdict with reason — the structural guarantee no tool becomes the
    screener again); 4 DECIDE & ACT (fully the model's) with the HISTORY
    sub-step (paste `transactions_read` rows before any entry — surfaces, never
    gates); 5 status-aware PROTECT (working-state stop read off `get_orders` or
    a written self-managed exit; futures `presubmitted` + crypto stop-limit
    venue facts); 6 JOURNAL format; 7 WAKE cadence floors; Tool Call Mechanics;
    Placing an Order; friction table.
  - **Removed (now the model's judgment):** OFFENSE/DEFENSE/PATIENCE posture,
    the fully-deployed+levered default, cash-is-failure, the number-or-it's-a-BUY
    gate, the per-holding REVIEW tables, RANK, the forced CARD line (cards remain
    in memory, consulted at the model's judgment), the trail-winners + LOCKS-GAIN
    tables, the lenses section.
- **File map:** frozen experiment baseline = `prompts/constitution.md.minimal`;
  the full aggressive build preserved at `prompts/constitution.md.backup-20260709`
  (revert = copy it back over `constitution.md` + `make const`); `.backup` remains
  the Jul 6 pre-strip original, `.passive` the 1.34.0 strip.

### Watch for (at the owner's review)
- **Churn:** does buy→stop→re-buy of the same names stay dead now that the feed
  is the whole tape?
- **Passivity signature** (the documented failure this build re-risks): fluent
  PASS verdicts + idle cash cycle after cycle in an up tape. If it reappears,
  disposition was load-bearing after all → revert to the aggressive build.

## [1.35.0] — 2026-07-09 — survey CSV: guard invalid/`-1` snapshot prices (SI fix) — recorded post-hoc

Entry backfilled: the change was made and pyproject was bumped to 1.35.0 in an
earlier session that ended before writing this entry. `get_all_snapshots` row
building (`broker_server.py`): a snapshot whose last price is missing or invalid
(e.g. `-1`, IBKR's no-quote sentinel — bit SI futures) now falls back to the
daily-bar close, and a row with no usable price is skipped instead of emitting a
negative price into the survey CSV. Verified live in survey runs prior to the
agent restart.

## [1.34.0] — 2026-07-09 — discovery feed: canned movers/most-active screeners → `get_all_snapshots` (rank the whole tape yourself); constitution restored + rewired

### Why
atrader kept churning the same 2–3 AI names — buy → stop-out → re-buy → stop-out,
−$1,100 on the day / −$3,500 on the week. Two findings reframed the cause:
- **It was not the model.** The SAME churn ran on BOTH the local vLLM (atrader) and
  opus (itrader) — they share the Alpaca data feed and both kept picking the same
  names. No model-specific (or prompt-aggression) fix can explain identical behavior
  across two very different models.
- **It was not really the aggression either — it was a NARROW LIST.** The candidate
  feeds were junk: `get_top_movers` returns only penny/warrant pumps (a $0.01→$0.02
  warrant is +100%, and the vendor ranks by % then truncates, so the liquid leaders
  never even appear to be filtered); `get_most_actives` returns a near-static set of
  leveraged ETFs (SOXS/BITO/TZA…) by raw volume. And an LLM agent does whatever a tool
  returns and nothing else — so the shortlist WAS the strategy. Starved of tradeable
  candidates, the agent looped on its own positions + self-seeded web searches
  ("AI infrastructure … NVDA AMD ORCL") and re-bought the two names it already held;
  aggression only set how HARD it hammered that tiny list. (Ledger: NVDA 4 buys/2
  sells, AMD 3/2; neither MCP feed ever surfaced NVDA/AMD.)

An earlier cut of 1.34.0 stripped the constitution's aggression to fight the churn —
that treated the symptom. Reverted here; the stripped brief is preserved as
`prompts/constitution.md.passive` as a fallback. The real fix is widening the list.

### Changed — broker MCP: screener feeds → whole-tape snapshot
- **Removed `get_top_movers` + `get_most_actives`** (broker MCP wrappers +
  `AlpacaBroker` methods + the now-dead `ScreenerClient`). `broker_server.py`
  0.7.1→0.8.0, `alpaca.py` 0.5.0→0.6.0.
- **Added `get_all_snapshots(asset_type)`** — pulls a raw snapshot for EVERY tradeable
  name in ONE call, WRITES it to `{state_dir}/snapshots_{asset}.csv`, and returns
  `{path, count, asset_type, as_of, columns}` (not the rows — ~12k names). Columns:
  `symbol, price, pct_1d, day_volume, rel_vol, day_open/high/low, prev_close`. It
  ranks / filters / scores NOTHING — the whole tape as data (§2); the agent reads the
  file and ranks it ITSELF in the sandbox (its own liquidity floor + metric). Pure
  orchestration over the routed `get_tradeable_assets` + `get_snapshots`, so it is
  cross-asset (stock/crypto → Alpaca, forex/futures → IBKR). This is MORE §2-pure than
  the screeners it replaces (infra ranks nothing) and is the fix for the narrow-list
  churn. **Verified live (as atrader, real Alpaca):** `get_all_snapshots("stock")` →
  12,731 names in ~7s; a sandbox `price>5 & day_volume>1M` filter surfaced 82 liquid
  movers (OPEN +10%, HPE, MARA, RIVN, NOK, SOFI…) the old feeds buried — with NVDA/AMD
  now competing in the pack (NVDA red on the day) instead of being the only options.
  crypto → 73 names in 1.3s.

### Changed — `prompts/constitution.md`
- **Restored** the full aggressive constitution (the strip is reverted; kept as
  `.passive`). The narrow list was the churn engine, not the OFFENSE posture.
- **Rewired step 4 (SURVEY)** from "pull `get_top_movers` + `get_most_actives`" to
  "call `get_all_snapshots`, then rank the CSV yourself in the sandbox" — with an
  anti-tunnel clause (NOT just the 2–3 you hold; the same names cycle after cycle means
  you free-associated, not surveyed) and an IEX-`day_volume` calibration note.
- `docs/broker-mcp.md` updated (movers-feeds section → universe-snapshot section).

### Not deployed / not committed
Deploy = `make build && make install` (broker MCP code) + `make const` (constitution)
+ restart, per node. `snapshots_{asset}.csv` lands in each instance's `state_dir`.

## [1.33.0] — 2026-07-09 — report emails: daily + weekly/monthly/yearly (facts only; the /src/trader report minus its score)

### Why
The old /src/trader emailed daily/weekly/monthly/yearly reports of how the account
did (`/src/trader/bin/report`). aitrader had no equivalent — the dashboard shows
live state but nothing lands in your inbox. Rebuilt all four against the new data
sources. Deliberately dropped the old report's **0–10 daily "score"** (Return +
Win-Rate + Discipline, deductions for "risk violations") and the periodic report's
`avg_score`: a fixed *opinion of good trading* baked into code — exactly what
CLAUDE.md §2 calls cognition and §8 forbids porting. FACTS ONLY; the reader judges.

### Added — `bin/aitrader-report` (v1.1.0) + templated systemd timers
- **Daily report** — factual HTML email: starting/ending equity, chronological
  activity timeline (buys+sells from the fill ledger), realized P&L (plain FIFO
  arithmetic over recorded fills), day P&L split into realized vs.
  market-move-on-holds. No score, no grade, no ranking. **No open-positions table** —
  a positions snapshot is point-in-time (what's held now), not a fact about the
  report day; holdings live on the dashboard.
- **Periodic reports** (`--period weekly|monthly|yearly`) — aggregate summaries over
  the last complete week (Mon–Sun) / calendar month / calendar year: equity change,
  realized P&L, closed-trade count, wins/losses, win rate, avg P&L/trade, profit
  factor, max drawdown, best/worst day. All raw arithmetic over recorded facts (the
  old `avg_score` is gone). Ranges via `compute_period_range`; equity stats over
  `equity_snapshots` (only `equity > 0` rows — the recorder's own validity rule, so a
  pre-account year reports "no data" not a misleading all-zero summary); trade stats
  reuse the day FIFO over the period window.
- **Data sources (new-system, not the old DB+engine):** ending-equity (in-progress
  day) + day-boundary anchor from the dashboard API (`/status` over HTTP, exactly like
  `aitrader-snapshot` — so it needs NO broker client id of its own); fills + equity
  baseline from `journal.db` (`transactions` ledger + `equity_snapshots`), read-only.
  The "day" is the **ET calendar day**, matching `/status` `day_pl` + dashboard 1D.
- A sell with no covering buy in the ledger reports the fill with **P&L unknown** —
  it never invents a cost basis (no fake numbers).
- **Daily defaults to YESTERDAY** (the completed ET day) — run on day X reports day
  X-1, the way /src/trader's report ran overnight. `--date today` = in-progress session
  (live ending equity); `--date YYYY-MM-DD` = any day; `--no-email` prints plain text.
- **`systemd/aitrader-report@.service`** (one template, `--period %i`) + four instance
  timers `aitrader-report@{daily,weekly,monthly,yearly}.timer`, each firing 08:00 ET
  the morning after its period closes (daily every day; weekly Mon; monthly the 1st;
  yearly Jan 1). TZ-aware (tracks EDT/EST), `Persistent=true`. Installed + enabled by
  `install.sh` / `make install` alongside the snapshot timer.
- **`make install-report`** — one target to add the report to an existing stack
  (rebuild pkg + script + units + enable the 4 timers), for a second instance
  (`sudo -iu itrader; cd /src/aitrader; make install-report`) without a full reinstall.

### Added — config
- `report_email_to` (default empty → timers run but send nothing),
  `report_email_from` (default `aitrader@<hostname>`), and **`report_name`** (default
  = the unix user → subjects/headers read `atrader …` vs `itrader …`, so two stacks on
  one host are distinct with no config; override for a friendlier name) in `config.py`
  DEFAULTS + `Settings`; documented in `settings.toml.example`. The instance name
  prefixes every subject and the email body header.

### Verified
Ran live (read-only) against the real journal + API: daily 07-08/07-09 (day P&L
reconciles, FIFO realized + held-position split correct); weekly 06/29–07/05 and
monthly June aggregates (equity change, win rate, profit factor, max drawdown,
best/worst day); yearly 2025 correctly reports "no data" (pre-account). Deployed to
`~/.local` (pkg 1.33.0, script v1.1.0) and enabled the four timers; the
`aitrader-report@daily.service` systemd run exited 0 and emailed via postfix. See
`docs/report.md`.

## [1.32.3] — 2026-07-06 — step 9 PROTECT: status-aware forced table (a pending_cancel is NOT a stop)

### Why
MSFT sat NAKED for ~4 days while the agent reported it protected every cycle:
`STOPS: MSFT: 386.00 (ID: f41f7112... pending cancel)`. Root cause: the 07-02 stop
was cancelled and the cancel JAMMED in Alpaca `pending_cancel` (the 42210000 bug),
which (a) reserved all 76 shares so `qty_available=0` → any replacement stop would be
rejected, and (b) still matched step 9(b)'s `(symbol, side, qty)` test — so the agent
counted a DYING order as its stop and never placed a replacement (no `insufficient`
rejection in the journal — it never even tried). 9(b) MATCH and 9(d) VERIFY were both
**status-blind** (and prose, so collapsed to a one-line summary). Price bled through
386 to 384 (−$400) with the "stop" never able to fire. Order has since resolved to
`canceled`, freeing the shares → position was truly naked + placeable when found.

### Changed — `prompts/constitution.md` (step 9 PROTECT)
- **9(b) MATCH is now a FORCED TABLE** (the proven 9(e) pattern), one row per position,
  cells read off `get_orders`, with a **STATUS** column and a **WORKING? YES/NO** judgment.
  A matched order counts ONLY if status ∈ {`new`,`accepted`,`held`,resting `partially_filled`};
  **`pending_cancel`/`pending_replace`/`canceled`/`replaced`/`rejected`/`expired`/`filled`
  = NOT protection → treat as NONE, place a fresh stop.** Names the real MSFT case so the
  model can't rationalize a dying order as coverage.
- **9(c)** gains the blocked-shares edge: if a replacement is rejected because a stale
  `pending_cancel` reserves the shares (`qty_available` < position qty), write
  `NAKED — BLOCKED by stuck order <id>`, retry each cycle, never report protected.
- **9(d) VERIFY** now requires seeing a WORKING stop's id (a `pending_cancel`/blocked order
  does not count); a naked/blocked position must be stated plainly, never disguised.

### Also — placed the missing MSFT stop manually
GTC stop-market `sl_msft_20260706_1` @ 380.50 (just under the 07-06 session low 381.33),
order `a054da8d`, status `new`. MSFT no longer naked.

## [1.32.2] — 2026-07-04 — symbol sanitizer: survive the vLLM last-arg trailing-backtick

### Why
Watched live: the agent wedged in an unbreakable retry loop calling `get_snapshots`
with `…,BNB/USD\`` — a trailing backtick on the LAST symbol. It reasoned "I keep
typing a backtick… I'm not adding it in my thought, but it's appearing in the tool
call" and retried the identical call ~12×. The backtick is NOT in the model's output:
the local vLLM gemma tool-parser appends a trailing backtick to the **last string
argument** of a tool call (same parser family as `vllm-gemma4-quotefix-patch`). Alpaca's
`^[A-Z]+x?/[A-Z]+$` validator then rejects `BNB/USD\``, and the model can't fix what it
can't see. Same corruption had already stored position/journal symbols as `XRP/USD\``
this session, and would silently make `transactions_read(symbol='X\`')` match zero rows —
re-breaking the 1.32.1 HISTORY table via a corrupted filter.

Root fix is the vLLM parser (steve's model-server node, not reachable/owned here);
this is the in-repo defense so a mangled arg can never wedge the agent or corrupt a key.

### Added — `aitrader/asset_types.py` (0.11.0 → 0.12.0)
- `clean_symbol(s)`: strips backticks/quotes/whitespace a mangled tool-call arg leaves on
  a symbol. A backtick/quote is never valid in a symbol, so this is pure lenience per the
  `mcp-tools-tolerate-comma-strings` doctrine, not a guess. Non-strings pass through.

### Changed
- `broker_server.py` (0.7.0 → 0.7.1): `clean_symbols()` (list/CSV) built on the shared
  `clean_symbol`; applied to every symbol/symbols arg — `get_snapshot(s)`, `get_bars`,
  `get_open_orders_for_symbol`, all `place_*` orders, `close_position`,
  `get_historical_executions`, options tools. `parse_asset_type` now cleans its input too
  (so `crypto\`` no longer crashes the enum).
- `journal_server.py` (0.2.0 → 0.2.1): `clean_symbol` on the symbol key/filter of
  `transactions_read`, `journal_read/write`, `position_record_*`, `order_record(_list)` —
  prevents corrupted records and silent zero-row filters (protects the HISTORY table).

## [1.32.1] — 2026-07-04 — HISTORY: fakeable line → forced table (tool-output cells)

### Why
1.32.0's step-7 HISTORY was a prose LINE with an "or 'no recent activity'" escape.
First live cycle exposed the flaw exactly as `constitution-steps-not-prose` predicts:
the local model wrote `HISTORY BTC/USD: No recent activity in the last 7 days` **from
memory, never calling `transactions_read`** — and it was false (the ledger showed BTC
bought→stopped→re-bought→stopped in the prior 3 days). It then bought 0.15 BTC more on
the fabricated line — the very churn the ledger exists to stop. A line of prose can be
authored from memory; the escape hatch made the assertion free.

### Changed — `prompts/constitution.md`
- Step-7 HISTORY is now a **FORCED TABLE** on the proven step-9(e) pattern: one row per
  name about to be bought/added, cells **read off the `transactions_read` output** —
  the fills column is the tool's RETURNED ROWS pasted verbatim (timestamps + prices it
  cannot type from memory), "cannot be asserted from memory." No table = step 7 not
  done, no order in step 8 without it. "No recent activity" is legal ONLY when the tool
  actually returned zero rows. Still REPORTS, never gates (re-buying a churned name
  stays the agent's call). Names a concrete failure example so the model can't pattern
  off a friendly one.

## [1.32.0] — 2026-07-04 — transaction-history ledger the agent can read by symbol + timeframe

### Why
The agent churns (the XRP episode: ~$1k lost re-buying a name it had just
stop-churned, then re-buying it AGAIN the next clean cycle). Root cause, confirmed
by dumping the journal DB: **it has no memory of its own executions.** The journal
holds prose; `orders_of_record` had 15 rows for 548 real fills; `positions_of_record`
was purged to 0. There was **no place the agent could look up "what did I actually
DO with symbol X over the past Y days"** — so it re-entered names blind to the fact
it had bought-and-sold them repeatedly that week. Real trade history lived only at
the broker, undigested.

The fix is a plain **transaction ledger** — one row per broker fill, `bought/sold
SYMBOL qty @ price — reason` — queryable by symbol + timeframe. **Deliberately NO
realized-P&L / FIFO / win-rate computation:** the churn is self-evident from the raw
sequence (`buy 1.18 → sell 1.16 → buy 1.19 → sell 1.17`) and computing P&L would edge
toward cognition. And the constitution change only *surfaces* the history at decision
time — it never gates. If the agent re-enters a name it stopped out of 4× today, that
is its call (§2: infra reports facts, the agent decides). This is also the clean
experiment the handoff wanted: with its own record finally in front of it, does
behavior change, or is the churn a model ceiling?

### Added — storage (`aitrader/journal_db.py` 0.1.0 → 0.2.0)
- New `transactions` table (PK `fill_id`): `symbol, side, qty, price,
  transaction_time, order_id, order_ref, fill_type, asset_type, reason, synced_at`.
  Append-only log of broker FACTS (a fill happened) — not mutable state, so it does
  not conflict with §6 "broker is source of truth" (we reconstruct it FROM the broker).
- `tx_upsert` (idempotent on `fill_id`; ON CONFLICT refreshes only `reason`/`order_ref`
  via COALESCE — a later sync that can't re-classify never wipes a found reason),
  `tx_latest_time` (incremental-sync cursor), `tx_read(symbol, since, limit)` newest-first.

### Added — sync (`aitrader/mcp/broker_server.py` 0.6.0 → 0.7.0)
- `sync_transactions(b)`, modeled on `maybe_backfill_equity` (same "broker MCP writes
  journal.db on a confirmed-good read" precedent). Incremental + throttled (≤1 pass /
  45s); pulls `get_fill_activities(after=<latest day we have>)`, upserts each. First
  pass backfills the ~30d the broker retains. Called from `get_account` + `get_positions`
  (not `broker_status`, to keep the readiness poll fast). Wrapped so a sync hiccup can
  never break the broker read that invoked it.
- **reason** attached best-effort (degrades to null): the agent's own recorded
  `intent` (joined `order_ref`→`orders_of_record.client_tag`), else a factual exit
  label read off the order type (`stopped out` / `take profit` / `manual`). Never an
  opinion of edge/quality.

### Added — agent tool (`aitrader/mcp/journal_server.py` 0.1.0 → 0.2.0)
- `transactions_read(symbol, since, limit)` — your own trade history, newest-first,
  with reasons. "See what you did with a name over a window before you act on it again."

### Changed — `prompts/constitution.md`
- **Step 7 GATE**: new neutral **HISTORY line** before any buy/add/re-entry — call
  `transactions_read(symbol, since=~7d)` and write the recent buy/sell sequence. It
  REPORTS; it does NOT gate or demand justification (no anti-churn opinion — that would
  be cognition per §2). Missing it is an incomplete artifact, like a missing CARD line.
- **Step 5(c)** now points at `transactions_read` to ground "is the strategy working"
  in the actual trade record.
- **Placing an Order step 1** now records structured `order_record(..., intent=…)` —
  that intent is what becomes the *reason* on the fill in the ledger.

## [1.31.0] — 2026-07-04 — constitution step 0: READY gate (broker_status must confirm before any action) — fixes the MCP startup race

### Why
On a fresh session the MCP servers (broker/scheduler/journal/memory) take ~30–60s
to come online; until then EVERY tool call returns "No such tool available". The
model fired its whole reconcile burst the instant the session started, all bounced,
and it risked proceeding/deciding on a blank read (concluding "flat / stopped
out"). `broker_status` already exists for exactly this ("call this first to verify
the broker is reachable") — the constitution just never gated on it. First attempt
was a prose `## READY` section; that violates `constitution-steps-not-prose` (the
model obeys numbered STEPS with a forced artifact, ignores prose), so it was made
a real step.

### Changed — `prompts/constitution.md`
- New **step 0 · READY**: first action every wake is `broker_status`; forced
  artifact `READY: broker_status connected=true` before step 1. If it errors or
  `connected: false`, call it again and do NOTHING else (no now/memory/reconcile/
  order) until connected. Never place/modify/cancel or conclude "flat/stopped out"
  on a wake without that READY line — a failed read is the servers loading, not truth.
- Old `0·TIME` folded into **step 1 · RECONCILE** (call `now` first), so steps
  2–11 and all their cross-references are unchanged — no renumber.

### Deploy
Deployed to run-dir CLAUDE.md; agent halted pending owner start.



### Why
Live incident: the agent trailed its XRP stop with `modify_order(stop_price=1.165)`
and the resulting stop was **1.17** (0.3% under a 1.1732 market) → instant
full-position wick-out of ~25k XRP. It then misread the stop-out as a tool bug
("modify_order acted as a market sell — I accidentally liquidated my position")
and re-bought 25k @ ~1.178 (higher), then stopped out AGAIN at 1.165. Day P&L
swung from +$387 to ~−$1,100 on churn + fees. Root causes, all confirmed:
- **Rounding:** `AlpacaBroker.modify_order` rounds with `symbol or ""`; the agent
  omits symbol on a trail, so a crypto price rounds as a STOCK (2dp):
  `round_price(1.165, "") == 1.17`. Proven in-repl.
- **IBKR has the SAME bug:** its `modify_order` had no crypto branch, so crypto
  fell into `else: round(x, 2)` — identical 1.165→1.17. Latent (IBKR crypto is
  Paxos/live-only, untradeable on paper) but would bite at go-live.
- **Cushion:** even the *correctly* rounded 1.165 (0.7% under price) triggered the
  second stop-out — crypto's range makes a last-candle-low stop a hair-trigger.

### Changed
- `brokers/alpaca.py` `modify_order`: look up the order's symbol when the caller
  omits it, so crypto rounds to 8dp (stocks stay 2dp).
- `brokers/ibkr.py` `modify_order`: added a crypto branch that passes prices RAW
  (matching its own `place_stop_limit_order`), not `round(x, 2)`.
- `brokers/ibkr.py` `place_stop_order`: documented that the crypto path sends a
  stop-MARKET which is UNVERIFIED on Paxos (go-live checklist: verify on a live
  IBKR crypto account; route to stop-limit like Alpaca if rejected).
- `prompts/constitution.md` 9(e): crypto stops need far more room — anchor under a
  real swing low several bars back, never the last candle's low (that liquidates
  the whole position, then it re-enters higher — the `card-crypto` churn).

### Deploy
`make build && make install` (broker code) + deploy constitution. Agent is HALTED
(`systemctl --user stop aitrader`) pending these fixes — start it back up only after.



### Why
The dashboard's "Engine Log" pop-out (LogViewer/LogPeek) was tailing the wrong
file: `/log` globbed `run_dir/.ccloop/runs/<run>/session*` and matched the ccloop
relay-PROMPT files (`session-N.prompt`), not the agent's output — so it showed a
handoff blurb, never the agent's actual work. Meanwhile Claude Code already writes
a complete structured transcript per session (thinking, tool_use, tool_result) to
`~/.claude/projects/<run-dir-mangled>/*.jsonl` (ccloop even symlinks it into the
run dir's `transcripts/`). Nothing was being logged that isn't already on disk —
it just wasn't surfaced.

### Changed — `aitrader/api.py` `/log`
- Reads the NEWEST Claude Code JSONL transcript for the run dir (the live session;
  dir name = run_dir with `/` and `.` → `-`, with a glob fallback) and RENDERS it
  to readable text: `💭` thinking, assistant text, `→ tool(args)`, `← result`,
  each timestamped. Injected system/user prompts are skipped as noise; tool
  results are kept. Tails the last `bytes` of the rendering; returns the same
  `LogTail` shape the panels already consume — so ZERO frontend changes.
- "Show thinking always" is automatic: thinking is in the JSONL, so it renders
  inline — a render, not a toggle.
- Display-only endpoint (served by aitrader-api); no trading path touched.

### Deploy
`make api` (rebuild package + restart aitrader-api). Follow-up idea: stitch across
relay sessions with `── relay ──` markers (currently shows the current session).



### Why
The agent tried to trail its XRP stop (1.12 → 1.144) and hit a tool error
(journal 161). Root cause: `AlpacaBroker.place_stop_order` unconditionally built a
`StopOrderRequest`, but Alpaca rejects naked stop-MARKET on crypto (only
stop-limit) — the very thing the code already knew for brackets (`no naked crypto
stop-market`, place_bracket_order). Meanwhile constitution step 9(c) told the
agent to "use `place_stop_order` (stop-market), NOT a stop-limit" — equity-correct,
crypto-broken. Evidence: every live crypto stop in the account is `stop_limit`,
every stock stop is `stop`. Secondary trap: trailing by *placing a new* stop for
the full qty fails anyway — the coins are held by the resting stop
(`qty_available` ~0), so a second order is rejected for insufficient quantity; a
trail must `modify_order` the existing stop.

### Changed
- `aitrader/brokers/alpaca.py` `place_stop_order`: if `is_crypto(symbol)`, route to
  `place_stop_limit_order` with a mechanical limit just past the stop (sell
  `stop*0.995`, buy `stop*1.005`) — same convention as `_place_crypto_bracket`.
  Caller's `stop_price` untouched; returned order reads `stop_limit` on reconcile.
  Pure venue adaptation (like the tif GTC-coercion), no strategy.
- `prompts/constitution.md` step 9(c): crypto carve-out — call `place_stop_order`
  there too (infra makes it a stop-limit; `stop_limit` on reconcile is correct, not
  a bug), and MOVE any stop via `modify_order` on the existing order, never a
  second stop.

### Deploy
Package change → `make build && make install`; constitution → `make const`. Both
land on the agent's next restart (broker MCP respawns from the installed package).



### Why
First post-1.27.0 cycle on atrader: the agent read card-crypto and declined
XRP/ADA momentum entries citing the 1.26.0 weekend-entry warning — with ONE
blanket card citation for five names, no step-4 numeric columns, no step-7
per-candidate numbers (the 1.10.0 channel-arbitration failure mode: the
caution channel wins ties and eats the discipline). The user then challenged
the premise itself — crypto trades 24/7; the agent CAN trade/watch all
weekend — and the account's own data agrees: FIFO by entry weekday shows NO
weekend-entry penalty (Sat 41% WR/−$2.4k, Sun 47%/−$0.2k vs Mon 53%/−$4.2k,
Wed 40%/−$6.0k — the losses were names/structure, not calendar). The 1.26.0
veto had imported the PREDECESSOR's architecture (daytime cron, genuinely
unwatched weekends) into an agent that never has to sleep. Meanwhile the
agent's actual weekend behavior — sleeping until Monday while HOLDING $20k
of crypto on stop-limits — was the real hazard, and step 11 said so only
implicitly.

### Changed — `prompts/ccmemory-seed/card-crypto.md`
- Weekend paragraph rewritten: weekends/nights are a CONDITION you price,
  never a calendar veto — "a qualifying setup on a Saturday is still a
  qualifying setup," with the entry-weekday data cited. What weekend tape
  demands instead: a structural stop thin-tape noise can't reach (sized to
  survive a gap through the stop-LIMIT band) and STAYING ON WATCH (step 11).
  Disaster clustering (FTX/Luna/Mt Gox) reframed as punishing UNWATCHED
  books.
- Closing action clause (from the staged-but-never-shipped 1.27.1): the card
  describes HOW to enter crypto, not WHETHER; deploy-default applies
  unchanged when its conditions hold; "because of the card" with no step-7
  number is an excuse; the card sharpens the step-4/7 discipline, never
  replaces it. Description line updated.

### Changed — `prompts/constitution.md` (step 11)
- Explicit off-hours leash: holding ANY position in an open class (crypto
  nights/weekends) → the leash never exceeds ~2h, 5–15m when it's moving,
  around the clock; stop-LIMITs can gap through unfilled while asleep; only
  a FLAT book earns a long sleep while crypto is open. (The live agent's
  "wake Monday morning" while holding BTC+SOL violated the old wording's
  intent; now it violates its letter.)

### Deploy
`make const` on both nodes + card copy/index clear/restart on atrader (and
itrader for card parity). Restarts are free (agents idle into the weekend).
Watch: the agent's next wait while holding crypto must be ≤~2h, and Monday's
first crypto cycle must show step-4 numbers + per-candidate step-7 numbers
with no card-as-blanket-veto.



## [1.27.0] — 2026-07-03 — constitution: step-7 CARD LINE — forced card-read artifact on every carded-class entry

### Why
The 5 `card-*` notes (per-asset scar tissue, enriched in 1.26.0) were wired
only as a session-start step-A prose rider — and atrader's journal shows ZERO
card reads ever. Established doctrine: the local model obeys discrete
steps/sub-steps with forced artifacts and ignores prose riders
(`constitution-enforce-via-step-not-column`; the 1.23.0 column failed where
the 1.23.1 9(f) sub-step verified live). Trigger: the 2026-07-03 BTC+SOL
weekend entry — ~31% of equity into crypto, SOL from the old catastrophic
tier, sub-1% stop-limits into a 3-day weekend — while the card that argues
with every part of that sat unread.

### Changed — `prompts/constitution.md`
- **Step 7 gains the CARD LINE sub-step** (between the SELL and BUY bullets):
  before ANY entry (open, add, or short) in a carded class (crypto / forex /
  futures / options / leveraged-daily-reset ETP), `memory_get` the class card
  on first use per session (relays reset), then EVERY carded entry writes ONE
  line before placement: `CARD <class>: "<the card line that argues hardest
  AGAINST this trade>" — <why the trade survives it, or the evidence that
  overrides it>`. Judgment, not a veto — trading against the card is legal
  only with the overriding evidence in the line. No line = step-7 FAILURE
  (the order may not be placed in step 8). `memory_get` error → the line
  says so and the trade proceeds (a memory outage never blocks trading).
  Plain unlevered stock entries need no line.
- **Step 10** now requires the `CARD` line per carded entry in the journal
  (same pattern as the 9(f) line requirement).
- **Step A** now points at the step-7 enforcement instead of carrying the
  (proven-dead) "read before you trade" prose rider on its own.

### Boundary
The card stays guidance the agent weighs — the artifact forces READING and an
ARGUED position, never an auto-reject. No screener, no allowlist, no code
gate (BRIEF §2/§8).

### Deploy
`make const` on BOTH nodes (constitution → run-dir CLAUDE.md + agent
restart). atrader ALSO needs `./install.sh` first so the 1.26.0-enriched
card-crypto is in its store (cards are canon, install overwrites). Live
test: the next carded-class entry must render the `CARD <class>:` line in
the journal — same verification pattern as 9(f).



## [1.26.0] — 2026-07-03 — card-crypto gains the predecessor's autopsy: the 6.7% win rate's three causes + the weekend-ENTRY corollary

### Why
atrader bought ~$20k of BTC+SOL (~31% of equity) at 13:23 ET on the Friday of
a 3-day US holiday weekend, thesis "confirmed recovery / short-squeeze", with
stop_limits 0.6%/1.1% below entry — after journaling crypto "Extreme Fear,
multi-month lows" two days earlier. That is, pattern-for-pattern, how the
predecessor system (/src/archive/trader, /home/trader trading.db) produced its
documented 6.7% crypto win rate: chasing "confirmed recoveries" that were
distribution/markdown in disguise, re-entering after stop-outs (its single
biggest documented loss source), and equity-width stops that crypto noise
harvests. DB corroboration: of 195 crypto sells (502 crypto trades,
2026-02-23→06-22), only 9 were full take-profits vs 59 stop_losses + 84
trail exits. The existing card-crypto carried the mined universe/vol/weekend
lessons but NOT this three-pattern autopsy — and the journal shows the agent
has never read any card (zero card-* mentions ever): the step-A prose rider
"memory_get the card before you trade a class" does not bind the local model
(same failure class as [[constitution-enforce-via-step-not-column]]).

### Changed — `prompts/ccmemory-seed/card-crypto.md`
- New paragraph: the 6.7% autopsy as three named patterns (recovery-chasing in
  broken structure; re-entry after repeated stop-outs — walking away IS the
  winning move; sub-1% stops as noise-harvesters, with sizing bound to a
  structural stop). Evidence + disposition prose, no thresholds-as-gates
  (BRIEF §2): numbers appear as the predecessor's record, not as rules.
- Weekend paragraph gains the timing corollary: ENTERING Friday before a
  (long) weekend is the worst-timed add, and Alpaca crypto protective stops
  are stop-LIMIT — a fast gap through the limit can skip the fill and leave
  the book naked when no one is watching. Momentum chases have no business
  spanning a weekend.
- Universe paragraph gains the v3.1.15 validated tier record behind the
  "-$20k → +$3.5k" swing: the six Tier-1 names (BTC/ETH/DOGE/AAVE/SHIB/SKY,
  +$3,485 on 52 trades) vs the catastrophic ten (incl. SOL: −$19,672 on 50),
  framed as evidence-not-canon with the small-n caveat and a burden-of-proof
  disposition for re-entering old catastrophic-tier names; notes the same
  validation DISPROVED exit-tightening. The shipped allowlist mechanism
  itself (`screener.crypto.allowlist` / `get_crypto_universe`) stays dead —
  restriction-by-edge is the agent's reasoning, not a config gate (§2/§8).
  Pointed today: atrader's SOL buy is an old catastrophic-tier name.
- Description line updated to lead with the autopsy.

### NOT done (deliberately)
No code gate, no size cap, no crypto block — cognition stays in prose
(BRIEF §2/§3). Constitution change (forced card-read artifact at first entry
per class per session) proposed to the user separately — constitution surgery
is deployed judgment, not a unilateral edit.

### Deploy
Cards are canon and OVERWRITE on install: `./install.sh` (or make install) on
the atrader node, then the agent picks it up at next session start (step A) —
IF it reads cards at all, hence the proposed constitution step.



## [1.25.0] — 2026-07-03 — IBKR forex/futures availability from real contract hours (finishing what 1.24.0 started)

### Why
1.24.0 gated only the STOCK flag on broker truth; `get_available_types`' forex/
futures booleans were still Sun-5PM-to-Fri-5PM weekday arithmetic — no broker
query at all. On the observed-July-4 holiday that overreports: CME Globex halts
at 12:00 CT / 13:00 ET but the math keeps futures "open" until 17:00 ET. The
user's point stands: the broker PUBLISHES per-contract hours; asking anything
else is indefensible.

### Changed — `ibkr.py` 1.4.0
- Forex/futures flags now come from the LIVE trading windows of a
  representative contract — forex: EUR/USD (IDEALPRO), futures: front-month ES
  (CME Globex) — the same representative-proxy pattern as SPY for the stock
  session. `class_windows_from_gateway` pulls contract-details `tradingHours`
  (NOT liquidHours: the overnight Globex session is tradeable);
  `parse_trading_hours` (module-level, pure) converts modern
  `YYYYMMDD:HHMM-YYYYMMDD:HHMM`, legacy `YYYYMMDD:HHMM-HHMM,…`, and `:CLOSED`
  entries into UTC windows using the details' own `timeZoneId` (US/Central for
  CME). `class_open_now` evaluates now-in-window per call; windows cached per
  (class, ET date) in `class_windows_by_date`; gateway failure returns the
  weekday-math fallback and is never cached. Helpers are undecorated
  (the 1.24.0 route_to re-entry rule).
- Alpaca/MYSE untouched (neither serves forex/futures).

### Verified — live against the real paper gateway (2026-07-03, port 4002)
Read-only contract-details queries on client id 993, single asyncio loop:
futures window today `Thu 18:00 → Fri 13:00 ET` (the CME holiday halt, from
the broker's own string), forex `Thu 17:15 → Fri 17:00 ET` (normal forex
Friday), gate == window math with no fallback consumed, caches populated —
and `market_session_now` returned `closed` from real SPY liquidHours,
confirming the 1.24.0 stock gate against the live broker as well. As of 11:09
ET the flags read futures=OPEN forex=OPEN stock=closed — all three exchange
facts. After 13:00 ET futures flips to closed (pre-1.4.0 math would have said
open until 17:00).
Note: the legacy `pool_mode=False` + sync `IB.connect()` path cannot make
post-connect gateway calls from the route wrapper's `asyncio.run` (cross-loop
deadlock in ib_async) — pre-existing, test-mode-only; pool mode (production)
runs all of this on persistent worker loops like every other data method.

### Deploy
`make build` + install + restart broker MCP (and `aitrader-api`) on the IBKR
node. Until ~13:00 ET today itrader legitimately shows futures/forex open.



## [1.24.0] — 2026-07-03 — holiday-aware market sessions: brokers gate the clock on their own calendar; the resolver stops fabricating closes on holidays

### Why
On 2026-07-03 (Independence Day observed — NYSE closed all day) BOTH live nodes
(itrader/IBKR and atrader/Alpaca) reported the stock market open. Root cause:
`get_market_session` on both drivers was pure weekday + 9:30-16:00 ET time math
with zero holiday awareness, `get_available_types` derives `stock` from it, and
constitution step 2 tells the agent to trust that tool ("Don't assume market
hours — use the tool"). The old /src/trader IBKR driver consulted Alpaca's
clock here; the clean-room port dropped that cross-broker call "in favor of
pure time math" and the holiday awareness silently went with it. The ABC even
specified the blindness as contract ("Pure time-math check — no API calls").
Meanwhile the genuinely holiday-aware plumbing (`get_session_close`: Alpaca
`/v2/calendar`, IBKR SPY liquidHours; MYSE's `/clock`) sat unused for the
open/closed answer. Compounding it, `market_calendar.query_library` conflated
"holiday" with "library failed", so the resolver fabricated a 16:00 ET close on
weekday holidays — `market_status` emitted a contradictory `session_close_utc`
and `wait_until_session_close` would sleep to 16:00 on a closed market.

### Fixed — brokers (`alpaca.py` 0.5.0, `ibkr.py` 1.3.0, `broker.py` ABC 2.4.0)
- `get_market_session` is now gated on today's session close from the broker's
  OWN calendar (Alpaca `/v2/calendar`; IBKR SPY liquidHours), cached once per
  ET date (`session_close_by_date`; None = confirmed no-session day). A holiday
  is `closed` outright (no extended windows); half-days end the regular session
  at the real early close (bonus fix — 16:00 was hardcoded before). Only when
  the calendar is UNREACHABLE (failures never cached; IBKR wrapped in a 10s
  `wait_for`) does it degrade to the old weekday math, so an outage yields the
  pre-1.24.0 answer rather than calling a live session closed.
- `get_available_types` (`stock`/`options`) inherits the gate. Forex/futures
  weekday math is unchanged (their own holiday schedules remain unmodeled).
- IBKR plumbing: `get_market_session`/`get_available_types` became routed-async;
  shared bodies live in undecorated helpers (`market_session_now`,
  `session_close_from_gateway`) because routed methods must not re-enter
  `@route_to` (pool re-entry hands back a raw coroutine; non-pool mode would
  nest `asyncio.run`). Alpaca: calendar parse extracted to
  `calendar_session_close` (raises on API failure so the gate can tell "no
  session" from "no answer"); `get_session_close` keeps its None-on-failure
  contract.
- ABC docstrings now REQUIRE the holiday-aware gate (the old "Pure time-math
  check — no API calls" contract was the codified bug).

### Fixed — `market_calendar.py` 0.2.0
- `query_library` returns a `NOT_TRADING_DAY` sentinel when the NYSE schedule
  is empty (authoritative no-session) vs None only for "library unavailable";
  `resolve_and_cache` caches a confirmed holiday as `(None, "library")` and
  returns None instead of falling through to the weekday-16:00 fabrication.
  `market_status` now reports `session_close_utc: null` on holidays and
  `wait_until_session_close` returns `no_session_today` immediately.

### Verified
13/13 live checks (real NYSE rules calendar + real failing API/gateway calls,
no mocks): 2026-07-03 resolves to no-session `(None, "library")` (was
fabricated 16:00 "fallback"); 2026-07-02 close 20:00Z; 2026-11-27 half-day
18:00Z; both drivers return `closed` when the gate knows today has no session,
`{stock: False, crypto: True}` from Alpaca `get_available_types`; both degrade
to legacy math on unreachable calendar/gateway without caching the failure;
IBKR's routed-async path runs clean in non-pool mode (`asyncio.run` wrapper).

### Deploy
`make build` + `install` + restart broker MCP (and `aitrader-api`) on each
node — the MCP runs the INSTALLED package. No constitution change: step 2
already says "use the tool"; the tool just stops lying on holidays.



## [1.23.1] — 2026-07-01 — constitution: move the profit-lock from a 9(e) COLUMN to a discrete 9(f) SUB-STEP (the column was ignored)

### Why
1.23.0's `locks a gain?` column deployed and loaded correctly (verified: run-dir
CLAUDE.md updated 15:33:58 UTC, agent restarted 15:33:59, journal entry 125 at
15:47) — and the model IGNORED it, reproducing its habitual 5-column trail table
with no such column. A weak local model templates off its own prior journal
entries (5-column tables) over a format tweak buried in the constitution. Lesson
(now memory `constitution-enforce-via-step-not-column`): the model obeys a
STEP/SUB-STEP as an obligation but treats a column/field inside an already-
established artifact as optional. The user proposed a 9(f) two revisions ago; it
was the right call. Enforcement must be its own step, not a graft onto a table.

### Changed — `prompts/constitution.md`
- Reverted the 9(e) trail table to 5 columns and removed the "LOCK THE GAIN"
  bullet that fed the column.
- Added discrete **step 9(f)**: for every green position, write one line
  `SYMBOL — stop vs entry — LOCKS GAIN / NO`. NO on a name up more than a session
  is a step-9 FAILURE with a forced fix (raise the stop under the nearest higher-
  low above entry, confirm the new id) — cannot leave step 9 until every winner
  reads LOCKS GAIN. This is a discrete CHECK + ACTION (a binary the model can
  evaluate), not a skill; boundary-clean (stop-vs-entry is a fact, no coded %).
- Step 10 (JOURNAL) now requires the 9(f) line per winner.

### Deploy
`make const`. Live test: does 9(f) render where the 1.23.0 column didn't?



## [1.23.0] — 2026-07-01 — constitution: step 9(e) trail table gains a `locks a gain?` column (a below-entry stop on a winner protects nothing)

### Why
Live under 1.22.0: META entered 604.47, ran to ~627 (+3.6%, +$1,500), but its
trailed stop sat at 595 — BELOW entry. The "trail" (590→595) locked in nothing; a
reversal to 595 would give back the whole gain AND book a ~$663 loss (~$2,180
round-trip exposed). The journal cited "structure price 595.10" — not a real
higher-low of a stock at 627 (which has printed higher-lows above 604), just its
original entry-stop area dropped into the cell. Same skill ceiling as NVDA's
equal-to-current structure fabrication, opposite direction (too loose vs too
tight). 9(e) told it to trail under a higher-low but never forced the consequence:
on a real winner that higher-low is ABOVE entry, so the stop should lock a profit.

### Changed — `prompts/constitution.md` step 9(e)
- Trail table gains a column: `new stop vs ENTRY — locks a gain?` (YES = new stop
  > entry; NO = new stop ≤ entry). Forces the agent to confront that a below-entry
  stop on a winner protects nothing.
- New rule: a meaningful winner (up multiple percent for >1 session) whose row
  reads NO is a step-9 FAILURE — either it lowballed the structure (find the
  higher-low above entry and trail under it) or it is knowingly leaving profit on
  a below-entry stop. The only legit NO is a fresh/vertical position with no
  higher-low above entry yet, stated explicitly.
- Boundary: comparing new-stop-to-entry is observing a FACT, and "trail under the
  higher-low above entry" is structure logic — no fixed %/formula, no coded gate.
  Folded into 9(e) (not a new 9(f)) so the profit-lock can't be skipped separately.

### Deploy
`make const` (prompts/constitution.md → run-dir CLAUDE.md + agent restart).



## [1.22.0] — 2026-07-01 — constitution: step 9(e) structure price must sit below current + step 5 restructured into a 3-part REVIEW

### Why
The 1.21.0 forced-table pattern worked live (agent trailed TSLA/NVDA/PM the next
cycle), but the first cycle also exposed two gaps:
1. **9(e) structure cell could be gamed:** NVDA's row cited a "structure price"
   equal to its current price (not a real higher-low), and all three trails came
   in ~0.6–0.75% under current — hair-triggers 9(e) warns against.
2. **Step 5 was being skipped the same way trailing was.** Step 5 already demanded
   a per-position `thesis | buy again? YES/NO` verdict, but the journals never
   contained it — every cycle collapsed it to "All holdings justified for hold,"
   so WMT/COST/PG rode falsified strength theses down for a week (WMT 119→111,
   lower lows, journaled as "stable demand"). A bare YES/NO is trivially
   rubber-stamped; without an evidence column there's nothing to contradict.

### Changed — `prompts/constitution.md`
- Step 9(e): the structure price MUST be strictly below current (a higher-low is
  a pullback the market has since risen above; equal-to-current = no higher-low →
  HELD), and the stop rides just under that structure so it keeps room — a stop
  within a normal wiggle of current is the forbidden hair-trigger. Kills both the
  NVDA-style fabricated cell and the too-tight trails.
- Step 5: restructured from a one-line verdict into a 3-part REVIEW (sub-steps
  like step 9's a–e), all forced:
  - **(a) each held item** — a FORCED TABLE, one row per position with an EVIDENCE
    column (price since entry: %, higher/lower lows) and a CONFIRM/FALSIFY judgment
    against the position's own thesis. A strength/leadership/momentum thesis on a
    name making lower lows CANNOT be CONFIRM; FALSIFY → NO → SELL. A genuine
    patient/value hold must say so explicitly and name its break level.
  - **(b) the book as one object** — the gap per-item review is blind to:
    aggregate exposure/leverage, the largest correlated cluster as % of equity
    (the one-bet check that the 5-staple 1.4× book failed), and coherence vs the
    step-3 posture. Verdict can force a trim/de-lever/hedge (→ SELLs into step 6).
    No coded cap — the agent writes the concentration number and judges it (§2).
  - **(c) is the strategy working** — grade the step-3 posture against RESULTS, not
    intentions; a losing stance re-affirmed cycle after cycle ("still OFFENSE"
    while the book bleeds) must be CHANGED, and the revised posture overrides
    step 3 for the rest of the cycle.
- Step 10 (JOURNAL): must reproduce all three review parts; "all holdings
  justified" now reads as step 5 skipped.

### Deploy
`make const` (prompts/constitution.md → run-dir CLAUDE.md + agent restart).



## [1.21.0] — 2026-07-01 — constitution: step 9(e) TRAIL-WINNERS rewritten prose → FORCED TABLE (structure price unfillable without `get_bars`)

### Why
Observed live: NVDA (+2.5%) and TSLA (+5% over several sessions) sat on their
entry-era stops (188, 400) for a week — untrailed — while every hourly journal
said "All positions protected by GTC stops / all holdings justified for hold."
Asked why, the agent produced a fluent, correct-sounding "I trail under structure,
not price; waiting for a higher-low" answer — lifted almost verbatim from the
EXISTING step 9(e) — but the journals contain ZERO structural analysis: no bars
pulled, no higher-low/MA prices, no `old → new`. It recited the rule and then did
nothing, using the "avoid hair-triggers" caveat as blanket cover for inaction —
the exact loophole 9(e) already tried to close with prose. A strongly-worded prose
rule doesn't bind this (local gemma-4) model; a forced artifact does (cf.
`constitution-steps-not-prose`). So 9(e) is now a table whose structure-price cell
is unfillable without actually calling `get_bars`, and `HELD` is only legal when
that price is ≤ the current stop. Boilerplate "held" can no longer satisfy it.

### Changed — `prompts/constitution.md`
- Step 9(e): rewritten from a prose paragraph into a FORCED TABLE — one row per
  position green since entry (columns: symbol, entry→current %, structure price
  read off the bars, old→new stop, action = modify_order id or `HELD` + reason).
  No row for a green name = step 9 not done; a `HELD` with no qualifying number
  (structure price ≤ stop) is a step-9 failure.
- Step 10 (JOURNAL): the STOPS section must now reproduce the 9(e) TRAIL TABLE in
  full; a list of static stop levels with no trail table = 9(e) was skipped.

### Deploy
`make const` (deploys prompts/constitution.md → run-dir CLAUDE.md + restarts the
agent, which reconciles from broker+journal on relaunch). Not live until deployed.



## [1.20.3] — 2026-07-01 — fix: `to_stp` + heat display for a breached stop (a pre-market gap past a long's stop read as 0% risk / ~1% to-stop)

### Why
A pre-market gap put WMT's price (110.90) below its 112 long stop. Both the
`positions` CLI and the dashboard read `/status`, and both showed nonsense: Heat
`0.00%` and "To Stp" `~1%` on a position that was actually *past* its stop. Two
display formulas assumed a long's stop always sits *below* price:
- `to_stp = abs(cur − sp) / cur` — the `abs()` threw away the sign, so a stop 1%
  ABOVE a long's price (breached) was indistinguishable from 1% of cushion below.
- heat `|mv| × max(0, cur − stop) / cur` — the `max(0, …)` floored a crossed
  (negative-distance) stop to 0, reporting "no risk" on a breached position.

Not a bug investigated but discarded: the price mark itself (110.90) was CORRECT
— it's the live pre-market print (confirmed vs MarketWatch). What's stale in
pre-market is `get_snapshot.latestTrade` (sticks at the prior regular close,
113.26), so re-marking positions FROM the snapshot was considered and REJECTED —
it would have overwritten the fresh mark with a stale one. The stop also
correctly did NOT trigger: simple stop orders only arm during the regular
session, so a pre-market gap through the level waits for the 9:30 open.

### Changed — `aitrader/api.py`
- `enrich_positions_with_protective_orders`: `to_stp` is now progress-toward-stop
  (`stop/current` long, `current/stop` short) — 100% = at the stop, >100% =
  breached. Renders via the UI's `formatPercent` (×100) and the CLI's `×100`
  unchanged, so a breached stop now reads `101%` instead of `1%`.
- `enrich_positions_with_heat`: a stop crossed to the wrong side (dist ≤ 0) now
  counts full `|market_value|` at risk (same as unprotected) instead of flooring
  to 0 — a breached stop protects at no known level (fills at the next open).



## [1.20.2] — 2026-06-29 — constitution step 10: journal entries MUST be human-readable (labeled sections, not a wall of text)

### Why
The account owner reads the journal. The agent had been cramming RECONCILE +
REGIME + SURVEY + STEP-5 + GATE + TRADE + STOPS + NEXT into one unbroken run-on
paragraph — complete but unreadable, explicitly (and forcefully) called out. A
formatting rule that applies to EVERY `journal_write` shouldn't depend on a
memory being recalled at write-time; the constitution is loaded unconditionally
every session/relay, so the enforceable rule belongs in step 10 (which specified
*what* to include but nothing about *format* — exactly where the run-on slipped
through). The `journal-must-be-human-readable` seed memory carries the detailed
how-to as reinforcement.

### Changed — `prompts/constitution.md` step 10 (JOURNAL)
- Added a FORMAT directive: short LABELED sections (`RECONCILE:`, `REGIME:`,
  `SURVEY:`, `TRADE:`, `STOPS:`, `NEXT:`) each on its own line with line
  breaks/bullets, NEVER one run-on paragraph; the body is Markdown, use real
  line breaks; "completeness without readability is a failure." Plain imperative
  voice (no persona, no malformed examples — per the constitution memories).
- Deploy with `make const` (constitution-only; `make full` does not touch it).
- Also seeded `prompts/ccmemory-seed/journal-must-be-human-readable.md` so every
  `./install` ships the detailed rule as canon. A live row (itrader journal id
  168) was reformatted in place as the worked example.

## [1.20.1] — 2026-06-29 — fix: Alpaca data feed defaults to IEX (real-time) instead of SIP (silently ~15-min stale)

### Why
`AlpacaBroker.get_stock_bars` defaulted its feed to `DataFeed.SIP`. On a
free/basic Alpaca plan (which both nodes share) SIP is **delayed ~15 min and
recent SIP is blocked outright** — so the default silently returned intraday
bars ~15 minutes stale (measured live: default-SIP last 5-min bar 18:20 UTC vs
IEX 18:35, the recent window simply missing, no error). A 15-min-old view of the
5/15-min tape defeats the whole momentum/discovery loop (constitution step 4:
"confirm clean directional structure before entering"). Snapshots had the
inverse quirk — they used the SDK default (IEX), which is why `latestTrade` was a
thin single-venue print (see the `snapshot-latesttrade-unreliable` agent memory).
Root: the feed wasn't configurable and the bars default was wrong for a non-SIP
account.

### Fixed — Alpaca feed is now configurable, defaulting IEX (real-time)
- New setting `alpaca_data_feed` (`config.py` DEFAULTS + `Settings` property),
  default **`"iex"`**. `"sip"` opts a SIP-entitled (paid) plan into the full
  consolidated tape.
- `AlpacaBroker.__init__` takes `data_feed="iex"`; new `resolve_feed()` maps it
  to the `DataFeed` enum. `get_stock_bars` now defaults to the configured feed
  (was hardcoded SIP); `get_stock_snapshot`/`get_stock_snapshots` now pass it
  explicitly (was the implicit SDK IEX default). Callers can still pass
  `feed=DataFeed.SIP` for full-session historical volume.
- Wired through every `AlpacaBroker` construction: `broker_server.build_data_broker`
  + `build_execution_broker`, and `api.build_data_broker` + the API's execution
  path — so the dashboard sees the same feed as the agent.
- Net effect on the current (IEX-only) accounts: intraday bars + snapshots are
  now REAL-TIME instead of ~15-min stale. No `settings.toml` change needed (IEX
  is the default). To use SIP, buy the Alpaca plan and set `alpaca_data_feed = "sip"`.

## [1.20.0] — 2026-06-29 — broker: `get_most_actives` feed (the liquid, large-cap side of the tape)

### Why
The agent looked for movers during a broad market rally and reported "no
candidates," then self-diagnosed correctly: it only had `get_top_movers`, which
ranks the whole US tape by raw % change and is structurally dominated by
low-float pump stocks (a $0.01→$0.02 warrant is +100% and crowds out the
large-cap up 2% on a billion shares). The liquid, institutionally-traded leaders
the rally actually runs on never appear in that feed — and a liquidity filter on
it wouldn't help, because the vendor ranks by % and truncates (`top` caps ~50),
so the leaders never make the returned list to be filtered. The missing thing was
a different *fact*: a volume-ranked view. Per CLAUDE.md §2, "most-active-by-volume"
is explicitly allowed DATA (a fact about price/volume, like a quote) — not a
quality/edge screen — so it belongs in infra, not in the agent's reasoning.

### Added — `get_most_actives(top_n=20, by="volume")` (broker MCP + `AlpacaBroker`)
- Pass-through to Alpaca `ScreenerClient.get_most_actives(MostActivesRequest)`.
  `by='volume'` (shares) or `by='trades'` (count). Returns
  `{actives:[{symbol, volume, trade_count}], by, as_of}`.
- DATA ONLY: ranked by raw trading activity, no edge/score/buy-sell. Carries no
  price/% (most-active ≠ moving up — a name can be ripping or dumping); the agent
  pulls bars/snapshots and judges direction/strength itself.
- Alpaca-only, mirroring `get_top_movers`: the MCP wrapper uses `getattr` and
  returns a graceful `error` on a node whose feed lacks it. `get_top_movers` is
  left untouched — it's a real fact (small-cap/penny momentum), just a different
  one. Two complementary feeds; the agent picks the lens.
- Docs: `docs/broker-mcp.md` "Deliberately absent" section corrected (it claimed
  no movers tool existed) — now documents both factual feeds and the
  fact-vs-edge line.

### Changed — constitution step 4 (`prompts/constitution.md`) — the disposition half
- Step 4 (SURVEY THE ACTUAL MOVERS) named only `get_top_movers`. Now directs the
  agent to pull BOTH feeds, explains WHY each covers a different part of the tape
  (% feed = low-float/penny; most-actives = liquid large-caps where an index
  rally runs, carrying no direction so read each name's bars), and adds the
  anti-passivity rule that surfaced this whole change: **"A quiet `get_top_movers`
  is NOT a quiet market … 'No big % gainers' is NEVER 'no candidates.'"** Deploy
  with `make const` (separate from the package — `make full` does NOT touch the
  constitution).

## [data repair] — 2026-06-29 — journal: repair tag fields corrupted by a malformed `journal_write`
*(live-data fix only — no package change; version stays 1.19.0)*

### Why
The dashboard JournalFeed couldn't render the 07:31 entry (id 92) — its `}}}`
ran off the screen. Root cause was a malformed `journal_write` tool call: the
agent wrote a perfectly good reconcile note (the **body** was clean), but the
`symbol` arg and a runaway-`}` flood spilled into the `kind` field — a 31KB
`kind` of literal `}` chars, with `symbol` left NULL. `kind` is rendered as a
short badge, so a 31KB value blew out the layout and bloated `journal_read`.
The same failure had recurred in milder form (`entry**, symbol: "GIS"`,
`note\``, `"reconcile"` on entries 40–43, 57) — the weak-model malformed-tool-
call mode (see memory `constitution-no-malformed-tool-examples`). The **root
cause was fixed at the vLLM tool-parser layer** (separate session), so no
MCP-side input sanitization was added — fix the cause, not the symptom.

### Fixed — live data (`journal.db`, in place per memory `live-journal-db-edit-in-place`)
- Repaired entries 40, 41, 42, 43, 57, 92: normalized `kind` to its real tag,
  recovered the embedded `symbol` where unambiguous (40→GIS, 92→PORTFOLIO),
  stripped a stray wrapping quote from 42's body. Bodies were already clean
  (the corruption was tag-only). Original rows saved to
  `journal-row92.backup` + `journal-malformed-kinds.backup` in the state dir.

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
