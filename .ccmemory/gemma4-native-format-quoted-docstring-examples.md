---
name: gemma4-native-format-quoted-docstring-examples
description: 1.49.2: gemma4's native tool-call format uses <|"|> delimiters, not JSON quotes; tool docstrings showing quoted example literals ('up', lenses="...")…
metadata:
  type: project
tags: [gemma4, vllm, tool-parser, rank-instruments, docstring, 1.49.2, atrader]
---

# gemma4 native tool-call format vs quoted docstring examples (1.49.2, 2026-07-13)

## The symptom
atrader's log showed `rank_instruments` calls arriving corrupted:
`{"asset_type": "stock**,by:", "pct_intraday**,direction": "up**,n:3"}` →
correctly rejected (`'stock**,by:' is not a valid AssetType`) — aitrader was
never fooled, the call was garbage before it ever reached broker_server.py.

## Root cause, confirmed not guessed
This model is served via a LOCAL vLLM fork with a CUSTOM native tool-call
format for gemma4 (`vllm/tool_parsers/gemma4_engine_tool_parser.py` +
`vllm/parser/gemma4.py` in `/src/vllm`) — NOT standard JSON function
calling. Format: `<|tool_call>call:func{key:<|"|>value<|"|>,num:42}<tool_call|>`
— strings are delimited by the literal 5-char token `<|"|>`, not `"`.

No raw request/response logging exists (`journalctl` on the
`gemma-4-31B-it-INT8.service` unit: zero entries across a 7-hour window —
default vLLM logging doesn't capture completion content), so the exact raw
text couldn't be pulled directly. Instead: copied `_parse_gemma4_args` out
of `vllm/parser/gemma4.py` into a standalone script (avoids importing the
full `vllm` package, which needs a CUDA/torch build not present outside the
model server) and tested candidate raw strings against the REAL parser
logic until one reproduced the garbage character-for-character:
`asset_type:<|"|>stock**,by:<|"|>pct_intraday**,direction:<|"|>up**,n:3<|"|>`
— confirmed exact match, not a plausible-sounding guess.

Two occurrences, two different malformation shapes (one merged 2 args
behind one `**,` boundary; the other swallowed the ENTIRE rest of the call
into one string using ordinary `"..."` quotes for a nested piece) — not one
fixed bug, the model intermittently blends the native `<|"|>` convention
with the ordinary-quote convention nearly every other tool-calling model
uses. The model's own transcript self-diagnosed it: "I included the `**` in
the argument keys because I was trying to emphasize them."

**The connecting thread across both failures:** `rank_instruments`'s own
docstring shows example values in ordinary quotes — `'up'`/`'down'`/`'abs'`,
`'stock'|'crypto'|...`, and (added this session) `lenses="pct_1d:up,..."`.
Both failing calls involved arguments whose docstring example uses this
quoting convention. A model pattern-matching its own tool's documented
example directly into the call it constructs would produce exactly this.

## Why NOT patched at the parser/tool-call level
Unlike two PRIOR gemma4 parser fixes in this same file
([[vllm-gemma4-quotefix-patch]], [[vllm-gemma-trailing-backtick-lastarg]]),
this isn't one well-defined edge case — the malformation shape varies. Any
attempt to "repair" the corrupted JSON after the fact means guessing intent
from ambiguous garbage, risking silently executing the WRONG call instead
of the current safe, loud rejection. Also: self-recovering — both observed
cases got a clean, valid retry within 5-10 seconds (a token/latency cost,
not a blocking or correctness issue), so the urgency is low and the fix
should stay low-risk.

## Fix (`rank_instruments` docstring, `broker_server.py` 0.10.1→0.10.2)
Removed every quoted-literal example value: `'up' | 'down' | 'abs'` →
"up or down ... or abs (no quote marks around any of the three)";
`'stock'|'crypto'|...` → "stock, crypto, forex, or futures"; the
`lenses="pct_1d:up,..."` example → described in prose ("four entries:
pct_1d up, pct_1d down, day_notional up, rel_vol up") with an explicit
"No quote characters belong inside an entry itself." Placeholders use
backtick code-spans (`` `<by>` ``) instead of quote marks. No behavior
change, docstring only — verified module still imports and the existing
regression suite passes unchanged.

## Explicitly NOT touched (out of scope, shared infra)
The vLLM chat template / gemma4 tool parser itself — confirmed the running
`gemma-4-31B-it-INT8.service` has no `--chat-template` override (uses
whatever ships in the `lokeshe09/gemma-4-31B-it-INT8` HF snapshot), and
that bundled template is functionally identical (one trivial Jinja
`default()` filter syntax diff) to the standalone
`~/models/tool_chat_template_gemma4.jinja` copy — so it doesn't matter
which file is technically "in use." Two OTHER scripts in `~/models/`
(`vllm.sh`, `vllm-gemma-4-26B.sh`) were briefly and wrongly investigated
before realizing neither is what starts the actual running service (one's
for a different 26B model, the other's a generic scratch launcher
currently configured for an unrelated model) — dead end, noted so a future
session doesn't repeat it.

## If this recurs
Enable vLLM request-level debug logging BEFORE the next occurrence (no
retroactive log exists) to get the exact raw text instead of reconstructing
it. Consider whether other MCP tool docstrings anywhere in this project
have the same quoted-example pattern (this pass only covered
`rank_instruments`, the tool actually observed failing).
