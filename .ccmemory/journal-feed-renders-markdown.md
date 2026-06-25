---
name: journal-feed-renders-markdown
description: 1.17.0: dashboard JournalFeed renders Markdown via react-markdown + remark-gfm (GFM tables); the agent journals in Markdown so this is load-bearing.
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

## Don't regress
- Do NOT revert to `<div className="journal-text">{entry.text}</div>` or drop react-markdown/remark-gfm —
  tables go back to raw `|`-pipes in serif. remark-gfm is REQUIRED for tables (plain CommonMark has none).
- Keep the `.markdown` `white-space:normal` override; pre-wrap on rendered block elements double-spaces.
- Deploy: `make ui` (rebuilds to `~/.local/share/aitrader/ui`; assets are content-hashed → hard-refresh).
  Build is `tsc -b && vite build`. Related: [[aitrader-ui-build-deploy]].
