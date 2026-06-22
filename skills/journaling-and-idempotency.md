# Skill — Memory discipline and never double-submitting

Guidance for the two habits that make a persistent, restartable trader safe.

## Journaling — write so a stranger (future you) can continue

Your context is scratch and will be compacted away; the journal is what
survives. After every cycle in which you did anything — or decided pointedly to
do nothing — leave enough that a future you who remembers *nothing* could pick up
the thread. Concretely, the things worth capturing:

- **Theses with falsifiers.** One sentence why, one sentence what would prove you
  wrong. A thesis you can't falsify isn't a thesis; it's a hope.
- **Why you entered / exited / sized as you did.** Not the mechanics (the broker
  records those) — the *reasoning*. "Bought because…", "sized small because the
  thesis is early and ATR is wide", "exited because the falsifier triggered".
- **What you're waiting for.** The specific thing that would make you act next:
  a level, a print, a fill, a time. This is what your next wake reads first.

Keep the position-of-record current: it is your *why* for everything you hold.
When the broker shows a position, you should be able to point to its
position-of-record and explain it. When a position closes, update or remove it.

## Idempotency — the discipline that makes "just relaunch me" safe

You can be restarted at any moment, possibly with orders in flight. The rule that
prevents catastrophe is: **every order gets a deterministic client tag derived
from its intent**, and you check before you place.

The loop for any order:
1. Derive a tag from the intent so the *same decision* always produces the *same
   tag* — e.g. `SYMBOL-side-YYYY-MM-DD-thesisslug`. Two genuinely different
   decisions must produce different tags; the same decision re-derived after a
   restart must produce the identical tag.
2. `order_record(client_tag=…, …)` to log the intent **before** you place.
3. Place the order at the broker **with that same tag** as its client ref.
4. `order_record(client_tag=…, broker_order_id=…, status="placed")` to link them.

On reconcile after any restart, before acting: look up the tags you would be
about to use, and check the broker's open orders and fills. If the order already
exists at the broker or is recorded as placed/filled, **do not place it again** —
adopt it. Reconcile the broker's positions against your positions-of-record and
fix any drift in your *why*, never by overriding the broker's *what*.

The broker is always the source of truth for what exists. Your records exist so
that, on waking into an unknown moment, you can recognize your own footprints.
