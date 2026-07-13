---
name: card-shorting
description: ASSET-NEUTRAL CARD (load when evaluating any stock/futures candidate, either side) — this account supports short orders in borrowable stocks and futures; states the execution mechanics and short-specific exposures only, not a selection or sizing view.
metadata:
  type: reference
---

Execution mechanics and short-specific exposures. Candidate selection, directional preference, sizing, and stop policy are the constitution's job, not this card's — this card records facts only.

**This account supports short orders in borrowable stocks and futures.** A stock short requires the shares to be borrowable; availability and borrow rate can change, and the broker can require covering or force-liquidate a short after a recall or a margin-requirement change. A short seller owes any dividends or distributions paid while the position is open.

**A stop on a short does not cap the loss.** A resting stop is an order, not a guarantee: a gap, a trading halt, or a squeeze can fill far through the stop price. An unlevered cash long's maximum loss is its investment; a margined long can also lose beyond posted capital. A stock short's maximum loss has no price ceiling at all.

**Futures shorting uses the same contract mechanics as a long in the same contract** — margin, gaps, price limits, and liquidation rules apply identically regardless of direction (see the futures card for the class's own hazards: expiry/roll/delivery, contango/backwardation).

**Crypto cannot be shorted via this account's configured spot route (IBKR/Paxos-ZeroHash).** That route is spot-only with no margin or short mechanism. This is a fact about the configured execution route, not a statement about crypto shorting in general.

**Paper-account caveat:** this account may not realistically model live-account short frictions — borrow availability, borrow fee, recall risk, margin-requirement changes, forced buy-ins. Treat a real-money short's true cost and tail risk as higher than whatever this paper account shows you.

This card records execution mechanics and short-specific exposures only. It does not alter candidate selection, directional preference, sizing, or qualification standards, which are defined elsewhere.
