import { useState, useEffect, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { TradePeriod, JournalEntry } from '../types';
import { getJournal } from '../api';

const PERIODS: TradePeriod[] = ['1D', '1W', '1M', '3M', '6M', '1Y', 'YTD', 'ALL'];
const DEFAULT_LIMIT = 100;

// time arrives as ISO-8601 UTC; new Date() parses the offset correctly. Display
// in the viewer's LOCAL time (no forced timeZone); "06/16 09:32" compact form.
const LOCAL_FMT = new Intl.DateTimeFormat('en-US', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});
function formatLocalTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const parts = LOCAL_FMT.formatToParts(d);
  const get = (t: string) => parts.find(p => p.type === t)?.value ?? '';
  return `${get('month')}/${get('day')} ${get('hour')}:${get('minute')}`;
}

// Map the period selector to a `since` instant, computed client-side. ALL → no
// bound. YTD → Jan 1 of the current year. Others → now minus the window.
function sinceFor(period: TradePeriod): string | undefined {
  if (period === 'ALL') return undefined;
  const now = new Date();
  if (period === 'YTD') {
    return new Date(Date.UTC(now.getUTCFullYear(), 0, 1)).toISOString();
  }
  const d = new Date(now);
  switch (period) {
    case '1D': d.setDate(d.getDate() - 1); break;
    case '1W': d.setDate(d.getDate() - 7); break;
    case '1M': d.setMonth(d.getMonth() - 1); break;
    case '3M': d.setMonth(d.getMonth() - 3); break;
    case '6M': d.setMonth(d.getMonth() - 6); break;
    case '1Y': d.setFullYear(d.getFullYear() - 1); break;
  }
  return d.toISOString();
}

// The agent journals GFM tables that often start on the line directly after a
// section label ("REVIEW:") or inside a list item ("- GATE:"). remark-gfm
// treats those pipe rows as lazy paragraph continuation, so no table renders —
// the pipes come out as run-on text. Guarantee a blank line on each side of
// every pipe-table block so the table always parses as its own block.
function normalizeTables(text: string): string {
  const isPipeRow = (s: string) => /^\s*\|.*\|\s*$/.test(s);
  const lines = text.split('\n');
  const out: string[] = [];
  for (const line of lines) {
    const prev = out.length > 0 ? out[out.length - 1] : '';
    const boundary =
      out.length > 0 && prev.trim() !== '' && isPipeRow(line) !== isPipeRow(prev);
    if (boundary) out.push('');
    out.push(line);
  }
  return out.join('\n');
}

function JournalRow({ entry }: { entry: JournalEntry }) {
  const risk = entry.meta && 'risk_check_passed' in entry.meta
    ? Boolean(entry.meta.risk_check_passed)
    : null;

  return (
    <article className="journal-entry">
      <div className="journal-entry-head">
        <span className="journal-time mono">{formatLocalTime(entry.time)}</span>
        {entry.kind && <span className="badge badge-kind">{entry.kind}</span>}
        {entry.symbol && <span className="badge badge-symbol">{entry.symbol}</span>}
        {entry.tags && <span className="badge badge-tag">{entry.tags}</span>}
        {risk !== null && (
          <span className={`badge ${risk ? 'badge-ok' : 'badge-fail'}`}>
            {risk ? '✓' : '✗'} risk
          </span>
        )}
      </div>
      <div className="journal-text markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeTables(entry.text)}</ReactMarkdown>
      </div>
    </article>
  );
}

interface JournalFeedProps {
  reloadKey?: number;
}

export default function JournalFeed({ reloadKey = 0 }: JournalFeedProps) {
  const [period, setPeriod] = useState<TradePeriod>('1D');
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (p: TradePeriod) => {
    setLoading(true);
    try {
      const data = await getJournal({ limit: DEFAULT_LIMIT, since: sinceFor(p) });
      setEntries(data.entries);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load journal';
      setError(msg);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(period); }, [period, reloadKey, load]);

  // Newest first.
  const sorted = useMemo(
    () => [...entries].sort((a, b) => b.time.localeCompare(a.time)),
    [entries],
  );

  return (
    <section className="panel">
      <div className="section-head">
        <div className="section-head-title">
          <span className="section-marker">§</span>
          <h2>Journal</h2>
        </div>
        <div className="trades-controls">
          <span className="section-meta">{sorted.length} ENTRIES</span>
          <select
            className="trades-period"
            value={period}
            onChange={e => setPeriod(e.target.value as TradePeriod)}
            disabled={loading}
            aria-label="Journal period"
          >
            {PERIODS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>
      <div className="section-rule" />

      {error ? (
        <div className="empty-state">{error}</div>
      ) : loading && entries.length === 0 ? (
        <div className="empty-state">loading…</div>
      ) : sorted.length === 0 ? (
        <div className="empty-state">no journal entries in period</div>
      ) : (
        <div className="journal-feed">
          {sorted.map(e => <JournalRow key={e.id} entry={e} />)}
        </div>
      )}
    </section>
  );
}
