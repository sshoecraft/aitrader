---
name: data-execution-broker-split
description: aitrader broker model (0.13.0): settings.broker selects execution backend ibkr|alpaca|myse; optional data_broker fronts it; Alpaca/MYSE now full exec…
metadata:
  type: project
---

aitrader's broker layer mirrors `/src/trader`'s factory model: a selectable
EXECUTION backend + an optional separate market-DATA feed in front.

**Execution backend** — `settings.broker` ∈ {ibkr (default), alpaca, myse}.
`broker_server.build_execution_broker()` constructs it: IBKR claims the clientId
flock lease (see [[broker-clientid-lease]]); alpaca/myse just connect. Paper-only
fuse per backend — IBKR refuses non-DU/DF; Alpaca connects `paper=(not
allow_live)`. aitrader stays `broker=ibkr` (DO NOT change — its live account is
IBKR DU0000000). A pure-Alpaca box sets `broker=alpaca`.

**Data feed** — `settings.data_broker` (optional, e.g. "alpaca") +
`data_broker_types` (default ["stock","crypto"]). `BrokerRouter` routes those
asset types' bars/snapshots/tradeable-list to the data broker; everything else
(account/orders/fills + non-stock/crypto + omitted asset_type) to the execution
broker. With NO data_broker, the execution broker serves data too.

**Backends (aitrader/brokers/):**
- `ibkr.py` — IBKRBroker (execution; pools/lease).
- `alpaca.py` — AlpacaBroker, FULL data + execution (0.13.0 added execution;
  was data-only refuse-stubs in 0.11.0). Used as data_broker on aitrader, or as
  execution on a pure-Alpaca box.
- `myse.py` — MYSEBroker (REST, stocks-only, localhost:7777). 0.13.0 NEW.
- `router.py` — BrokerRouter (the routing seam).
- `sim` backtester NOT ported (the 4th /src/trader backend; parquet-driven,
  off the live path).

**aitrader adaptations vs /src/trader brokers:** accept `client_tag` → Alpaca
`client_order_id`/MYSE body, surfaced as `order_ref` for idempotent reconcile;
signatures match the MCP tool calls (e.g. cancel_order timeout/poll); NO
long-only enforcement (check_no_short dropped — agent owns sizing, CLAUDE.md §2);
options + Alpaca/MYSE bracket raise NotImplementedError (clear, not AttributeError).

**Config:** `settings.broker`/`data_broker`/`data_broker_types`;
`credentials.load_alpaca_credentials`/`load_myse_credentials`; deps `alpaca-py`,
`requests`. The "get_fill_activities stays on IBKR" routing note still holds.

Live-verified 2026-06-17: Alpaca DATA (pre-market AAPL 299.26 vs IBKR 0.0) AND
Alpaca EXECUTION (paper PA000000000000: place limit w/ client_tag → order_ref, then
cancel). Relates to [[gateway-topology]], [[config-no-env-vars]],
[[src-nfs-all-squash-root]].
