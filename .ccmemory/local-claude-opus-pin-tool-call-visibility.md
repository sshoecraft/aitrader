---
name: local-claude-opus-pin-tool-call-visibility
description: extras/local_claude: pin served model to ANTHROPIC_DEFAULT_OPUS_MODEL + _SUPPORTED_CAPABILITIES instead of bare ANTHROPIC_MODEL — fixes TUI swallowin…
metadata:
  type: project
tags: [local-claude, clyde, vllm, tui, claude-code-config, supported-capabilities]
---

## The problem
Running Claude Code against a local vLLM server (`extras/local_claude`, same
pattern as `/usr/local/bin/clyde`) via `ANTHROPIC_BASE_URL` + a bare
`ANTHROPIC_MODEL=<served model id>` (e.g. `lokeshe09/gemma-4-31B-it-INT8`)
left the TUI showing only a single collapsed line per turn —
`Thought for 8m 12s, called ccmemory, broker, journal, scheduler 50 times
(ctrl+o to expand)` — with NO visible final answer text, unlike a native
Opus session where each tool call renders live and the answer prints
normally. Only `ctrl+o` revealed anything.

## Root cause (confirmed via code.claude.com/docs/en/model-config)
Claude Code enables features (`thinking`, `interleaved_thinking` = "thinking
between tool calls", `effort` levels) by pattern-matching the model ID
against known Claude signatures (`claude-` prefix etc). A raw vLLM model ID
matches nothing, so Claude Code can't tell the backend supports interleaving
reasoning with tool calls — it assumes not, so the whole turn (thinking + all
tool calls + answer) gets resolved and returned as one lump and rendered only
as history's collapsed digest.

The `_SUPPORTED_CAPABILITIES` override that fixes this **only takes effect on
the pinned-model slots** — `ANTHROPIC_DEFAULT_OPUS_MODEL` /
`_SONNET_MODEL` / `_HAIKU_MODEL` / `_FABLE_MODEL`, or `ANTHROPIC_CUSTOM_MODEL_OPTION`
— NOT on a bare `ANTHROPIC_MODEL` string. That's why the naive wrapper (which
sets `ANTHROPIC_MODEL` directly) can never declare capabilities no matter what
else is tried.

## The fix (extras/local_claude, 2026-07-11, VERIFIED working live)
- Commented out (not deleted — one-line revert) `env["ANTHROPIC_MODEL"] = model_id`.
- Added:
  ```
  env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = model_id
  env["ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES"] = (
      "effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"
  )
  ```
- Added `"--model", "opus"` to the `claude` invocation's `cmd` list so it
  resolves through that pinned slot explicitly, independent of whatever
  `settings.json`'s `model` field happens to be.
- Left `ANTHROPIC_SMALL_FAST_MODEL` / `CLAUDE_CODE_SUBAGENT_MODEL` untouched
  (unrelated to this capability path).

Verified live 2026-07-11: tool-call turns now show the normal collapsed
thinking/tool-count line (same as native Opus — thinking is *always*
collapsed by default, `ctrl+o` toggles it) but the actual response text now
renders below it, instead of the entire turn vanishing into just that one
summary line.

## Scope / not yet done
Only `extras/local_claude` (repo source) was changed —
**`/usr/local/bin/clyde` (the currently-active `CCLOOP_CLAUDE_BIN`) was
deliberately left untouched** per explicit instruction. This fix is not live
on atrader until the owner deploys `extras/local_claude` to
`/usr/local/bin/local_claude` and repoints `~/.config/environment.d/ccloop.conf`'s
`CCLOOP_CLAUDE_BIN` at it (deploys are owner-run, see [[deploys-are-owner-run]]).
Related: [[local-model-gemma31b-dense-validated]], [[runtime-no-headless-p-tmux]].
