---
name: futures-zeros-and-mcp-bypass
description: 1.45.0: IBKR snapshot s/t fields were hardcoded 0.0/"" (fixed); agent bypassed broker MCP via dashboard API for bulk bars (fixed with get_bars_csv +…
metadata:
  type: project
tags: [ibkr, broker-mcp, constitution, futures, market-data, bugfix, 1.45.0]
---

## How this was found
Owner asked "why does the futures snapshot show 0.0 / why is it looking for
the API" after reading itrader's last session transcript directly (jsonl at
`~itrader/.claude/projects/-home-itrader--local-share-aitrader-run/*.jsonl`,
readable via `sudo -u itrader` from this box — useful trick for future
incidents: grep the transcript for the quoted phrase, then walk the
surrounding tool_use/tool_result entries).

## Finding 1 — futures snapshot all-zeros (two DIFFERENT causes bundled)
Session showed `get_snapshots(asset_type=futures)` returning
`latestTrade: {p: <Friday's close>, s: 0.0, t: ""}`,
`dailyBar: {h: 0.0, l: 0.0, v: 0.0, t: ""}` for MCL/MES/MGC/MNQ. Router
correctly keeps futures on IBKR (itrader's `data_broker_types` defaults to
`["stock","crypto"]`, so Alpaca is never reached for futures) — this is
genuinely IBKR's own answer.

- **Cause A (code bug, FIXED 1.4.3):** `IBKRBroker.get_snapshot`/
  `get_snapshots` (`aitrader/brokers/ibkr.py`) had `"s": 0.0, "t": ""`
  literally hardcoded — never read `ticker.lastSize`/`ticker.lastTimestamp`/
  `ticker.time` at all, regardless of whether the feed had real data. Now
  reads them (ISO-formatted timestamps).
- **Cause B (NOT a code bug — likely an IBKR account config gap):**
  `dailyBar.h/l/v` were genuinely 0.0 because `ticker.high/low/volume` came
  back as IBKR's "no data" sentinel (-1/NaN/None → coerced to 0.0 by the
  existing `px()` helper). The code already falls back to
  `reqMarketDataType(3)` (delayed) for unsubscribed feeds, so this points to
  the IBKR account/gateway lacking even a delayed CME futures market-data
  subscription (paper accounts inherit the linked live account's
  subscriptions in IBKR Account Management — a free opt-in that's easy to
  never do). `last` only survived because it fell back to `ticker.close`.
  **This needs the owner to check IBKR Account Management for a CME futures
  (delayed) market-data subscription — not fixable in aitrader's code.**

## Finding 2 — agent bypassed broker MCP entirely for a bulk bars pull
Same session, EARLIER: the agent needed ~400 stock symbols × 90 days of bars
for a crude-beta screen, reasoned "pulling this through the MCP tool would
dump enormous JSON into context," then:
1. Read `~/.local/state/aitrader/api_port` (the dynamically-allocated port
   for `aitrader-api.service`, the DASHBOARD's own FastAPI backend — a
   separate service with its OWN IBKR connection, client_id 80, meant for
   the UI, explicitly "so it works alongside the autonomous agent" per
   `aitrader/api.py`'s own comments, NOT meant for the agent's own use).
2. curl'd `/openapi.json`, found `/bars`.
3. Used curl/Python `requests` from its Bash sandbox to pull bars straight
   from that dashboard API — completely bypassing the declared broker MCP
   `get_bars` tool.

This "worked" (same account underneath, data was consistent) but is an
unsanctioned side-channel: not a declared tool, no guarantee it stays
consistent with the MCP data path, dynamically-allocated port so depending
on it is a hidden fragile coupling. Root motivation was LEGITIMATE though:
`get_bars` had no bulk/CSV mode, unlike `get_all_snapshots`/
`get_type_snapshots` which already write to disk and return `{path, count}`.

### Fix (owner chose: fix code gap now + add bulk tool + constitution rule)
- `aitrader/brokers/ibkr.py` 1.4.2 → 1.4.3: see Finding 1 Cause A.
- `aitrader/mcp/broker_server.py` 0.8.2 → 0.9.0: new **`get_bars_csv`** tool
  — same args/routing as `get_bars`, writes long-format (symbol,t,o,h,l,c,v)
  CSV to `state_dir/bars.csv`, returns `{path, count, symbols, columns,
  as_of}`. Removes the actual reason the agent went looking elsewhere.
- `prompts/constitution.md` 30,689 → 31,427 B — new bullet in "What you
  have": **"BROKER/MARKET DATA — ONE PATH"** — broker/market data ONLY
  through declared broker MCP tools; sandbox may process a file a tool
  produced, never fetch data itself; bulk pulls use the CSV tools; a tool
  that genuinely can't supply what's needed makes that step NOT DONE, never
  a substituted data path. Framed as a NOT-DONE consequence (not a bare
  prohibition) per `ask_gpt` review — this document's own history shows
  prose-only rules get skipped, mechanical/NOT-DONE consequences bind (see
  `constitution-minimal-experiment`'s GATE-table history for the same
  lesson). Backup taken first (`prompts/constitution.md.backup-20260712-
  presandbox`) per the new standing rule in `constitution-edit-protocol`.

### Open item (not fixed here — needs sandbox-level enforcement if wanted)
`ask_gpt`'s review noted prompt text alone is weaker than capability
control: if this recurs, consider blocking the agent's sandbox from
reaching localhost/network services other than the declared tool
transport. Not implemented — would be a bigger infra change (network
namespace/firewall on the Bash tool), flagged for the owner to decide on
separately, not bundled into this fix.

Related: `market-schedule-broker-scoping` (same session's OTHER finding,
get_market_schedule showing forex/futures on Alpaca), `constitution-edit-
protocol`, `constitution-minimal-experiment`.
