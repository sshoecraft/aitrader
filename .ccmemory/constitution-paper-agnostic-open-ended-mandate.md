---
name: constitution-paper-agnostic-open-ended-mandate
description: 1.48.0: constitution stripped of paper/live wording (enforcement lives in broker code, not the prompt); mandate now open-ended growth, no VTI, no dol…
metadata:
  type: project
tags: [constitution, mandate, paper, live, 1.48.0]
---

## Why
Owner review: the constitution's opening line ("portfolio manager for a
paper trading account") and a House-fuses bullet ("Paper account only. The
broker adapter refuses anything else.") baked paper-specific wording into
the PROMPT, when the actual paper-only enforcement lives entirely in
broker code (`ibkr_connection.py::assert_paper` — verifies the real
connected account ID against IBKR's own API, fails closed, raises a fatal
non-retryable `PaperOnlyError` unless `allow_live=True`; Alpaca's `paper=`
flag selects a physically separate API endpoint) and is completely
unaffected by anything the prompt says. Owner wants ONE constitution text
usable unmodified whether the account is paper or eventually live.

Separately, "why beat VTI? what happened to the success criteria" — the
mandate line didn't match the actual operational goal already used as the
ccloop harness's stop-hook criteria (`settings.toml` `criteria = "Grow the
account to $1,000,000,000... by any means necessary"`, identical on both
itrader and atrader).

## The correction that mattered (read this before touching the mandate again)
First attempt literally copied the $1,000,000,000 figure from the ccloop
criteria into the constitution's mandate too. **Owner caught this as
wrong**: that number is the ccloop STOP condition — a harness concern for
when the never-stop loop's Stop-hook gate is satisfied — not the agent's
own operational identity. Hardcoding it into the constitution would (a)
imply a ceiling ("stop trying once you hit $1B"), which the owner
explicitly does NOT want (if the account ever hits $1B, it should keep
trading, not treat that as a finish line), and (b) create a second place
needing an edit if the harness target ever changes independently. Final
wording has NO dollar figure at all — just open-ended growth.

## What changed (`prompts/constitution.md`, 31,427 → 31,481 B)
- "for a paper trading account" → "for a brokerage account."
- Mandate: "grow the account and beat VTI, net of costs" → "grow the
  account, by any means necessary within the house fuses below, net of
  costs — judged on long-run compounded growth, never any single cycle's
  result." The "within the house fuses below" bound was added per `ask_gpt`
  review: an unbounded "by any means necessary" could read as license to
  override the fuses themselves (naked-position, liquidation-cushion) —
  narrower than "beat VTI, net of costs" ever implied. "Judged on long-run
  compounded growth, never any single cycle's result" guards against the
  opposite failure GPT flagged: requiring positive performance every cycle
  would encourage forced trades.
- Deleted the "Paper account only" House-fuses bullet entirely — unlike
  every other fuse in that list (which ARE behavioral instructions the
  agent must act on), this was never something the agent does anything
  with; it's an infra fact enforced in code, doesn't belong in a doc meant
  to read identically across paper/live.
- "On the paper feed a marketable order fills GRADUALLY" → "In this
  execution environment a marketable order fills GRADUALLY" — same
  fill-latency guidance, no paper-specific framing.
- Verified zero remaining case-insensitive "paper"/"VTI"/"live account"
  matches anywhere in the file.

Backup taken first (`prompts/constitution.md.backup-20260712-premandate`)
and `ask_gpt` review obtained before landing, per the `constitution-edit-
protocol` standing rule. Deploy is owner-run.
