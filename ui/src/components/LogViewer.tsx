import { useEffect, useRef, useState } from 'react';
import { getLog } from '../api';

interface LogViewerProps {
  open: boolean;
  onClose: () => void;
}

const POLL_MS = 2000;

export default function LogViewer({ open, onClose }: LogViewerProps) {
  const [content, setContent] = useState('');
  const [path, setPath] = useState('');
  const [size, setSize] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const preRef = useRef<HTMLPreElement>(null);
  const autoScrollRef = useRef(autoScroll);
  autoScrollRef.current = autoScroll;

  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    async function tick() {
      try {
        const tail = await getLog();
        if (cancelled) return;
        setContent(tail.content);
        setPath(tail.path);
        setSize(tail.size);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Failed to load log';
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    setLoading(true);
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [open]);

  // Auto-scroll to bottom when content changes, if enabled.
  useEffect(() => {
    if (!autoScrollRef.current) return;
    const el = preRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [content]);

  function onScroll() {
    const el = preRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
    if (atBottom !== autoScroll) setAutoScroll(atBottom);
  }

  function jumpToBottom() {
    const el = preRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setAutoScroll(true);
  }

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="log-modal" onClick={(e) => e.stopPropagation()}>
        <div className="log-modal-header">
          <div className="log-modal-title">
            <span>Engine Log</span>
            <span className="log-modal-path">{path || '/home/trader/log/trader-engine.log'}</span>
          </div>
          <div className="log-modal-controls">
            <span className="log-modal-meta">
              {size ? `${(size / 1024).toFixed(1)} KiB` : ''}
              {!autoScroll && (
                <button className="log-jump-btn" onClick={jumpToBottom}>Jump to bottom</button>
              )}
            </span>
            <button className="settings-btn settings-btn-cancel" onClick={onClose}>Close</button>
          </div>
        </div>
        {error && <div className="error-banner">{error}</div>}
        <pre
          ref={preRef}
          className="log-modal-body"
          onScroll={onScroll}
        >
          {loading && !content ? 'Loading…' : content}
        </pre>
      </div>
    </div>
  );
}
