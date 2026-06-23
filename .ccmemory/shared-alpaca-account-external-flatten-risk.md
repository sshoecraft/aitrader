---
name: shared-alpaca-account-external-flatten-risk
description: 2026-06-22 atrader flatten: proven NOT the agent/dashboard; an external rogue EOD-flatten server hit the shared Alpaca acct. NOT itrader (IBKR on thi…
metadata:
  type: project
---

## Incident 2026-06-22 (atrader) — RESOLVED cause

At 19:50:43 UTC all 7 atrader positions were market-sold in a 16ms window (mixed
TIF), bare-UUID `order_ref`s, account → flat $64,813. Agent's live memory
misdiagnosed it as Alpaca margin auto-liquidation (WRONG).

**Actual cause (confirmed by user):** a separate server that was running an
**EOD flatten that was not supposed to be running**, hitting the shared Alpaca
paper account. NOT a margin call, NOT the atrader agent, NOT atrader's dashboard.
**NOT `itrader`** — itrader on this host is the IBKR instance, unrelated.

## Forensics that hold up (reusable)

- atrader **agent didn't place them**: zero tool calls in the turn between
  "quick close check" (19:50:08) and the API error (19:54:16).
- atrader **dashboard didn't**: aitrader-api log 19:50-19:59 = GET polling only,
  no `POST /sell`.
- Mechanism fingerprint: bare-UUID `order_ref` ⇒ `close_position`/close-all, not
  `place_market_order`. `brokers/alpaca.py:437 close_position` **drops
  client_tag** (Alpaca's close endpoint assigns its own id); so does dashboard
  `POST /sell`. 16ms simultaneity ⇒ single Alpaca `DELETE /v2/positions`.
- Lesson: an unrecognized bare-UUID flatten on an Alpaca paper acct = an external
  actor on the SAME account, not the local agent. Don't assume margin call.

Related: [[broker-clientid-lease]] [[data-execution-broker-split]]
</body>
