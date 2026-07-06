---
name: vllm-gemma-trailing-backtick-lastarg
description: Local vLLM gemma parser appends a trailing backtick to the LAST tool-call string arg; wedges agent (BNB/USD` reject loop). In-repo defense = asset_ty…
metadata:
  type: project
tags: [vllm, gemma, tool-parser, broker_mcp, journal_mcp, symbols]
---

# vLLM gemma tool-parser: trailing backtick on the LAST string arg (2026-07-04)

## Symptom (observed live)
The atrader agent wedged in an unbreakable loop calling `get_snapshots` with `…,BNB/USD\`` — a trailing backtick on the last symbol. Alpaca's `^[A-Z]+x?/[A-Z]+$` validator rejects it; the model retried the IDENTICAL call ~12×, reasoning "I keep typing a backtick… I'm not adding it in my thought, but it's appearing in the tool call." It literally cannot fix it — the backtick is added DOWNSTREAM of the model.

## Root cause
The local vLLM gemma tool-parser (`vllm/tool_parsers/gemma4_tool_parser.py`, same family as [[vllm-gemma4-quotefix-patch]]) appends a trailing backtick to the **LAST string argument** of a tool call. It's positional to the model's emitted arg ORDER, not the function signature — whatever key the model emits last gets the backtick. Same corruption stored position/journal symbols as `XRP/USD\`` this session, and would silently make `transactions_read(symbol='X\`')` match ZERO rows (re-breaking the 1.32.1 HISTORY table via a corrupted filter, not a fabricated line).

## Fixes
- **Root (NOT done here):** patch the vLLM parser to strip/handle the trailing backtick, like the quotefix. BUT the model server is steve's separate venv/host — `vllm` isn't in the atrader env and the parser file wasn't reachable/writable from this session. This is steve's infra call. The quotefix precedent: `/home/steve/models/gemma4-quotefix.patch`, applied from `site-packages/vllm/`, needs a vLLM restart (~4min) + aitrader restart.
- **In-repo defense (1.32.2, DONE + deployed):** `aitrader/asset_types.py:clean_symbol(s)` strips backticks/quotes/whitespace (a backtick is never valid in a symbol → pure lenience per [[mcp-tools-tolerate-comma-strings]]). Applied to EVERY symbol arg in broker_server (get_snapshot(s)/get_bars/place_*/close_position/get_open_orders_for_symbol/get_historical_executions/options) and journal_server (transactions_read/journal_read+write/position_record_*/order_record(_list)). `parse_asset_type` also cleans its input (so `crypto\`` doesn't crash the enum). Verified: `clean_symbol('BNB/USD\`')=='BNB/USD'`, `parse_asset_type('crypto\`')==CRYPTO`.

## Caveat / scope
The in-repo fix only covers SYMBOL and asset_type args. The parser still corrupts the last arg of OTHER calls (journal body/tags, order intent, client_tag). Symbols were the highest-value (keys/filters/order-routing); prose bodies are cosmetic. Full coverage needs the vLLM root fix. If order/journal corruption resurfaces on a non-symbol field, that's why. See [[transactions-ledger-surface-not-gate]] (the HISTORY table this protects), [[journal-malformed-toolcall-kind-corruption]].
