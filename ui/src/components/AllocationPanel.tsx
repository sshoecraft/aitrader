import { useMemo, useState } from 'react';
import type React from 'react';
import type { Position, AccountInfo } from '../types';

export interface RailPanel {
  key: string;
  node: React.ReactNode;
}

interface Slice {
  key: string;
  label: string;
  value: number;
  color: string;
  detail?: string;
}

const PALETTE = [
  '#f0a826', // amber primary
  '#d97a4a', // sienna
  '#4a9faa', // teal
  '#8ca87a', // sage
  '#9b6a8e', // plum
  '#b89b5e', // gold-slate
  '#6a78b8', // indigo
  '#c47878', // rose
  '#5e8c8a', // pine
  '#cf8c12', // amber deep
  '#a16a4c', // umber
  '#7a98c4', // periwinkle
  '#8e9b4a', // olive
  '#b85e74', // berry
];

const TAU = Math.PI * 2;
const QUARTER = Math.PI / 2;

function describeArc(
  cx: number, cy: number,
  rOuter: number, rInner: number,
  startAngle: number, endAngle: number,
): string {
  // Single-slice degenerate (full circle) — draw as two half-circles
  if (Math.abs(endAngle - startAngle) >= TAU - 0.0001) {
    return [
      `M ${cx + rOuter} ${cy}`,
      `A ${rOuter} ${rOuter} 0 1 1 ${cx - rOuter} ${cy}`,
      `A ${rOuter} ${rOuter} 0 1 1 ${cx + rOuter} ${cy}`,
      `M ${cx + rInner} ${cy}`,
      `A ${rInner} ${rInner} 0 1 0 ${cx - rInner} ${cy}`,
      `A ${rInner} ${rInner} 0 1 0 ${cx + rInner} ${cy}`,
      'Z',
    ].join(' ');
  }
  const x1o = cx + rOuter * Math.cos(startAngle);
  const y1o = cy + rOuter * Math.sin(startAngle);
  const x2o = cx + rOuter * Math.cos(endAngle);
  const y2o = cy + rOuter * Math.sin(endAngle);
  const x1i = cx + rInner * Math.cos(endAngle);
  const y1i = cy + rInner * Math.sin(endAngle);
  const x2i = cx + rInner * Math.cos(startAngle);
  const y2i = cy + rInner * Math.sin(startAngle);
  const large = (endAngle - startAngle) > Math.PI ? 1 : 0;
  return [
    `M ${x1o} ${y1o}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${x2o} ${y2o}`,
    `L ${x1i} ${y1i}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${x2i} ${y2i}`,
    'Z',
  ].join(' ');
}

function formatMoney(v: number): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(v);
}

function formatPct(v: number, digits = 1): string {
  return `${(v * 100).toFixed(digits)}%`;
}

interface DonutProps {
  title: string;
  subtitle?: string;
  subtitleClass?: string;
  slices: Slice[];
  total: number;
  totalLabel: string;
}

function Donut({ title, subtitle, subtitleClass, slices, total, totalLabel }: DonutProps) {
  const [hover, setHover] = useState<string | null>(null);
  const size = 200;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = 88;
  const rInner = 56;
  const rPop = 4; // outward offset when hovered

  // Generate arc paths
  let angle = -QUARTER;
  const arcs = slices.map(s => {
    const sweep = total > 0 ? (s.value / total) * TAU : 0;
    const start = angle;
    const end = angle + sweep;
    angle = end;
    // Pop offset direction = midpoint angle of the slice
    const mid = (start + end) / 2;
    const dx = Math.cos(mid) * rPop;
    const dy = Math.sin(mid) * rPop;
    return { slice: s, start, end, sweep, dx, dy };
  });

  const hoveredArc = arcs.find(a => a.slice.key === hover);
  const centerPrimary = hoveredArc
    ? hoveredArc.slice.label
    : totalLabel;
  const centerValue = hoveredArc
    ? `$${formatMoney(hoveredArc.slice.value)}`
    : `$${formatMoney(total)}`;
  const centerPct = hoveredArc && total > 0
    ? formatPct(hoveredArc.slice.value / total, 1)
    : null;

  return (
    <div className="donut">
      <div className="donut-head">
        <h3>{title}</h3>
        {subtitle && <span className={`donut-sub ${subtitleClass ?? ''}`}>{subtitle}</span>}
      </div>

      {slices.length === 0 ? (
        <div className="donut-empty">— no allocation —</div>
      ) : (
        <>
          <div className="donut-svg-wrap">
            <svg
              viewBox={`0 0 ${size} ${size}`}
              className="donut-svg"
              role="img"
              aria-label={title}
            >
              {arcs.map(a => {
                const active = a.slice.key === hover;
                const dim = hover !== null && !active;
                return (
                  <path
                    key={a.slice.key}
                    d={describeArc(cx, cy, rOuter, rInner, a.start, a.end)}
                    fill={a.slice.color}
                    opacity={dim ? 0.28 : 1}
                    transform={active ? `translate(${a.dx} ${a.dy})` : undefined}
                    onMouseEnter={() => setHover(a.slice.key)}
                    onMouseLeave={() => setHover(null)}
                    style={{ transition: 'opacity .15s ease, transform .15s ease', cursor: 'pointer' }}
                  />
                );
              })}
              {/* center text */}
              <g pointerEvents="none">
                <text
                  x={cx}
                  y={cy - 8}
                  textAnchor="middle"
                  className="donut-center-label"
                >
                  {centerPrimary}
                </text>
                <text
                  x={cx}
                  y={cy + 12}
                  textAnchor="middle"
                  className="donut-center-value"
                >
                  {centerValue}
                </text>
                {centerPct && (
                  <text
                    x={cx}
                    y={cy + 28}
                    textAnchor="middle"
                    className="donut-center-pct"
                  >
                    {centerPct}
                  </text>
                )}
              </g>
            </svg>
          </div>

          <ul className="donut-legend">
            {slices.map(s => {
              const active = s.key === hover;
              const dim = hover !== null && !active;
              const pct = total > 0 ? s.value / total : 0;
              return (
                <li
                  key={s.key}
                  className={`donut-legend-row ${active ? 'active' : ''} ${dim ? 'dim' : ''}`}
                  onMouseEnter={() => setHover(s.key)}
                  onMouseLeave={() => setHover(null)}
                >
                  <span className="swatch" style={{ background: s.color }} />
                  <span className="label">{s.label}</span>
                  <span className="value">${formatMoney(s.value)}</span>
                  <span className="pct">{formatPct(pct)}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}

export function useAllocationPanels(positions: Position[], account: AccountInfo | null): RailPanel[] {
  const data = useMemo(() => {
    const cash = account?.cash ?? 0;
    // Account-level scalars shown under the Cash-vs-Invested donut. buying_power is the
    // headline on a margin account; settled/unsettled is what matters on a cash account
    // (unsettled = proceeds still in T+1/T+2, not yet redeployable). settled_cash falls
    // back to cash for brokers that don't expose it (then unsettled reads 0).
    const buyingPower = account?.buying_power ?? 0;
    const settledCash = account?.settled_cash ?? cash;
    const unsettledCash = account?.unsettled_cash ?? 0;
    const valid = positions.filter(p => p.market_value > 0);

    const invested = valid.reduce((s, p) => s + p.market_value, 0);
    // Negative cash means the account is on margin: holdings are partly
    // funded by borrowed money. Free cash funds nothing extra in that case.
    const onMargin = cash < 0;
    const margin = onMargin ? -cash : 0;
    const freeCash = Math.max(0, cash);
    const total = invested + freeCash;

    const sortedBySize = [...valid].sort((a, b) => b.market_value - a.market_value);

    const bySymbol: Slice[] = sortedBySize.map((p, i) => ({
      key: p.symbol,
      label: p.symbol,
      value: p.market_value,
      color: PALETTE[i % PALETTE.length],
    }));

    // Sector
    const sectorBuckets: Record<string, { value: number; tickers: string[] }> = {};
    for (const p of valid) {
      const sec = p.sector ?? 'Unclassified';
      if (!sectorBuckets[sec]) sectorBuckets[sec] = { value: 0, tickers: [] };
      sectorBuckets[sec].value += p.market_value;
      sectorBuckets[sec].tickers.push(p.symbol);
    }
    const sectorKeys = Object.keys(sectorBuckets).sort(
      (a, b) => sectorBuckets[b].value - sectorBuckets[a].value,
    );
    const bySector: Slice[] = sectorKeys.map((k, i) => ({
      key: k,
      label: `${k} · ${sectorBuckets[k].tickers.length}`,
      value: sectorBuckets[k].value,
      color: PALETTE[i % PALETTE.length],
    }));

    // Asset class
    const classBuckets: Record<string, { value: number; tickers: string[] }> = {};
    for (const p of valid) {
      const cls = p.asset_class || 'unknown';
      if (!classBuckets[cls]) classBuckets[cls] = { value: 0, tickers: [] };
      classBuckets[cls].value += p.market_value;
      classBuckets[cls].tickers.push(p.symbol);
    }
    const CLASS_LABELS: Record<string, string> = {
      us_equity: 'Equities',
      crypto: 'Crypto',
      forex: 'Forex',
      futures: 'Futures',
      unknown: 'Other',
    };
    const classKeys = Object.keys(classBuckets).sort(
      (a, b) => classBuckets[b].value - classBuckets[a].value,
    );
    const byClass: Slice[] = classKeys.map((k, i) => ({
      key: k,
      label: `${CLASS_LABELS[k] ?? k} · ${classBuckets[k].tickers.length}`,
      value: classBuckets[k].value,
      color: PALETTE[i % PALETTE.length],
    }));

    // How your firepower splits: what's deployed (on margin, your own equity vs.
    // borrowed margin in red), the free cash (when not on margin), and the buying
    // power still available to deploy (dry powder, green). Buying power is its own
    // slice now instead of a line of text under the donut.
    const cashVsInvested: Slice[] = (onMargin
      ? [
          { key: 'equity', label: `Invested · ${valid.length}`,
            value: Math.max(0, invested - margin), color: '#f0a826' },
          { key: 'margin', label: 'Margin (borrowed)',
            value: margin, color: '#c45252' },
        ]
      : [
          { key: 'invested', label: `Invested · ${valid.length}`, value: invested,
            color: '#f0a826' },
          { key: 'cash',     label: 'Cash',                       value: freeCash,
            color: '#4a9faa' },
        ]).concat([
          { key: 'buyingpower', label: 'Buying power',
            value: Math.max(0, buyingPower), color: '#8ca87a' },
        ]).filter(s => s.value > 0);

    // Heat-weighted: which positions are pulling the most portfolio risk
    const heated = valid
      .filter(p => p.heat > 0)
      .sort((a, b) => b.heat - a.heat);
    const heatTotal = heated.reduce((s, p) => s + p.heat, 0);
    const byHeat: Slice[] = heated.map((p, i) => ({
      key: p.symbol,
      label: p.symbol,
      value: p.heat,
      color: PALETTE[i % PALETTE.length],
    }));

    // P&L exposure: each position sized by |unrealized_pl|, colored by sign.
    // Within winners/losers, cycle through tonal variants so adjacent slices
    // remain visually distinguishable.
    const GREENS = ['#9ec47a', '#7eb35a', '#5e9c40', '#a8d18b', '#8fc270', '#73a050'];
    const REDS   = ['#d76a6a', '#c45252', '#a14444', '#e08a8a', '#b66060', '#cc7878'];
    const plPositions = valid
      .filter(p => Math.abs(p.unrealized_pl) > 0)
      .sort((a, b) => Math.abs(b.unrealized_pl) - Math.abs(a.unrealized_pl));
    const plTotal = plPositions.reduce((s, p) => s + Math.abs(p.unrealized_pl), 0);
    let winIdx = 0, lossIdx = 0;
    const byPL: Slice[] = plPositions.map(p => {
      const sign = p.unrealized_pl >= 0 ? '+' : '−';
      const isWin = p.unrealized_pl >= 0;
      const color = isWin ? GREENS[winIdx++ % GREENS.length]
                          : REDS[lossIdx++ % REDS.length];
      return {
        key: p.symbol,
        label: `${p.symbol} ${sign}$${formatMoney(Math.abs(p.unrealized_pl))}`,
        value: Math.abs(p.unrealized_pl),
        color,
      };
    });

    const winners = valid.filter(p => p.unrealized_pl > 0);
    const losers  = valid.filter(p => p.unrealized_pl < 0);
    const winSum  = winners.reduce((s, p) => s + p.unrealized_pl, 0);
    const lossSum = Math.abs(losers.reduce((s, p) => s + p.unrealized_pl, 0));

    return {
      bySymbol,
      byClass,
      bySector,
      byHeat,
      byPL,
      cashVsInvested,
      onMargin, margin,
      buyingPower, settledCash, unsettledCash,
      totals: { invested, total, heat: heatTotal, plExposure: plTotal },
      winSum, lossSum,
      winnerCount: winners.length,
      loserCount: losers.length,
    };
  }, [positions, account]);

  const panels: RailPanel[] = [];

  panels.push({
    key: 'alloc-cash-vs-invested',
    node: (
      <section className="panel">
        <div className="section-head">
          <div className="section-head-title">
            <span className="section-marker">§</span>
            <h2>Allocation</h2>
          </div>
          <div className="section-meta">CAPITAL DISTRIBUTION</div>
        </div>
        <div className="section-rule" />
        <Donut
          title="Cash vs. Invested"
          subtitle={data.onMargin
            ? `⚠ on margin · borrowed $${formatMoney(data.margin)}`
            : 'of total capital'}
          subtitleClass={data.onMargin ? 'donut-sub-warn' : undefined}
          slices={data.cashVsInvested}
          total={data.cashVsInvested.reduce((s, x) => s + x.value, 0)}
          totalLabel="Total"
        />
        {Math.abs(data.unsettledCash) >= 1 && (
          <ul className="alloc-stats">
            <li className="alloc-stat-unsettled">
              <span className="alloc-stat-label">Unsettled · T+2</span>
              <span className="alloc-stat-value">${formatMoney(data.unsettledCash)}</span>
            </li>
          </ul>
        )}
      </section>
    ),
  });

  panels.push({
    key: 'alloc-by-position',
    node: (
      <section className="panel">
        <Donut
          title="By Position"
          subtitle="share of invested capital"
          slices={data.bySymbol}
          total={data.totals.invested}
          totalLabel="Invested"
        />
      </section>
    ),
  });

  // All panels are always rendered so the natural order is stable even
  // before /status data arrives. Donut shows its empty state on its own.
  panels.push({
    key: 'alloc-by-sector',
    node: (
      <section className="panel">
        <Donut
          title="By Sector"
          subtitle="hover for tickers"
          slices={data.bySector}
          total={data.totals.invested}
          totalLabel="Invested"
        />
      </section>
    ),
  });

  panels.push({
    key: 'alloc-by-class',
    node: (
      <section className="panel">
        <Donut
          title="By Asset Class"
          subtitle="hover for tickers"
          slices={data.byClass}
          total={data.totals.invested}
          totalLabel="Invested"
        />
      </section>
    ),
  });

  panels.push({
    key: 'alloc-by-heat',
    node: (
      <section className="panel">
        <Donut
          title="Risk Concentration"
          subtitle="share of total heat"
          slices={data.byHeat}
          total={data.totals.heat}
          totalLabel="Total Heat"
        />
      </section>
    ),
  });

  panels.push({
    key: 'alloc-by-pl',
    node: (
      <section className="panel">
        <Donut
          title="P&amp;L Exposure"
          subtitle={`${data.winnerCount} winners · ${data.loserCount} losers`}
          slices={data.byPL}
          total={data.totals.plExposure}
          totalLabel="|P&L| Total"
        />
      </section>
    ),
  });

  return panels;
}

