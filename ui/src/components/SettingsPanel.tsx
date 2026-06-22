import { useState, useEffect, useCallback } from 'react';
import {
  getSettings, putSettings, deleteSettings,
  listStrategies, listMethods, addStrategyMethod, removeStrategyMethod,
  resetStrategyOverride,
  createStrategy, updateStrategyMetadata, deleteStrategy, duplicateStrategy,
  getRetirementAllocation, saveRetirementAllocation,
} from '../api';
import type {
  SettingsData, SettingEntry,
  StrategySummary, StrategyMethod, MethodInfo,
  RetirementPosition,
} from '../api';

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

function deepEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function formatLabel(key: string): string {
  const last = key.split('.').pop() || key;
  return last.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatSectionTitle(prefix: string): string {
  // Preserve symbol-like names (e.g. SHIB/USD) verbatim
  if (/^[A-Z0-9]+\/[A-Z0-9]+$/.test(prefix)) return prefix;
  return prefix.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

type ValueType = 'boolean' | 'number' | 'string' | 'array' | 'unknown';

function getValueType(entry: SettingEntry): ValueType {
  const sample = entry.default !== null ? entry.default : entry.current;
  if (sample === null || sample === undefined) return 'unknown';
  if (typeof sample === 'boolean') return 'boolean';
  if (typeof sample === 'number') return 'number';
  if (Array.isArray(sample)) return 'array';
  return 'string';
}

// For settings with default=null and current=null, we have no type hint.
// Try JSON first (handles numbers, bools, arrays, "null"), fall back to string.
function coerceUnknown(v: string): unknown {
  if (v === '') return null;
  const trimmed = v.trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    return v;
  }
}

function isOverridden(draftCurrent: unknown, defaultVal: unknown): boolean {
  return draftCurrent !== null && !deepEqual(draftCurrent, defaultVal);
}

// Unflatten dot-path keys to nested object for PUT
function unflatten(flat: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(flat)) {
    const parts = key.split('.');
    let obj = result;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!(parts[i] in obj) || typeof obj[parts[i]] !== 'object' || obj[parts[i]] === null) {
        obj[parts[i]] = {};
      }
      obj = obj[parts[i]] as Record<string, unknown>;
    }
    obj[parts[parts.length - 1]] = value;
  }
  return result;
}

// Recursively group keys by dot segments to arbitrary depth so deeply
// nested namespaces (e.g. exits.crypto.per_symbol.SHIB/USD.*) render as
// nested sections instead of collapsing into duplicate-looking labels.
interface Tree {
  leafKeys: string[];
  subSections: Record<string, Tree>;
}

function buildTree(keys: string[], prefix: string): Tree {
  const tree: Tree = { leafKeys: [], subSections: {} };
  const groups: Record<string, string[]> = {};
  for (const key of keys) {
    const rest = prefix ? key.substring(prefix.length + 1) : key;
    const dotIdx = rest.indexOf('.');
    if (dotIdx === -1) {
      tree.leafKeys.push(key);
    } else {
      const sub = rest.substring(0, dotIdx);
      if (!groups[sub]) groups[sub] = [];
      groups[sub].push(key);
    }
  }
  for (const sub of Object.keys(groups)) {
    const subPrefix = prefix ? `${prefix}.${sub}` : sub;
    tree.subSections[sub] = buildTree(groups[sub], subPrefix);
  }
  return tree;
}

function countKeys(tree: Tree): number {
  let n = tree.leafKeys.length;
  for (const sub of Object.values(tree.subSections)) n += countKeys(sub);
  return n;
}

function NumberInput({
  value,
  placeholder,
  onCommit,
}: {
  value: unknown;
  placeholder: string;
  onCommit: (v: number | null) => void;
}) {
  const externalStr =
    value !== null && value !== undefined ? String(value) : '';
  const [buf, setBuf] = useState<string>(externalStr);
  const [focused, setFocused] = useState(false);

  // When the external value changes (load, reset, save) and the field is
  // not being edited, sync the buffer.
  useEffect(() => {
    if (!focused) setBuf(externalStr);
  }, [externalStr, focused]);

  return (
    <input
      className="settings-input settings-input-number"
      type="text"
      inputMode="decimal"
      value={buf}
      placeholder={placeholder}
      onFocus={() => setFocused(true)}
      onBlur={() => {
        setFocused(false);
        if (buf === '' || buf === '-' || buf === '.' || buf === '-.') {
          onCommit(null);
          setBuf('');
          return;
        }
        const n = Number(buf);
        if (Number.isNaN(n)) {
          setBuf(externalStr);
        } else {
          onCommit(n);
          setBuf(String(n));
        }
      }}
      onChange={e => {
        const v = e.target.value;
        // Accept any partial-decimal input (incl. "", "-", "0.", ".5", "1e-")
        if (!/^-?(\d+\.?\d*|\.\d*)?(e-?\d*)?$/i.test(v)) return;
        setBuf(v);
        if (v === '' || v === '-' || v === '.' || v === '-.') {
          onCommit(null);
          return;
        }
        const n = Number(v);
        if (!Number.isNaN(n)) onCommit(n);
      }}
    />
  );
}

function ResetIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
    </svg>
  );
}

function SettingRow({
  settingKey,
  entry,
  draftValue,
  onChange,
  onReset,
}: {
  settingKey: string;
  entry: SettingEntry;
  draftValue: unknown;
  onChange: (key: string, value: unknown) => void;
  onReset: (key: string) => void;
}) {
  const overridden = isOverridden(draftValue, entry.default);
  const type = getValueType(entry);
  const effective = draftValue !== null ? draftValue : entry.default;
  const rowClass = `settings-row ${overridden ? 'settings-row-active' : 'settings-row-muted'}`;

  function renderInput() {
    switch (type) {
      case 'boolean':
        return (
          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={Boolean(effective)}
              onChange={e => onChange(settingKey, e.target.checked)}
            />
            <span className="settings-toggle-slider" />
          </label>
        );
      case 'number':
        return (
          <NumberInput
            value={draftValue}
            placeholder={entry.default !== null ? String(entry.default) : ''}
            onCommit={v => onChange(settingKey, v)}
          />
        );
      case 'array':
        return (
          <input
            className="settings-input"
            type="text"
            value={Array.isArray(draftValue) ? (draftValue as unknown[]).join(', ') : ''}
            placeholder={Array.isArray(entry.default) ? (entry.default as unknown[]).join(', ') : ''}
            onChange={e => {
              const v = e.target.value;
              if (v.trim() === '') {
                onChange(settingKey, null);
              } else {
                onChange(settingKey, v.split(',').map(s => s.trim()).filter(Boolean));
              }
            }}
          />
        );
      default: {
        // type is 'string' or 'unknown' (default+current both null).
        // Render as text; for 'unknown' coerce numeric/bool/array via JSON
        // so e.g. risk.max_combined_daily_loss_pct is stored as a number.
        const displayValue =
          draftValue === null || draftValue === undefined
            ? ''
            : typeof draftValue === 'string'
              ? draftValue
              : JSON.stringify(draftValue);
        return (
          <input
            className="settings-input"
            type="text"
            value={displayValue}
            placeholder={entry.default !== null ? String(entry.default) : ''}
            onChange={e => {
              const v = e.target.value;
              if (type === 'unknown') {
                onChange(settingKey, coerceUnknown(v));
              } else {
                onChange(settingKey, v === '' ? null : v);
              }
            }}
          />
        );
      }
    }
  }

  const defaultLabel = entry.default !== null ? JSON.stringify(entry.default) : 'none';

  return (
    <div className={rowClass}>
      <span className="settings-label">{formatLabel(settingKey)}</span>
      <div className="settings-row-controls">
        {renderInput()}
        <button
          className={`settings-reset-btn ${overridden ? 'settings-reset-visible' : ''}`}
          onClick={() => onReset(settingKey)}
          title={`Reset to default: ${defaultLabel}`}
          tabIndex={overridden ? 0 : -1}
        >
          <ResetIcon />
        </button>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  defaultOpen,
  count,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen: boolean;
  count: number;
}) {
  const [expanded, setExpanded] = useState(defaultOpen);
  return (
    <div className="settings-section">
      <button className="settings-section-header" onClick={() => setExpanded(!expanded)}>
        <span className={`settings-chevron ${expanded ? 'expanded' : ''}`}>&#9656;</span>
        <span className="settings-section-title">{formatSectionTitle(title)}</span>
        <span className="settings-section-count">{count}</span>
      </button>
      {expanded && <div className="settings-section-body">{children}</div>}
    </div>
  );
}

function ParkingPicker({ onChanged }: { onChanged: () => void }) {
  const [activeStrategy, setActiveStrategy] = useState<string>('');
  const [currentParking, setCurrentParking] = useState<string>('');
  const [parkingOptions, setParkingOptions] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([listStrategies(), listMethods()]);
      const active = s.active || '';
      const strat = s.strategies.find(x => x.name === active) || null;
      const parkings = m.filter(x => x.kind === 'parking').map(x => x.name);
      const parkingSet = new Set(parkings);
      const current =
        (strat?.methods || []).find(mm => parkingSet.has(mm.name))?.name || '';
      setActiveStrategy(active);
      setCurrentParking(current);
      setParkingOptions(parkings);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load parking');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleChange(newName: string) {
    if (!activeStrategy || newName === currentParking) return;
    setBusy(true);
    setError(null);
    try {
      if (currentParking) {
        await removeStrategyMethod(activeStrategy, currentParking);
      }
      if (newName) {
        await addStrategyMethod(activeStrategy, newName);
      }
      await load();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set parking');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="settings-row settings-row-active">
      <span className="settings-label">Method</span>
      <div className="settings-row-controls">
        <select
          className="settings-input"
          value={currentParking}
          onChange={e => handleChange(e.target.value)}
          disabled={busy || !activeStrategy}
          title={
            activeStrategy
              ? `Sets the parking method on strategy "${activeStrategy}"`
              : 'No active strategy'
          }
        >
          <option value="">(none)</option>
          {parkingOptions.map(n => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        {error && (
          <span style={{ color: 'var(--red)', fontSize: 11 }}>{error}</span>
        )}
      </div>
    </div>
  );
}


function EditIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function DuplicateIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

const iconBtnStyle: React.CSSProperties = {
  width: 26,
  height: 26,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--paper-mute)',
  border: '1px solid transparent',
  transition: 'color .15s, border-color .15s',
};

function StrategySection({
  activeDraft,
  onActiveChange,
  reloadTick,
}: {
  activeDraft: unknown;
  onActiveChange: (name: string) => void;
  reloadTick: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [strategies, setStrategies] = useState<StrategySummary[] | null>(null);
  const [methods, setMethods] = useState<MethodInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Editor draft state. editing === null → no editor open.
  // isNew distinguishes "create" (createStrategy) from "edit existing".
  const [editing, setEditing] = useState<string | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftDescription, setDraftDescription] = useState('');
  const [draftReviewer, setDraftReviewer] = useState(false);
  const [draftMethods, setDraftMethods] = useState<StrategyMethod[]>([]);
  const [origMethods, setOrigMethods] = useState<StrategyMethod[]>([]);
  const [pickerMethod, setPickerMethod] = useState('');

  const activeName =
    typeof activeDraft === 'string' && activeDraft !== '' ? activeDraft : '';

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, m] = await Promise.all([listStrategies(), listMethods()]);
        if (cancelled) return;
        setStrategies(s.strategies);
        setMethods(m);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load strategies');
      }
    })();
    return () => { cancelled = true; };
  }, [refreshKey, reloadTick]);

  function openEdit(s: StrategySummary) {
    setEditing(s.name);
    setIsNew(false);
    setDraftName(s.name);
    setDraftDescription(s.description || '');
    setDraftReviewer(Boolean(s.reviewer));
    setDraftMethods((s.methods || []).map(m => ({ ...m })));
    setOrigMethods((s.methods || []).map(m => ({ ...m })));
    setPickerMethod('');
    setError(null);
  }

  function openNew() {
    setEditing('');
    setIsNew(true);
    setDraftName('');
    setDraftDescription('');
    setDraftReviewer(false);
    setDraftMethods([]);
    setOrigMethods([]);
    setPickerMethod('');
    setError(null);
  }

  function closeEditor() {
    setEditing(null);
    setIsNew(false);
    setError(null);
  }

  const draftMethodNames = new Set(draftMethods.map(m => m.name));
  const addable = (methods || [])
    .filter(m => !draftMethodNames.has(m.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  function addMethod() {
    if (!pickerMethod || draftMethodNames.has(pickerMethod)) return;
    setDraftMethods(prev => [...prev, { name: pickerMethod, config: {} }]);
    setPickerMethod('');
  }

  function removeMethod(name: string) {
    setDraftMethods(prev => prev.filter(m => m.name !== name));
  }

  async function handleSaveEdit() {
    setBusy(true);
    setError(null);
    try {
      if (isNew) {
        const name = draftName.trim();
        if (!name) throw new Error('Strategy name is required');
        if ((strategies || []).some(s => s.name === name)) {
          throw new Error(`Strategy "${name}" already exists`);
        }
        await createStrategy({
          name,
          description: draftDescription.trim() || undefined,
          reviewer: draftReviewer,
          methods: draftMethods.map(m => ({ name: m.name, ...m.config })),
        });
      } else {
        const target = editing as string;
        await updateStrategyMetadata(target, {
          description: draftDescription.trim(),
          reviewer: draftReviewer,
        });
        const origNames = new Set(origMethods.map(m => m.name));
        for (const m of draftMethods) {
          if (!origNames.has(m.name)) await addStrategyMethod(target, m.name);
        }
        for (const m of origMethods) {
          if (!draftMethodNames.has(m.name)) await removeStrategyMethod(target, m.name);
        }
      }
      closeEditor();
      setRefreshKey(k => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save strategy');
    } finally {
      setBusy(false);
    }
  }

  async function handleDuplicate(s: StrategySummary) {
    const newName = prompt(`Duplicate "${s.name}" as:`, `${s.name}-copy`);
    if (!newName) return;
    const trimmed = newName.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await duplicateStrategy(s.name, trimmed);
      setRefreshKey(k => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to duplicate');
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(s: StrategySummary) {
    if (!confirm(`Delete strategy "${s.name}"? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteStrategy(s.name);
      if (editing === s.name) closeEditor();
      setRefreshKey(k => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setBusy(false);
    }
  }

  async function handleResetOverride(s: StrategySummary) {
    if (!s.user_override) return;
    if (!confirm(
      `Reset strategy "${s.name}" to the built-in manifest? ` +
      `This deletes your local override.`,
    )) return;
    setBusy(true);
    setError(null);
    try {
      await resetStrategyOverride(s.name);
      if (editing === s.name) closeEditor();
      setRefreshKey(k => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset');
    } finally {
      setBusy(false);
    }
  }

  const count = strategies?.length ?? 0;

  return (
    <div className="settings-section">
      <button
        className="settings-section-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className={`settings-chevron ${expanded ? 'expanded' : ''}`}>&#9656;</span>
        <span className="settings-section-title">Strategy</span>
        <span className="settings-section-count">{count}</span>
      </button>
      {expanded && (
        <div className="settings-section-body">
          {error && (
            <div className="settings-row settings-row-muted">
              <span className="settings-label" style={{ color: 'var(--down)' }}>
                {error}
              </span>
            </div>
          )}

          <div className="settings-row settings-row-active">
            <span className="settings-label">Active</span>
            <div className="settings-row-controls">
              <select
                className="settings-input"
                value={activeName}
                onChange={e => onActiveChange(e.target.value)}
                disabled={!strategies}
              >
                <option value="">(none)</option>
                {(strategies || []).map(s => (
                  <option key={s.name} value={s.name}>
                    {s.name}{s.user_override ? ' (override)' : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Strategy list with per-row actions */}
          <ul style={{ listStyle: 'none', margin: '4px 0 0 0', padding: 0 }}>
            {(strategies || []).map(s => {
              const isActive = s.name === activeName;
              const isEditing = editing === s.name && !isNew;
              return (
                <li
                  key={s.name}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 10,
                    padding: '6px 12px',
                    borderBottom: '1px dotted var(--rule)',
                    background: isEditing ? 'var(--amber-trace)' : undefined,
                  }}
                >
                  <span style={{
                    display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0,
                  }}>
                    <span style={{
                      fontFamily: 'var(--mono)', fontSize: 13,
                      color: isActive ? 'var(--amber)' : 'var(--paper)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {s.name}
                    </span>
                    {isActive && (
                      <span style={{
                        fontFamily: 'var(--sans)', fontSize: 9, fontWeight: 700,
                        letterSpacing: '0.16em', textTransform: 'uppercase',
                        color: 'var(--amber)',
                      }}>
                        active
                      </span>
                    )}
                    {s.user_override && (
                      <span style={{
                        fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--paper-mute)',
                      }}>
                        override
                      </span>
                    )}
                    <span style={{
                      fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--paper-mute)',
                    }}>
                      {s.methods?.length ?? 0}m
                    </span>
                  </span>
                  <span style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                    <button
                      style={iconBtnStyle}
                      title="Edit strategy"
                      disabled={busy}
                      onClick={() => openEdit(s)}
                      onMouseEnter={e => (e.currentTarget.style.color = 'var(--amber)')}
                      onMouseLeave={e => (e.currentTarget.style.color = 'var(--paper-mute)')}
                    >
                      <EditIcon />
                    </button>
                    <button
                      style={iconBtnStyle}
                      title="Duplicate strategy"
                      disabled={busy}
                      onClick={() => handleDuplicate(s)}
                      onMouseEnter={e => (e.currentTarget.style.color = 'var(--amber)')}
                      onMouseLeave={e => (e.currentTarget.style.color = 'var(--paper-mute)')}
                    >
                      <DuplicateIcon />
                    </button>
                    {s.user_override && (
                      <button
                        className="settings-btn settings-btn-cancel"
                        style={{ padding: '2px 8px', fontSize: 10 }}
                        title={`Delete the user-override TOML and fall back to the built-in "${s.name}" manifest`}
                        disabled={busy}
                        onClick={() => handleResetOverride(s)}
                      >
                        Reset
                      </button>
                    )}
                    {s.user_override && (
                      <button
                        style={iconBtnStyle}
                        title="Delete strategy (removes user override)"
                        disabled={busy}
                        onClick={() => handleDelete(s)}
                        onMouseEnter={e => (e.currentTarget.style.color = 'var(--down)')}
                        onMouseLeave={e => (e.currentTarget.style.color = 'var(--paper-mute)')}
                      >
                        <TrashIcon />
                      </button>
                    )}
                  </span>
                </li>
              );
            })}
            {strategies && strategies.length === 0 && (
              <li style={{ color: 'var(--paper-mute)', fontSize: 12, padding: '6px 12px' }}>
                No strategies defined.
              </li>
            )}
          </ul>

          {editing === null && (
            <button
              className="settings-btn settings-btn-cancel"
              style={{ marginTop: 10 }}
              onClick={openNew}
              disabled={busy}
            >
              + New strategy
            </button>
          )}

          {/* Editor */}
          {editing !== null && (
            <div style={{
              marginTop: 12,
              border: '1px solid var(--rule)',
              borderRadius: 0,
              padding: '12px',
              background: 'var(--ink-card)',
            }}>
              <div style={{
                fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 700,
                letterSpacing: '0.16em', textTransform: 'uppercase',
                color: 'var(--amber)', marginBottom: 10,
              }}>
                {isNew ? 'New strategy' : `Editing: ${editing}`}
              </div>

              {isNew && (
                <div className="settings-row settings-row-active">
                  <span className="settings-label">Name</span>
                  <div className="settings-row-controls">
                    <input
                      className="settings-input"
                      type="text"
                      value={draftName}
                      placeholder="my-strategy"
                      onChange={e => setDraftName(e.target.value)}
                      style={{ textAlign: 'left' }}
                    />
                  </div>
                </div>
              )}

              <div className="settings-row settings-row-active" style={{ display: 'block' }}>
                <span className="settings-label">Description</span>
                <textarea
                  className="settings-input"
                  value={draftDescription}
                  placeholder="What this strategy does"
                  onChange={e => setDraftDescription(e.target.value)}
                  rows={2}
                  style={{ width: '100%', textAlign: 'left', marginTop: 6, resize: 'vertical' }}
                />
              </div>

              <div className="settings-row settings-row-active">
                <span className="settings-label">Reviewer</span>
                <div className="settings-row-controls">
                  <label className="settings-toggle">
                    <input
                      type="checkbox"
                      checked={draftReviewer}
                      onChange={e => setDraftReviewer(e.target.checked)}
                    />
                    <span className="settings-toggle-slider" />
                  </label>
                </div>
              </div>

              <div className="settings-row settings-row-active" style={{ display: 'block' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span className="settings-label">Methods</span>
                  <span className="settings-section-count">{draftMethods.length}</span>
                </div>
                <ul style={{ listStyle: 'none', margin: '6px 0 0 0', padding: 0 }}>
                  {draftMethods.map(m => (
                    <li
                      key={m.name}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        fontFamily: 'var(--mono)', fontSize: 12,
                        padding: '3px 0', color: 'var(--paper)',
                      }}
                    >
                      <span>
                        • {m.name}
                        {Object.keys(m.config || {}).length > 0 && (
                          <span style={{ color: 'var(--paper-mute)' }}>
                            {' '}{JSON.stringify(m.config)}
                          </span>
                        )}
                      </span>
                      <button
                        style={iconBtnStyle}
                        title="Remove method"
                        onClick={() => removeMethod(m.name)}
                        onMouseEnter={e => (e.currentTarget.style.color = 'var(--down)')}
                        onMouseLeave={e => (e.currentTarget.style.color = 'var(--paper-mute)')}
                      >
                        <TrashIcon />
                      </button>
                    </li>
                  ))}
                  {draftMethods.length === 0 && (
                    <li style={{ color: 'var(--paper-mute)', fontSize: 12 }}>(none)</li>
                  )}
                </ul>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
                  <select
                    className="settings-input"
                    value={pickerMethod}
                    onChange={e => setPickerMethod(e.target.value)}
                    style={{ flex: 1, textAlign: 'left' }}
                    disabled={addable.length === 0}
                  >
                    <option value="">
                      {addable.length === 0 ? '— no methods available —' : '— pick a method —'}
                    </option>
                    {addable.map(m => (
                      <option key={m.name} value={m.name}>
                        {m.name} [{m.assets.join(',') || '-'}]
                      </option>
                    ))}
                  </select>
                  <button
                    className="settings-btn settings-btn-cancel"
                    onClick={addMethod}
                    disabled={!pickerMethod}
                  >
                    + Add
                  </button>
                </div>
              </div>

              <div style={{
                display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12,
              }}>
                <button
                  className="settings-btn settings-btn-cancel"
                  onClick={closeEditor}
                  disabled={busy}
                >
                  Cancel
                </button>
                <button
                  className="settings-btn settings-btn-save"
                  onClick={handleSaveEdit}
                  disabled={busy || (isNew && !draftName.trim())}
                >
                  {busy ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ── Retirement Allocation section ────────────────────────────────────
//
// Custom widget for settings.toml [retirement_allocation].positions —
// a list of {symbol, alloc} that describes how the retirement method
// splits its equity slice across symbols. Per-position allocs are
// relative weights summing to 1.0 (displayed as % in the UI).
//
// NOTE: the retirement method's *equity slice* (how much of the
// account it controls) is NOT set here — it's the method's `equity_pct`
// in the active strategy's TOML. This widget only edits the symbol pie.
// The generic settings tree can't render arrays-of-tables; this owns it.

interface DraftPosition {
  symbol: string;
  allocPct: string;       // user-facing %, e.g. "25"
}

function RetirementAllocationSection({ reloadTick }: { reloadTick: number }) {
  // Section collapsed by default — most operators don't touch this every
  // time they open Settings. Expand on click.
  const [expanded, setExpanded] = useState(false);
  const [positions, setPositions] = useState<DraftPosition[]>([]);
  // Snapshot of what's on the server, used to detect "user cleared a
  // previously-saved allocation" (so Save is enabled to persist the empty list).
  const [loadedCount, setLoadedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await getRetirementAllocation();
        if (cancelled) return;
        const loaded = (data.positions || []).map(p => ({
          symbol: p.symbol,
          allocPct: String(Math.round(p.alloc * 1000) / 10),
        }));
        setPositions(loaded);
        setLoadedCount(loaded.length);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshKey, reloadTick]);

  function updatePosition(i: number, patch: Partial<DraftPosition>) {
    setPositions(prev => prev.map((p, idx) => idx === i ? { ...p, ...patch } : p));
  }

  function addRow() {
    // First row auto-fills to 100% (most likely intent for a single-line
    // pie). Subsequent rows default to 0% — they're drafts until the user
    // assigns weight; 0% rows are dropped at save time.
    setPositions(prev => {
      const allocPct = prev.length === 0 ? '100' : '0';
      return [...prev, { symbol: '', allocPct }];
    });
  }

  function removeRow(i: number) {
    setPositions(prev => prev.filter((_, idx) => idx !== i));
  }

  // "Effective" positions = those that would actually be persisted:
  // non-empty symbol AND positive alloc. 0% / blank rows are drafts.
  const effective: { symbol: string; allocPct: number; idx: number }[] = [];
  positions.forEach((p, idx) => {
    const sym = p.symbol.trim().toUpperCase();
    const n = Number(p.allocPct);
    if (sym && Number.isFinite(n) && n > 0) {
      effective.push({ symbol: sym, allocPct: n, idx });
    }
  });
  const effectiveTotal = effective.reduce((acc, e) => acc + e.allocPct, 0);
  const effectiveTotalOk = effective.length === 0 || Math.abs(effectiveTotal - 100) < 0.5;

  // Duplicate detection across effective rows (case-insensitive, trim).
  const dupSymbols = new Set<string>();
  {
    const seen = new Set<string>();
    for (const e of effective) {
      if (seen.has(e.symbol)) dupSymbols.add(e.symbol);
      seen.add(e.symbol);
    }
  }
  // Mark each row's symbol field as duplicate (for visual error state).
  const rowIsDup = positions.map(p => {
    const s = p.symbol.trim().toUpperCase();
    return s.length > 0 && dupSymbols.has(s);
  });

  // Save enabled in two cases:
  //  (a) Effective rows exist, sum to 100%, no duplicates → save the pie.
  //  (b) Empty list AND server has a non-empty list → "Clear (pause)"
  //      action persists the empty list.
  const hasEffective = effective.length > 0;
  const noDups = dupSymbols.size === 0;
  const canSave = !saving && (
    (hasEffective && effectiveTotalOk && noDups)
    || (positions.length === 0 && loadedCount > 0)
  );

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    setError(null);
    setSavedFlash(false);
    try {
      // Persist only effective positions — drop 0% / blank-symbol drafts.
      const cleaned: RetirementPosition[] = effective.map(e => ({
        symbol: e.symbol,
        alloc: e.allocPct / 100,
      }));
      await saveRetirementAllocation({ positions: cleaned });
      setSavedFlash(true);
      setRefreshKey(k => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  const headerStatusText = loadedCount === 0
    ? 'paused — no allocations'
    : `${loadedCount} ${loadedCount === 1 ? 'position' : 'positions'}`;

  const saveLabel = (positions.length === 0 && loadedCount > 0)
    ? 'Clear (Pause)'
    : 'Save Allocation';

  // Validation hint line under the total — explain WHY Save is disabled.
  let hint = '';
  if (positions.length === 0 && loadedCount === 0) {
    hint = 'Add a position to begin.';
  } else if (!hasEffective && positions.length > 0) {
    hint = 'Assign a non-zero allocation to at least one row.';
  } else if (!noDups) {
    hint = `Duplicate symbol${dupSymbols.size === 1 ? '' : 's'}: ${[...dupSymbols].join(', ')}`;
  } else if (hasEffective && !effectiveTotalOk) {
    hint = 'Non-zero allocations must sum to 100%.';
  }

  return (
    <div className="settings-section">
      <button
        className="settings-section-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className={`settings-chevron ${expanded ? 'expanded' : ''}`}>&#9656;</span>
        <span className="settings-section-title">Retirement Allocation</span>
        <span className="settings-section-count">{headerStatusText}</span>
      </button>
      {expanded && (
        <div className="settings-section-body">
          {error && (
            <div className="settings-row settings-row-muted">
              <span className="settings-label" style={{ color: 'var(--red)' }}>
                {error}
              </span>
            </div>
          )}
          {loading ? (
            <div className="settings-row settings-row-muted">
              <span className="settings-label">Loading...</span>
            </div>
          ) : (
            <>
              <div className="settings-row settings-row-muted" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                <span className="settings-label">
                  Symbol pie only. The retirement method's equity slice is set
                  via its <code>equity_pct</code> in the active strategy.
                </span>
              </div>
              <div className="settings-row settings-row-active" style={{ display: 'block' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span className="settings-label">Positions</span>
                  <span className="settings-section-count">{positions.length}</span>
                </div>
                <table
                  style={{
                    width: '100%', marginTop: 6, borderCollapse: 'collapse',
                    fontFamily: 'var(--font-mono)', fontSize: 13,
                  }}
                >
                  <thead>
                    <tr style={{ color: 'var(--text-muted)', fontSize: 11, textAlign: 'left' }}>
                      <th style={{ padding: '4px 8px 4px 0', fontWeight: 'normal' }}>Symbol</th>
                      <th style={{ padding: '4px 8px', fontWeight: 'normal', textAlign: 'right' }}>Alloc %</th>
                      <th style={{ width: 32 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p, i) => {
                      const isDup = rowIsDup[i];
                      return (
                        <tr key={i}>
                          <td style={{ padding: '2px 8px 2px 0' }}>
                            <input
                              type="text"
                              className="settings-input"
                              value={p.symbol}
                              placeholder="VTI"
                              onChange={e => updatePosition(i, { symbol: e.target.value })}
                              style={{
                                width: '100%',
                                textTransform: 'uppercase',
                                borderColor: isDup ? 'var(--red)' : undefined,
                              }}
                              title={isDup ? 'Duplicate symbol' : undefined}
                            />
                          </td>
                          <td style={{ padding: '2px 8px', textAlign: 'right' }}>
                            <input
                              type="number"
                              className="settings-input"
                              value={p.allocPct}
                              min={0}
                              max={100}
                              step={0.5}
                              onChange={e => updatePosition(i, { allocPct: e.target.value })}
                              style={{ width: 80, textAlign: 'right' }}
                            />
                          </td>
                          <td style={{ padding: '2px 0', textAlign: 'center' }}>
                            <button
                              type="button"
                              className="settings-btn settings-btn-cancel"
                              onClick={() => removeRow(i)}
                              title="Remove this position"
                              style={{ padding: '2px 8px', fontSize: 14, lineHeight: 1 }}
                            >
                              −
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                    {positions.length === 0 && (
                      <tr>
                        <td colSpan={3} style={{
                          padding: '8px 0', color: 'var(--text-muted)',
                          fontSize: 12, fontStyle: 'italic',
                        }}>
                          No positions configured — strategy is paused.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  marginTop: 8,
                }}>
                  <button
                    type="button"
                    className="settings-btn settings-btn-cancel"
                    onClick={addRow}
                  >
                    + Add position
                  </button>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12,
                    color: !hasEffective
                      ? 'var(--text-muted)'
                      : (effectiveTotalOk && noDups ? 'var(--green)' : 'var(--red)'),
                  }}>
                    Total: {effectiveTotal.toFixed(1)}%
                    {hasEffective && (effectiveTotalOk && noDups ? ' ✓' : ' ⚠')}
                  </span>
                </div>
                {hint && (
                  <div style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11,
                    color: 'var(--text-muted)', marginTop: 4,
                  }}>
                    {hint}
                  </div>
                )}
              </div>
              <div className="settings-row settings-row-active" style={{ justifyContent: 'flex-end' }}>
                {savedFlash && (
                  <span style={{
                    color: 'var(--green)', fontSize: 12, marginRight: 12,
                    fontFamily: 'var(--font-mono)',
                  }}>
                    Saved
                  </span>
                )}
                <button
                  className="settings-btn settings-btn-save"
                  disabled={!canSave}
                  onClick={handleSave}
                >
                  {saving ? 'Saving...' : saveLabel}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}


export default function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getSettings();
      setSettings(data);
      const d: Record<string, unknown> = {};
      for (const [key, entry] of Object.entries(data)) {
        d[key] = entry.current;
      }
      setDraft(d);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
    }
  }, []);

  useEffect(() => {
    if (open) {
      load();
      setSaved(false);
    }
  }, [open, load]);

  if (!open) return null;

  if (!settings) {
    return (
      <div className="settings-backdrop" onClick={onClose}>
        <div className="settings-modal" onClick={e => e.stopPropagation()}>
          <div className="settings-header">
            <span className="settings-title">Settings</span>
            <button className="settings-close" onClick={onClose}>&times;</button>
          </div>
          <div className="settings-body">
            <div className="settings-loading">{error || 'Loading...'}</div>
          </div>
        </div>
      </div>
    );
  }

  const dirty = Object.keys(settings).some(key => !deepEqual(draft[key], settings[key].current));

  function handleChange(key: string, value: unknown) {
    setDraft(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  function handleReset(key: string) {
    setDraft(prev => ({ ...prev, [key]: null }));
    setSaved(false);
  }

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    setError(null);
    try {
      const updates: Record<string, unknown> = {};
      const deletes: string[] = [];
      for (const key of Object.keys(settings)) {
        if (!deepEqual(draft[key], settings[key].current)) {
          if (draft[key] === null) {
            deletes.push(key);
          } else {
            updates[key] = draft[key];
          }
        }
      }
      if (deletes.length) {
        await deleteSettings(deletes);
      }
      if (Object.keys(updates).length) {
        await putSettings(unflatten(updates));
      }
      await load();
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    if (settings) {
      const d: Record<string, unknown> = {};
      for (const [key, entry] of Object.entries(settings)) {
        d[key] = entry.current;
      }
      setDraft(d);
    }
    setSaved(false);
    onClose();
  }

  // The Strategy section owns `strategy.active`; the Retirement Allocation
  // section owns everything under `retirement_allocation.*`. Hide both from
  // the generic tree so they're not editable twice.
  const filteredKeys = Object.keys(settings).filter(k =>
    k !== 'strategy.active' && !k.startsWith('retirement_allocation.'),
  );
  const tree = buildTree(filteredKeys, '');

  function renderRows(keys: string[]) {
    return keys.map(key => (
      <SettingRow
        key={key}
        settingKey={key}
        entry={settings![key]}
        draftValue={draft[key]}
        onChange={handleChange}
        onReset={handleReset}
      />
    ));
  }

  function renderTree(t: Tree): React.ReactNode {
    return (
      <>
        {renderRows(t.leafKeys)}
        {Object.keys(t.subSections).map(sub => (
          <Section key={sub} title={sub} defaultOpen={false} count={countKeys(t.subSections[sub])}>
            {renderTree(t.subSections[sub])}
          </Section>
        ))}
      </>
    );
  }

  return (
    <div className="settings-backdrop" onClick={handleCancel}>
      <div className="settings-modal" onClick={e => e.stopPropagation()}>
        <div className="settings-header">
          <span className="settings-title">Settings</span>
          <button className="settings-close" onClick={handleCancel}>&times;</button>
        </div>
        <div className="settings-body">
          <StrategySection
            activeDraft={draft['strategy.active']}
            onActiveChange={name => handleChange('strategy.active', name)}
            reloadTick={settings ? Object.keys(settings).length : 0}
          />
          <RetirementAllocationSection
            reloadTick={settings ? Object.keys(settings).length : 0}
          />
          {tree.leafKeys.length > 0 && (
            <Section title="General" defaultOpen={false} count={tree.leafKeys.length}>
              {renderRows(tree.leafKeys)}
            </Section>
          )}
          {Object.keys(tree.subSections).map(prefix => (
            <Section
              key={prefix}
              title={prefix}
              defaultOpen={false}
              count={countKeys(tree.subSections[prefix])}
            >
              {prefix === 'parking' && (
                <ParkingPicker onChanged={() => { /* settings unchanged */ }} />
              )}
              {renderTree(tree.subSections[prefix])}
            </Section>
          ))}
        </div>
        <div className="settings-footer">
          {error && <span className="settings-error-msg">{error}</span>}
          {saved && <span className="settings-saved-msg">Saved</span>}
          <div className="settings-footer-buttons">
            <button className="settings-btn settings-btn-cancel" onClick={handleCancel}>Cancel</button>
            <button
              className="settings-btn settings-btn-save"
              onClick={handleSave}
              disabled={!dirty || saving}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
