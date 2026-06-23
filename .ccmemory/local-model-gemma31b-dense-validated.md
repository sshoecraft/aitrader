---
name: local-model-gemma31b-dense-validated
description: atrader local model: Qwen3.6-35B-A3B (3B active) clung to losers / wouldn't use margin; gemma-4-31B-it-INT8 (dense, 31B active) on the same constitut…
metadata:
  type: project
---

## Finding (2026-06-23)
The atrader node runs a LOCAL model via vLLM (`:8000`, picked up by the `clyde` wrapper / `CCLOOP_CLAUDE_BIN`). itrader runs **opus** (Anthropic backend), not local.

**Qwen3.6-35B-A3B** (35B total, **only 3B active** per token) aced single-turn benchmarks (96% finance MMLU, risk-neutral on the risk-persona test) but FAILED the live agentic loop: clung to an inherited losing BTC position for multiple cycles, refused to use ~$34K of buying power ("cash too thin"), skipped momentum scans. It would do the right thing only when the user explicitly badgered it — reactive, not proactive. This is the few-active-param MoE weakness (cross-turn / multi-step instruction-following), corroborated by vLLM/community reports.

**gemma-4-31B-it-INT8** (DENSE, 31B active) on the **same constitution + clean memory**, first clean cycle: cut the BTC knife (regime-aware, to kill margin debt) and redeployed into defensive momentum. Dense (full active params) >> few-active MoE for multi-step agentic judgment + instruction-following.

## Serving config that works (gemma-4 on vLLM, for Claude Code)
- INT8 quant (`lokeshe09/gemma-4-31B-it-INT8`) is REQUIRED for the full 262144 ctx — full precision only fits ~155k on the 4×24GB box (too small for Claude Code).
- `--tool-call-parser gemma4 --reasoning-parser gemma4` (gemma4 IS correct; hermes/pythonic are wrong) + **`--chat-template tool_chat_template_gemma4.jinja`** (from the vLLM repo, pinned to the build commit).
- BUT the quote-mangling was NOT the parser/template — it was the constitution's malformed tool examples. See [[constitution-no-malformed-tool-examples]].

Related: [[seeded-trader-wisdom-architecture]], [[agent-must-be-guided-not-unguided]], [[runtime-no-headless-p-tmux]].
