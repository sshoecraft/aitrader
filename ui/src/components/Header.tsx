import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { AccountInfo, AvailableTypes, HealthInfo } from '../types';
import { getPortfolioHistory, getBars } from '../api';
import type { Bar } from '../api';

interface HeaderProps {
  account: AccountInfo | null;
  health: HealthInfo | null;
  dayPL: number;
  version: string | null;
  lastUpdated: Date | null;
  onRefresh: () => void;
  refreshing: boolean;
  availableTypes: AvailableTypes;
  accountType: string | null;
  onSettingsOpen: () => void;
  onLogOpen: () => void;
  onAnalyzeOpen: () => void;
  onTriggerBuyCycle: () => void;
  heroPanels?: ReactNode;
}

const TYPE_LABELS: Record<keyof AvailableTypes, string> = {
  stock: 'Equities',
  crypto: 'Crypto',
  forex: 'Forex',
  futures: 'Futures',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday',
              'Thursday', 'Friday', 'Saturday'];

function formatMoney(value: number, opts: { sign?: boolean; cents?: boolean } = {}): string {
  const { sign = false, cents = true } = opts;
  const abs = Math.abs(value);
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  }).format(abs);
  const prefix = sign ? (value >= 0 ? '+' : '−') : (value < 0 ? '−' : '');
  return `${prefix}$${formatted}`;
}

function formatEditionDate(d: Date): string {
  return `${DAYS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

function formatClock(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

function formatUpdateAge(d: Date | null): string {
  if (!d) return '—';
  const sec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (sec < 60) return `updated ${sec}s ago`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `updated ${m}m ago`;
  const h = Math.floor(m / 60);
  return `updated ${h}h ago`;
}

type ChartPeriod = '1D' | '1W' | '2W' | '1M' | '3M' | '6M' | '1Y';

const PERIOD_CONFIG: Record<ChartPeriod, { apiPeriod: string; timeframe: string }> = {
  '1D': { apiPeriod: '1D',  timeframe: '5Min' },
  '1W': { apiPeriod: '1W',  timeframe: '1H'   },
  '2W': { apiPeriod: '2W',  timeframe: '1H'   },
  '1M': { apiPeriod: '1M',  timeframe: '1D'   },
  '3M': { apiPeriod: '3M',  timeframe: '1D'   },
  '6M': { apiPeriod: '6M',  timeframe: '1D'   },
  '1Y': { apiPeriod: '1A',  timeframe: '1D'   },
};

// Engine /bars uses Alpaca-style timeframe names, distinct from the
// portfolio_history names above (1H -> 1Hour, 1D -> 1Day).
const BENCH_SYMBOL = 'VTI';
const BARS_TIMEFRAME: Record<ChartPeriod, string> = {
  '1D': '5Min',
  '1W': '1Hour',
  '2W': '1Hour',
  '1M': '1Day',
  '3M': '1Day',
  '6M': '1Day',
  '1Y': '1Day',
};

// Start of the window for the VTI /bars fetch ONLY (the equity series uses a
// server-side window via portfolio_since — this never touches it). 1D looks back
// a week, NOT to today's midnight: Alpaca returns bars chronologically FROM start
// and gives ZERO if start is past the last session (weekend / holiday — e.g. a
// Sunday after a Fri Juneteenth has its last session 3 days back). IBKR masked
// this by padding start backwards; Alpaca doesn't. The extra lookback only feeds
// alignment/Mode-B selection — Mode A still draws today-only via the equity grid.
function periodStartISO(period: ChartPeriod): string {
  const d = new Date();
  switch (period) {
    case '1D': d.setDate(d.getDate() - 7); break;
    case '1W': d.setDate(d.getDate() - 7); break;
    case '2W': d.setDate(d.getDate() - 14); break;
    case '1M': d.setMonth(d.getMonth() - 1); break;
    case '3M': d.setMonth(d.getMonth() - 3); break;
    case '6M': d.setMonth(d.getMonth() - 6); break;
    case '1Y': d.setFullYear(d.getFullYear() - 1); break;
  }
  return d.toISOString();
}

function tsToEpoch(ts: string | number): number {
  const n = Number(ts);
  if (!isNaN(n) && String(ts).trim() !== '') {
    return n > 1e10 ? n : n * 1000;
  }
  return new Date(ts as string).getTime();
}

// Map each equity timestamp to the close of the nearest VTI bar, so the
// benchmark series lines up index-for-index with the equity series even
// though the two come on different sampling grids.
function alignBars(eqTs: (string | number)[], bars: Bar[]): number[] {
  if (!bars.length) return [];
  const barEpochs = bars.map(b => tsToEpoch(b.t));
  return eqTs.map(ts => {
    const target = tsToEpoch(ts);
    if (isNaN(target)) return bars[bars.length - 1].c;
    let best = 0, bestDiff = Infinity;
    for (let i = 0; i < barEpochs.length; i++) {
      const diff = Math.abs(barEpochs[i] - target);
      if (diff < bestDiff) { bestDiff = diff; best = i; }
    }
    return bars[best].c;
  });
}

// Min/max epoch (ms) over a list of timestamps. null if none parse.
function epochRange(ts: (string | number)[]): { min: number; max: number } | null {
  let min = Infinity, max = -Infinity;
  for (const t of ts) {
    const e = tsToEpoch(t);
    if (isNaN(e)) continue;
    if (e < min) min = e;
    if (e > max) max = e;
  }
  return isFinite(min) ? { min, max } : null;
}

// Calendar-day key (YYYY-MM-DD) from a bar timestamp, read in the bar's own
// tz offset (the leading date component) — not the viewer's local day.
function dayKey(t: string | number): string {
  const s = String(t);
  const m = s.match(/^\d{4}-\d{2}-\d{2}/);
  return m ? m[0] : s;
}

// Bars in the most-recent calendar session present in the list (assumes
// chronological order, oldest→newest, as IBKR/Alpaca return them).
function lastSessionBars(bars: Bar[]): Bar[] {
  if (!bars.length) return [];
  const key = dayKey(bars[bars.length - 1].t);
  return bars.filter(b => dayKey(b.t) === key);
}

// Resample a source series (values at srcFracs, both in 0..1) onto target
// x-fractions by nearest-neighbour. Used in Mode B to project VTI's own-session
// curve onto the equity x-grid so the crosshair can read a VTI% at the hovered
// screen position even though the two series live on different time axes.
function resampleByX(targetFracs: number[], srcFracs: number[], srcVals: number[]): number[] {
  if (!srcVals.length) return [];
  return targetFracs.map(tf => {
    let best = 0, bd = Infinity;
    for (let i = 0; i < srcFracs.length; i++) {
      const d = Math.abs(srcFracs[i] - tf);
      if (d < bd) { bd = d; best = i; }
    }
    return srcVals[best];
  });
}

const CHART_W = 180, CHART_H = 52, CHART_PAD = 2;

function projectY(v: number, min: number, max: number): number {
  const range = max - min;
  const midY = CHART_H / 2;
  const bottomY = CHART_H - CHART_PAD;
  return range === 0 ? midY : bottomY - ((v - min) / range) * (CHART_H - CHART_PAD * 2);
}

// Horizontal position fraction (0..1) for each sample, proportional to its
// timestamp so points are spaced by REAL elapsed time, not by array index.
// Mixed cadence (sparse daily backfill over a month + dense 15-min snapshots
// over the last few days) would otherwise crush the older span into a sliver
// of the chart while the recent dense points hog most of the width.
function timeFractions(ts: (string | number)[]): number[] {
  const n = ts.length;
  if (n === 0) return [];
  if (n === 1) return [0.5];
  const epochs = ts.map(tsToEpoch);
  const t0 = epochs[0];
  const t1 = epochs[n - 1];
  const span = t1 - t0;
  if (!isFinite(span) || span <= 0) {
    // No usable time axis — fall back to even index spacing.
    return epochs.map((_, i) => i / (n - 1));
  }
  return epochs.map((e, i) => (isNaN(e) ? i / (n - 1) : (e - t0) / span));
}

// Project a series onto chart coords using a shared min/max so multiple
// series (equity + benchmark) sit on the same vertical scale. xFracs gives
// each sample's horizontal position (0..1) by time; both series share the
// same eqTs grid so they pass the same fractions.
function seriesPoints(values: number[], xFracs: number[], min: number, max: number): [number, number][] {
  const midY = CHART_H / 2;
  const leftX = CHART_PAD;
  const rightX = CHART_W - CHART_PAD;
  if (values.length === 1) return [[leftX, midY], [rightX, midY]];
  return values.map((v, i) => {
    const f = xFracs[i] ?? (i / (values.length - 1));
    const x = leftX + f * (rightX - leftX);
    return [x, projectY(v, min, max)];
  });
}

function buildSpark(values: number[], xFracs: number[], min: number, max: number): { line: string; area: string } | null {
  if (values.length < 1) return null;
  const leftX = CHART_PAD;
  const bottomY = CHART_H - CHART_PAD;
  const pts = seriesPoints(values, xFracs, min, max);
  const coords = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`);
  const firstX = pts[0][0].toFixed(1);
  const firstY = pts[0][1].toFixed(1);
  const lastX = pts[pts.length - 1][0].toFixed(1);
  return {
    line: `M ${coords.join(' L ')}`,
    area: `M ${firstX},${firstY} L ${coords.join(' L ')} L ${lastX},${bottomY.toFixed(1)} L ${leftX.toFixed(1)},${bottomY.toFixed(1)} Z`,
  };
}

function buildLine(values: number[], xFracs: number[], min: number, max: number): string | null {
  if (values.length < 1) return null;
  const pts = seriesPoints(values, xFracs, min, max);
  const coords = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`);
  return `M ${coords.join(' L ')}`;
}

function Icon({ name }: { name: string }) {
  switch (name) {
    case 'refresh':
      return (
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 8a6 6 0 1 1-1.76-4.24" />
          <path d="M14 2v4h-4" />
        </svg>
      );
    case 'analyze':
      return (
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 13l3.5-4 3 2.5L13 4" />
          <circle cx="13" cy="4" r="1.4" fill="currentColor" />
        </svg>
      );
    case 'settings':
      return (
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="8" cy="8" r="2.2" />
          <path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8 3.4 3.4" strokeLinecap="round" />
        </svg>
      );
    case 'log':
      return (
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
          <path d="M3 2h7l3 3v9H3z" />
          <path d="M10 2v3h3" />
          <path d="M5.5 8h5M5.5 10h5M5.5 12h3" strokeLinecap="round" />
        </svg>
      );
    case 'play':
      return (
        <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4 3l9 5-9 5z" />
        </svg>
      );
    default:
      return null;
  }
}

export default function Header({
  account, health, dayPL, version, lastUpdated,
  onRefresh, refreshing, availableTypes,
  onSettingsOpen, onLogOpen, onAnalyzeOpen, onTriggerBuyCycle,
  heroPanels,
}: HeaderProps) {
  const [now, setNow] = useState<Date>(() => new Date());
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('1D');
  const [chartValues, setChartValues] = useState<number[]>([]);
  const [chartTimestamps, setChartTimestamps] = useState<(string | number)[]>([]);
  const [chartPL, setChartPL] = useState<number | null>(null);
  const [chartPLPct, setChartPLPct] = useState<number | null>(null);
  const [benchBars, setBenchBars] = useState<Bar[]>([]);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const chartFetchRef = useRef(0);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const seq = ++chartFetchRef.current;
    const { apiPeriod, timeframe } = PERIOD_CONFIG[chartPeriod];
    getPortfolioHistory(apiPeriod, timeframe)
      .then(data => {
        if (seq !== chartFetchRef.current) return;
        const rawEq = data.equity ?? [];
        const rawTs = data.timestamp ?? [];
        const baseIdx = rawEq.findIndex(v => v > 0);
        const eq = baseIdx > 0 ? rawEq.slice(baseIdx) : rawEq;
        const ts = baseIdx > 0 ? rawTs.slice(baseIdx) : rawTs;
        setChartValues(eq);
        setChartTimestamps(ts);
        if (eq.length >= 2 && eq[0] > 0) {
          const delta = eq[eq.length - 1] - eq[0];
          setChartPL(delta);
          setChartPLPct(delta / eq[0]);
        } else {
          setChartPL(null);
          setChartPLPct(null);
        }
      })
      .catch(() => {
        if (seq !== chartFetchRef.current) return;
        setChartValues([]);
        setChartTimestamps([]);
        setChartPL(null);
        setChartPLPct(null);
      });

    // Benchmark (VTI) bars over the same window. Fetched alongside equity
    // so the trend/$/% toggle is instant; failure leaves equity intact.
    getBars(BENCH_SYMBOL, BARS_TIMEFRAME[chartPeriod], periodStartISO(chartPeriod))
      .then(data => {
        if (seq !== chartFetchRef.current) return;
        setBenchBars(data[BENCH_SYMBOL] ?? []);
      })
      .catch(() => {
        if (seq !== chartFetchRef.current) return;
        setBenchBars([]);
      });
  }, [chartPeriod, lastUpdated]);

  function handleChartMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || chartValues.length < 1) return;
    if (chartValues.length === 1) {
      setHoverIdx(0);
      return;
    }
    const rect = svg.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    // Points are spaced by time, so pick the sample whose x-fraction is
    // closest to the cursor rather than scaling by a uniform index.
    let best = 0, bestDiff = Infinity;
    for (let i = 0; i < xFracs.length; i++) {
      const diff = Math.abs(xFracs[i] - ratio);
      if (diff < bestDiff) { bestDiff = diff; best = i; }
    }
    setHoverIdx(best);
  }

  function formatHoverTs(ts: string | number): string {
    if (ts === '' || ts == null) return '';
    let d: Date;
    const n = Number(ts);
    if (!isNaN(n) && String(ts).trim() !== '') {
      // Unix epoch — seconds if < 1e10, milliseconds otherwise
      d = new Date(n > 1e10 ? n : n * 1000);
    } else {
      d = new Date(ts as string);
    }
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  const connected = health?.connected ?? false;
  const equity = account?.equity ?? 0;
  const portfolio = account?.portfolio_value ?? 0;

  const eqBase = chartValues[0] ?? 0;
  const chartLast = chartValues[chartValues.length - 1] ?? 0;
  const chartPositive = chartLast >= eqBase;
  const sparkColor = chartPositive ? 'var(--up)' : 'var(--down)';
  const sparkFill  = chartPositive ? 'rgba(143,194,112,0.12)' : 'rgba(215,106,106,0.12)';

  // --- Benchmark (VTI) overlay, rebased to % return --------------------
  // Two render modes, picked by whether the equity window and VTI's bars
  // share a time span:
  //   A) Overlap → sample VTI at each equity timestamp (nearest bar), rebased
  //      to the first sample. Shares the equity x-grid, so the crosshair can
  //      report VTI% at each hovered equity point.
  //   B) No overlap → e.g. the 1D chart on a weekend/overnight: equity is 24/7
  //      crypto snapshots dated today while VTI's latest bars are a prior
  //      session. Nearest-bar alignment would snap every equity point onto a
  //      single VTI bar — a flat 0% line hidden behind equity. Instead plot
  //      VTI's own most-recent session on its OWN time axis, rebased to that
  //      session's first bar, spanning the chart width.
  const primaryVals = eqBase > 0
    ? chartValues.map(v => (v / eqBase - 1) * 100)
    : chartValues;

  const vtiAligned = alignBars(chartTimestamps, benchBars);
  const eqRange = epochRange(chartTimestamps);
  const barRange = epochRange(benchBars.map(b => b.t));
  const windowsOverlap = !!eqRange && !!barRange
    && barRange.max >= eqRange.min && barRange.min <= eqRange.max;
  const alignedOk = vtiAligned.length === chartValues.length
    && chartValues.length > 0 && eqBase > 0 && vtiAligned[0] > 0;

  // Equity x-fractions up front — Mode B resamples the benchmark onto this grid
  // so the crosshair tooltip can still report VTI% at the hovered position.
  const xFracs = timeFractions(chartTimestamps);

  // benchVals: VTI% sampled on the EQUITY x-grid — drives the per-point crosshair
  // tooltip + amber hover dot in BOTH modes. null only when no benchmark exists.
  let benchVals: number[] | null = null;
  // benchSeries / benchXFracs: the % series + x-fractions actually drawn for the
  // amber line and used for vertical scaling, in whichever mode is active.
  let benchSeries: number[] = [];
  let benchXFracs: number[] = [];
  let vtiReturnPct: number | null = null;

  if (alignedOk && windowsOverlap) {
    const vtiBase = vtiAligned[0];
    benchVals = vtiAligned.map(v => (v / vtiBase - 1) * 100);
    benchSeries = benchVals;
    benchXFracs = xFracs;
    vtiReturnPct = vtiAligned[vtiAligned.length - 1] / vtiBase - 1;
  } else {
    const session = lastSessionBars(benchBars);
    if (session.length >= 2 && session[0].c > 0) {
      const base = session[0].c;
      benchSeries = session.map(b => (b.c / base - 1) * 100);
      benchXFracs = timeFractions(session.map(b => b.t));
      vtiReturnPct = session[session.length - 1].c / base - 1;
      // Resample VTI's own session onto the equity x-grid so a hover at screen-x
      // reports the VTI% the amber line shows at that same x (and the dot returns).
      benchVals = resampleByX(xFracs, benchXFracs, benchSeries);
    }
  }

  const allVals = benchSeries.length ? [...primaryVals, ...benchSeries] : primaryVals;
  const vMin = allVals.length ? Math.min(...allVals) : 0;
  const vMax = allVals.length ? Math.max(...allVals) : 0;

  const spark = buildSpark(primaryVals, xFracs, vMin, vMax);
  const benchLine = benchSeries.length ? buildLine(benchSeries, benchXFracs, vMin, vMax) : null;

  // Footer benchmark stats (always expressed as % return for comparability).
  const ourReturnPct = eqBase > 0 ? (chartLast / eqBase - 1) : 0;
  const outperformPct = vtiReturnPct !== null ? ourReturnPct - vtiReturnPct : null;

  const fmtPct = (p: number) => `${p >= 0 ? '+' : ''}${(p * 100).toFixed(2)}%`;

  return (
    <header className="masthead">
      <div className="masthead-topbar">
        <div className="status-clock">
          {formatEditionDate(now)} · {formatClock(now)} · {formatUpdateAge(lastUpdated)}
          {version && <> · v{version}</>}
          {' · '}
          <span className={`live ${connected ? '' : 'offline'}`}>
            {connected ? 'live' : 'offline'}
          </span>
        </div>
        <div className="market-flags">
          {(Object.keys(TYPE_LABELS) as Array<keyof AvailableTypes>).map(k => (
            <span key={k} className={`market-flag ${availableTypes[k] ? 'open' : 'closed'}`}>
              {TYPE_LABELS[k]} {availableTypes[k] ? 'Open' : 'Closed'}
            </span>
          ))}
        </div>
        <div className="masthead-actions">
          <button
            className={`tool-btn ${refreshing ? 'spinning' : ''}`}
            onClick={onRefresh}
            disabled={refreshing}
            title="Refresh"
          >
            <Icon name="refresh" /> Refresh
          </button>
          <button className="tool-btn" onClick={onAnalyzeOpen} title="Analyze">
            <Icon name="analyze" /> Analyze
          </button>
          <button className="tool-btn" onClick={onTriggerBuyCycle} title="Trigger buy cycle">
            <Icon name="play" /> Buy Cycle
          </button>
          <button className="tool-btn" onClick={onLogOpen} title="Engine log">
            <Icon name="log" />
          </button>
          <button className="tool-btn" onClick={onSettingsOpen} title="Settings">
            <Icon name="settings" />
          </button>
        </div>
      </div>

      <div className="masthead-rule-top" />

      <div className="masthead-hero">
        <div className="hero-cell equity-cell">
          <div className="equity-numbers">
            <div className="equity-num-col">
              <div className="hero-label">Equity</div>
              <div className="hero-value equity">{formatMoney(equity)}</div>
              <div className="hero-sub">
                Portfolio <b>{formatMoney(portfolio, { cents: false })}</b>
              </div>
            </div>
            <div className="equity-num-col">
              <div className="hero-label">{chartPeriod} P&amp;L</div>
              <div className={`hero-value ${(chartPL ?? dayPL) >= 0 ? 'up' : 'down'}`}>
                {formatMoney(chartPL ?? dayPL, { sign: true })}
              </div>
              {chartPLPct !== null && (
                <div className="hero-sub">
                  {chartPLPct >= 0 ? '+' : ''}{(chartPLPct * 100).toFixed(2)}%
                </div>
              )}
            </div>
          </div>
          <div className="equity-chart-area" onMouseLeave={() => setHoverIdx(null)}>
            <svg
              ref={svgRef}
              width="100%" height="100%"
              viewBox={`0 0 ${CHART_W} ${CHART_H}`}
              preserveAspectRatio="none"
              className="equity-spark"
              onMouseMove={handleChartMouseMove}
            >
              {spark ? (
                <>
                  <path d={spark.area} fill={sparkFill} stroke="none" />
                  {benchLine && (
                    <path d={benchLine} fill="none" stroke="var(--amber)"
                      strokeWidth="1.1" strokeDasharray="3,2" opacity="0.85"
                      strokeLinejoin="round" strokeLinecap="round" />
                  )}
                  <path d={spark.line} fill="none" stroke={sparkColor} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" />
                  {hoverIdx !== null && (() => {
                    const hx = primaryVals.length === 1
                      ? CHART_W / 2
                      : CHART_PAD + (xFracs[hoverIdx] ?? hoverIdx / (primaryVals.length - 1)) * (CHART_W - CHART_PAD * 2);
                    const hy = projectY(primaryVals[hoverIdx], vMin, vMax);
                    return (
                      <g>
                        <line x1={hx} y1={CHART_PAD} x2={hx} y2={CHART_H - CHART_PAD}
                          stroke="var(--paper-mute)" strokeWidth="0.8" strokeDasharray="2,2" />
                        {benchVals && benchVals[hoverIdx] !== undefined && (
                          <circle cx={hx} cy={projectY(benchVals[hoverIdx], vMin, vMax)}
                            r="2.2" fill="var(--amber)" stroke="var(--ink-paper)" strokeWidth="1" />
                        )}
                        <circle cx={hx} cy={hy}
                          r="2.5" fill={sparkColor} stroke="var(--ink-paper)" strokeWidth="1" />
                      </g>
                    );
                  })()}
                </>
              ) : (
                <line x1={CHART_PAD} y1={CHART_H / 2} x2={CHART_W - CHART_PAD} y2={CHART_H / 2}
                  stroke="var(--rule-strong)" strokeWidth="1" strokeDasharray="3,3" />
              )}
            </svg>
            {hoverIdx !== null && chartValues[hoverIdx] !== undefined && (() => {
              const ratio = chartValues.length === 1 ? 0.5 : (xFracs[hoverIdx] ?? hoverIdx / (chartValues.length - 1));
              const plPct = eqBase > 0 ? (chartValues[hoverIdx] / eqBase - 1) * 100 : null;
              const vtiPct = benchVals && benchVals[hoverIdx] !== undefined ? benchVals[hoverIdx] : null;
              const signed = (p: number) => `${p >= 0 ? '+' : ''}${p.toFixed(2)}%`;
              return (
              <div
                className="equity-chart-tooltip"
                style={{ left: `${ratio * 100}%`,
                         transform: ratio > 0.6 ? 'translateX(-100%)' : 'translateX(8px)' }}
              >
                <div className="tooltip-equity">Equity {formatMoney(chartValues[hoverIdx])}</div>
                {plPct !== null && (
                  <div className={`tooltip-bench ${plPct >= 0 ? 'up' : 'down'}`}>
                    P&amp;L {signed(plPct)}
                  </div>
                )}
                {vtiPct !== null && (
                  <div className={`tooltip-bench ${vtiPct >= 0 ? 'up' : 'down'}`}>
                    {BENCH_SYMBOL} {signed(vtiPct)}
                  </div>
                )}
                <div className="tooltip-ts">{formatHoverTs(chartTimestamps[hoverIdx] ?? '')}</div>
              </div>
              );
            })()}
          </div>
          <div className="chart-periods">
            {(['1D', '1W', '2W', '1M', '3M', '6M', '1Y'] as ChartPeriod[]).map(p => (
              <button
                key={p}
                className={`chart-period-btn ${chartPeriod === p ? 'active' : ''}`}
                onClick={() => setChartPeriod(p)}
              >{p}</button>
            ))}
            {chartValues.length > 0 && (
              <div className="chart-stats">
                {outperformPct !== null ? (
                  <>
                    <span>{BENCH_SYMBOL}: {fmtPct(vtiReturnPct ?? 0)}</span>
                    <span className={outperformPct >= 0 ? 'up' : 'down'}>
                      Δ {fmtPct(outperformPct)}
                    </span>
                    <span>Last: {formatMoney(chartLast)}</span>
                  </>
                ) : (
                  <>
                    <span>Min: {formatMoney(Math.min(...chartValues))}</span>
                    <span>Max: {formatMoney(Math.max(...chartValues))}</span>
                    <span>Last: {formatMoney(chartLast)}</span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {heroPanels}
      </div>

      <div className="masthead-rule-bottom" />
    </header>
  );
}
