---
name: rank-instruments-tool
description: 1.38.0: rank_instruments — agent-parameterized mechanical ranker over the snapshot CSV (any column, up/down/abs, floors, fresh_only, exclude_held def…
metadata:
  type: project
tags: [rank-instruments, survey, tools, 1.38.0, gemma, shorts]
---

# rank_instruments (1.38.0) — mechanical ranking at agent-chosen parameters

## Why it exists
gemma's sandbox ranking step failed CONTINUOUSLY (watched live): its parser
mangles long quoted `python3 -c` strings — unterminated f-strings, malformed
tool-call JSON, bash EOF — so "rank the CSV yourself" collapsed exactly where
the weak model needed it. A tool call with short scalar args is immune. Owner
directed the tool + defaults (n=20, exclude_held=True: "the model doesn't have
to spend tokens filtering positions").

## §2/§8 boundary (why this is NOT the 1.34.0 shortlist trap)
Infra sorts OUR whole-tape CSV by a RAW FACT at parameters the AGENT chooses
per call — no house defaults doing silent work beyond n/exclude_held, no
pre-picked list (no call → no list), CSV stays for compound cuts. §8 blesses
rank_gainers-style fact-ranking as data. The old junk vendor tool was named
get_top_movers — deliberately NOT reused: (a) agents' memories reference that
name as removed garbage; (b) "top movers" preaches chasing completed moves
(owner: "doesn't top movers imply the move already happened?").

## The lens menu (all raw facts; agent picks per call via `by`)
- pct_1d — completed 1-day move (includes gap) — the chase/fade lens
- pct_intraday — today ex-gap (SPLIT-IMMUNE — kills INHD +3559% artifacts)
- gap_pct — overnight repricing alone
- rel_vol — unusual participation (meaningful now on consolidated volume) —
  the PRE-move lens: first live pull ranked IQMM rel_vol 28x with price FLAT
- range_pos — 0=day low..1=day high (0.9+ = pressing highs)
- direction=down — losers/shorts are first-class (models had NEVER evaluated
  the short side)
Verified live vs consolidated tape incl. held-exclusion (NVDA dropped) and
inline JSON-number rows ({count, csv_age_seconds, filters, movers}).
Core = plain fn rank_snapshot_csv (testable without MCP).
Related: [[survey-feed-delayed-sip]], [[mcp-list-results-render-per-element]],
[[constitution-minimal-experiment]], [[deploys-are-owner-run]].
