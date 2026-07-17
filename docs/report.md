# report — `bin/aitrader-report`

**Factual emails of how the account did — daily, weekly, monthly, yearly. Pure
infra, ZERO cognition.** Added in 1.33.0. This is the `/src/trader` report
(`bin/report`) rebuilt against aitrader's data sources and **deliberately stripped
of its 0–10 daily "score"** (and the periodic report's `avg_score`).

Periods (`--period`, default `daily`), each with its own systemd timer:

| Period | Covers | Timer fires |
|---|---|---|
| `daily` | yesterday (the completed ET day) | every morning 08:00 ET |
| `weekly` | last complete Mon–Sun week | Monday 08:00 ET |
| `monthly` | last complete calendar month | 1st of month 08:00 ET |
| `yearly` | last complete calendar year | Jan 1 08:00 ET |

The **daily** report is the activity balance-sheet (below). The **periodic** reports
are aggregate summaries: equity change, realized P&L, closed-trade count, win rate,
avg P&L/trade, profit factor, max drawdown, best/worst day — all raw arithmetic over
recorded facts, no graded score.

## What it is / is not

It reports **facts** and nothing else:

- Starting & ending equity (ET calendar day)
- Chronological **activity timeline** — every buy and sell of the day, with a
  one-line headline of the agent's recorded reason (the full rationale stays in
  `journal.db`; the table isn't the place for a multi-paragraph thesis).
  Fills that share the same side/symbol/reason/displayed-minute (partial fills
  of one order) collapse into a single row — the report reads as a trade log,
  one row per decision, not one row per broker fill
- **Realized P&L** — plain FIFO arithmetic (`(exit − avg_entry) × qty`) over the
  fills the agent actually executed
- **Day P&L** split into *realized from closed trades* vs. *market move on
  positions held during the day*

It does **not** list open positions: a positions table is a point-in-time snapshot
(what's held *now*), not a fact about the report day, and there's no cheap
point-in-time position source to reconstruct the day's close. Holdings live on the
dashboard; the report stays about what happened *that day*.

It contains **no score, no grade, no ranking, no win-rate "component," no
discipline deductions.** The old report computed a 0–10 daily score
(Return + Win-Rate + Discipline) — a fixed opinion of "good trading" encoded in
code. CLAUDE.md §2 lists scoring as *cognition*; §8 forbids porting it. So it's
gone. Win **counts** are a raw fact and may appear; a graded win-rate *judgment*
does not. The reader judges the day.

> The line (CLAUDE.md §2): reporting a fact about what happened = infra. Grading
> whether it was *good* = the agent's / the human's job, never a code threshold.

## Data sources (new-system)

The old report read the `/src/trader` DB (`trades`/`decisions`) + the engine at
`localhost:7000`. Neither exists here. This one reads:

| Datum | Source | How |
|---|---|---|
| ending equity (in-progress day) | dashboard API `/status` | HTTP to `127.0.0.1:<api_port>` (port from `state_dir/api_port`, portd-aware) — **same pattern as `aitrader-snapshot`; needs NO broker client id** (the API owns broker client 80) |
| the day's fills (activity + FIFO P&L) | `journal.db` `transactions` ledger | `journal_db.tx_read`, **read-only** |
| starting/ending equity baseline | `journal.db` `equity_snapshots` | `journal_db.equity_read`, read-only |

The **"day" is the ET calendar day** (`et_day_bounds` converts ET midnight → UTC
via `ZoneInfo`, DST-safe per §6). This matches `/status` `day_pl` and the
dashboard's 1D view, so the report's numbers reconcile with the UI.

Ending equity = live `/status` equity when reporting *today*; otherwise the last
`equity_snapshots` row of that ET day. Starting equity = the first snapshot of the
day (the same baseline `day_pl` uses), falling back to the most recent snapshot
before the day (prior close). A sell with no covering buy in the ledger is
**reported with P&L unknown** — the report never invents a cost basis.

## Usage

```
aitrader-report                       # daily: YESTERDAY (the completed ET day), email it
aitrader-report --no-email            # same, print plain text, don't send
aitrader-report --date today          # the in-progress session (live ending equity)
aitrader-report --date 2026-07-08     # a specific ET day
aitrader-report --period weekly       # last complete Mon–Sun week
aitrader-report --period monthly      # last complete calendar month
aitrader-report --period yearly       # last complete calendar year
aitrader-report --period weekly --no-email
```

`--date` applies to `--period daily` only; the periodic ranges are computed from the
run date (`compute_period_range`).

**The default report date is YESTERDAY** — the just-completed ET day, run on day X
to report day X-1 (the way `/src/trader`'s report ran overnight and reported the day
that ended). By the 08:00 ET timer fire the prior day is fully closed and its final
15-min equity snapshot is recorded, so ending equity is the true close. `--date today`
reports the in-progress session and uses live `/status` equity for ending.

## Configuration (`settings.toml`)

| Key | Default | Meaning |
|---|---|---|
| `report_email_to` | `""` | Recipient. **Empty → the timer runs but sends nothing** (the report still renders; use `--no-email` to see it). |
| `report_email_from` | `aitrader@<hostname>` | From/envelope address. Override if postfix needs a specific sender. |
| `report_name` | the unix user | Label in the subject + body header (`atrader Daily Report …`). Default = the running unix user, so multiple stacks on one host (`atrader` vs `itrader`) are already distinct with no config; set it for a friendlier name. |

Email goes out via local **postfix** (`smtplib` → `localhost:25`), same as the old
report.

## Scheduling

One **templated** oneshot, `systemd/aitrader-report@.service`
(`ExecStart=… aitrader-report --period %i`), with four instance timers — each fires
the morning AFTER its period closes and reports the completed period:

```
aitrader-report@daily.timer     OnCalendar=*-*-* 08:00 America/New_York
aitrader-report@weekly.timer    OnCalendar=Mon *-*-* 08:00 America/New_York
aitrader-report@monthly.timer   OnCalendar=*-*-01 08:00 America/New_York
aitrader-report@yearly.timer    OnCalendar=*-01-01 08:00 America/New_York
Persistent=true                 # one catch-up if the box was off at fire time
```

The `America/New_York` zone in each calendar spec makes the timers track EDT/EST
automatically — no hardcoded UTC offset (§6). Daily is **every** day, not weekdays:
the account trades crypto 24/7, so every calendar day has a completed session (and a
Mon-Fri schedule would also never report Friday's session). Change any timer to taste.

Installed + enabled by `install.sh` (and `make install`) alongside the snapshot
timer:

```
systemctl --user enable --now aitrader-report@{daily,weekly,monthly,yearly}.timer
systemctl --user list-timers 'aitrader-report@*'
journalctl --user -u aitrader-report@daily      # run logs (per instance)
```

## Design invariants (don't regress)

- **Facts only.** Never add a score, grade, ranking, or gate. If you're tempted to
  "rate the day," that belongs in the human's head or the agent's journal, not here
  (§2/§8).
- **No broker client id.** Read equity over HTTP from `/status`. Do not open a broker
  connection — that would contend for a client id (see the snapshot recorder's note,
  and `broker-clientid-lease`).
- **No point-in-time positions.** Don't re-add an open-positions table — it's a *now*
  snapshot, not a fact about the report day, and can't be cheaply reconstructed
  as-of the close. Holdings belong on the dashboard.
- **Read-only on the journal.** Only `equity_read`/`tx_read`. Never write, never
  `rm`+recreate the live `journal.db` (`live-journal-db-edit-in-place`).
- **ET calendar day.** Keep the day boundary aligned with `/status` `day_pl` and the
  dashboard, or the email will disagree with the UI.
- **No fabricated cost basis.** A sell without a covering buy → P&L unknown, never a
  made-up entry price (no fake data).
- **Reason is a headline, not the transcript.** `reason_oneline()` shows the first
  sentence only (capped at 160 chars) — the table is a scannable ledger, the full
  narrative belongs in the journal. Don't grow this back into the full string.
- **One row per decision.** `merge_fills()` collapses same-minute fills sharing
  side/symbol/reason before rendering. Don't remove it or partial fills of a
  single order fragment back into duplicate-looking rows.
- **LOCAL disk.** Ships in `~/.local/bin`; imports the installed `aitrader` package.
  Never runs from `/src` (NFS).

## Related

- `docs/snapshot-recorder.md` — the equity-snapshot cron this report's HTTP pattern
  and ET-day baseline build on.
- `docs/api.md` — `/status`, `day_pl`, `/portfolio_history`.
- `docs/journal-mcp.md` — the `transactions` ledger + `equity_snapshots` schema.
