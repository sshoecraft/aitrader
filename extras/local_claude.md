# local_claude — run Claude Code against a local OpenAI-compatible vLLM server

Install (interactive + ccloop use the same shim):

    sudo cp extras/local_claude /usr/local/bin/clyde
    mkdir -p ~/.config/environment.d
    echo 'CCLOOP_CLAUDE_BIN=/usr/local/bin/clyde' > ~/.config/environment.d/ccloop.conf

## Why the served model is pinned into the "opus" slot

A bare `ANTHROPIC_MODEL=<served-id>` is an unrecognized id to Claude Code, so it
cannot tell the model supports thinking/interleaved thinking — the whole turn
(reasoning + every tool call) resolves server-side and renders only as a
collapsed post-hoc "Thought for Xm Ys, called ... N times" digest. The shim
instead sets `ANTHROPIC_DEFAULT_OPUS_MODEL=<served-id>` plus
`ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES=effort,xhigh_effort,
max_effort,thinking,adaptive_thinking,interleaved_thinking` and launches with
`--model opus`, so capabilities are declared and tool calls stream live. Do NOT
"fix" rendering by removing `interleaved_thinking` from that string — it
reverts to the far worse post-hoc digest.

## What the tmux attach shows under ccloop (and why it differs from interactive)

A constitution cycle is ONE long interleaved turn — thinking → ~25 tool calls →
journal → a blocking wait — with no user-facing text, so the TUI groups it into
a single live-updating line: `Thinking for Xm, calling ... N times… (ctrl+o to
expand)` (a `⎿ NN%` sub-line is a wait's progress heartbeat). The steps are all
there, collapsed. Interactive sessions look step-by-step because their turns
are short, not because ccloop breaks rendering. Also note ccloop passes
`--effort max` (from `CCLOOP_EFFORT`); the shim itself leaves effort at the
default for interactive use.

- Live toggle: `ctrl+o` in the attached tmux expands/collapses — the
  on-demand lens.
- Default-expanded was TRIED and REVERTED (`"verbose": true` in the run dir's
  `.claude/settings.json`, seeded 1.41.3, removed 1.42.4): it is just the
  ctrl+o dump made permanent — full thinking walls between tool lines — and
  reads worse than the collapsed digest. Don't re-add it. The grouping itself
  is stream-shape behavior (text blocks segment the display; the local agent
  emits none mid-cycle), not something a display default can fix.
