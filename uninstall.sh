#!/usr/bin/env bash
# aitrader uninstaller — reverses install.sh for the current user.
#
# Stops + removes the systemd user units, the CLI scripts, the installed package,
# the UI, and the run dir, and deregisters the MCP servers. By default it KEEPS
# your data (journal.db) and config (settings.toml/secrets.toml) — pass --purge to
# delete those too (you'll be asked to confirm).
#
# Usage:
#   ./uninstall.sh            # remove install, keep data + config
#   ./uninstall.sh --purge    # also delete journal.db, settings, secrets (confirmed)
#   ./uninstall.sh --purge -y # purge without the confirm prompt
set -euo pipefail

LOCAL_BIN="$HOME/.local/bin"
DATA_DIR="$HOME/.local/share/aitrader"
STATE_DIR="$HOME/.local/state/aitrader"
CONFIG_DIR="$HOME/.config/aitrader"
SVC_DIR="$HOME/.config/systemd/user"

PURGE=0; ASSUME_YES=0
for a in "$@"; do case "$a" in
  --purge) PURGE=1 ;; -y|--yes) ASSUME_YES=1 ;;
  -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $a" >&2; exit 2 ;;
esac; done

info() { echo "  $*"; }
step() { echo; echo "==> $*"; }

UNITS="aitrader.service aitrader-api.service aitrader-ui.service \
ibgateway-ready.service aitrader-snapshot.service aitrader-snapshot.timer"

step "Stop + remove systemd user units"
if command -v systemctl >/dev/null 2>&1; then
  # shellcheck disable=SC2086
  systemctl --user disable --now $UNITS aitrader-snapshot.timer 2>/dev/null || true
fi
for u in $UNITS; do rm -f "$SVC_DIR/$u" && info "removed $u" || true; done
systemctl --user daemon-reload 2>/dev/null || true

step "Remove CLI scripts ($LOCAL_BIN)"
for f in aitrader aitrader-api aitrader-broker-mcp aitrader-scheduler-mcp \
         aitrader-journal-mcp aitrader-snapshot aitrader-ui aitrader-gateway-wait \
         positions trader_ui; do
  rm -f "$LOCAL_BIN/$f" && info "removed $f" || true
done

step "Deregister MCP servers (~/.claude.json)"
python3 - <<'PY' || true
import json, os
p = os.path.expanduser("~/.claude.json")
if os.path.exists(p):
    d = json.load(open(p)); s = d.get("mcpServers", {})
    for n in ("broker", "scheduler", "journal"):
        s.pop(n, None)
    json.dump(d, open(p, "w"), indent=2)
    print("  deregistered broker/scheduler/journal")
PY

step "Uninstall python package"
python3 -m pip uninstall -y --break-system-packages aitrader 2>/dev/null || true

step "Remove UI + run dir"
rm -rf "$DATA_DIR/ui" "$DATA_DIR/run" "$DATA_DIR/prompts" "$DATA_DIR/skills"
info "removed $DATA_DIR/{ui,run,prompts,skills}"

if [ "$PURGE" -eq 1 ]; then
  step "PURGE: delete data + config"
  echo "  This deletes: $STATE_DIR (journal.db!), $CONFIG_DIR (settings + secrets)"
  if [ "$ASSUME_YES" -eq 0 ]; then
    read -r -p "  Type 'purge' to confirm: " ans
    [ "$ans" = "purge" ] || { echo "  aborted purge (install removed, data kept)"; exit 0; }
  fi
  rm -rf "$STATE_DIR" "$CONFIG_DIR"
  info "purged data + config"
else
  step "Kept your data + config"
  info "journal/config preserved: $STATE_DIR , $CONFIG_DIR"
  info "(run with --purge to delete them)"
fi

echo; echo "aitrader uninstalled."
