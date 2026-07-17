---
name: card-extended-hours
description: ASSET-NEUTRAL CARD (load when holding or entering a stock/ETF position in pre-market or after-hours) — on this account's Alpaca node the position mark can be fresher than the snapshot; a simple stop typically does not arm outside the regular session and so cannot fire on an extended-hours gap.
metadata:
  type: reference
---

Execution mechanics for extended-hours stock/ETF trading only — not a view on
whether to hold through pre-market or after-hours. Candidate selection,
sizing, and stop policy are the constitution's job, not this card's; this
card records facts only.

**On this account's Alpaca node, a snapshot's last-trade field can stick at
the prior regular-session close in pre/post-market (thin/no extended-hours
prints on the IEX feed), while the position's own current-price field keeps
updating.** Confirmed against an outside price source during a real incident:
the position mark was live and correct, the snapshot was the stale one — the
opposite of the usual assumption that a snapshot is closer to ground truth
than a derived field. Don't assume either one is right by default outside
regular hours; a mismatch between a position's mark and a snapshot in
extended hours is itself a signal to check which one is actually current
(compare against another source, or note the trade timestamp each carries)
before treating either the position or the snapshot as broken. This is a
feed characteristic of the Alpaca/IEX node specifically — verify the
equivalent on any other broker before assuming it transfers.

**A simple stop order typically does not arm outside the regular session.**
On Alpaca, extended-hours execution is only available on DAY limit orders —
never stop, stop-limit, or trailing-stop. A resting stop placed for regular
hours can sit through a pre-market or after-hours move untouched and only
become eligible once the regular session reopens, by which point price may
already be well past where the stop was set. This is not visible from the
order's own status — a resting stop still reads `status: new` (its normal,
correct, armed-for-regular-hours state) whether or not the current session
would actually let it fire. Verify what your specific broker arms in
extended hours rather than assuming a resting stop is protection around the
clock.

**The mechanical consequence:** a stop that can't fire in the current session
provides no automated exit until it can. Whether holding through pre-market
or after-hours without one is an acceptable exposure, and at what size, is
the same judgment call as any other overnight/weekend carry decision — this
card states the mechanics that decision has to be made against, nothing more.
