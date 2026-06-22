import { useState, useEffect, useRef, useCallback } from 'react';
import { getApiBase } from '../api';
import type { AnalysisResult } from '../types';

interface AnalyzeModalProps {
  open: boolean;
  onClose: () => void;
}

type AnalyzeState = 'idle' | 'analyzing' | 'complete' | 'error';

function formatPrice(value: number | null | undefined): string {
  if (value == null) return '--';
  return '$' + value.toFixed(2);
}

function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '--';
  return value.toFixed(decimals);
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return '--';
  return (value * 100).toFixed(1) + '%';
}

function scoreColor(score: number): string {
  if (score > 4) return 'var(--green)';
  if (score >= 2) return 'var(--yellow)';
  return 'var(--red)';
}

function trendStrength(adx: number | null | undefined): string {
  if (adx == null) return 'unknown';
  if (adx >= 50) return 'very strong';
  if (adx >= 25) return 'strong';
  if (adx >= 20) return 'moderate';
  return 'weak';
}

function macdSignalText(macd: AnalysisResult['indicators']['macd']): string {
  if (!macd) return '--';
  const hist = macd.histogram != null ? formatNumber(macd.histogram, 4) : '--';
  return `${macd.signal ?? 'n/a'} (histogram: ${hist})`;
}

export default function AnalyzeModal({ open, onClose }: AnalyzeModalProps) {
  const [symbol, setSymbol] = useState('');
  const [includeReview, setIncludeReview] = useState(false);
  const [analyzeState, setAnalyzeState] = useState<AnalyzeState>('idle');
  const [summary, setSummary] = useState<AnalysisResult | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [reviewText, setReviewText] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const userScrolled = useRef(false);

  // Auto-scroll the terminal pane unless user has scrolled up
  useEffect(() => {
    const el = logRef.current;
    if (!el || userScrolled.current) return;
    el.scrollTop = el.scrollHeight;
  }, [logLines, reviewText]);

  // Focus input when modal opens
  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  // Cleanup EventSource on unmount or close
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const handleScroll = useCallback(() => {
    const el = logRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    userScrolled.current = !atBottom;
  }, []);

  function startAnalysis() {
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;

    // Reset state
    setSummary(null);
    setLogLines([]);
    setReviewText('');
    setErrorMsg('');
    setAnalyzeState('analyzing');
    userScrolled.current = false;

    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const apiBase = getApiBase();
    const url = `${apiBase}/analyze/${encodeURIComponent(sym)}/stream?include_review=${includeReview}&reviewer_type=opus`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('log', (e: MessageEvent) => {
      setLogLines(prev => [...prev, e.data]);
    });

    es.addEventListener('summary', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as AnalysisResult;
        setSummary(data);
      } catch {
        // If parse fails, treat as log
        setLogLines(prev => [...prev, `[summary parse error] ${e.data}`]);
      }
    });

    es.addEventListener('review', (e: MessageEvent) => {
      setReviewText(prev => prev + e.data);
    });

    es.addEventListener('complete', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        // If summary hasn't arrived yet, use complete data as fallback
        setSummary(prev => prev ?? (data as AnalysisResult));
      } catch {
        // ignore parse errors on complete
      }
      setAnalyzeState('complete');
      es.close();
      eventSourceRef.current = null;
    });

    es.addEventListener('error', (e: MessageEvent) => {
      if (e.data) {
        setErrorMsg(e.data);
        setLogLines(prev => [...prev, `ERROR: ${e.data}`]);
      }
      setAnalyzeState('error');
      es.close();
      eventSourceRef.current = null;
    });

    // Handle connection errors (EventSource.onerror)
    es.onerror = () => {
      // Use state setter callback to read current state without stale closure
      setAnalyzeState(prev => {
        if (prev === 'analyzing') {
          setErrorMsg('Connection lost. Is the trading engine running?');
          return 'error';
        }
        return prev;
      });
      es.close();
      eventSourceRef.current = null;
    };
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && analyzeState !== 'analyzing') {
      startAnalysis();
    }
  }

  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  if (!open) return null;

  const ind = summary?.indicators;
  const orderPrices = summary?.order_prices;

  return (
    <div className="analyze-backdrop" onClick={handleBackdropClick}>
      <div className="analyze-modal">
        {/* Top bar: input controls */}
        <div className="analyze-modal-toolbar">
          <div className="analyze-modal-toolbar-left">
            <span className="analyze-modal-title">Analyze Symbol:</span>
            <input
              ref={inputRef}
              className="analyze-modal-input"
              type="text"
              placeholder="NVDA"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              onKeyDown={handleKeyDown}
              disabled={analyzeState === 'analyzing'}
            />
            <button
              className="analyze-modal-btn"
              onClick={startAnalysis}
              disabled={analyzeState === 'analyzing' || !symbol.trim()}
            >
              {analyzeState === 'analyzing' ? (
                <>
                  <span className="analyze-modal-spinner" />
                  Analyzing...
                </>
              ) : 'Analyze'}
            </button>
            <label className="analyze-modal-checkbox">
              <input
                type="checkbox"
                checked={includeReview}
                onChange={(e) => setIncludeReview(e.target.checked)}
                disabled={analyzeState === 'analyzing'}
              />
              Review
            </label>
          </div>
          <button className="analyze-modal-close" onClick={onClose} title="Close (Esc)">
            &#x2715;
          </button>
        </div>

        {/* Top pane: structured summary */}
        <div className="analyze-modal-summary">
          {summary ? (
            <div className="analyze-summary-content">
              <div className="analyze-summary-header">
                <span className="analyze-summary-symbol">{summary.symbol}</span>
                <span className="analyze-summary-price mono">@ {formatPrice(summary.price)}</span>
                {summary.gap_pct !== 0 && (
                  <span className={`analyze-summary-gap mono ${summary.gap_pct >= 0 ? 'positive' : 'negative'}`}>
                    Gap {summary.gap_pct >= 0 ? '+' : ''}{formatNumber(summary.gap_pct, 1)}%
                  </span>
                )}
                {summary.trend_blocked && (
                  <span className="analyze-summary-blocked">TREND BLOCKED</span>
                )}
              </div>
              <div className="analyze-summary-divider" />
              <div className="analyze-summary-grid">
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">RSI:</span>
                  <span className="analyze-summary-val mono">{formatNumber(ind?.rsi?.value)}</span>
                </div>
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">MACD:</span>
                  <span className="analyze-summary-val mono">{macdSignalText(ind?.macd ?? null)}</span>
                </div>
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">SMA-20:</span>
                  <span className="analyze-summary-val mono">{formatPrice(ind?.sma_20)}</span>
                </div>
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">SMA-50:</span>
                  <span className="analyze-summary-val mono">{formatPrice(ind?.sma_50)}</span>
                </div>
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">Volume Ratio:</span>
                  <span className="analyze-summary-val mono">{ind?.volume_ratio != null ? formatNumber(ind.volume_ratio) + 'x' : '--'}</span>
                </div>
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">ADX:</span>
                  <span className="analyze-summary-val mono">{formatNumber(ind?.adx, 1)} ({trendStrength(ind?.adx)} trend)</span>
                </div>
              </div>
              <div className="analyze-summary-divider" />
              <div className="analyze-summary-row">
                <span className="analyze-summary-label">Score:</span>
                <span className="analyze-summary-val mono" style={{ color: scoreColor(summary.score) }}>
                  {summary.score}/8
                </span>
              </div>
              {(summary.signals?.length > 0 || summary.bearish_signals?.length > 0) && (
                <div className="analyze-summary-row">
                  <span className="analyze-summary-label">Signals:</span>
                  <span className="analyze-summary-val mono">
                    {[...(summary.signals ?? []), ...(summary.bearish_signals ?? [])].join(', ')}
                  </span>
                </div>
              )}
              {orderPrices && (
                <>
                  <div className="analyze-summary-divider" />
                  <div className="analyze-summary-row">
                    <span className="analyze-summary-label">Entry:</span>
                    <span className="analyze-summary-val mono">{formatPrice(orderPrices.entry)}</span>
                  </div>
                  <div className="analyze-summary-row">
                    <span className="analyze-summary-label">Stop Loss:</span>
                    <span className="analyze-summary-val mono negative">
                      {formatPrice(orderPrices.stop_loss)} ({formatPercent(orderPrices.stop_loss_pct)})
                    </span>
                  </div>
                  <div className="analyze-summary-row">
                    <span className="analyze-summary-label">Take Profit:</span>
                    <span className="analyze-summary-val mono positive">
                      {formatPrice(orderPrices.take_profit)} ({formatPercent(orderPrices.take_profit_pct)})
                    </span>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="analyze-summary-placeholder">
              {analyzeState === 'idle' && <span>Enter a symbol and click Analyze</span>}
              {analyzeState === 'analyzing' && <span>Waiting for analysis data...</span>}
              {analyzeState === 'error' && <span className="negative">Analysis failed</span>}
            </div>
          )}
        </div>

        {/* Bottom pane: terminal log */}
        <div
          className="analyze-modal-terminal"
          ref={logRef}
          onScroll={handleScroll}
        >
          {logLines.map((line, i) => (
            <div
              key={i}
              className={`analyze-terminal-line${line.startsWith('ERROR:') ? ' analyze-terminal-error' : ''}`}
            >
              &gt; {line}
            </div>
          ))}
          {reviewText && (
            <div className="analyze-terminal-review">
              {reviewText}
            </div>
          )}
          {errorMsg && !logLines.some(l => l.includes(errorMsg)) && (
            <div className="analyze-terminal-line analyze-terminal-error">
              &gt; {errorMsg}
            </div>
          )}
          {analyzeState === 'analyzing' && (
            <div className="analyze-terminal-cursor">
              &gt; <span className="analyze-blink">_</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
