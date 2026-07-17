export interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  side: string;
  cost_basis: number;
  asset_class: string;
  stop: number;
  has_broker_stop: boolean;
  trail: number | null;
  limit_price: number;
  has_broker_limit: boolean;
  heat: number;
  to_stp: number;
  to_lim: number;
  sector: string | null;
  industry: string | null;
  expiry: string;
}

export interface AccountInfo {
  equity: number;
  cash: number;
  buying_power: number;
  settled_cash?: number;
  unsettled_cash?: number;
  portfolio_value: number;
  [key: string]: unknown;
}

export interface HeatPosition {
  symbol: string;
  heat: number;
  [key: string]: unknown;
}

export interface HeatInfo {
  equity: number;
  total_heat: number;
  stock_heat: number;
  crypto_heat: number;
  forex_heat: number;
  futures_heat: number;
  position_count: number;
  positions: HeatPosition[];
}

export interface HealthInfo {
  status: string;
  connected: boolean;
  positions: number;
}

export interface AvailableTypes {
  stock: boolean;
  crypto: boolean;
  forex: boolean;
  futures: boolean;
}

export interface Order {
  id: string;
  symbol: string;
  side: string;
  type: string;
  qty: number;
  stop_price: number;
  limit_price: number;
  status: string;
}

export type TradePeriod = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'YTD' | 'ALL';

export interface TradeTransaction {
  id: number;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  total_value: number;
  commission: number;
  strategy: string | null;
  is_day_trade: boolean;
  executed_at: string;
  asset_type: string | null;
  [key: string]: unknown;
}

export interface RoundTrip {
  symbol: string;
  pnl: number;
  pnl_pct: number;
  buy_executed_at: string;
  sell_executed_at: string;
  holding_hours: number;
}

export interface TradesResponse {
  period: TradePeriod;
  start: string | null;
  end: string;
  count: number;
  realized_pnl: number;
  transactions: TradeTransaction[];
  round_trips: RoundTrip[];
}

export interface JournalEntry {
  id: number;
  time: string;            // ISO-8601 UTC on the wire
  kind: string;            // free-form: buy/sell (trader) or cycle/exit/note/plan… (aitrader)
  symbol: string | null;
  text: string;            // one-liner OR multi-paragraph prose
  tags?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface AnalysisIndicators {
  rsi: { value: number | null; signal: string } | null;
  macd: {
    value: number | null;
    signal_line: number | null;
    histogram: number | null;
    signal: string;
  } | null;
  sma_20: number | null;
  sma_50: number | null;
  atr: number | null;
  adx: number | null;
  volume_ratio: number | null;
  [key: string]: unknown;
}

export interface AnalysisOrderPrices {
  entry: number;
  stop_loss: number;
  stop_loss_pct: number;
  take_profit: number;
  take_profit_pct: number;
  [key: string]: unknown;
}

export interface AnalysisReview {
  approved: boolean;
  confidence: number;
  reasoning: string;
  risk_assessment: string;
  [key: string]: unknown;
}

export interface AnalysisResult {
  symbol: string;
  price: number;
  timestamp: string;
  indicators: AnalysisIndicators;
  score: number;
  signals: string[];
  bearish_signals: string[];
  warnings: string[];
  trend: string;
  trend_blocked: boolean;
  wyckoff_phase: string;
  gap_pct: number;
  avg_volume: number;
  order_prices: AnalysisOrderPrices | null;
  review: AnalysisReview | null;
  [key: string]: unknown;
}
