import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import './App.css';
import Header from './components/Header';
import PositionsTable from './components/PositionsTable';
import OrdersTable from './components/OrdersTable';
import JournalFeed from './components/JournalFeed';
import HeatPanel from './components/HeatPanel';
import { useAllocationPanels } from './components/AllocationPanel';
import type { RailPanel } from './components/AllocationPanel';
import LogPeek from './components/LogPeek';
import AnalyzeModal from './components/AnalyzePanel';
import SettingsPanel from './components/SettingsPanel';
import LogViewer from './components/LogViewer';
import { getStatus, getSettings, sellPosition, cancelOrder, triggerBuyCycle, getPortfolioHistory } from './api';
import type {
  Position, Order, AccountInfo, AvailableTypes, HeatInfo, HealthInfo,
} from './types';

const REFRESH_INTERVAL = 60_000;
const RAIL_ORDER_KEY = 'trader-ui:rail-order:v2';

function DraggableRail({ panels }: { panels: RailPanel[] }) {
  const allKeys = useMemo(() => panels.map(p => p.key), [panels]);
  const { order, move } = useDraggableOrder(allKeys, RAIL_ORDER_KEY);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [overKey, setOverKey] = useState<string | null>(null);
  const slotRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Native HTML5 drag doesn't auto-scroll the viewport. Track mouse Y during
  // drag and scroll programmatically when within EDGE pixels of top/bottom.
  useEffect(() => {
    if (!dragKey) return;

    let rafId: number | null = null;
    let velocity = 0;
    const EDGE = 90;
    const MAX_SPEED = 22;

    const tick = () => {
      if (velocity !== 0) {
        window.scrollBy(0, velocity);
        rafId = requestAnimationFrame(tick);
      } else {
        rafId = null;
      }
    };

    const onDragOver = (e: DragEvent) => {
      const y = e.clientY;
      const h = window.innerHeight;
      if (y < EDGE) {
        velocity = -MAX_SPEED * ((EDGE - y) / EDGE);
      } else if (y > h - EDGE) {
        velocity = MAX_SPEED * ((y - (h - EDGE)) / EDGE);
      } else {
        velocity = 0;
      }
      if (velocity !== 0 && rafId === null) {
        rafId = requestAnimationFrame(tick);
      }
    };

    window.addEventListener('dragover', onDragOver);
    return () => {
      window.removeEventListener('dragover', onDragOver);
      if (rafId !== null) cancelAnimationFrame(rafId);
    };
  }, [dragKey]);

  const byKey = useMemo(() => {
    const m = new Map<string, RailPanel>();
    for (const p of panels) m.set(p.key, p);
    return m;
  }, [panels]);

  return (
    <aside className="col-rail">
      {order.map(key => {
        const panel = byKey.get(key);
        if (!panel) return null;
        const isDragging = dragKey === key;
        const isOver = overKey === key && dragKey !== null && dragKey !== key;
        return (
          <div
            key={key}
            ref={el => { slotRefs.current[key] = el; }}
            className={`rail-slot${isDragging ? ' dragging' : ''}${isOver ? ' drop-target' : ''}`}
            onDragOver={e => {
              if (!dragKey) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = 'move';
              if (overKey !== key) setOverKey(key);
            }}
            onDragLeave={e => {
              // Only clear if leaving the slot entirely
              if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                if (overKey === key) setOverKey(null);
              }
            }}
            onDrop={e => {
              e.preventDefault();
              const src = e.dataTransfer.getData('text/x-rail-panel');
              if (src && src !== key) move(src, key);
              setDragKey(null);
              setOverKey(null);
            }}
          >
            <span
              className="rail-grip"
              role="button"
              tabIndex={0}
              title="Drag to reorder"
              aria-label="Drag to reorder panel"
              draggable
              onDragStart={e => {
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/x-rail-panel', key);
                const slot = slotRefs.current[key];
                if (slot) {
                  const rect = slot.getBoundingClientRect();
                  e.dataTransfer.setDragImage(slot, 24, Math.min(40, rect.height / 6));
                }
                setDragKey(key);
              }}
              onDragEnd={() => { setDragKey(null); setOverKey(null); }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                <circle cx="5" cy="3.5" r="1.2" fill="currentColor" />
                <circle cx="11" cy="3.5" r="1.2" fill="currentColor" />
                <circle cx="5" cy="8" r="1.2" fill="currentColor" />
                <circle cx="11" cy="8" r="1.2" fill="currentColor" />
                <circle cx="5" cy="12.5" r="1.2" fill="currentColor" />
                <circle cx="11" cy="12.5" r="1.2" fill="currentColor" />
              </svg>
            </span>
            {panel.node}
          </div>
        );
      })}
    </aside>
  );
}

function useDraggableOrder(allKeys: string[], storageKey: string) {
  const [order, setOrder] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
      if (Array.isArray(saved)) {
        const filtered = saved.filter((k): k is string => typeof k === 'string' && allKeys.includes(k));
        const missing  = allKeys.filter(k => !filtered.includes(k));
        return [...filtered, ...missing];
      }
    } catch { /* ignore */ }
    return [...allKeys];
  });

  const keysSig = allKeys.join('|');
  useEffect(() => {
    setOrder(prev => {
      const filtered = prev.filter(k => allKeys.includes(k));
      const missing  = allKeys.filter(k => !filtered.includes(k));
      const next = [...filtered, ...missing];
      if (next.length === prev.length && next.every((k, i) => k === prev[i])) return prev;
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keysSig]);

  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(order)); } catch { /* ignore */ }
  }, [order, storageKey]);

  function move(fromKey: string, toKey: string) {
    if (fromKey === toKey) return;
    setOrder(prev => {
      const next = [...prev];
      const from = next.indexOf(fromKey);
      const to   = next.indexOf(toKey);
      if (from < 0 || to < 0) return prev;
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  }

  return { order, move };
}

function App() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [heat, setHeat] = useState<HeatInfo | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [availableTypes, setAvailableTypes] = useState<AvailableTypes>({
    stock: false, crypto: false, forex: false, futures: false,
  });
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  const [dayPL, setDayPL] = useState(0);
  // /status.day_pl is unreliable (the engine reports 0 when last_equity is
  // null, e.g. fresh paper accounts), so derive the day's P&L from the 1D
  // portfolio_history journal series — the same source the header chart uses.
  const [dayPLFromHistory, setDayPLFromHistory] = useState<number | null>(null);
  const [accountType, setAccountType] = useState<string | null>(null);
  // Browser tab title prefix: the configured portd_name if set, else "Trader".
  const [titleName, setTitleName] = useState('Trader');
  const [error, setError] = useState<string | null>(null);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const status = await getStatus();
      setPositions(status.positions);
      setOrders(status.orders);
      setAccount(status.account);
      setHeat(status.heat);
      setHealth(status.health);
      setAvailableTypes(status.availableTypes);
      setDayPL(status.dayPL);
      setVersion(status.version);
      setLastUpdated(status.lastSync ? new Date(status.lastSync) : new Date());
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch data';
      setError(msg);
      setLastUpdated(new Date());
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [refresh]);

  // Refresh the derived day P&L alongside the status poll.
  useEffect(() => {
    let cancelled = false;
    getPortfolioHistory('1D', '5Min')
      .then(data => {
        if (cancelled) return;
        const rawEq = data.equity ?? [];
        const baseIdx = rawEq.findIndex(v => v > 0);
        const eq = baseIdx > 0 ? rawEq.slice(baseIdx) : rawEq;
        if (eq.length >= 2 && eq[0] > 0) {
          setDayPLFromHistory(eq[eq.length - 1] - eq[0]);
        } else {
          setDayPLFromHistory(null);
        }
      })
      .catch(() => { if (!cancelled) setDayPLFromHistory(null); });
    return () => { cancelled = true; };
  }, [lastUpdated]);

  const effectiveDayPL = dayPLFromHistory ?? dayPL;

  useEffect(() => {
    const sign = effectiveDayPL >= 0 ? '+' : '−';
    const abs = Math.abs(effectiveDayPL).toLocaleString('en-US', {
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
    document.title = `${titleName} ${sign}$${abs}`;
  }, [effectiveDayPL, titleName]);

  useEffect(() => {
    // broker_options.account_type & portd_name rarely change; fetch once on mount.
    getSettings().then(s => {
      const entry = s['broker_options.account_type'];
      const v = entry?.current ?? entry?.default;
      if (typeof v === 'string') setAccountType(v.toLowerCase());

      const nameEntry = s['portd_name'];
      const name = nameEntry?.current ?? nameEntry?.default;
      if (typeof name === 'string' && name.trim().length > 0) setTitleName(name.trim());
    }).catch(() => { /* ignore — buying-power cell just won't render */ });
  }, []);

  async function handleSell(symbol: string) {
    try {
      const result = await sellPosition(symbol) as { order_id: string; state: string };
      await refresh();
      return result ?? null;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Sell failed';
      alert(`Failed to sell ${symbol}: ${msg}`);
      return null;
    }
  }

  async function handleCancelOrder(orderId: string) {
    try {
      await cancelOrder(orderId);
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Cancel failed';
      alert(`Failed to cancel order: ${msg}`);
    }
  }

  const allocPanels = useAllocationPanels(positions, account?.cash ?? 0);
  const railPanels = useMemo<RailPanel[]>(() => ([
    ...allocPanels.slice(1),
  ]), [allocPanels]);

  async function handleTriggerBuyCycle() {
    try {
      await triggerBuyCycle();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Trigger failed';
      alert(`Failed to trigger buy cycle: ${msg}`);
    }
  }

  return (
    <div className="app">
      <Header
        account={account}
        health={health}
        dayPL={effectiveDayPL}
        version={version}
        lastUpdated={lastUpdated}
        onRefresh={refresh}
        refreshing={refreshing}
        availableTypes={availableTypes}
        accountType={accountType}
        onAnalyzeOpen={() => setAnalyzeOpen(true)}
        onSettingsOpen={() => setSettingsOpen(true)}
        onLogOpen={() => setLogOpen(true)}
        onTriggerBuyCycle={handleTriggerBuyCycle}
        heroPanels={<>
          {allocPanels[0]?.node}
          <HeatPanel heat={heat} />
          <LogPeek onExpand={() => setLogOpen(true)} />
        </>}
      />
      {error && <div className="error-banner">{error}</div>}

      <main className="main">
        <div className="col-ledger">
          <PositionsTable
            positions={positions}
            onSell={handleSell}
            availableTypes={availableTypes}
            totalHeat={heat?.total_heat ?? 0}
          />
          <OrdersTable orders={orders} onCancel={handleCancelOrder} />
          <JournalFeed reloadKey={lastUpdated?.getTime() ?? 0} />
        </div>

        <DraggableRail panels={railPanels} />
      </main>

      <AnalyzeModal open={analyzeOpen} onClose={() => setAnalyzeOpen(false)} />
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <LogViewer open={logOpen} onClose={() => setLogOpen(false)} />
    </div>
  );
}

export default App;
