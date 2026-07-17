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

## Local-model tool-calling robustness

The atrader node is served via a local vLLM fork with a CUSTOM native
tool-call format for gemma4 (`vllm/tool_parsers/gemma4_engine_tool_parser.py`
+ `vllm/parser/gemma4.py` in `/src/vllm`) — NOT standard JSON function
calling. Strings are delimited by the literal token `<|"|>`, not `"`. Two
classes of fragility have shown up in production, at two different layers:

- **Docstring quoting (prompt-side, no parser fix possible).** gemma4
  sometimes blends its native `<|"|>` convention with the ordinary-quote
  convention nearly every other tool-calling model uses, producing garbage
  like `{"asset_type": "stock**,by:", "pct_intraday**,direction": "up**,n:3"}`
  (aitrader correctly rejects it before it does anything — the failure is
  loud, not silent). Root cause traced to `rank_instruments`'s own docstring
  showing quoted example literals (`'up'`/`'down'`/`'abs'`,
  `lenses="pct_1d:up,..."`) — the model pattern-matches its own tool's
  documented example directly into the call it constructs. Not one
  well-defined edge case (the malformation shape varies), so it can't be
  patched at the parser level without risking silently executing the WRONG
  call from ambiguous garbage. Fix: MCP tool docstrings avoid quoted-literal
  example values entirely — describe choices in prose ("up or down, or abs;
  no quote marks around any of the three") and use backtick code-spans for
  placeholders instead of quote marks. No behavior change, docstring only.
  Check other tool docstrings for the same pattern before it recurs elsewhere.
- **vLLM parser bugs (patched in the served fork, reapply after any vLLM
  upgrade).** Two distinct, well-defined parser bugs, both fixed by patching
  `vllm/tool_parsers/gemma4_tool_parser.py` directly (needs a vLLM service
  restart to load; patches live at `/home/steve/models/*.patch`, applied from
  `site-packages/vllm/`):
  - **Quote/comma truncation.** `_parse_gemma4_args` only recognized the
    native `<|"|>` delimiter; a value starting with an ordinary `"` fell
    through to the bare-value branch, which reads until the first `,` —
    truncating any quoted string arg containing a comma (a journal `body`
    with a list in it broke this way). Fixed by adding a regular-quote branch
    that reads to the closing unescaped quote, honoring `\"` escapes and
    preserving internal commas/colons. Verified live 2026-06-23.
  - **Trailing backtick on the last string arg.** The parser appends a
    stray trailing backtick to the LAST string argument of a tool call —
    positional to the model's emitted arg order, not the function signature.
    Wedged the agent in an unbreakable retry loop (`get_snapshots` with a
    `BNB/USD\`` symbol the model could see was wrong but could not stop
    producing — the backtick is added downstream of the model, it never
    "wrote" it). Root fix belongs in the vLLM parser (not yet done — the
    model server is a separate venv/host from aitrader); in-repo defense is
    `aitrader/asset_types.py:clean_symbol()`, which strips backticks/quotes/
    whitespace from every symbol arg across both MCP servers (a backtick is
    never valid in a symbol, so stripping it is pure lenience). Scope: this
    only covers symbol/asset_type args — the parser still corrupts the last
    arg of OTHER calls (journal body/tags, order intent, client_tag) until the
    root fix lands.

## Model selection notes

The atrader node compared two local models on the SAME constitution + clean
memory, in the live agentic trading loop (not single-turn benchmarks):

- **Qwen3.6-35B-A3B** (35B total, only ~3B active per token — MoE) aced
  single-turn benchmarks (96% finance MMLU, risk-neutral on a risk-persona
  test) but failed the live loop: clung to an inherited losing position for
  multiple cycles, refused to use available buying power ("cash too thin"),
  skipped momentum scans, and only did the right thing when explicitly
  badgered — reactive, not proactive. Consistent with the few-active-param MoE
  weakness on cross-turn / multi-step instruction-following.
- **gemma-4-31B-it-INT8** (dense, full 31B active) cut a losing position and
  redeployed on its FIRST clean cycle under the identical constitution. Dense
  (full active params) outperformed the few-active MoE for this multi-step
  agentic judgment task, despite losing the single-turn benchmark comparison.

**Serving flags that work** (vLLM, for Claude Code via this shim):
- `--tool-call-parser gemma4 --reasoning-parser gemma4` (gemma4 is correct
  for this model family; hermes/pythonic tool-call parsers were tried and are
  wrong).
- `--chat-template tool_chat_template_gemma4.jinja` (from the vLLM repo,
  pinned to the build commit).
- **INT8 quant is required for full context** — `lokeshe09/gemma-4-31B-it-INT8`
  fits the full 262144-token context on the serving box; full precision only
  fits ~155k, too small for Claude Code's context needs.
