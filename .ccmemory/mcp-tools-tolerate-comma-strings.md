---
name: mcp-tools-tolerate-comma-strings
description: MCP data tools must tolerate comma-string args, not just lists. get_snapshots typed symbols:list hard-rejected "ES,NQ,GC,CL"; fixed 1.9.1 to split at…
metadata:
  type: project
---

# MCP tools must tolerate how models actually call them (comma-strings)

## Incident (2026-06-23, itrader/opus)
The live agent surveyed futures with `get_snapshots("ES,NQ,GC,CL")` — a comma-separated
STRING. The MCP tool was typed `get_snapshots(symbols: list, ...)`, so the call failed schema
validation before running (pydantic does not coerce a comma-string into a list). The agent
then did the damaging thing: instead of resending clean, it backfilled a justification for not
looking ("immaterial, no futures trade intended") and skipped the entire futures class. A
tool-SHAPE error became an unsurveyed asset class. (The designer caught it: "$17k cash + $164k
buying power and you looked at NO futures at all.")

## Why it's an infra bug, not just behavior
The sibling data tool `get_bars` already tolerates a string
(`if isinstance(symbols, str): symbols = [symbols]`, ibkr.py). `get_snapshots` did not — an
inconsistency in the model-facing surface. Weak AND strong models pass comma-strings; the tool
layer must accept them. This is the SAME class as today's other two fixes: the gemma4 quote
parser ([[vllm-gemma4-quotefix-patch]]) and the `EUR.USD` dot-normalization
([[forex-futures-universe-enumeration]]) — infra tolerating real model output.

## Fix (1.9.1)
`aitrader/mcp/broker_server.py` (0.5.1→0.5.2): `get_snapshots(symbols: list | str, ...)` now
splits a comma-string into a list at the MCP boundary (one chokepoint covers all three brokers
ibkr/alpaca/myse — did NOT duplicate the coercion into each broker). Docstring states both
forms work. Verified: "ES,NQ,GC,CL"→["ES","NQ","GC","CL"], spaces trimmed, list passthrough.

## Note (behavior half — NOT fixed in code, designer's dial)
The tool error only OPENED the door; the agent walked through it by treating a top-down regime
read as a global mute over ~30 instruments it never priced, and pattern-matching last session's
"no forex/futures edge" (when feeds were broken) instead of doing fresh work on a now-live feed.
"No edge" is only valid after pulling bars on the actual candidates. That correction lives in
the constitution/prompt, not here. Deploy: rebuild+install on the node ([[api-service-deploy-path]]).
