---
name: mcp-list-results-render-per-element
description: MCP SDK renders a list return as one content block PER ELEMENT — a 1-element get_positions arrived as a bare object (gemma rightly confused). 1.37.1:…
metadata:
  type: project
tags: [mcp, serialization, tool-shape, 1.37.1, gemma, data-quality]
---

# MCP list returns render per-element — never return a bare list from a tool

## The finding (owner caught it live, 2026-07-10)
gemma's transcript showed it puzzling over `get_positions` returning "a single
object, not a list" when only NVDA was held. It was RIGHT: the MCP SDK
(fastmcp `_convert_to_content`) renders a Python list as ONE content block PER
ELEMENT:
    if isinstance(result, list | tuple):
        return list(chain.from_iterable(_convert_to_content(i) for i in result))
So 3 positions arrive as 3 loose JSON objects and 1 position arrives as a BARE
OBJECT — the model never sees array brackets and cannot distinguish
"one row" from "wrong shape". Same defect on every list-returning tool.

## Fix (1.37.1)
All 14 list-returning MCP tools (8 broker: positions/orders/open-orders-for-
symbol/balances/fills/executions/assets/flatten-results; 6 journal:
entries×2/por-records/equity-snapshots/order-records/transactions) now return
a self-describing dict: `{count, <plural-key>: [...]}` — one content block
always, identical shape at 0/1/many, `count==0` is the only "no rows" form
(transactions_read docstring says so explicitly — HISTORY depends on it).

## Rule going forward
An MCP tool NEVER returns a bare list. New collection-shaped tools return
{count, key: [...]}. (get_all_snapshots already returns a dict of results.)
Verified: broker methods / journal lib callers (api.py) bypass the MCP
wrappers and are unaffected. Related: [[crypto-volume-venue-only]],
[[mcp-tools-tolerate-comma-strings]].
