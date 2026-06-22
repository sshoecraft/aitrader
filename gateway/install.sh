#!/usr/bin/env bash
# Install the aitrader IBKR gateway server (IB Gateway under IBC, headless via Xvfb).
#
# Does the whole bring-up:
#   * installs the X/font system deps the Gateway's Java UI needs,
#   * downloads + installs IB Gateway (IBKR standalone installer, unattended),
#   * downloads + installs IBC (IbcAlpha/IBC latest release) into ~/ibc and wires
#     its gatewaystart.sh to the installed Gateway build,
#   * drops your ibc/config.ini in place (from the example if you haven't already),
#   * installs the ibgateway.service USER unit into ~/.config/systemd/user/.
#
# Every step is idempotent: anything already present is detected and skipped.
#
# This does NOT trade anything by itself, and it does NOT fill in your IBKR
# credentials — edit ~/ibc/config.ini (IbLoginId/IbPassword/TradingMode) after.
# See README.md for the paper/live decision.
#
# Usage:
#   ./install.sh              # full install: deps + IB Gateway + IBC + unit
#   ./install.sh --no-deps    # skip the apt step (deps already present)
#   ./install.sh --no-app     # skip IB Gateway + IBC download (you provide them)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SVC_DIR="${HOME}/.config/systemd/user"
JTS_DIR="${HOME}/Jts"
IBC_DIR="${HOME}/ibc"
INSTALL_DEPS=1
INSTALL_APP=1

IBKR_INSTALLER_URL="https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh"
IBC_API_LATEST="https://api.github.com/repos/IbcAlpha/IBC/releases/latest"

for arg in "$@"; do
  case "$arg" in
    --no-deps) INSTALL_DEPS=0 ;;
    --no-app)  INSTALL_APP=0 ;;
    -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

DEPS="xvfb libxtst6 libxrender1 libxi6 libxext6 libxslt1.1 fontconfig libfreetype6"

echo "==> aitrader IBKR gateway installer"

# Pick how we elevate for apt: root → none, passwordless sudo → sudo, else "".
choose_sudo() {
  if [ "$(id -u)" -eq 0 ]; then echo ""; return 0; fi
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then echo "sudo"; return 0; fi
  return 1
}

# A downloader that follows redirects, retries, and fails loudly. $1=url $2=dest
fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -fSL --retry 3 --retry-delay 2 -o "$2" "$1"
  else
    wget -O "$2" "$1"
  fi
}

# Detect an installed IB Gateway build under ~/Jts/ibgateway/<build>/ (needs jars/).
# IBC requires this nested layout (ibcstart.sh: gateway_program_path=
# ${TWS_PATH}/ibgateway/${TWS_MAJOR_VRSN}); the standalone installer ships flat,
# so install() stages + renames into it. Build name = the jts4launch-<build>.jar.
detect_build() {
  local d
  for d in "$JTS_DIR"/ibgateway/[0-9]*; do
    [ -d "$d/jars" ] && basename "$d"
  done 2>/dev/null | sort -rn | head -1
}

# Pull the build number (e.g. 1045) out of a flat install's jts4launch-<n>.jar.
build_from_jars() {
  local jar
  jar="$(ls "$1"/jars/jts4launch-*.jar 2>/dev/null | head -1)"
  [ -n "$jar" ] && basename "$jar" | sed -E 's/^jts4launch-([0-9]+)\.jar$/\1/'
}

# 1. System deps (Java Swing + Xvfb) ------------------------------------------
if [ "$INSTALL_DEPS" -eq 1 ]; then
  if command -v apt-get >/dev/null 2>&1; then
    # Figure out what's actually missing before touching apt or sudo.
    MISSING_DEPS=""
    if command -v dpkg-query >/dev/null 2>&1; then
      for pkg in $DEPS; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
          MISSING_DEPS="$MISSING_DEPS $pkg"
        fi
      done
      MISSING_DEPS="${MISSING_DEPS# }"
    else
      MISSING_DEPS="$DEPS"  # no dpkg — can't tell, assume all needed
    fi

    if [ -z "$MISSING_DEPS" ]; then
      echo "--> X/font deps already installed"
    elif SUDO="$(choose_sudo)"; then
      echo "--> installing X/font deps: $MISSING_DEPS"
      $SUDO apt-get update -qq
      # shellcheck disable=SC2086
      $SUDO apt-get install -y $MISSING_DEPS
    else
      echo "!!  missing deps and no root/passwordless sudo — install these yourself, then re-run with --no-deps:" >&2
      echo "      sudo apt-get install -y $MISSING_DEPS" >&2
    fi
  else
    echo "!!  no apt-get found — install these with your package manager: $DEPS" >&2
  fi
else
  echo "--> skipping system deps (--no-deps)"
fi

# 2. IB Gateway (IBKR standalone installer, unattended) -----------------------
# 3. IBC (IbcAlpha/IBC) wired to the installed Gateway build ------------------
if [ "$INSTALL_APP" -eq 1 ]; then
  # --- IB Gateway ---
  BUILD="$(detect_build || true)"
  if [ -n "$BUILD" ]; then
    echo "--> IB Gateway already installed ($JTS_DIR/ibgateway/$BUILD)"
  else
    TMP_INSTALLER="$(mktemp --suffix=-ibgateway.sh)"
    STAGING="${JTS_DIR}/ibgateway/.staging-$$"
    trap 'rm -f "$TMP_INSTALLER"; rm -rf "$STAGING"' EXIT
    echo "--> downloading IB Gateway installer (~320MB)"
    fetch "$IBKR_INSTALLER_URL" "$TMP_INSTALLER"
    chmod +x "$TMP_INSTALLER"
    echo "--> installing IB Gateway unattended"
    # install4j -q unattended, -dir target. The standalone installer lays the app
    # out FLAT in -dir, but IBC wants ~/Jts/ibgateway/<build>/, so stage then rename.
    mkdir -p "${JTS_DIR}/ibgateway"
    "$TMP_INSTALLER" -q -dir "$STAGING"
    rm -f "$TMP_INSTALLER"
    BUILD="$(build_from_jars "$STAGING" || true)"
    if [ -z "$BUILD" ]; then
      echo "!!  IB Gateway installed but couldn't determine build (no jts4launch jar in $STAGING/jars)" >&2
      exit 1
    fi
    rm -rf "${JTS_DIR}/ibgateway/${BUILD}"
    mv "$STAGING" "${JTS_DIR}/ibgateway/${BUILD}"
    trap - EXIT
    echo "--> IB Gateway installed: build $BUILD ($JTS_DIR/ibgateway/$BUILD)"
  fi

  # --- IBC ---
  if [ -x "$IBC_DIR/gatewaystart.sh" ]; then
    echo "--> IBC already installed ($IBC_DIR)"
  else
    echo "--> resolving latest IBC release"
    IBC_URL="$(fetch "$IBC_API_LATEST" /dev/stdout 2>/dev/null \
      | grep -Eo 'https://[^"]*IBCLinux-[^"]*\.zip' | head -1)"
    if [ -z "$IBC_URL" ]; then
      echo "!!  could not resolve IBC download URL from $IBC_API_LATEST" >&2
      exit 1
    fi
    TMP_IBC="$(mktemp --suffix=-ibc.zip)"
    trap 'rm -f "$TMP_IBC"' EXIT
    echo "--> downloading IBC: $IBC_URL"
    fetch "$IBC_URL" "$TMP_IBC"
    mkdir -p "$IBC_DIR"
    echo "--> extracting IBC into $IBC_DIR"
    python3 -m zipfile -e "$TMP_IBC" "$IBC_DIR"
    rm -f "$TMP_IBC"; trap - EXIT
    chmod +x "$IBC_DIR"/*.sh "$IBC_DIR"/scripts/*.sh 2>/dev/null || true
    mkdir -p "$IBC_DIR/logs"
    # IBC ships its own generic config.ini (defaults to TradingMode=live,
    # manual API accept, no port override — all wrong for aitrader). Drop it so
    # the seed step below installs aitrader's template instead.
    rm -f "$IBC_DIR/config.ini"
  fi

  # Wire gatewaystart.sh to the real paths + installed build (idempotent: re-run
  # just re-pins these lines, which is what we want if the build changed).
  if [ -f "$IBC_DIR/gatewaystart.sh" ] && [ -n "${BUILD:-}" ]; then
    sed -i \
      -e "s|^TWS_MAJOR_VRSN=.*|TWS_MAJOR_VRSN=${BUILD}|" \
      -e "s|^IBC_PATH=.*|IBC_PATH=${IBC_DIR}|" \
      -e "s|^IBC_INI=.*|IBC_INI=${IBC_DIR}/config.ini|" \
      -e "s|^TWS_PATH=.*|TWS_PATH=${JTS_DIR}|" \
      -e "s|^LOG_PATH=.*|LOG_PATH=${IBC_DIR}/logs|" \
      "$IBC_DIR/gatewaystart.sh"
    echo "--> wired $IBC_DIR/gatewaystart.sh -> build $BUILD, $JTS_DIR, $IBC_DIR"
  fi
else
  echo "--> skipping IB Gateway + IBC download (--no-app)"
fi

# 4. IBC config.ini (your credentials live here; we never overwrite an edited one)
mkdir -p "$IBC_DIR"
if [ ! -f "$IBC_DIR/config.ini" ]; then
  install -m 600 "$REPO_DIR/ibc/config.ini.example" "$IBC_DIR/config.ini"
  echo "--> seeded $IBC_DIR/config.ini from example (EDIT: IbLoginId/IbPassword/TradingMode)"
fi

# 5. Prereq verification -------------------------------------------------------
missing=0
if [ ! -x "$IBC_DIR/gatewaystart.sh" ]; then
  echo "!!  $IBC_DIR/gatewaystart.sh missing/not executable (the IBC gateway launcher)" >&2
  missing=1
fi
if [ -z "$(detect_build || true)" ]; then
  echo "!!  no IB Gateway build found under $JTS_DIR/ibgateway" >&2
  missing=1
fi
if grep -q "your_ibkr_username" "$IBC_DIR/config.ini" 2>/dev/null; then
  echo "!!  $IBC_DIR/config.ini still has placeholder credentials — fill in IbLoginId/IbPassword" >&2
  missing=1
fi

# 6. Install the user unit -----------------------------------------------------
mkdir -p "$SVC_DIR"
install -m 644 "$REPO_DIR/systemd/ibgateway.service" "$SVC_DIR/ibgateway.service"
echo "--> installed $SVC_DIR/ibgateway.service"
systemctl --user daemon-reload

echo
if [ "$missing" -eq 1 ]; then
  echo "Installed, but the items above still need you. Resolve them, then:"
else
  echo "Done. Enable the gateway with:"
fi
echo "    systemctl --user enable --now ibgateway"
echo "    ss -tlnp | grep 4002      # confirm it's listening (4001 if live)"
echo
echo "Then point aitrader's ~/.config/aitrader/secrets.toml at it (ibkr_host/ibkr_port)"
echo "and set broker = \"ibkr\" in settings.toml."
