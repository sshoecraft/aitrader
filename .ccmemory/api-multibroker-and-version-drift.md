---
name: api-multibroker-and-version-drift
description: aitrader 0.15.0: dashboard api.py broker() now honors settings.broker (was IBKR-hardwired, broke Alpaca/gtrader node); Broker.list_all_open_orders AB…
metadata:
  type: project
---

The dashboard API (`aitrader/api.py`) lagged the MCP `broker_server` on the
broker-selection model and broke on any non-IBKR node.

**Symptom (gtrader/clyde, `broker = "alpaca"`):** `aitrader-api` on its port
(that node uses 7800) returned `/health {"connected":false}` then, once connected,
`/status` 500'd. Root cause was NOT config — `settings.toml` was correct.

**Three bugs fixed in 0.15.0:**
1. `api.py` `broker()` hardwired `IBKRBroker(client_id=80)`, ignoring
   `settings.broker`. On an Alpaca node it threw `ibkr_port not found in
   secrets.toml`. Fixed: `broker()` now selects ibkr|alpaca|myse (mirrors
   `mcp/broker_server.build_execution_broker`) and wraps it in a `BrokerRouter`
   with the optional `data_broker` (inlined `build_data_broker` to keep FastMCP
   out of the API process). IBKR still pins client_id 80 + tiny pools; data-broker
   failure degrades to execution-broker-for-data. See [[data-execution-broker-split]].
2. `compute_status()` calls `b.list_all_open_orders()`, which existed ONLY on
   `IBKRBroker` (`reqAllOpenOrders` — needed because each IBKR clientId sees only
   its own orders, and the API connects as a different id than the agent). Added a
   concrete default on the `Broker` ABC (`aitrader/broker.py`) =
   `get_orders(status="open")`, correct for shared-account brokers (Alpaca/MYSE);
   IBKR keeps its cross-client override. When adding API features, check every
   `b.<method>()` exists on ALL backends, not just IBKR.
3. **Version drift trap:** `aitrader/__init__.__version__` was stuck at `0.10.1`
   while `pyproject.toml` had advanced to `0.14.0`. Prior bumps touched only
   pyproject. `/health` and `/status` report `aitrader.__version__` (the
   `__init__` string), so the running dashboard mislabeled itself even though the
   wheel METADATA said 0.14.0. When chasing "is the deployed code current?", trust
   `grep __version__ <site-packages>/aitrader/__init__.py`, NOT `importlib.metadata`
   /pip — they can disagree. (`asset_types.py` also carries its own `__version__`,
   also drifted at 0.10.1 — left as-is, it's a separate module marker.) Synced
   `__init__` + pyproject to 0.15.0; `api.py` module to 0.4.0.

`get_classification` is also IBKR-only but already guarded by try/except in
`enrich_positions_with_classification`, so it degrades to null sector/industry on
Alpaca — no crash. Deploy via the [[api-service-deploy-path]] path (make build &&
make install && `systemctl --user restart aitrader-api`). Verified live vs Alpaca
paper PA000000000000.
</body>
