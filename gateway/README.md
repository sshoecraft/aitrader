# IBKR gateway

The **IBKR gateway server** for [aitrader](..) — IB Gateway run headless
under [IBC](https://github.com/IbcAlpha/IBC) on a virtual X display (Xvfb), exposed
as a localhost API socket that the aitrader IBKR *client* connects to.

This lives in its own `gateway/` subdir, and aitrader only touches it for
`broker = "ibkr"`. aitrader ships the IBKR *client* (it dials a gateway at
`ibkr_host:ibkr_port`); this is what actually runs that gateway. Standing it up
requires decisions aitrader cannot make for you — **paper vs live, your IBKR
credentials, and explicit consent to trade real money** — which is why the
installer below stops and hands those steps back to you. Because it's isolated to
this subdir, installing aitrader against Alpaca or MYSE pulls none of its X/font
deps or binaries.

> You do **not** need any of this to run aitrader against Alpaca or MYSE.
> It is used only when aitrader's `broker = "ibkr"` — and
> `./install.sh --broker ibkr` from the aitrader root runs this installer for you.

---

## ⚠️ Decisions you must make before installing

### 1. Paper or live?
IB Gateway speaks to one account at a time, selected by **port** and **trading
mode**:

| Mode  | Gateway API port | IBC `TradingMode` | aitrader account ids |
|-------|------------------|-------------------|----------------------|
| Paper | `4002`           | `paper`           | start with `DU`/`DF` |
| Live  | `4001`           | `live`            | start with `U`/`F`   |

aitrader defends paper with a **constitutional fuse**: its broker adapter
(`aitrader/fuses.py`) *refuses* any account id that is not paper unless you set
`allow_live = true` in `~/.config/aitrader/settings.toml`. **Running this gateway
in live mode does nothing on its own** — aitrader still refuses to trade a live
account until you consciously flip `allow_live`. Two independent switches
(gateway mode + `allow_live`) must agree before a single real-money order is
possible. That is by design.

**Default and recommendation: paper (4002).** Do not run live until you have a
track record you would stake real capital on.

### 2. Credentials
You need an IBKR account and its Gateway login (username/password). For paper,
generate a paper user in IBKR Client Portal. These go in `ibc/config.ini` (see
`ibc/config.ini.example`) — **never commit the filled-in file** (`.gitignore`
excludes `ibc/config.ini`).

### 3. Live-trading consent (if you chose live)
Live mode means an autonomous agent places **real orders with real money**. aitrader
deliberately has **no notional/position-size caps in code** — the agent owns all
sizing by reasoning. Before you enable live, read aitrader's `BRIEF.md`/`CLAUDE.md`
on the fuse model and decide whether you want to add *kill-condition* safety fuses
(e.g. a max-drawdown auto-halt — a breaker, not a trade decision). That is your
call to make, consciously, in writing.

---

## The contract with aitrader

aitrader's client side expects exactly this, and nothing more:

1. A systemd **user** unit named **`ibgateway.service`** (aitrader's
   `ibgateway-ready.service` orders `After=ibgateway.service`).
2. The Gateway API **accepting logins on the configured port** (`4002` paper /
   `4001` live), localhost-only. aitrader's readiness probe
   (`aitrader-gateway-wait`) does a real IB API handshake and only lets the agent
   and dashboard connect once the gateway returns accounts — this avoids the
   client-id 326 reconnect storm during the gateway's post-boot login window.
3. aitrader's `~/.config/aitrader/secrets.toml` pointing at it:
   ```toml
   ibkr_host = "127.0.0.1"
   ibkr_port = 4002          # 4001 for live
   ibkr_client_id = 40
   ```

The gateway can be co-located (same host, the common case) or remote — set
`ibkr_host` accordingly and open the port to that host only.

---

## Install

`./install.sh --broker ibkr` from the aitrader root runs all of this for you. To
set up (or re-run) the gateway on its own:

```bash
cd /src/aitrader/gateway
./install.sh                                # full bring-up (downloads IB Gateway + IBC)
$EDITOR ~/ibc/config.ini                    # fill in IbLoginId / IbPassword / TradingMode
./install.sh                                # re-run: confirms creds are set (idempotent)
systemctl --user enable --now ibgateway
ss -tlnp | grep 4002                        # confirm it's listening (4001 for live)
```

`install.sh` does the whole thing, and every step is idempotent (anything already
present is detected and skipped):
- installs the X/font system deps IB Gateway's Java Swing UI needs
  (`xvfb libxtst6 libxrender1 libxi6 libxext6 libxslt1.1 fontconfig libfreetype6`)
  — only the missing ones, and only if root / passwordless sudo is available
  (otherwise it prints the apt line for you and continues),
- **downloads + installs IB Gateway** (IBKR's standalone installer, run unattended)
  into `~/Jts/ibgateway/<build>/`,
- **downloads + installs IBC** (latest IbcAlpha/IBC release) into `~/ibc` and wires
  its `gatewaystart.sh` to the installed Gateway build and paths,
- seeds `~/ibc/config.ini` from this subdir's template (with **paper** + port 4002
  defaults) — it never overwrites a `config.ini` you've already edited,
- installs the `ibgateway.service` **user** unit to `~/.config/systemd/user/`.

It does **not** fill in your IBKR credentials and it does **not** flip you to live —
that's the one thing only you can decide (see below). After the first run it will
flag that `config.ini` still has placeholder credentials.

Flags: `--no-deps` skips the apt step; `--no-app` skips the IB Gateway + IBC
download (use it if you've installed those yourself at `~/Jts` and `~/ibc`).

### Third-party binaries it pulls
- **IB Gateway** — Interactive Brokers' standalone Gateway (not TWS), from IBKR's
  download CDN. A login is needed only at *runtime*, not to download.
- **IBC** — https://github.com/IbcAlpha/IBC (drives the headless login).
These have their own licenses; this subdir holds only the config template, the
systemd unit, and the installer glue — it does not redistribute the binaries.

---

## Operate

```bash
systemctl --user status ibgateway
journalctl --user -u ibgateway -f       # also ~/ibc/logs/
systemctl --user restart ibgateway
```

IBC auto-logs-in, auto-restarts daily, and closes down on the schedule in
`ibc/config.ini`. `Restart=always` brings the unit back.

## Layout
```
README.md                  ← this file (decisions + contract)
install.sh                 ← deps + unit install + prereq checks
systemd/ibgateway.service  ← the headless-gateway user unit
ibc/config.ini.example     ← IBC config template (copy → config.ini, then edit)
docs/setup.md              ← detailed gateway bring-up notes
```
