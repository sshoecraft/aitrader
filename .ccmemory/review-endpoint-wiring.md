---
name: review-endpoint-wiring
description: aitrader 0.14.0: /review (was 404 stub) serves agent rationale = positions_of_record + symbol journal entries. Constitution now MANDATES position_rec…
metadata:
  type: project
---

**What.** trader-ui's click-a-held-symbol panel calls `GET /review?symbol=`
(`api.ts getReview`, rendered by `PositionsTable.tsx FormattedReview`). aitrader
had stubbed `/review` to a flat `404` (leftover from gutting /src/trader's
reviewer cognition). 0.14.0 wires it to surface the agent's OWN recorded
rationale — pure read, no scoring/reviewer:
- `positions_of_record` (via `por_get`): `entry_rationale`, `thesis`,
  `planned_exit`, status/opened — the bullseye "why purchased".
- that symbol's `journal` entries (via `journal_read`) as a chronological log.
- Returns UI `ReviewData` with `content` = preformatted text + `format:"text"`
  (UI falls back to `<pre>`; avoid `--- PROMPT/RESPONSE/PARSED ---` markers in
  content or FormattedReview tries to parse it as a /src/trader log). Still 404
  if nothing recorded. Matches crypto under slash or no-slash keying.

**No new journal tool was needed** — `position_record_upsert` already captures
the why. Deploy = API-only: `make build+install` + `systemctl --user restart
aitrader-api` (see [[api-service-deploy-path]]).

**Populating it — now mandated.** The new S-objective `prompts/constitution.md`
(deployed 2026-06-18) originally had NO recording instruction, so positions
opened under it risked never getting `position_record_upsert` → stale `/review`.
Fixed: added a "Recording Requirement (MANDATORY)" section to the constitution —
"on every entry or material resize, call position_record_upsert(symbol,
entry_rationale, thesis, planned_exit); on exit update status" + explicit "does
NOT enter the S calculation" so it's record-keeping, not a decision input.
Deployed via `make run-dir` + agent restart. Note: free-form journal notes are
written with symbol=NULL, so POR is what feeds the per-symbol panel.
