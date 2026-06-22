import { useState } from 'react';
import type { Position, AvailableTypes } from '../types';
import { getReview } from '../api';
import type { ReviewData } from '../api';

const ASSET_CLASS_TO_TYPE: Record<string, keyof AvailableTypes> = {
  us_equity: 'stock',
  crypto: 'crypto',
  forex: 'forex',
  futures: 'futures',
};

export interface SellResult {
  order_id: string;
  state: string;
}

interface PositionsTableProps {
  positions: Position[];
  onSell: (symbol: string) => Promise<SellResult | null>;
  availableTypes: AvailableTypes;
  totalHeat: number;
}

type SortKey = keyof Position;
type SortDir = 'asc' | 'desc';

const COLUMNS: { key: SortKey; label: string; cls: string }[] = [
  { key: 'symbol',           label: 'Symbol',  cls: 'col-symbol' },
  { key: 'qty',              label: 'Qty',     cls: 'col-qty' },
  { key: 'avg_entry_price',  label: 'Entry',   cls: 'col-number' },
  { key: 'current_price',    label: 'Last',    cls: 'col-number' },
  { key: 'stop',             label: 'Stop',    cls: 'col-number' },
  { key: 'limit_price',      label: 'Limit',   cls: 'col-number' },
  { key: 'market_value',     label: 'Mkt Val', cls: 'col-number' },
  { key: 'unrealized_pl',    label: 'P&L',     cls: 'col-number' },
  { key: 'unrealized_plpc',  label: 'P&L %',   cls: 'col-number' },
  { key: 'heat',             label: 'Heat',    cls: 'col-number' },
  { key: 'to_stp',           label: '% Stop',  cls: 'col-number' },
  { key: 'to_lim',           label: '% Lim',   cls: 'col-number' },
];

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value);
}
function formatPrice(value: number): string { return value.toFixed(2); }
function formatPercent(value: number): string { return (value * 100).toFixed(2) + '%'; }
function formatSignedPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
}
function formatSignedCurrency(value: number): string {
  return `${value >= 0 ? '+' : '−'}$${formatCurrency(Math.abs(value))}`;
}
function formatQty(qty: number): string {
  if (Number.isInteger(qty)) return qty.toString();
  return qty.toFixed(4);
}

function sortPositions(positions: Position[], key: SortKey, dir: SortDir): Position[] {
  return [...positions].sort((a, b) => {
    const av = a[key] ?? 0;
    const bv = b[key] ?? 0;
    let cmp: number;
    if (typeof av === 'string' && typeof bv === 'string') {
      cmp = av.localeCompare(bv);
    } else {
      cmp = (Number(av) || 0) - (Number(bv) || 0);
    }
    return dir === 'asc' ? cmp : -cmp;
  });
}

function FormattedReview({ data }: { data: ReviewData }) {
  const content = data.content ?? '';
  let promptText = '';
  let jsonObj: Record<string, unknown> | null = null;

  if (data.record) {
    jsonObj = data.record;
    if (typeof jsonObj.response === 'object' && jsonObj.response !== null) {
      jsonObj = jsonObj.response as Record<string, unknown>;
    }
  } else {
    const promptMatch = content.match(/---\s*PROMPT\s*---\s*\n([\s\S]*?)(?=\n---\s*RESPONSE\s*---)/);
    const respMatch = content.match(/---\s*RESPONSE\s*---\s*\n([\s\S]*?)(?=\n---\s*PARSED\s*---|$)/);

    if (promptMatch) {
      promptText = promptMatch[1].replace(/\nStep \d:[\s\S]*$/, '').trim();
    }
    if (respMatch) {
      const text = respMatch[1].trim();
      const jsonMatch = text.match(/\{[\s\S]*\}\s*$/);
      if (jsonMatch) {
        try { jsonObj = JSON.parse(jsonMatch[0]); } catch { /* skip */ }
      }
    }
    if (!jsonObj) {
      const parsedMatch = content.match(/---\s*PARSED\s*---\s*\n([\s\S]*?)$/);
      if (parsedMatch) {
        try { jsonObj = JSON.parse(parsedMatch[1].trim()); } catch { /* skip */ }
      }
    }
  }

  if (!jsonObj) {
    return <pre className="review-content">{content || 'No review content available'}</pre>;
  }

  return (
    <div className="review-formatted">
      {promptText && <div className="review-prompt">{promptText}</div>}
      <div className="review-response">
        {Object.entries(jsonObj).map(([key, val]) => (
          <div key={key} className="review-field">
            <span className="review-field-key">{key}</span> {String(val)}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PositionsTable({ positions, onSell, availableTypes, totalHeat }: PositionsTableProps) {
  const [confirmSymbol, setConfirmSymbol] = useState<string | null>(null);
  const [selling, setSelling] = useState<string | null>(null);
  const [closingSymbols, setClosingSymbols] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>('unrealized_pl');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewSymbol, setReviewSymbol] = useState<string>('');

  async function handleSymbolClick(symbol: string) {
    setReviewData(null);
    setReviewError(null);
    setReviewLoading(true);
    setReviewSymbol(symbol);
    try {
      const data = await getReview(symbol);
      if (data) setReviewData(data);
      else setReviewError(`No review found for ${symbol}.`);
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : 'Failed to load review.');
    } finally {
      setReviewLoading(false);
    }
  }

  function closeReview() {
    setReviewData(null);
    setReviewError(null);
    setReviewSymbol('');
  }

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'symbol' ? 'asc' : 'desc');
    }
  }

  const sorted = sortPositions(positions, sortKey, sortDir);

  const totalValue = positions.reduce((s, p) => s + p.market_value, 0);
  const totalPL    = positions.reduce((s, p) => s + p.unrealized_pl, 0);
  const totalCost  = totalValue - totalPL;
  const totalPLPct = totalCost !== 0 ? totalPL / totalCost : 0;

  async function handleSell(symbol: string) {
    if (confirmSymbol !== symbol) {
      setConfirmSymbol(symbol);
      return;
    }
    setSelling(symbol);
    setConfirmSymbol(null);
    try {
      const result = await onSell(symbol);
      if (result?.order_id) {
        setClosingSymbols(prev => new Set(prev).add(symbol));
      }
    } finally {
      setSelling(null);
    }
  }

  return (
    <>
      <div className="section-head">
        <div className="section-head-title">
          <span className="section-marker">§</span>
          <h2>Positions</h2>
        </div>
        <div className="section-meta">
          {positions.length} OPEN · HEAT {(totalHeat * 100).toFixed(1)}%
        </div>
      </div>
      <div className="section-rule" />

      {positions.length === 0 ? (
        <div className="empty-state">no open positions</div>
      ) : (
        <div className="table-container">
          <table className="ledger">
            <thead>
              <tr>
                {COLUMNS.map(col => {
                  const active = sortKey === col.key;
                  return (
                    <th
                      key={col.key}
                      className={`${col.cls} sortable ${active ? 'active' : ''}`}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}
                      {active && (
                        <span className="sort-arrow">{sortDir === 'asc' ? '▲' : '▼'}</span>
                      )}
                    </th>
                  );
                })}
                <th className="col-action">Action</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(pos => {
                const plClass = pos.unrealized_pl >= 0 ? 'positive' : 'negative';
                const isConfirming = confirmSymbol === pos.symbol;
                const isSelling = selling === pos.symbol;
                const isClosing = closingSymbols.has(pos.symbol);
                const typeKey = ASSET_CLASS_TO_TYPE[pos.asset_class] ?? 'stock';
                const tradable = availableTypes[typeKey];
                const stopStr  = pos.has_broker_stop ? formatPrice(pos.stop) : `~${formatPrice(pos.stop)}`;
                const limitStr = pos.has_broker_limit ? formatPrice(pos.limit_price) : `~${formatPrice(pos.limit_price)}`;

                return (
                  <tr key={pos.symbol}>
                    <td className="col-symbol">
                      <button className="symbol-link" onClick={() => handleSymbolClick(pos.symbol)}>
                        {pos.symbol}
                      </button>
                    </td>
                    <td className="col-qty mono">{formatQty(pos.qty)}</td>
                    <td className="mono">{formatPrice(pos.avg_entry_price)}</td>
                    <td className="mono">{formatPrice(pos.current_price)}</td>
                    <td className={`mono ${pos.has_broker_stop ? '' : 'text-muted'}`}>{stopStr}</td>
                    <td className={`mono ${pos.has_broker_limit ? '' : 'text-muted'}`}>{limitStr}</td>
                    <td className="mono">{formatCurrency(pos.market_value)}</td>
                    <td className={`mono ${plClass}`}>{formatSignedCurrency(pos.unrealized_pl)}</td>
                    <td className={`mono ${plClass}`}>{formatSignedPct(pos.unrealized_plpc)}</td>
                    <td className="mono">{formatPercent(pos.heat)}</td>
                    <td className="mono">{formatPercent(pos.unrealized_pl < 0 ? pos.to_stp : 0)}</td>
                    <td className="mono">{formatPercent(pos.unrealized_pl >= 0 ? pos.to_lim : 0)}</td>
                    <td className="col-action">
                      {isSelling ? (
                        <span className="selling-text">Selling…</span>
                      ) : isClosing ? (
                        <span className="selling-text">Closing…</span>
                      ) : isConfirming ? (
                        <span className="confirm-group">
                          <button className="btn-confirm" onClick={() => handleSell(pos.symbol)}>Yes</button>
                          <button className="btn-cancel"  onClick={() => setConfirmSymbol(null)}>No</button>
                        </span>
                      ) : (
                        <button
                          className="btn-sell"
                          onClick={() => handleSell(pos.symbol)}
                          disabled={!tradable}
                          title={tradable ? 'Sell position' : 'Market closed'}
                        >
                          {tradable ? 'Sell' : 'Closed'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="totals-row">
                <td className="col-symbol">Totals · {positions.length}</td>
                <td colSpan={5} />
                <td className="mono">{formatCurrency(totalValue)}</td>
                <td className={`mono ${totalPL >= 0 ? 'positive' : 'negative'}`}>
                  {formatSignedCurrency(totalPL)}
                </td>
                <td className={`mono ${totalPLPct >= 0 ? 'positive' : 'negative'}`}>
                  {formatSignedPct(totalPLPct)}
                </td>
                <td className="mono">{formatPercent(totalHeat)}</td>
                <td />
                <td />
                <td className="col-action" />
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {(reviewData || reviewLoading || reviewError) && (
        <div className="review-backdrop" onClick={closeReview}>
          <div className="review-modal" onClick={e => e.stopPropagation()}>
            <div className="review-header">
              <span className="review-title">
                {reviewSymbol || reviewData?.symbol || ''} — Review
              </span>
              <button className="review-close" onClick={closeReview}>×</button>
            </div>
            <div className="review-body">
              {reviewLoading ? (
                <div className="review-loading">Loading review…</div>
              ) : reviewError ? (
                <div className="review-loading">{reviewError}</div>
              ) : reviewData ? (
                <FormattedReview data={reviewData} />
              ) : null}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
