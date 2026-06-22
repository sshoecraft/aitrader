import { useState } from 'react';
import type { Order } from '../types';

interface OrdersTableProps {
  orders: Order[];
  onCancel: (orderId: string) => Promise<void>;
}

function formatPrice(value: number): string {
  return value.toFixed(2);
}

function formatQty(qty: number): string {
  if (Number.isInteger(qty)) return qty.toString();
  return qty.toFixed(4);
}

export default function OrdersTable({ orders, onCancel }: OrdersTableProps) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);

  const sorted = [...orders].sort((a, b) => a.symbol.localeCompare(b.symbol));

  async function handleCancel(orderId: string) {
    if (confirmId !== orderId) {
      setConfirmId(orderId);
      return;
    }
    setCancelling(orderId);
    setConfirmId(null);
    try {
      await onCancel(orderId);
    } finally {
      setCancelling(null);
    }
  }

  return (
    <section className="panel">
      <div className="section-head">
        <div className="section-head-title">
          <span className="section-marker">§</span>
          <h2>Open Orders</h2>
        </div>
        <div className="section-meta">{orders.length} ACTIVE</div>
      </div>
      <div className="section-rule" />

      {orders.length === 0 ? (
        <div className="empty-state">no working orders</div>
      ) : (
        <div className="table-container">
          <table className="ledger">
            <thead>
              <tr>
                <th className="col-symbol">Symbol</th>
                <th className="col-qty">Type</th>
                <th className="col-qty">Qty</th>
                <th className="col-number">Stop</th>
                <th className="col-number">Limit</th>
                <th className="col-action">Action</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(o => {
                const isConfirming = confirmId === o.id;
                const isCancelling = cancelling === o.id;
                const hasStop = o.stop_price > 0;
                const hasLimit = o.limit_price > 0;
                return (
                  <tr key={o.id}>
                    <td className="col-symbol">{o.symbol}</td>
                    <td className="col-qty mono">{o.side?.toUpperCase()}</td>
                    <td className="col-qty mono">{formatQty(o.qty)}</td>
                    <td className="mono">{hasStop ? formatPrice(o.stop_price) : ''}</td>
                    <td className="mono">{hasLimit ? formatPrice(o.limit_price) : ''}</td>
                    <td className="col-action">
                      {isCancelling ? (
                        <span className="selling-text">Cancelling…</span>
                      ) : isConfirming ? (
                        <span className="confirm-group">
                          <button className="btn-confirm" onClick={() => handleCancel(o.id)}>Yes</button>
                          <button className="btn-cancel"  onClick={() => setConfirmId(null)}>No</button>
                        </span>
                      ) : (
                        <button className="btn-sell" onClick={() => handleCancel(o.id)} title="Cancel order">
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            {/* Blank totals row: mirrors the Positions table footer so the
                gap below Open Orders matches the gap above it. */}
            <tfoot>
              <tr className="totals-row">
                <td colSpan={6}>&nbsp;</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  );
}
