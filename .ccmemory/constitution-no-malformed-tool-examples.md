---
name: constitution-no-malformed-tool-examples
description: NEVER put malformed/negative ('WRONG') tool-call examples in the constitution — weak/local models template off the LAST example and copy the bad form…
metadata:
  type: feedback
---

## What happened (2026-06-23)
The live agent on a local model (gemma-4-31B-it-INT8) mangled EVERY tool call — `journal_write(kind="\"note\"")`, `symbol="\"BTC/USD\""` — wrapping every string arg in literal escaped quotes, breaking journal writes and (would have) broker orders.

I wasted time blaming the vLLM tool-call parser (tried hermes ❌, pythonic ❌, gemma4+official chat template ❌ — all still mangled). **The user diagnosed the real cause:** the constitution's "Tool Call Mechanics" section *ended* with a `**WRONG**` block whose last lines were `side="\"sell\""` and a quote-crammed `client_tag`. A weak model **templates off the LAST concrete example it saw** and reproduced that exact escaped-quote form. Negation ("never do this") does not work on weak models — showing the malformed form teaches it.

## The rule
- In prompts, show **clean examples only** — never "good vs bad" / CORRECT vs WRONG, never the malformed form, even labeled as wrong.
- The **last** concrete example in a section is the template the model copies — make it the correct one.
- State formatting rules positively ("each value is bare: side is sell") without printing the quoted token.

## The fix (worked immediately)
Rewrote `prompts/constitution.md` Tool Call Mechanics: removed CORRECT/WRONG framing + all quoted/escaped examples; ended on one clean bare-value example. Next gemma cycle wrote `kind='thesis'`, `symbol='BTC/USD'` — bare. Parser/template were NOT the cause.

This applies to any model; the WRONG examples were originally added for Qwen and were likely counterproductive there too. Related: [[local-model-gemma31b-dense-validated]], [[constitution-stops-and-tool-mechanics]].
