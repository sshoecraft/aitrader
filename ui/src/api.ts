import type { Position, AccountInfo, AvailableTypes, HeatInfo, HealthInfo, Order, AnalysisResult, TradePeriod, TradesResponse, TradeTransaction, RoundTrip, JournalEntry } from './types';

// API host/port resolution, highest precedence first:
//   1. RUNTIME: window.__API_PORT__ / window.__API_HOST__ injected by the
//      trader_ui server's /config.js route (set via --api-port / --api-host).
//      This needs no rebuild — it lives in the systemd service file.
//   2. BUILD-TIME: VITE_API_PORT baked into the bundle (legacy fallback).
//   3. Default: 2499 (the aitrader dashboard API default; see config.py).
//      Only hit in a bare `npm run dev` with no runtime /config.js injection.
//
// window.__API_BASE__ (also from /config.js) overrides all of the above with an
// explicit base. portd mode sets it to a same-origin PATH like "/aitrader-api"
// so the SPA reaches the API through Caddy (the allocated port is localhost-only
// and the public host is shared) instead of a host:port URL.
const API_PORT = window.__API_PORT__
  ?? (import.meta.env.VITE_API_PORT as string | undefined)
  ?? '2499';
const API_HOST = window.__API_HOST__ ?? window.location.hostname;
const API_BASE = window.__API_BASE__ ?? `http://${API_HOST}:${API_PORT}`;

export function getApiBase(): string {
  return API_BASE;
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: 'no-cache' });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function parsePosition(raw: Record<string, unknown>): Position {
  return {
    symbol: String(raw.symbol ?? ''),
    qty: Number(raw.qty ?? 0),
    avg_entry_price: Number(raw.avg_entry_price ?? 0),
    current_price: Number(raw.current_price ?? 0),
    market_value: Number(raw.market_value ?? 0),
    unrealized_pl: Number(raw.unrealized_pl ?? 0),
    unrealized_plpc: Number(raw.unrealized_plpc ?? 0),
    side: String(raw.side ?? 'long'),
    cost_basis: Number(raw.cost_basis ?? 0),
    asset_class: String(raw.asset_class ?? ''),
    stop: Number(raw.stop ?? 0),
    has_broker_stop: Boolean(raw.has_broker_stop),
    trail: raw.trail != null ? Number(raw.trail) : null,
    limit_price: Number(raw.limit_price ?? 0),
    has_broker_limit: Boolean(raw.has_broker_limit),
    heat: Number(raw.heat ?? 0),
    to_stp: Number(raw.to_stp ?? 0),
    to_lim: Number(raw.to_lim ?? 0),
    sector: typeof raw.sector === 'string' && raw.sector ? raw.sector : null,
    industry: typeof raw.industry === 'string' && raw.industry ? raw.industry : null,
  };
}

function parseOrder(raw: Record<string, unknown>): Order {
  return {
    id: String(raw.id ?? ''),
    symbol: String(raw.symbol ?? ''),
    side: String(raw.side ?? ''),
    type: String(raw.type ?? ''),
    qty: Number(raw.qty ?? 0),
    stop_price: Number(raw.stop_price ?? 0),
    limit_price: Number(raw.limit_price ?? 0),
    status: String(raw.status ?? ''),
  };
}

export interface StatusData {
  positions: Position[];
  orders: Order[];
  account: AccountInfo;
  heat: HeatInfo;
  health: HealthInfo;
  availableTypes: AvailableTypes;
  lastSync: string | null;
  version: string | null;
  dayPL: number;
}

export async function getStatus(): Promise<StatusData> {
  const raw = await fetchJson<Record<string, unknown>>('/status');

  // Positions: array or dict → array
  const rawPos = raw.positions ?? [];
  const posArr = Array.isArray(rawPos) ? rawPos : Object.values(rawPos);
  const positions = (posArr as Record<string, unknown>[]).map(parsePosition);

  // Orders: array or dict → array
  const rawOrd = raw.orders ?? [];
  const ordArr = Array.isArray(rawOrd) ? rawOrd : Object.values(rawOrd);
  const orders = (ordArr as Record<string, unknown>[]).map(parseOrder);

  // Account
  const acctRaw = (raw.account ?? {}) as Record<string, unknown>;
  const account: AccountInfo = {
    equity: Number(acctRaw.equity ?? 0),
    cash: Number(acctRaw.cash ?? 0),
    buying_power: Number(acctRaw.buying_power ?? 0),
    portfolio_value: Number(acctRaw.portfolio_value ?? 0),
  };

  // Available types
  const rawTypes = (raw.available_types ?? {}) as Record<string, unknown>;
  const availableTypes: AvailableTypes = {
    stock: Boolean(rawTypes.stock),
    crypto: Boolean(rawTypes.crypto),
    forex: Boolean(rawTypes.forex),
    futures: Boolean(rawTypes.futures),
  };

  // Heat: use /status heat if present, otherwise compute from positions
  const connected = Boolean(raw.connected);

  const heatRaw = (raw.heat ?? {}) as Record<string, unknown>;
  const heat: HeatInfo = {
    equity: account.equity,
    total_heat: Number(heatRaw.total_heat ?? 0),
    stock_heat: Number(heatRaw.stock_heat ?? 0),
    crypto_heat: Number(heatRaw.crypto_heat ?? 0),
    forex_heat: Number(heatRaw.forex_heat ?? 0),
    futures_heat: Number(heatRaw.futures_heat ?? 0),
    position_count: Number(heatRaw.position_count ?? positions.length),
    positions: positions.map(p => ({ symbol: p.symbol, heat: p.heat })),
  };

  const health: HealthInfo = {
    status: connected ? 'ok' : 'disconnected',
    connected,
    positions: positions.length,
  };

  const lastSync = typeof raw.last_sync === 'string' ? raw.last_sync : null;
  const version = typeof raw.version === 'string' ? raw.version : null;
  const dayPL = Number(raw.day_pl ?? 0);

  return { positions, orders, account, heat, health, availableTypes, lastSync, version, dayPL };
}

export async function sellPosition(symbol: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/sell?symbol=${encodeURIComponent(symbol)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Sell error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function cancelOrder(orderId: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/cancel/${encodeURIComponent(orderId)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Cancel error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface PortfolioHistory {
  equity: number[];
  profit_loss: number[];
  profit_loss_pct: number[];
  timestamp: (string | number)[];
  base_value: number;
  timeframe: string;
  source?: string;
}

export async function getPortfolioHistory(period: string, timeframe: string): Promise<PortfolioHistory> {
  return fetchJson<PortfolioHistory>(`/portfolio_history?period=${encodeURIComponent(period)}&timeframe=${encodeURIComponent(timeframe)}`);
}

export interface Bar {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

export type BarsResponse = Record<string, Bar[]>;

export async function getBars(symbols: string, timeframe: string, start?: string): Promise<BarsResponse> {
  const params = new URLSearchParams({ symbols, timeframe });
  if (start) params.set('start', start);
  return fetchJson<BarsResponse>(`/bars?${params.toString()}`);
}

function parseTransaction(raw: Record<string, unknown>): TradeTransaction {
  return {
    ...raw,
    id: Number(raw.id ?? 0),
    symbol: String(raw.symbol ?? ''),
    side: String(raw.side ?? ''),
    quantity: Number(raw.quantity ?? 0),
    price: Number(raw.price ?? 0),
    total_value: Number(raw.total_value ?? 0),
    commission: Number(raw.commission ?? 0),
    strategy: typeof raw.strategy === 'string' && raw.strategy ? raw.strategy : null,
    is_day_trade: Boolean(raw.is_day_trade),
    executed_at: String(raw.executed_at ?? ''),
    asset_type: typeof raw.asset_type === 'string' && raw.asset_type ? raw.asset_type : null,
  };
}

function parseRoundTrip(raw: Record<string, unknown>): RoundTrip {
  return {
    symbol: String(raw.symbol ?? ''),
    pnl: Number(raw.pnl ?? 0),
    pnl_pct: Number(raw.pnl_pct ?? 0),
    buy_executed_at: String(raw.buy_executed_at ?? ''),
    sell_executed_at: String(raw.sell_executed_at ?? ''),
    holding_hours: Number(raw.holding_hours ?? 0),
  };
}

export async function getTrades(period: TradePeriod): Promise<TradesResponse> {
  const raw = await fetchJson<Record<string, unknown>>(`/trades?period=${encodeURIComponent(period)}`);
  const tx = Array.isArray(raw.transactions) ? raw.transactions : [];
  const rt = Array.isArray(raw.round_trips) ? raw.round_trips : [];
  return {
    period: String(raw.period ?? period) as TradePeriod,
    start: typeof raw.start === 'string' ? raw.start : null,
    end: String(raw.end ?? ''),
    count: Number(raw.count ?? tx.length),
    realized_pnl: Number(raw.realized_pnl ?? 0),
    transactions: (tx as Record<string, unknown>[]).map(parseTransaction),
    round_trips: (rt as Record<string, unknown>[]).map(parseRoundTrip),
  };
}

function parseJournalEntry(raw: Record<string, unknown>): JournalEntry {
  const meta = raw.meta && typeof raw.meta === 'object' && !Array.isArray(raw.meta)
    ? (raw.meta as Record<string, unknown>)
    : null;
  return {
    id: Number(raw.id ?? 0),
    time: String(raw.time ?? ''),
    kind: String(raw.kind ?? ''),
    symbol: typeof raw.symbol === 'string' && raw.symbol ? raw.symbol : null,
    text: String(raw.text ?? ''),
    tags: typeof raw.tags === 'string' && raw.tags ? raw.tags : null,
    meta,
  };
}

// Shared by the trader and aitrader APIs: GET /journal?limit=&kind=&symbol=&since=
// `since` is an ISO-8601 UTC instant; `time` on each entry is UTC on the wire.
export async function getJournal(
  opts: { limit?: number; kind?: string; symbol?: string; since?: string } = {},
): Promise<{ entries: JournalEntry[] }> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.kind) params.set('kind', opts.kind);
  if (opts.symbol) params.set('symbol', opts.symbol);
  if (opts.since) params.set('since', opts.since);
  const qs = params.toString();
  const raw = await fetchJson<Record<string, unknown>>(`/journal${qs ? `?${qs}` : ''}`);
  const arr = Array.isArray(raw.entries) ? raw.entries : [];
  return { entries: (arr as Record<string, unknown>[]).map(parseJournalEntry) };
}

export interface SettingEntry {
  default: unknown;
  current: unknown;
}

export type SettingsData = Record<string, SettingEntry>;

export async function getSettings(): Promise<SettingsData> {
  return fetchJson<SettingsData>('/settings');
}

export async function putSettings(changes: Record<string, unknown>): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Settings error: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  return (data.settings ?? data) as SettingsData;
}

export async function deleteSettings(keys: string[]): Promise<SettingsData> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Settings delete error: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  return (data.settings ?? data) as SettingsData;
}

export interface StrategyMethod {
  name: string;
  config: Record<string, unknown>;
}

export interface StrategySummary {
  name: string;
  description?: string;
  reviewer?: boolean;
  source?: string;
  methods?: StrategyMethod[];
  disables?: Record<string, boolean>;
  overrides?: Record<string, unknown>;
  path?: string;
  user_override?: boolean;
  error?: string;
}

export interface CreateStrategyInput {
  name: string;
  description?: string;
  reviewer?: boolean;
  source?: string;
  methods: Array<{ name: string } & Record<string, unknown>>;
  disables?: Record<string, boolean>;
  overrides?: Record<string, unknown>;
}

export interface UpdateStrategyMetadataInput {
  description?: string;
  reviewer?: boolean;
  source?: string;
  disables?: Record<string, boolean>;
  overrides?: Record<string, unknown>;
}

export interface StrategiesResponse {
  active: string | null;
  strategies: StrategySummary[];
}

export interface MethodInfo {
  name: string;
  kind: 'entry' | 'parking';
  assets: string[];
  cadence_days: number;
  cross_asset: boolean;
}

export async function listStrategies(): Promise<StrategiesResponse> {
  return fetchJson<StrategiesResponse>('/strategies');
}

export async function listMethods(): Promise<MethodInfo[]> {
  const data = await fetchJson<{ methods: MethodInfo[] }>('/methods');
  return data.methods;
}

export async function addStrategyMethod(
  strategy: string,
  method: string,
  config: Record<string, unknown> = {},
): Promise<unknown> {
  const res = await fetch(
    `${API_BASE}/strategies/${encodeURIComponent(strategy)}/methods`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method, config }),
    },
  );
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Add method error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function updateStrategyMethod(
  strategy: string,
  method: string,
  config: Record<string, unknown>,
): Promise<unknown> {
  const res = await fetch(
    `${API_BASE}/strategies/${encodeURIComponent(strategy)}/methods/${encodeURIComponent(method)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config }),
    },
  );
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Update method error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function removeStrategyMethod(
  strategy: string,
  method: string,
): Promise<unknown> {
  const res = await fetch(
    `${API_BASE}/strategies/${encodeURIComponent(strategy)}/methods/${encodeURIComponent(method)}`,
    { method: 'DELETE' },
  );
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Remove method error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface RetirementPosition {
  symbol: string;
  alloc: number;
}

export interface RetirementAllocation {
  positions: RetirementPosition[];
}

// Sugar over the generic /settings endpoints. The retirement allocation
// pie lives at the flat key `retirement_allocation.positions` in
// engine.settings; these wrappers shape-convert so the widget doesn't
// have to think about it.

export async function getRetirementAllocation(): Promise<RetirementAllocation> {
  const all = await getSettings();
  const entry = all['retirement_allocation.positions'];
  const raw = (entry?.current ?? entry?.default ?? []) as unknown;
  const positions: RetirementPosition[] = [];
  if (Array.isArray(raw)) {
    for (const p of raw) {
      if (!p || typeof p !== 'object') continue;
      const obj = p as Record<string, unknown>;
      const symRaw = typeof obj.symbol === 'string' ? obj.symbol.trim().toUpperCase() : '';
      const allocNum = Number(obj.alloc);
      if (!symRaw || !Number.isFinite(allocNum) || allocNum <= 0) continue;
      positions.push({ symbol: symRaw, alloc: allocNum });
    }
  }
  return { positions };
}

export async function saveRetirementAllocation(
  payload: RetirementAllocation,
): Promise<unknown> {
  return putSettings({
    retirement_allocation: { positions: payload.positions },
  });
}

export async function createStrategy(input: CreateStrategyInput): Promise<unknown> {
  const res = await fetch(`${API_BASE}/strategies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Create strategy: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function updateStrategyMetadata(
  name: string, patch: UpdateStrategyMetadataInput,
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/strategies/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Update strategy: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function deleteStrategy(name: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/strategies/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Delete strategy: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function duplicateStrategy(
  source: string, newName: string, description?: string,
): Promise<unknown> {
  const body: Record<string, unknown> = { new_name: newName };
  if (description !== undefined) body.description = description;
  const res = await fetch(
    `${API_BASE}/strategies/${encodeURIComponent(source)}/duplicate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Duplicate strategy: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function resetStrategyOverride(strategy: string): Promise<unknown> {
  const res = await fetch(
    `${API_BASE}/strategies/${encodeURIComponent(strategy)}/override`,
    { method: 'DELETE' },
  );
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Reset error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface ReviewData {
  symbol: string;
  asset_type: string;
  reviewed_at: string;
  content?: string;
  record?: Record<string, unknown>;
  format?: string;
}

export async function getReview(symbol: string): Promise<ReviewData | null> {
  const res = await fetch(`${API_BASE}/review?symbol=${encodeURIComponent(symbol.toUpperCase())}`);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Review error: ${res.status} ${res.statusText}`);
  }
  return await res.json() as ReviewData;
}

export interface LogTail {
  path: string;
  size: number;
  mtime: number;
  returnedBytes: number;
  truncated: boolean;
  content: string;
}

export async function getLog(bytes?: number): Promise<LogTail> {
  const qs = bytes ? `?bytes=${bytes}` : '';
  const res = await fetch(`${API_BASE}/log${qs}`);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Log error: ${res.status} ${res.statusText}`);
  }
  const raw = await res.json() as Record<string, unknown>;
  return {
    path: String(raw.path ?? ''),
    size: Number(raw.size ?? 0),
    mtime: Number(raw.mtime ?? 0),
    returnedBytes: Number(raw.returned_bytes ?? 0),
    truncated: Boolean(raw.truncated),
    content: String(raw.content ?? ''),
  };
}

export async function analyzeSymbol(symbol: string, includeReview: boolean): Promise<AnalysisResult> {
  const url = `${API_BASE}/analyze/${encodeURIComponent(symbol.toUpperCase())}?include_review=${includeReview}`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Analysis error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<AnalysisResult>;
}

export async function triggerBuyCycle(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/actions/restart-buyer`, {
    method: 'POST',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Trigger buy cycle error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
