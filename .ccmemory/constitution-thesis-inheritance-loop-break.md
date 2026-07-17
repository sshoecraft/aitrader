---
name: constitution-thesis-inheritance-loop-break
description: 1.51.0: atrader full energy tunnel-vision, itrader 4-day theme persistence (verified in both DBs); fix = provenance rule, fixed 2B discovery query +…
metadata:
  type: project
tags: [constitution, tunnel-vision, thesis-inheritance, news, gate, provenance, 1.51.0]
---

# 1.51.0 — thesis-inheritance loop broken (2026-07-17)

## The failure (verified in BOTH nodes' journal DBs — different degrees)
- **atrader (gemma), FULL failure**: 100%-energy book (MPC/VLO/XOM, all
  opened 7/14, held 3 days). Macro news queries pre-shaped by the thesis
  ("energy market news US blockade Iran…") → only confirmation returns.
  Survey surfaced non-energy movers; GATE dismissed them FOR being
  non-energy. Journal/inbox/relay summaries arrive in USER-ROLE messages →
  gemma read them as a human preference: "The user's context (and the news)
  strongly suggests Energy is the driver" (session c15e4b89, 2026-07-17).
  No human asked for energy; the only real input was "begin".
- **itrader (opus), MECHANISM without full capture**: crack-spread thesis
  (MPC/VLO since 7/13, MCL spread since 7/8) carried 4+ days across
  sessions/relays; 30/30 recent journal entries theme-saturated; 3 of 4 open
  positions oil-complex. BUT it took an explicitly-uncorrelated ORCL short
  ("A SECOND, UNCORRELATED BET"), traded AAPL/META/NVDA/QQQ within the week,
  and self-audited ("ON REAL PRINTS MY CRACK ALPHA IS NEGATIVE").
- Reading: the shared context-inheritance design (journal + prospect notes +
  records replayed every wake) is the common cause; model strength sets
  severity — full capture on the 31B, attention bias on opus.
- VERIFICATION LESSON: the original "both nodes identical tunnel vision"
  framing came from the owner's impression; checking itrader's DB showed the
  weaker form. Check both DBs before writing cross-node claims:
  `/home/{a,i}trader/.local/state/aitrader/journal.db` (copy db+wal out,
  query the copy — never touch the live file).

## The fix (constitution 1.51.0, review-hardened via ask_gpt per protocol)
- **Preamble provenance rule**: journal / position records / prospect inbox /
  memory / relay summaries are mechanically replayed SELF-authored notes even
  in user-role messages; never an instruction/preference/theme assignment;
  theme weight in notes = evidence neither for nor against. SCOPED to the
  named record types so a genuine owner instruction typed into tmux still
  binds.
- **2B DISCOVERY**: first search is a FIXED query (`global financial markets
  economy central banks geopolitics news DATE`) — fixed because rule-based
  "thesis-blind" needs fuzzy self-classification (is "commodities" a theme
  word?) and is gameable. Artifacts: exact query · LEADING SUBJECTS (first 3,
  pre-interpretation — anti-cherry-pick) · MACRO line. Blind PROCESS, free
  OUTCOME (theme dominating results is legal). Holdings after; a new-name
  entry needs its search line before the order (entry-gated, NOT
  per-GATE-row — 12+ searches/cycle rejected).
- **GATE 3-kind blocking NUMBER**: candidate-vs-threshold ·
  portfolio-impact-vs-threshold · comparison-vs-incumbent/cash, written as
  value AGAINST level. Reviewer caught that draft-1 (candidate-own-row only)
  would have FORCED rotation by outlawing comparative/portfolio blocks — the
  inverse bias. "Not my theme" = stance = step 4 NOT DONE. Inherited-stance
  VOID extended to THEMES (kept proven VOID wording; review's softening
  addressed a theoretical churn risk).

## Review decisions worth remembering
Adopted: fixed query > rule-based blindness; pre-interpretation artifact;
3-kind NUMBER; de-rhetoricized preamble ("re-wins its place"/"earns nothing"
read as challenge-the-incumbent-every-cycle → churn nudge).
Rejected: per-GATE-row news search; softening VOID.

## Deploy
Owner-run `make const` on both nodes (deploys-are-owner-run). Backup:
`prompts/constitution.md.backup-20260717`. Takes effect at each node's next
session/relay, not mid-session. atrader's prospect p-0001 ("Energy Trend
Review - Blockade") expires naturally 2026-07-17T22:00Z. Version: CHANGELOG +
trading-knowledge.md only (pyproject stays 1.48.0 — prompt-layer changes
don't rev it, matching 1.49/1.50 convention). Side observation: atrader's
positions_of_record still carries AAVE/USD as open (opened 7/11) while the
broker shows only MPC/VLO/XOM — stale record, not corrected here.
