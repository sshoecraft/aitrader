---
name: journal-feed-renders-markdown
description: JournalFeed renders Markdown via react-markdown + remark-gfm; normalizeTables repairs BOTH GFM defects — missing blank line (1.42.2) + missing delimi…
metadata:
  type: project
tags: [ui, journal, markdown, rendering]
---

The aitrader agent journals in **Markdown** — survey/ranking **GFM tables** especially (the constitution's
step-3 SURVEY table, step-4 REVIEW/GATE tables). The dashboard journal feed must render it as Markdown, not raw text.

## Implementation (1.17.0, ui 1.5.3→1.6.0)
- `ui/src/components/JournalFeed.tsx`: each entry's `text` renders via
  `<ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeTables(entry.text)}</ReactMarkdown>` inside
  `<div className="journal-text markdown">`. Deps: `react-markdown@^9` + `remark-gfm@^4` (React 19 compatible).
  react-markdown does NOT render raw HTML by default → safe to display agent text.
- `ui/src/App.css`: Markdown styling scoped to `.journal-text.markdown`. TABLES = monospace `--mono` 11.5px,
  `display:block; overflow-x:auto`, cells `white-space:nowrap`. Base `.journal-text` `white-space:pre-wrap`
  is RESET to `normal` for the `.markdown` variant.

## normalizeTables repairs TWO distinct GFM defects — display-only, DB never rewritten
1. **Missing blank line (1.42.2).** Agent opens a table under a label ("REVIEW:") or list item ("- GATE:");
   remark-gfm treats a pipe row after a non-blank line as lazy paragraph continuation. Fix = blank line at
   every pipe/non-pipe boundary.
2. **Missing delimiter row (1.49.9).** Agent reproduces the constitution's templates but intermittently drops
   the `|---|---|` row under the header (~8 of 53 recent pipe-bearing entries; older ones have it → model
   variance, NOT a template defect — the constitution's §3/§4(a) templates DO carry it). GFM *requires* it.
   Fix = synthesize a delimiter with the header's cell count + indentation. Guards: only when another pipe row
   sits beneath (a lone pipe row is prose, not a 1-col table); never when a delimiter already exists.

## Symptom → diagnosis (don't re-derive this)
Run-on pipe soup in the UI is **almost never a malformed journal body**. The tell is ADJACENT PIPES —
`| verdict | | futures |` = two rows collapsed into one paragraph line by soft-break-to-space. Check raw bytes
first (`sqlite3 ~/.local/state/aitrader/journal.db`, table `journal`, cols id/ts/kind/symbol/body/tags), then
ask which of the two GFM requirements is absent. 1.42.2's note that "the DB body is already valid" was true of
*that* bug only — 1.49.9's bodies are well-formed in content but NOT valid GFM.

## Don't regress
- Do NOT drop react-markdown/remark-gfm or `normalizeTables`. remark-gfm is REQUIRED for tables.
- Do NOT fix this class by prompting the agent — the templates are already correct; it's model variance.
  (Also: constitution edits need backup + higher-order review — [[constitution-edit-protocol]].)
- Keep the `.markdown` `white-space:normal` override.
- Regression-check any change here by REPLAYING real entries through react-markdown and diffing `<table>`
  counts before/after (1.49.9: 276 entries → 25 gained, 251 unchanged, 0 regressed). Node lives at
  `~/.cache/aitrader/node-v22.21.1-linux-x64/bin`; symlink `ui/node_modules` into a scratch dir + a
  `{"type":"module"}` package.json to get ESM resolution without putting temp files in the project.
- Deploy: `make ui` (owner-run — [[deploys-are-owner-run]]); content-hashed assets → hard-refresh.
  Related: [[aitrader-ui-build-deploy]].
