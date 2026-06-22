# Gateway bring-up — detailed notes

The headless IB Gateway stack, end to end. Assumes a Linux host with `systemd
--user` and lingering enabled (`loginctl enable-linger $USER`) so the unit starts
at boot without a login session.

## Components

```
IBC (~/ibc)  ──drives──>  IB Gateway (Java)  ──serves──>  API socket :4002 (paper) / :4001 (live)
     │                          │                                    │
 config.ini               needs an X display                 localhost-only
 (login, mode)            -> xvfb-run provides one           (jts.ini TrustedIPs)
```

- **IB Gateway** — Interactive Brokers' standalone gateway (lighter than TWS).
  Download from IBKR. Installs under `~/Jts/ibgateway/<build>/`.
- **IBC** (IbcAlpha/IBC) — automates the Gateway's login + daily restart so it runs
  unattended. Provides `~/ibc/gatewaystart.sh`. Reads `~/ibc/config.ini`.
- **Xvfb** — a virtual framebuffer X server; the Gateway is a Java Swing app and
  refuses to run with no display. `xvfb-run` wraps the launch (see the unit).

## Steps

`./install.sh` automates steps 1-4 and 6 below; they're documented here so you know
what it does (and how to do it by hand with `--no-app` / `--no-deps`).

1. **System deps** (installer: missing packages only, via sudo if available):
   ```
   sudo apt-get install -y xvfb libxtst6 libxrender1 libxi6 libxext6 \
       libxslt1.1 fontconfig libfreetype6
   ```
2. **Install IB Gateway** (installer: downloads IBKR's standalone installer and runs
   it unattended). The standalone installer lays the app out **flat** in its target
   dir, but IBC wants `~/Jts/ibgateway/<build>/`, so the installer stages the flat
   tree and renames it to the build number it reads from `jars/jts4launch-<build>.jar`
   (e.g. `1045` for Gateway 10.45). Unattended invocation:
   ```
   ./ibgateway-stable-standalone-linux-x64.sh -q -dir <staging>   # install4j: -q unattended
   ```
3. **Install IBC** (installer: downloads the latest IbcAlpha/IBC release zip,
   extracts to `~/ibc`, `chmod +x` the `.sh` files). It then sed-pins the editable
   vars at the top of `~/ibc/gatewaystart.sh`:
   `TWS_MAJOR_VRSN=<build>`, `TWS_PATH=~/Jts`, `IBC_PATH=~/ibc`,
   `IBC_INI=~/ibc/config.ini`, `LOG_PATH=~/ibc/logs`. IBC resolves the Gateway as
   `${TWS_PATH}/ibgateway/${TWS_MAJOR_VRSN}/jars` (see `scripts/ibcstart.sh`), which
   is why the nested layout in step 2 matters.
   > IBC's release zip ships its **own** generic `config.ini` (defaults to
   > `TradingMode=live`, `AcceptIncomingConnectionAction=manual`, no port override).
   > The installer deletes it on extract so aitrader's template governs instead —
   > don't be surprised it's gone.
4. **Configure IBC** (installer: seeds `~/ibc/config.ini` from
   `ibc/config.ini.example` if absent — never clobbers an edited one). Then **you**
   edit `IbLoginId`, `IbPassword`, and `TradingMode` (paper/live). The template
   already sets `OverrideTwsApiPort=4002` and `AcceptIncomingConnectionAction=accept`
   for headless.
5. **Lock the API to localhost**: in `~/Jts/.../jts.ini` set
   `TrustedIPs=127.0.0.1` (or open only to the aitrader host if remote). Gateway
   writes `jts.ini` on first run; this step is manual.
6. **Install + enable the unit** (installer does the install; you enable):
   ```
   ./install.sh
   systemctl --user enable --now ibgateway
   ```
7. **Verify**: `ss -tlnp | grep 4002` shows the listener; `journalctl --user -u
   ibgateway -f` shows IBC logging in; `~/ibc/logs/` has the IBC detail log.

## Readiness window (why aitrader has a gate)

`ibgateway.service` is `Type=simple`, so it's "active" as soon as the process
spawns (~13s) — but the Gateway's actual *login* takes 10-90s longer. A client that
connects into that window lands in a client-id 326 ("already in use") reconnect
storm. aitrader handles this on the client side: `ibgateway-ready.service` (a
oneshot that runs `aitrader-gateway-wait`) does a real API handshake and only
reports ready once the Gateway returns accounts, and the agent/dashboard order
`After=ibgateway-ready.service`. You don't configure anything here for that — just
ensure this unit is named `ibgateway.service`.

## Daily restart

IBC restarts the Gateway daily (IBKR forces a re-auth). With `IbAutoClosedown=no`
and the IBC restart settings, the session re-establishes automatically;
`Restart=always` on the unit covers a hard exit. The aitrader agent reconciles from
the broker + journal on its next wake, so a brief gateway blip is transparent.

## Paper vs live

This is the one decision the gateway can't default for you. Paper = port 4002,
`TradingMode=paper`, account `DU*`/`DF*`. Live = port 4001, `TradingMode=live`,
account `U*`/`F*`. Even in live mode, aitrader **independently** refuses a live
account until `allow_live = true` in its `settings.toml` — see the top-level
README and aitrader's `aitrader/fuses.py`.
