#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# DISCLAIMER — READ BEFORE USE
#   aitrader is licensed for PERSONAL, NON-COMMERCIAL use only (PolyForm
#   Noncommercial 1.0.0). It is NOT intended to be run against a live brokerage
#   account — it ships paper-only by design. The author bears NO responsibility
#   for any financial loss or damage of any kind arising from its use. You run
#   it entirely at your own risk.
# ─────────────────────────────────────────────────────────────────────────────
# aitrader installer — the product front door.
#
# Installs aitrader for the current user into ~/.local (LOCAL disk; the /src source
# tree is build-time only). It builds + pip-installs the package, deploys the
# dashboard UI, seeds the run dir + config, registers the MCP servers, and installs
# the systemd user units.
#
# Default (no flags): NO questions. It installs everything, seeds settings.toml
# (defaults: broker=alpaca, ports 2499/2500) and a secrets.toml template, then tells
# you to edit those two files and enable the services. That's the whole flow:
#   git clone … ; cd aitrader ; ./install.sh ; $EDITOR ~/.config/aitrader/{settings,secrets}.toml ; enable
#
# Usage:
#   ./install.sh                       # install + seed settings/secrets to edit (no prompts)
#   ./install.sh --wizard              # interactive: pick broker/ports, paste keys, auto-enable
#   ./install.sh -y --broker alpaca \  # fully non-interactive (auto-enable)
#       --alpaca-key KEY --alpaca-secret SECRET
#   ./install.sh -y --answers my.conf  # non-interactive from an answers file
#   ./install.sh --reconfigure         # rewrite settings.toml/secrets.toml
#   ./install.sh --no-services         # install but don't enable systemd units
#   ./install.sh --build-ui            # rebuild the UI from source (auto-downloads node if missing)
#   ./install.sh --broker ibkr --no-gateway   # IBKR client only, skip gateway setup
#
# IBKR: this installs the IBKR *client*. With --broker ibkr it ALSO sets up the
# bundled gateway server (gateway/ — IB Gateway under IBC) by descending into
# gateway/install.sh; pass --no-gateway to manage the gateway yourself. aitrader
# stays paper-only until you set allow_live=true in settings.toml.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SRC_DIR"

# Any unexpected non-zero command aborts (set -e) — say so loudly and point back to
# the safe re-run instead of dying silently mid-way. (die() clears this for its own
# clean exits.)
trap 'echo "ERROR: install aborted near line $LINENO. Fix the issue and re-run ./install.sh — it is idempotent (keeps your settings/secrets)." >&2' ERR

# ── paths (XDG; match aitrader/config.py) ────────────────────────────────────
LOCAL_BIN="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/aitrader"
RUN_DIR="$DATA_DIR/run"
STATE_DIR="$HOME/.local/state/aitrader"
UI_DIR="$DATA_DIR/ui"
CONFIG_DIR="$HOME/.config/aitrader"
SVC_DIR="$HOME/.config/systemd/user"
SETTINGS="$CONFIG_DIR/settings.toml"
SECRETS="$CONFIG_DIR/secrets.toml"

# ── defaults (overridable by flags / answers file / wizard) ──────────────────
INTERACTIVE=0; RECONFIGURE=0; NO_SERVICES=0; BUILD_UI=0; TEMPLATE=0; NO_GATEWAY=0
BROKER="alpaca"; API_PORT=2499; UI_PORT=2500; MODEL="opus"
DATA_BROKER=""           # optional separate market-data feed (e.g. alpaca)
ALPACA_KEY=""; ALPACA_SECRET=""
MYSE_HOST="http://localhost:7777"; MYSE_KEY=""
IBKR_HOST="127.0.0.1"; IBKR_PORT="4002"; IBKR_CLIENT_ID="40"
CRITERIA="Grow the account to \$1,000,000,000 (one billion dollars) in equity by any means necessary"
TASK="."

die() { trap - ERR; echo "ERROR: $*" >&2; exit 1; }
info() { echo "  $*"; }
step() { echo; echo "==> $*"; }

# Node is a BUILD-TIME-ONLY dependency for the dashboard UI (vite/tsc). The
# agent, MCP servers, and API never need it at runtime. Pinned so the bootstrap
# is reproducible; bump deliberately.
NODE_VERSION="22.21.1"

# A downloader that follows redirects, retries, and fails loudly. $1=url $2=dest.
# Returns non-zero when neither curl nor wget is present. Mirrors gateway/install.sh.
fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -fSL --retry 3 --retry-delay 2 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$2" "$1"
  else
    return 1
  fi
}

# Ensure `npm` is on PATH. If the system has none, download a pinned official
# Node toolchain into the XDG cache and prepend its bin to PATH for THIS process
# (never installed system-wide, never needed at runtime). Returns non-zero if it
# genuinely can't (unknown OS/arch, no curl/wget/tar, or download failure) — the
# caller then falls back to a prebuilt ui/dist or skips the UI. This is what lets
# a fresh clone on a node-less box still build the dashboard, the same way
# gateway/install.sh auto-downloads IB Gateway + IBC.
ensure_node() {
  command -v npm >/dev/null 2>&1 && return 0

  local cache os arch bin tarball url
  cache="${XDG_CACHE_HOME:-$HOME/.cache}/aitrader"
  case "$(uname -s)" in
    Linux)  os=linux  ;;
    Darwin) os=darwin ;;
    *) info "no system node and unsupported OS '$(uname -s)' — cannot bootstrap node"; return 1 ;;
  esac
  case "$(uname -m)" in
    x86_64|amd64)  arch=x64   ;;
    aarch64|arm64) arch=arm64 ;;
    *) info "no system node and unsupported arch '$(uname -m)' — cannot bootstrap node"; return 1 ;;
  esac

  bin="$cache/node-v$NODE_VERSION-$os-$arch/bin"
  if [ ! -x "$bin/npm" ]; then
    command -v tar >/dev/null 2>&1 || { info "no system node and no 'tar' — cannot bootstrap node"; return 1; }
    tarball="node-v$NODE_VERSION-$os-$arch.tar.gz"
    url="https://nodejs.org/dist/v$NODE_VERSION/$tarball"
    info "no system node — downloading Node v$NODE_VERSION ($os-$arch, ~30MB) → $cache"
    mkdir -p "$cache"
    fetch "$url" "$cache/$tarball" || { info "node download failed (no curl/wget, or network unreachable)"; return 1; }
    tar -xzf "$cache/$tarball" -C "$cache" || { info "node archive extract failed"; rm -f "$cache/$tarball"; return 1; }
    rm -f "$cache/$tarball"
  fi
  [ -x "$bin/npm" ] || { info "node bootstrap incomplete (no npm under $bin)"; return 1; }
  PATH="$bin:$PATH"; export PATH
  info "using bootstrapped Node $("$bin/node" --version) from $cache"
  return 0
}

load_answers() {  # parse KEY=VALUE lines safely (no source)
  local f="$1" line key val
  [ -f "$f" ] || die "answers file not found: $f"
  while IFS= read -r line; do
    line="${line%%#*}"; line="${line## }"; line="${line%% }"
    [ -z "$line" ] && continue
    key="${line%%=*}"; val="${line#*=}"
    case "$key" in
      broker) BROKER="$val" ;; api_port) API_PORT="$val" ;; ui_port) UI_PORT="$val" ;;
      model) MODEL="$val" ;; data_broker) DATA_BROKER="$val" ;;
      alpaca_key) ALPACA_KEY="$val" ;; alpaca_secret) ALPACA_SECRET="$val" ;;
      myse_host) MYSE_HOST="$val" ;; myse_key) MYSE_KEY="$val" ;;
      ibkr_host) IBKR_HOST="$val" ;; ibkr_port) IBKR_PORT="$val" ;;
      ibkr_client_id) IBKR_CLIENT_ID="$val" ;;
      criteria) CRITERIA="$val" ;; task) TASK="$val" ;;
      *) echo "  (ignoring unknown answers key: $key)" >&2 ;;
    esac
  done < "$f"
}

# ── arg parsing ──────────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --wizard) INTERACTIVE=1 ;;
    -y|--non-interactive|--yes) INTERACTIVE=0 ;;
    --reconfigure) RECONFIGURE=1 ;;
    --no-services) NO_SERVICES=1 ;;
    --no-gateway) NO_GATEWAY=1 ;;
    --build-ui) BUILD_UI=1 ;;
    --answers) load_answers "$2"; shift ;;
    --broker) BROKER="$2"; shift ;;
    --api-port) API_PORT="$2"; shift ;;
    --ui-port) UI_PORT="$2"; shift ;;
    --model) MODEL="$2"; shift ;;
    --data-broker) DATA_BROKER="$2"; shift ;;
    --alpaca-key) ALPACA_KEY="$2"; shift ;;
    --alpaca-secret) ALPACA_SECRET="$2"; shift ;;
    --myse-host) MYSE_HOST="$2"; shift ;;
    --myse-key) MYSE_KEY="$2"; shift ;;
    --ibkr-host) IBKR_HOST="$2"; shift ;;
    --ibkr-port) IBKR_PORT="$2"; shift ;;
    --ibkr-client-id) IBKR_CLIENT_ID="$2"; shift ;;
    -h|--help) sed -n '2,${/^#/!q;s/^# \{0,1\}//p;}' "$0"; exit 0 ;;
    *) die "unknown arg: $1 (try --help)" ;;
  esac
  shift
done

# ── disclaimer banner (always shown before doing anything) ───────────────────
cat <<'BANNER'

  ╔════════════════════════════════════════════════════════════════════════╗
  ║                          ⚠  DISCLAIMER  ⚠                               ║
  ║                                                                        ║
  ║  aitrader is for PERSONAL, NON-COMMERCIAL use only (PolyForm            ║
  ║  Noncommercial 1.0.0). It is NOT intended to be run against a LIVE      ║
  ║  brokerage account — it ships paper-only by design.                    ║
  ║                                                                        ║
  ║  The author bears NO responsibility for any financial loss or damage   ║
  ║  arising from its use. You run it ENTIRELY AT YOUR OWN RISK.            ║
  ╚════════════════════════════════════════════════════════════════════════╝

BANNER

# ── preflight ────────────────────────────────────────────────────────────────
step "Preflight"
# Hard requirements to build + install the package at all:
command -v python3 >/dev/null 2>&1 || die "python3 not found"
PYV=$(python3 -c 'import sys; print("%d.%d"%sys.version_info[:2])')
python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,12) else 1)' \
  || die "python3 >= 3.12 required (found $PYV)"
info "python3 $PYV"
python3 -m pip --version >/dev/null 2>&1 || die "pip not available (python3 -m pip)"
PIP_FLAGS="--user --break-system-packages --force-reinstall"

# Runtime tools the AGENT needs to actually run (not needed to install the package).
# Missing ones don't abort the install — but the aitrader agent service can't start
# until they're on PATH. Collect them, warn here, and remind again at the very end.
MISSING_TOOLS=""
check_tool() {  # $1=command  $2=why it's needed
  if command -v "$1" >/dev/null 2>&1; then info "$1: $(command -v "$1")"
  else MISSING_TOOLS="$MISSING_TOOLS $1"; echo "  MISSING: $1 — $2"; fi
}
check_tool tmux   "aitrader.service runs ccloop inside tmux (the agent needs a real PTY)"
check_tool claude "the Claude CLI the agent runs as"
check_tool ccloop "the never-stop runtime that drives the agent (usually ~/.local/bin)"
[ -n "$MISSING_TOOLS" ] && \
  echo "  -> put the above on PATH (e.g. ~/.local/bin) BEFORE enabling the agent service."
if [ -n "$MISSING_TOOLS" ] && [ "$INTERACTIVE" -eq 1 ]; then
  read -r -p "  Continue install anyway? [y/N]: " a; [ "${a,,}" = "y" ] || die "aborted (install the tools above first)"
fi

# ── config wizard ────────────────────────────────────────────────────────────
if [ "$INTERACTIVE" -eq 1 ]; then
  step "Configure"
  read -r -p "Execution broker [alpaca/myse/ibkr] ($BROKER): " a; BROKER="${a:-$BROKER}"
  read -r -p "Dashboard API port ($API_PORT): " a; API_PORT="${a:-$API_PORT}"
  read -r -p "Dashboard UI port ($((API_PORT+1))): " a; UI_PORT="${a:-$((API_PORT+1))}"
  read -r -p "Claude model ($MODEL): " a; MODEL="${a:-$MODEL}"
  case "$BROKER" in
    alpaca)
      read -r -p "Alpaca API key: " ALPACA_KEY
      read -rs -p "Alpaca secret key: " ALPACA_SECRET; echo ;;
    myse)
      read -r -p "MYSE host ($MYSE_HOST): " a; MYSE_HOST="${a:-$MYSE_HOST}"
      read -rs -p "MYSE API key: " MYSE_KEY; echo
      read -r -p "Use Alpaca for market data too? [y/N]: " a
      [ "${a,,}" = "y" ] && { DATA_BROKER="alpaca"; read -r -p "Alpaca API key: " ALPACA_KEY; read -rs -p "Alpaca secret key: " ALPACA_SECRET; echo; } ;;
    ibkr)
      echo "  NOTE: the bundled gateway (gateway/) is set up automatically at the end of this install."
      read -r -p "IBKR gateway host ($IBKR_HOST): " a; IBKR_HOST="${a:-$IBKR_HOST}"
      read -r -p "IBKR gateway port ($IBKR_PORT): " a; IBKR_PORT="${a:-$IBKR_PORT}"
      read -r -p "Use Alpaca for stock/crypto market data? [y/N]: " a
      [ "${a,,}" = "y" ] && { DATA_BROKER="alpaca"; read -r -p "Alpaca API key: " ALPACA_KEY; read -rs -p "Alpaca secret key: " ALPACA_SECRET; echo; } ;;
    *) die "unknown broker: $BROKER" ;;
  esac
fi
[ -z "$UI_PORT" ] && UI_PORT=$((API_PORT+1))

# If the broker's creds weren't supplied (and we're not in the wizard), seed
# editable TEMPLATES instead of failing — the user fills them in and enables. This
# is the default "clone → install → edit two files → done" flow.
case "$BROKER" in
  alpaca) { [ -n "$ALPACA_KEY" ] && [ -n "$ALPACA_SECRET" ]; } || TEMPLATE=1 ;;
  myse)   [ -n "$MYSE_KEY" ] || TEMPLATE=1 ;;
  ibkr)   : ;;  # no aitrader creds needed; gateway setup (gateway/) handles IBKR login
  *) die "unknown broker: $BROKER" ;;
esac
[ "$TEMPLATE" -eq 1 ] && NO_SERVICES=1   # don't enable services with no keys yet

# ── write settings.toml + secrets.toml ───────────────────────────────────────
step "Write config ($CONFIG_DIR)"
mkdir -p "$CONFIG_DIR"
if [ -f "$SETTINGS" ] && [ "$RECONFIGURE" -eq 0 ]; then
  info "kept existing settings.toml (use --reconfigure to overwrite)"
else
  { echo "# aitrader settings — written by install.sh. Restart services after edits."
    echo
    echo "ccloop_cutoff = 500"
    echo "criteria = \"$CRITERIA\""
    echo "task = \"$TASK\""
    echo
    echo "wake_floor_seconds = 5"
    echo "allow_live = false"
    echo
    echo "broker = \"$BROKER\""
    [ -n "$DATA_BROKER" ] && echo "data_broker = \"$DATA_BROKER\""
    [ -n "$DATA_BROKER" ] && echo "data_broker_types = [\"stock\", \"crypto\"]"
    echo
    echo "api_port = $API_PORT"
    [ -n "$UI_PORT" ] && echo "ui_port  = $UI_PORT"
  } > "$SETTINGS"
  info "wrote settings.toml (broker=$BROKER, api_port=$API_PORT, ui_port=$UI_PORT)"
fi

if [ -f "$SECRETS" ] && [ "$RECONFIGURE" -eq 0 ]; then
  info "kept existing secrets.toml (use --reconfigure to overwrite)"
elif [ "$TEMPLATE" -eq 1 ]; then
  umask 077
  { echo "# aitrader secrets — fill in the keys for your broker, then enable the services."
    echo "# Mode 0600. Do NOT commit. Only the block matching settings.toml 'broker' is needed."
    echo
    echo "# broker = \"alpaca\"  (also fill these if you set data_broker = \"alpaca\")"
    echo "alpaca_api_key = \"\""
    echo "alpaca_secret_key = \"\""
    echo
    echo "# broker = \"myse\""
    echo "# myse_host = \"http://localhost:7777\""
    echo "# myse_api_key = \"\""
    echo
    echo "# broker = \"ibkr\"  (gateway server is bundled in gateway/; set up by --broker ibkr)"
    echo "# ibkr_host = \"127.0.0.1\""
    echo "# ibkr_port = 4002"
    echo "# ibkr_client_id = 40"
  } > "$SECRETS"
  chmod 600 "$SECRETS"
  info "wrote secrets.toml TEMPLATE (mode 600) — edit it with your keys"
else
  umask 077
  { echo "# aitrader secrets — written by install.sh. Mode 0600. Do not commit."
    case "$BROKER" in
      alpaca) echo "alpaca_api_key = \"$ALPACA_KEY\""; echo "alpaca_secret_key = \"$ALPACA_SECRET\"" ;;
      myse)   echo "myse_host = \"$MYSE_HOST\""; echo "myse_api_key = \"$MYSE_KEY\""
              [ -n "$DATA_BROKER" ] && { echo "alpaca_api_key = \"$ALPACA_KEY\""; echo "alpaca_secret_key = \"$ALPACA_SECRET\""; } ;;
      ibkr)   echo "ibkr_host = \"$IBKR_HOST\""; echo "ibkr_port = $IBKR_PORT"; echo "ibkr_client_id = $IBKR_CLIENT_ID"
              [ -n "$DATA_BROKER" ] && { echo "alpaca_api_key = \"$ALPACA_KEY\""; echo "alpaca_secret_key = \"$ALPACA_SECRET\""; } ;;
    esac
  } > "$SECRETS"
  chmod 600 "$SECRETS"
  info "wrote secrets.toml (mode 600)"
fi

# ── build + install the package ──────────────────────────────────────────────
step "Build + install package"
rm -rf build dist ./*.egg-info aitrader.egg-info
python3 -m pip wheel --no-deps --wheel-dir dist .
WHL=$(ls -t dist/*.whl | head -1)
[ -n "$WHL" ] || die "wheel build produced nothing"
EXTRAS="api,calendar,sandbox"
# The 'ibkr' extra (ib_async) is pulled ONLY when this install runs with
# --broker ibkr. Flipping settings.toml's `broker = "ibkr"` LATER, after
# installing with a different default broker, does NOT retroactively install
# it — the IBKR adapter then fails at runtime with an opaque "requires
# ib_async which isn't installed" error. Re-run ./install.sh --broker ibkr
# (or pip install --user --break-system-packages "ib_async>=2.0.0" directly)
# to fix. See [[aitrader-ibkr-extra-ib-async]].
[ "$BROKER" = "ibkr" ] && EXTRAS="$EXTRAS,ibkr"
info "installing $WHL [$EXTRAS]"
# Purge orphaned "~"-prefixed leftovers from prior interrupted/force-reinstall
# runs. pip renames a dist-info to "~name" as a pre-delete backup; if the delete
# is interrupted (or a rename like eventkit->aeventkit churns it), the backup is
# stranded and pip then spams "Ignoring invalid distribution ~name" AND reports
# false "<pkg> ... not installed" conflicts. Removing them is always safe.
USER_SITE=$(python3 -c 'import site; print(site.getusersitepackages())' 2>/dev/null || true)
if [ -n "$USER_SITE" ] && [ -d "$USER_SITE" ]; then
  for leftover in "$USER_SITE"/~*; do
    [ -e "$leftover" ] || continue   # nullglob off: skip the literal pattern when no match
    rm -rf "$leftover" && info "purged orphaned leftover: $(basename "$leftover")"
  done
fi
# shellcheck disable=SC2086
python3 -m pip install $PIP_FLAGS "${WHL}[${EXTRAS}]"

# ── CLI scripts ──────────────────────────────────────────────────────────────
step "Install CLI scripts ($LOCAL_BIN)"
mkdir -p "$LOCAL_BIN"
n=0
for f in bin/*; do
  [ -f "$f" ] || continue   # skip __pycache__ / any stray non-file (install rejects dirs)
  install -m 755 "$f" "$LOCAL_BIN"/ && n=$((n + 1))
done
info "installed $n CLI scripts"

# ── dashboard UI (optional polish — NEVER abort the agent install over it) ───
step "Deploy dashboard UI ($UI_DIR)"
ui_ok=1
# Rebuild the bundle when it's STALE, not just when it's missing: if any UI build
# input (ui/src, index.html, vite/ts/package config, public assets) is newer than
# the built ui/dist/index.html, the existing dist is out of date and deploying it
# would silently ship old code. Scoped find over the small ui/ subtree only (NOT a
# scan of /src); -quit stops at the first newer file. So editing ui/src no longer
# requires remembering --build-ui.
ui_stale=0
if [ -d ui/dist ] && [ -n "$(find ui/src ui/public ui/index.html ui/vite.config.ts ui/package.json ui/tsconfig*.json -type f -newer ui/dist/index.html -print -quit 2>/dev/null)" ]; then
  ui_stale=1
fi
if [ "$BUILD_UI" -eq 1 ] || [ ! -d ui/dist ] || [ "$ui_stale" -eq 1 ]; then
  # ensure_node uses system npm if present, else auto-downloads a pinned local
  # Node — so a fresh clone with no node still builds the dashboard.
  if ensure_node; then
    [ "$ui_stale" -eq 1 ] && info "ui/dist is stale (source newer) — rebuilding"
    info "building UI from source (npm)"
    ( cd ui && npm install --no-audit --no-fund && npm run build ) || ui_ok=0
  elif [ ! -d ui/dist ]; then
    echo "  WARN: couldn't obtain node and no prebuilt ui/dist — skipping the dashboard UI."
    echo "        provide network access (or install node), then ./install.sh --build-ui later."
    ui_ok=0
  else
    echo "  WARN: ui/dist is stale but node unavailable — deploying the existing dist as-is."
    echo "        provide network access (or install node), then ./install.sh --build-ui to refresh."
  fi
fi
if [ "$ui_ok" -eq 1 ] && [ -d ui/dist ]; then
  mkdir -p "$UI_DIR"; rm -rf "${UI_DIR:?}/"*; cp -r ui/dist/* "$UI_DIR"/
  install -m 755 ui/bin/trader_ui "$LOCAL_BIN"/trader_ui
  info "UI served from $UI_DIR by trader_ui (api :$API_PORT, ui :$UI_PORT)"
else
  echo "  (dashboard UI not deployed — the agent + API still work; add it later with 'make ui')"
fi

# ── run dir + constitution + model ───────────────────────────────────────────
step "Seed run dir ($RUN_DIR)"
mkdir -p "$RUN_DIR/.claude" "$DATA_DIR/prompts" "$STATE_DIR/logs"
install -m 644 prompts/constitution.md "$RUN_DIR/CLAUDE.md"
install -m 644 prompts/constitution.md "$DATA_DIR/prompts/constitution.md"
if [ ! -f "$RUN_DIR/.claude/settings.json" ] || [ "$RECONFIGURE" -eq 1 ]; then
  printf '{\n  "model": "%s"\n}\n' "$MODEL" > "$RUN_DIR/.claude/settings.json"
  info "model: $MODEL"
fi
rm -f "$RUN_DIR/.mcp.json"
info "constitution -> $RUN_DIR/CLAUDE.md"

# ── register MCP servers at user scope ───────────────────────────────────────
step "Register MCP servers (~/.claude.json, user scope)"
python3 - "$LOCAL_BIN" <<'PY'
import json, os, sys
bin_dir = sys.argv[1]
p = os.path.expanduser("~/.claude.json")
d = json.load(open(p)) if os.path.exists(p) else {}
s = d.setdefault("mcpServers", {})
for n in ("broker", "scheduler", "journal"):
    s[n] = {"command": os.path.join(bin_dir, f"aitrader-{n}-mcp")}
json.dump(d, open(p, "w"), indent=2)
print("  registered broker/scheduler/journal at user scope")
PY

# ── seed agent memory so the store is never EMPTY on first boot ───────────────
# An empty memory_list() gives a fresh agent nothing to anchor on and makes weaker
# models re-query in a loop. One REAL orientation memory short-circuits that.
# ccmemory rebuilds its (derived) index on boot, so writing the .md + clearing the
# index is enough. Seed ONLY an empty store — never clobber the agent's memories.
step "Seed agent memory ($RUN_DIR/.ccmemory)"
CCMEM="$RUN_DIR/.ccmemory"
mkdir -p "$CCMEM"
existing=""
for f in "$CCMEM"/*.md; do
  [ -e "$f" ] || continue                       # no match -> glob stays literal
  [ "$(basename "$f")" = "MEMORY.md" ] || existing=1
done
if [ -n "$existing" ]; then
  info "kept existing agent memories (store not empty)"
else
  cat > "$CCMEM/agent-orientation.md" <<'MEM'
---
name: agent-orientation
description: Agent orientation — journal MCP holds trade state; this store holds durable lessons. Each wake reconcile from the broker, decide, record, then wait. Paper account.
metadata:
  type: project
tags: [orientation, memory, journal, startup]
---

You are the persistent autonomous trading agent. This note (seeded at install, so
your memory is never empty) orients a fresh session.

**Two memory stores, different jobs:**
- **Journal MCP** — ground-truth trade record: positions-of-record (entry rationale,
  thesis, planned exit), equity snapshots, the notebook. Write here on every entry,
  resize, and exit.
- **This ccmemory store** — durable knowledge meant to survive context-fill relays
  and restarts: lessons learned, recurring observations about names/sectors, what
  worked or didn't, standing preferences. Write a memory whenever you learn something
  the next session should know.

**Each wake (the cycle):** reconcile from the broker — it is the source of truth for
positions/orders; never trust memory over the broker — then orient (market, news,
P&L), decide and act by reasoning, record to the journal, and END the cycle in a
scheduler blocking wait. Doing nothing is a valid decision; sleeping correctly is the
default, not back-to-back loops.

**The account is paper** unless the operator has explicitly enabled live. All sizing
and decisions are yours, by reasoning — the infrastructure holds no strategy, caps,
or thresholds.
MEM
  rm -f "$CCMEM"/index.db "$CCMEM"/index.db-* "$CCMEM"/.memory_index.db 2>/dev/null || true
  info "seeded agent-orientation memory (store was empty); cleared index for rebuild"
fi

# Curated trading-wisdom CARDS (prompts/ccmemory-seed/card-*.md). These are CANON: we
# overwrite them on every install so edits propagate to existing nodes (a plain copy-if-
# absent would strand old content after a `git pull`). The agent's own relearning lives in
# DIFFERENTLY-NAMED notes / the journal and is never touched here. We also RETIRE notes we
# shipped earlier and have since folded into the constitution, so a `git pull` + reinstall
# removes them instead of leaving them orphaned in the store.
SEED_SRC="prompts/ccmemory-seed"

# Retirement manifest: prompts/ccmemory-seed/RETIRED (shared with `make const`) —
# previously-seeded names we removed/renamed, plus owner-directed agent-written notes
# that encode a since-fixed infrastructure defect. One name per line, `#` comments.
RETIRED_NOTES=""
[ -f "$SEED_SRC/RETIRED" ] && RETIRED_NOTES=$(sed 's/#.*//' "$SEED_SRC/RETIRED")
removed_notes=0
for name in $RETIRED_NOTES; do
  if [ -e "$CCMEM/$name.md" ]; then
    rm -f "$CCMEM/$name.md" && removed_notes=$((removed_notes + 1))
  fi
done
[ "$removed_notes" -gt 0 ] && info "removed $removed_notes retired lesson note(s) from $CCMEM"

# Install/refresh the curated cards (OVERWRITE — they are canon, not the agent's notes).
seeded_cards=0
if [ -d "$SEED_SRC" ]; then
  for src in "$SEED_SRC"/*.md; do
    [ -e "$src" ] || continue
    install -m 644 "$src" "$CCMEM/$(basename "$src")" && seeded_cards=$((seeded_cards + 1))
  done
  [ "$seeded_cards" -gt 0 ] && info "installed/refreshed $seeded_cards curated card(s) into $CCMEM"
fi

# If we changed the store, clear the derived index so ccmemory rebuilds it on next read.
# A LIVE ccmemory MCP holds the old index inode, so the trader must be restarted after.
if [ "$removed_notes" -gt 0 ] || [ "$seeded_cards" -gt 0 ]; then
  rm -f "$CCMEM"/index.db "$CCMEM"/index.db-* "$CCMEM"/.memory_index.db 2>/dev/null || true
  info "cleared ccmemory index for rebuild — RESTART the trader so the memory MCP re-reads (systemctl --user restart aitrader)"
fi

# ── systemd user units ───────────────────────────────────────────────────────
step "Install systemd --user units ($SVC_DIR)"
mkdir -p "$SVC_DIR"
# Universal units only — the IBKR gateway's own unit (ibgateway.service) is
# installed by gateway/install.sh when broker=ibkr (see the gateway step below).
install -m 644 systemd/aitrader.service systemd/aitrader-api.service \
  systemd/aitrader-ui.service systemd/ibgateway-ready.service \
  systemd/aitrader-snapshot.service systemd/aitrader-snapshot.timer \
  systemd/aitrader-report@.service \
  systemd/aitrader-report@daily.timer systemd/aitrader-report@weekly.timer \
  systemd/aitrader-report@monthly.timer systemd/aitrader-report@yearly.timer "$SVC_DIR"/
systemctl --user daemon-reload 2>/dev/null || echo "  (systemctl --user unavailable here; units copied)"
info "installed aitrader{,-api,-ui}.service, ibgateway-ready.service, snapshot timer, report@{daily,weekly,monthly,yearly} timers"

# ── IBKR gateway (bundled subdir; only for broker=ibkr) ──────────────────────
# The gateway is its own self-contained, idempotent installer (downloads IB
# Gateway + IBC, installs ibgateway.service, seeds ibc/config.ini, and stops at
# its own credentials gate). We descend into it only for broker=ibkr so Alpaca/
# MYSE installs pull none of its X/font deps or binaries. --no-gateway opts out.
if [ "$BROKER" = "ibkr" ] && [ "$NO_GATEWAY" -eq 0 ]; then
  step "Set up IBKR gateway (gateway/)"
  if [ -x "$SRC_DIR/gateway/install.sh" ]; then
    info "descending into gateway/install.sh (IB Gateway + IBC; idempotent)"
    if ( cd "$SRC_DIR/gateway" && ./install.sh ); then
      info "gateway setup complete (fill ~/ibc/config.ini, then: systemctl --user enable --now ibgateway)"
    else
      echo "  WARN: gateway setup did not finish — the IBKR client is installed but has no gateway yet."
      echo "        Resolve the above, then re-run:  ( cd gateway && ./install.sh )"
    fi
  else
    echo "  WARN: gateway/install.sh missing — cannot set up the IBKR gateway."
  fi
fi

ENABLE="systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer aitrader-report@daily.timer aitrader-report@weekly.timer aitrader-report@monthly.timer aitrader-report@yearly.timer"
if [ "$NO_SERVICES" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
  step "Enable services"
  if [ "$BROKER" = "ibkr" ]; then
    echo "  broker=ibkr: bring the gateway up first (systemctl --user enable --now ibgateway), then:"
    echo "    $ENABLE"
  else
    # shellcheck disable=SC2086
    $ENABLE && info "services enabled + started"
  fi
else
  info "skipped enabling (re-run without --no-services, or run): $ENABLE"
fi

# ── done ─────────────────────────────────────────────────────────────────────
step "Done — aitrader installed (broker=$BROKER)"
if [ "$TEMPLATE" -eq 1 ]; then
  cat <<EOF
  NEXT — edit your two files, then start:
    1. $SETTINGS        # broker + ports (defaults 2499/2500 are fine)
    2. $SECRETS         # your broker keys
    3. systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer aitrader-report@daily.timer aitrader-report@weekly.timer aitrader-report@monthly.timer aitrader-report@yearly.timer
EOF
fi
cat <<EOF
  Dashboard API : http://127.0.0.1:$API_PORT/status
  Dashboard UI  : http://127.0.0.1:$UI_PORT
  Live agent    : tmux -L aitrader attach        (Ctrl-b d to detach)
  Logs          : journalctl --user -u aitrader -f
  Config        : $SETTINGS  (+ secrets.toml)
  Stop          : systemctl --user stop aitrader
$( [ "$BROKER" = "ibkr" ] && echo "  Gateway       : edit ~/ibc/config.ini, then systemctl --user enable --now ibgateway (set up under gateway/)" )
EOF
