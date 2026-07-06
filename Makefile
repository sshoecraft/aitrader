# aitrader — build & install.
#
#   make build           — build wheel into dist/  (from NFS source; build-time only)
#   make install         — install to ~/.local (LOCAL disk) + run dir + systemd units (if absent)
#   make install-service — (re)install --user systemd units (force) + daemon-reload
#   make full            — build + install + restart the aitrader service (redeploy)
#   make restart         — restart the aitrader service
#   make run-dir         — (re)create the run dir (CLAUDE.md, model) + register MCP at user scope
#   make const           — deploy the constitution (prompts/constitution.md -> run dir CLAUDE.md) + restart aitrader
#   make uninstall / make clean
#
# Nothing here is run from /src at runtime: the package installs into
# ~/.local/lib, console scripts land in ~/.local/bin, the agent's prose installs
# into the run dir + ~/.local/share/aitrader. The source tree (NFS) is only
# touched to build.

# NOTE: no inline `#` comments on := lines — Make would keep the trailing spaces.
SHELL      := /bin/bash
LOCAL_BIN  := $(HOME)/.local/bin
DATA_DIR   := $(HOME)/.local/share/aitrader
RUN_DIR    := $(DATA_DIR)/run
# STATE_DIR = journal.db + logs (XDG state).
STATE_DIR  := $(HOME)/.local/state/aitrader
# UI_DIR = where trader_ui serves the built SPA from; UI_SRC = the UI source (this
# repo's ui/). The API port is injected at runtime via trader_ui's /config.js, so
# nothing is baked into the build.
UI_DIR     := $(HOME)/.local/share/aitrader/ui
UI_SRC     := ui
NODE_VERSION := 22.21.1
# SVC_DIR = ~/.config/systemd/user (--user units; linger enabled), like the box convention.
SVC_DIR    := $(HOME)/.config/systemd/user
WHEEL       = $(shell ls -t dist/*.whl 2>/dev/null | head -1)
# BROKER = execution backend from settings.toml; drives which pip extra installs
# (the [ibkr] extra only for ibkr). Falls back to ibkr if the package/settings
# aren't readable yet. (The IBKR gateway unit lives in the bundled gateway/ subdir.)
BROKER      = $(shell python3 -c 'from aitrader.config import settings; print(settings().broker)' 2>/dev/null || echo ibkr)

.PHONY: help build install install-service install-units-ifabsent full restart run-dir ui api const uninstall clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?#' $(MAKEFILE_LIST) | sed 's/:.*#/\t/' | sort

build: clean  ## build wheel into dist/
	python3 -m pip wheel --no-deps --wheel-dir dist .
	@echo "Built: $$(ls dist/*.whl)"

install: ## install to ~/.local (with deps) + run dir + systemd units (if absent)
	@WHL=$$(ls -t dist/*.whl 2>/dev/null | head -1); \
	if [ -z "$$WHL" ]; then echo "No wheel — run 'make build' first"; exit 1; fi; \
	EXTRAS="api,calendar,sandbox"; \
	if [ "$(BROKER)" = "ibkr" ]; then EXTRAS="$$EXTRAS,ibkr"; fi; \
	pip3 install --user --break-system-packages --force-reinstall "$$WHL[$$EXTRAS]"
	@$(MAKE) --no-print-directory run-dir
	@mkdir -p $(LOCAL_BIN)
	@install -m 755 bin/* $(LOCAL_BIN)/ 2>/dev/null && echo "  installed CLI scripts: $$(ls bin/ | tr '\n' ' ')" || true
	@$(MAKE) --no-print-directory install-units-ifabsent
	@echo "Installed. console scripts + 'aitrader' launcher + CLIs in $(LOCAL_BIN); run dir $(RUN_DIR)"
	@echo "Enable the snapshot recorder: systemctl --user enable --now aitrader-snapshot.timer"

install-units-ifabsent: ## install --user systemd units ONLY if absent (used by 'make install'); reload if changed
	@mkdir -p $(SVC_DIR)
	@changed=0; \
	units="aitrader.service aitrader-api.service aitrader-ui.service ibgateway-ready.service aitrader-snapshot.service aitrader-snapshot.timer"; \
	for u in $$units; do \
		if [ -e $(SVC_DIR)/$$u ]; then echo "  kept existing $$u"; \
		else install -m 644 systemd/$$u $(SVC_DIR)/$$u && echo "  + installed $$u" && changed=1; fi; \
	done; \
	echo "  (IBKR gateway unit installed by gateway/install.sh, not here)"; \
	if [ $$changed -eq 1 ]; then systemctl --user daemon-reload && echo "  daemon-reloaded"; else echo "  no unit changes"; fi

run-dir: ## (re)create the ccloop run dir (CLAUDE.md, model) + register MCP servers at USER scope
	@mkdir -p $(RUN_DIR)/.claude $(HOME)/.config/aitrader
	@install -m 644 prompts/constitution.md $(RUN_DIR)/CLAUDE.md
	@if [ ! -f $(HOME)/.config/aitrader/settings.toml ]; then \
		install -m 644 settings.toml.example $(HOME)/.config/aitrader/settings.toml; \
		echo "  seeded ~/.config/aitrader/settings.toml (edit criteria/prompt there)"; \
	else echo "  kept existing ~/.config/aitrader/settings.toml"; fi
	@python3 -c 'import json,os,sys; p=os.path.expanduser("~/.claude.json"); d=json.load(open(p)) if os.path.exists(p) else {}; s=d.setdefault("mcpServers",{}); s.update({n:{"command":sys.argv[1]+"/aitrader-"+n+"-mcp"} for n in ("broker","scheduler","journal")}); json.dump(d,open(p,"w"),indent=2); print("  registered broker/scheduler/journal MCP servers at USER scope in",p)' "$(LOCAL_BIN)"
	@rm -f $(RUN_DIR)/.mcp.json
	@if [ ! -f $(RUN_DIR)/.claude/settings.json ]; then \
		printf '{\n  "model": "opus"\n}\n' > $(RUN_DIR)/.claude/settings.json; \
		echo "  wrote $(RUN_DIR)/.claude/settings.json (model: opus)"; \
	else echo "  kept existing $(RUN_DIR)/.claude/settings.json"; fi
	@echo "  run dir ready: $(RUN_DIR)"

const: ## deploy the constitution (prompts/constitution.md -> run dir CLAUDE.md) + restart aitrader
	@mkdir -p $(RUN_DIR)
	@install -m 644 prompts/constitution.md $(RUN_DIR)/CLAUDE.md
	@echo "  deployed constitution -> $(RUN_DIR)/CLAUDE.md"
	@if [ -f $(SVC_DIR)/aitrader.service ]; then \
		systemctl --user restart aitrader && echo "  restarted aitrader (fresh session loads the new constitution; agent reconciles from broker + journal)"; \
	else echo "  (aitrader.service not installed yet — agent will load it on its next relay; or 'make install-service' / ./install.sh)"; fi

ui: ## build the dashboard UI (ui/) + (re)deploy + restart the aitrader-ui service (needs node)
	@mkdir -p $(UI_DIR) $(LOCAL_BIN)
	cd $(UI_SRC) && \
		if ! command -v npm >/dev/null 2>&1; then \
			[ -s $(HOME)/.nvm/nvm.sh ] && . $(HOME)/.nvm/nvm.sh; \
			NODE_BIN="$${XDG_CACHE_HOME:-$(HOME)/.cache}/aitrader/node-v$(NODE_VERSION)-linux-x64/bin"; \
			[ -x "$$NODE_BIN/npm" ] && PATH="$$NODE_BIN:$$PATH"; \
		fi; \
		command -v npm >/dev/null 2>&1 || { echo "  no npm — run ./install.sh once to bootstrap Node v$(NODE_VERSION)"; exit 1; }; \
		npm run build -- --outDir $(UI_DIR) --emptyOutDir
	install -m 755 $(UI_SRC)/bin/trader_ui $(LOCAL_BIN)/trader_ui
	@echo "Built UI -> $(UI_DIR) (API port injected at runtime); launcher -> $(LOCAL_BIN)/trader_ui"
	@if [ -f $(SVC_DIR)/aitrader-ui.service ]; then \
		systemctl --user restart aitrader-ui && echo "  restarted aitrader-ui (hard-refresh the browser; assets are content-hashed)"; \
	else echo "  (aitrader-ui.service not installed yet — run 'make install-service' or ./install.sh)"; fi

world:
	@$(MAKE) api
	@$(MAKE) ui
	@$(MAKE) full
	@$(MAKE) const

install-service: ## (re)install --user systemd units (force) + reload
	@mkdir -p $(SVC_DIR)
	install -m 644 systemd/aitrader.service systemd/aitrader-api.service systemd/aitrader-ui.service \
		systemd/ibgateway-ready.service systemd/aitrader-snapshot.service systemd/aitrader-snapshot.timer $(SVC_DIR)/
	systemctl --user daemon-reload
	@echo "Units installed. Enable: systemctl --user enable --now aitrader aitrader-api aitrader-ui aitrader-snapshot.timer"
	@if [ "$(BROKER)" = "ibkr" ]; then \
		echo "  broker=ibkr: set up the gateway first: ( cd gateway && ./install.sh ), then enable ibgateway."; \
	fi

restart: ## restart the aitrader service (safe: agent reconciles from broker+journal on relaunch)
	systemctl --user restart aitrader

api: build ## redeploy the dashboard API: rebuild the package + restart aitrader-api
	@WHL=$$(ls -t dist/*.whl 2>/dev/null | head -1); \
	if [ -z "$$WHL" ]; then echo "No wheel — run 'make build' first"; exit 1; fi; \
	EXTRAS="api,calendar,sandbox"; \
	if [ "$(BROKER)" = "ibkr" ]; then EXTRAS="$$EXTRAS,ibkr"; fi; \
	pip3 install --user --break-system-packages --force-reinstall "$$WHL[$$EXTRAS]"
	@if [ -f $(SVC_DIR)/aitrader-api.service ]; then \
		systemctl --user restart aitrader-api && echo "  restarted aitrader-api"; \
	else echo "  (aitrader-api.service not installed yet — run 'make install-service' or ./install.sh)"; fi

full: build install ## redeploy: build + install + restart the running service (like trader)
	@if [ -f $(SVC_DIR)/aitrader.service ]; then \
		systemctl --user daemon-reload && systemctl --user restart aitrader && \
		echo "Redeployed + restarted aitrader."; \
	else \
		echo "Installed. Run 'make install-service' once, then 'systemctl --user enable --now aitrader'."; \
	fi

uninstall: ## remove the installed package (leaves run dir + data)
	pip3 uninstall -y --break-system-packages aitrader 2>/dev/null || true

clean: ## remove build artifacts
	rm -rf build/ dist/ *.egg-info aitrader.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
