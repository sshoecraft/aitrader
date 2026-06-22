import { useEffect, useRef, useState } from 'react';
import { getLog } from '../api';

interface LogPeekProps {
  onExpand: () => void;
  compact?: boolean;
}

const POLL_MS = 5000;
const PEEK_BYTES = 4096;
const PEEK_LINES = 18;

function lastLines(text: string, n: number): string {
  const lines = text.split('\n').filter(l => l.length > 0);
  return lines.slice(-n).join('\n');
}

export default function LogPeek({ onExpand, compact = false }: LogPeekProps) {
  const [content, setContent] = useState('');
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;

    async function tick() {
      try {
        const tail = await getLog(PEEK_BYTES);
        if (cancelled) return;
        setContent(lastLines(tail.content, PEEK_LINES));
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'log unavailable');
      }
    }

    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      mounted.current = false;
      clearInterval(id);
    };
  }, []);

  if (compact) {
    return (
      <>
        <div className="log-peek" onClick={onExpand} title="Open full log">
          <pre>{error ? `— ${error} —` : (content || '— waiting for output —')}</pre>
        </div>
        <div className="log-peek-hint">click to expand</div>
      </>
    );
  }

  return (
    <section className="panel log-peek-panel">
      <div className="section-head">
        <div className="section-head-title">
          <span className="section-marker">§</span>
          <h2>Engine Log</h2>
        </div>
        <div className="section-meta">LIVE LOG</div>
      </div>
      <div className="section-rule" />

      <div className="log-peek" onClick={onExpand} title="Open full log">
        <pre>{error ? `— ${error} —` : (content || '— waiting for output —')}</pre>
      </div>
      <div className="log-peek-hint">click to expand</div>
    </section>
  );
}
