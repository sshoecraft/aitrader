---
name: weekend-carry-friday-ab-evidence
description: Fri 7/10 close A/B: opus priced the weekend gap unprompted (trim + sized hold); gemma zero weekend mentions; owner flattened both manually → orphaned…
metadata:
  type: project
tags: [weekend, gap-risk, experiment, spine, test-week, gemma, opus, external-flatten, orphaned-stop]
---

# Friday-close weekend-carry A/B evidence (2026-07-10, first test-week Friday)

Live observation at the 7/10 close, both instances long the SAME name (NVDA)
— the one-bet-book pattern from [[constitution-minimal-experiment]] compounding
into a weekend: the two-model A/B had zero diversification across the gap.

## itrader (opus, IBKR) — the 1.28.0 doctrine executed unprompted
- 15:01 ET (journal id345): "weekend concentration decision pending" — framed
  the decision an hour before the close, 90.3% of equity in NVDA (200 sh).
- 15:33 ET (id346): SOLD 100 of 200 @ 209.83, tagged `weekend-derisk`, gap
  math written ("the 207 stop cannot protect a Monday gap (-5% = -$2.1k =
  -4.5% equity, unhedgeable)"). Reduced stop qty FIRST to avoid the IBKR
  share-reservation reject, then sold. Kept a deliberate 45% core.
- 15:54 ET (EOD MANAGE): final check — "WEEKEND RISK (deliberate, sized):
  45% NVDA over a 2.5-day gap… -5% Monday gap = -$1.05k = -2.3% equity =
  ordinary drawdown. Unlevered, $25k cash → no liquidation risk." Planned
  ≤28-min weekend watch-chain. This is [[crypto-hard-lessons-provenance]]
  1.28.0 (weekend = priced condition + stay on watch) done natively — the
  minimal+spine constitution contains none of it; opus brought it.

## atrader (gemma-4-31B local, Alpaca) — calendar invisible
- 29 journal entries on 7/10; ZERO occurrences of weekend/Monday/gap. Last
  pre-close wake 15:07 ET set a 1-hour leash → next wake AFTER the close.
  Carried 150 NVDA (51% of equity, stop 206 GTC) with the weekend never
  appearing in any artifact. Not "decided to hold" — never saw the decision.
- Silent-failure #4 of the minimal constitution (with hesitation tax, one-bet
  books, margin ignored): calendar is invisible to the local model unless a
  step forces an artifact ([[constitution-steps-not-prose]]).

## OUTCOME — owner overrode: manual flatten of BOTH books ~15:57-15:59 ET
Owner judged any one-name weekend carry unacceptable and flattened both
before the close. Findings:
1. **Dashboard /sell 500s while a stop reserves the shares** (Alpaca): had to
   cancel atrader's stop via /cancel first; sell landed after. Alpaca cancel
   is async — an immediate retry can still hit the reservation. atrader's
   16:08 ET cycle reconciled the external flatten cleanly (journaled flat,
   0% exposure, no orders).
2. **ORPHANED-STOP HAZARD (IBKR): external flatten leaves the agent's GTC
   stop working with no position** — itrader was flattened via dashboard
   (IBKR accepts a market sell alongside a resting stop, unlike Alpaca);
   stop id372 (sell 100 NVDA @ 207 GTC) stayed `presubmitted` on a flat
   book = a naked short-entry order aimed at the weekend. The dashboard
   CANNOT cancel it: IBKR only accepts a cancel from the placing clientId
   (agent=40; API=80/90/100; Error 10147 semantics — ibkr.py cancel_order
   scatter no-ops by design). RESOLVED 16:30 ET via the agent connection
   (~30 min exposed, post-close so no trigger risk). This is the deleted
   [[shared-alpaca-account-external-flatten-risk]] lesson recurring on
   IBKR — external intervention MUST also clear the agent's working orders,
   stop-first, and only the agent (or gateway) can do the IBKR cancel.
3. Owner's real policy surfaced: **no weekend equity carry** (or a much
   tighter cap than 45%) — an appetite that exists nowhere in the
   constitution, so the agent's sized carry was compliant behavior. If the
   policy is durable it must be encoded as a step artifact (CARRY line or
   explicit weekend-flat rule). Note: that is NOT the disproven 1.28.0
   crypto veto — that evidence was 24/7-exitable crypto; equities are locked
   ~65h and unhedgeable on the Alpaca node. Distinct asset mechanics,
   distinct rule.

## For the owner's review
- Grade: weekend decision seen (opus yes / gemma no); owner override says the
  appetite question is OPEN — decide flat-vs-cap and encode it.
- Check itrader's 16:22+ ET journal: did opus reconcile the external flatten
  and cancel 372 on its own, or did the owner instruct it? (Self-heal =
  reconcile design validated; instructed = add orphan-order check to review.)
- Fix shape if amending: lettered sub-step, surface-not-gate or a hard owner
  rule — e.g. last cycle before any close→multi-day window, per position
  `CARRY: <sym> <gap % → $ → % equity> → hold/trim/exit + number` (or "exit
  all us_equity by 15:45 ET Friday" if owner mandates flat). Owner deploys
  ([[deploys-are-owner-run]]).
