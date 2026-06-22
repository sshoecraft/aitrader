import type { HeatInfo } from '../types';

interface HeatPanelProps {
  heat: HeatInfo | null;
}

const ROWS: Array<{ key: keyof HeatInfo; label: string }> = [
  { key: 'stock_heat',   label: 'Equities' },
  { key: 'crypto_heat',  label: 'Crypto' },
  { key: 'forex_heat',   label: 'Forex' },
  { key: 'futures_heat', label: 'Futures' },
];

function fillClass(heat: number): string {
  if (heat >= 0.40) return 'hot';
  if (heat <= 0.10) return 'cold';
  return '';
}

export default function HeatPanel({ heat }: HeatPanelProps) {
  const total = heat?.total_heat ?? 0;
  // Scale: anything >= 0.6 fills the bar fully; gives visual room for typical 0-50% range
  const scale = (h: number) => Math.max(0, Math.min(1, h / 0.6)) * 100;

  return (
    <section className="panel">
      <div className="section-head">
        <div className="section-head-title">
          <span className="section-marker">§</span>
          <h2>Heat</h2>
        </div>
        <div className="section-meta">RISK DISTRIBUTION</div>
      </div>
      <div className="section-rule" />

      <div className="heat-grid">
        {ROWS.map(({ key, label }) => {
          const value = Number(heat?.[key] ?? 0);
          return (
            <div key={key} className="heat-row">
              <span className="label">{label}</span>
              <div className="heat-bar">
                <div
                  className={`fill ${fillClass(value)}`}
                  style={{ width: `${scale(value)}%` }}
                />
              </div>
              <span className="val">{(value * 100).toFixed(1)}%</span>
            </div>
          );
        })}
      </div>

      <div className="heat-total">
        <span className="label">Total Portfolio Heat</span>
        <span className="val">{(total * 100).toFixed(1)}%</span>
      </div>
    </section>
  );
}
