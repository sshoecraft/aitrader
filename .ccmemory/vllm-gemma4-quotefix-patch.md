---
name: vllm-gemma4-quotefix-patch
description: Local vLLM patch: gemma4 tool parser truncated quoted string args at first comma. Added regular-quote branch. VERIFIED LIVE 2026-06-23 post-restart.
metadata:
  type: project
---

# gemma4 tool-parser quote/comma truncation (fixed 2026-06-23)

The atrader local-model node runs gemma-4-31B-it-INT8 on vLLM (0.22.1rc1.dev466). Its
journal/broker tool calls were mangled: a value like
`body:"End of day. Holding GIS, MRK, PM..."` parsed as `body='"End of day. Holding GIS'`
(truncated at the FIRST comma) with the rest becoming garbage keys, and `kind:"reconcile"`
stored as `'"reconcile"'` (quotes kept).

**Root cause:** the model wraps string args in regular/escaped quotes (`"..."`), but
vLLM's `vllm/tool_parsers/gemma4_tool_parser.py:_parse_gemma4_args` only recognized
Gemma's `<|"|>` delimiter — a value starting with `"` fell through to the BARE-value branch,
which reads until the first `,`. So any quoted value containing a comma was chopped.
(This is distinct from the constitution's malformed-examples bug, which was the model's
arg *quoting*; the parser bug is why even a single quoted+comma value broke.)

**Fix:** added a `elif args_str[i] == '"':` branch (and the same in `_parse_gemma4_array`)
that reads a regular double-quoted string to the closing unescaped quote, honoring `\"`
escapes and preserving internal commas/colons. Verified with a standalone repro
(`scratchpad/gemma4_parse_repro.py`): the full body now parses, `kind` is clean, and the
`<|"|>`/bare-value cases are unchanged. Backups: `<file>.bak` beside each parser.

**VERIFIED LIVE 2026-06-23 (post-restart):** restarted gemma-4-31B.service (patch loads
only on restart; running PID predated the patch file) → /health 200 after ~235s, model
`lokeshe09/gemma-4-31B-it-INT8` re-served → restarted atrader aitrader.service. First
post-restart journal write (row 44, ts 20:43 UTC) stored CLEAN: `kind=note` bare,
`symbol=PORTFOLIO` bare, body "...stop-limit orders for BTI, CL, and GIS... BTI stop at 55,
CL at 82, GIS at 31." — full commas intact, NOT truncated, no quotes/garbage keys. The
pre-restart rows (19:xx UTC) still show the old mangling (`kind="reconcile"` truncated;
`kind=thesis**, symbol:"BTI, CL"`), confirming the boundary is exactly the restart. Mangle
scan of all post-restart rows = empty. Agent also ran 25 tool calls (ccmemory/broker/
scheduler/searxng/journal) in cycle 1 with NO memory_list wedge, and is holding margin
(cash −$7,625 on $63,840 equity, 6 defensive-rotation equities) — not sitting on cash.

**Reapply after any vLLM upgrade/reinstall:** `patch -p0 < /home/steve/models/gemma4-quotefix.patch`
from `site-packages/vllm/` (alongside re-applying the DiffusionGemma TP patch — see that note).
Needs a vLLM restart to load. Related: [[local-model-gemma31b-dense-validated]], [[constitution-no-malformed-tool-examples]], [[diffusiongemma-vllm-nightly-tp-patch]].
