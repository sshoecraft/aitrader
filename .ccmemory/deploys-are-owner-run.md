---
name: deploys-are-owner-run
description: Standing rule (2026-07-10): Claude NEVER installs/deploys to the trader nodes (no make world/full/const/install, no service restarts) — the owner run…
metadata:
  type: feedback
tags: [deploy, boundary, owner, make-world]
---

# Deploys are owner-run — standing rule (2026-07-10)

Owner's directive after a day of rapid ship cycles: **"from now on, don't
install: I'll do it."**

- Claude prepares changes in /src/aitrader (code, constitution, version,
  CHANGELOG, docs, memories) and TESTS what's testable read-only or via
  source-tree runs (PYTHONPATH=/src/aitrader as an instance user is fine for
  data reads).
- Claude does NOT run `make world/full/const/install`, `./install.sh`, or any
  `systemctl` against the trader nodes. When something is ready, say so and
  state the command (canonical deploy verb: `make world` per instance user).
- Verification AFTER the owner deploys is fine and expected (read-only:
  versions, run-dir CLAUDE.md, journals, /status, CSV contents).

Context: earlier the same day Claude also wrote to /src during the owner's NFS
repair (see [[pre-testweek-hardening-plan]]) — same lesson family: the owner
owns mutations to shared infrastructure; Claude owns preparation and evidence.
