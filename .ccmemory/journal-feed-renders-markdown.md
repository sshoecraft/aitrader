---
name: journal-feed-renders-markdown
description: JournalFeed renders Markdown via react-markdown + remark-gfm; 1.42.2 normalizeTables blank-lines pipe blocks (labels/list items swallowed tables).
metadata:
  type: project
---

The aitrader agent journals in **Markdown** — survey/ranking **GFM tables** especially (the constitution's
step-4 SURVEY table, step-6 RANK list). The dashboard journal feed must render it as Markdown, not raw text.

## Implementation (1.17.0, ui 1.5.3→1.6.0)
- `ui/src/components/JournalFeed.tsx`: each entry's `text` renders via
  `<ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.text}</ReactMarkdown>` inside
  `<div className="journal-text markdown">`. Deps: `react-markdown@^9` + `remark-gfm@^4` (React 19 compatible).
  react-markdown does NOT render raw HTML by default → safe to display agent text.
- `ui/src/App.css`: Markdown styling scoped to `.journal-text.markdown` (headings, lists, code, blockquote,
  hr, links, tables) using existing tokens. TABLES = monospace `--mono` 11.5px, `display:block;
  overflow-x:auto`, cells `white-space:nowrap` → a wide survey table on the narrow journal rail scrolls
  horizontally instead of wrapping. The base `.journal-text` `white-space:pre-wrap` is RESET to `normal`
  for the `.markdown` variant.

## normalizeTables (1.42.2) — tables under labels/list items
The agent opens tables directly under a section label ("REVIEW:") or inside a list item ("- GATE:");
remark-gfm treats a pipe row after a non-blank line as lazy paragraph continuation → run-on pipe soup
(SURVEY rendered only because it's top-level). `normalizeTables` in JournalFeed.tsx inserts a blank line
at every pipe/non-pipe boundary before ReactMarkdown. The DB body is correct and untouched — this is
display-only normalization; verified against journal id 298's raw bytes.

## Don't regress
- Do NOT revert to `<div className="journal-text">{entry.text}</div>` or drop react-markdown/remark-gfm —
  tables go back to raw `|`-pipes in serif. remark-gfm is REQUIRED for tables (plain CommonMark has none).
- Do NOT remove `normalizeTables`, and do NOT try to fix table rendering by prompting the agent to
  journal differently — the body in the DB is the record and is already valid.
- Keep the `.markdown` `white-space:normal` override; pre-wrap on rendered block elements double-spaces.
- Deploy: `make ui` (rebuilds to `~/.local/share/aitrader/ui`; assets are content-hashed → hard-refresh).
  Build is `tsc -b && vite build`. Related: [[aitrader-ui-build-deploy]].
