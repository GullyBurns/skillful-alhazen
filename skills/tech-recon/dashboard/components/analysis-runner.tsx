'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { T } from './tokens';
import { Icon, MarkdownContent } from './atoms';

/** Try to parse a string as a JSON array. Returns null if not JSON or not an array. */
function tryParseJsonArray(s: string | undefined): Record<string, unknown>[] | null {
  if (!s) return null;
  const trimmed = s.trim();
  if (!trimmed.startsWith('[') && !trimmed.startsWith('{')) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) return parsed as Record<string, unknown>[];
    if (typeof parsed === 'object' && parsed !== null) return [parsed as Record<string, unknown>];
    return null;
  } catch {
    return null;
  }
}

/** Render a value as a table cell — nested arrays become inline sub-tables. */
function CellValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span style={{ color: T.fgFaint, fontStyle: 'italic' }}>--</span>;

  if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
    const rows = value as Record<string, unknown>[];
    const cols = Object.keys(rows[0]);
    return (
      <table style={{ fontSize: 11, borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            {cols.map(c => (
              <th key={c} style={{
                border: `1px solid ${T.borderDim}`,
                padding: '4px 8px',
                textAlign: 'left',
                fontWeight: 500,
                color: T.fgDim,
                whiteSpace: 'nowrap',
                fontFamily: T.mono,
                fontSize: 10,
              }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map(c => (
                <td key={c} style={{
                  border: `1px solid ${T.borderDim}`,
                  padding: '4px 8px',
                  verticalAlign: 'top',
                }}><CellValue value={row[c]} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (typeof value === 'number') return <span>{value.toFixed(4).replace(/\.?0+$/, '')}</span>;

  if (typeof value === 'object' && !Array.isArray(value)) {
    return (
      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
        {Object.entries(value as Record<string, unknown>)
          .map(([k, v]) => `${k}:${v}`)
          .join(' ')}
      </span>
    );
  }

  return <span>{String(value)}</span>;
}

/** Render an array of objects as a table. */
function TableRenderer({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <p style={{ fontSize: 13, color: T.fgDim }}>No rows.</p>;
  const cols = Object.keys(data[0]);

  return (
    <div style={{ overflowX: 'auto', borderRadius: 4, border: `1px solid ${T.borderDim}` }}>
      <table style={{ fontSize: 12, width: '100%', borderCollapse: 'collapse' }}>
        <thead style={{ background: T.bgSunken }}>
          <tr>
            {cols.map(c => (
              <th key={c} style={{
                border: `1px solid ${T.borderDim}`,
                padding: '8px 12px',
                textAlign: 'left',
                fontWeight: 600,
                color: T.fgDim,
                whiteSpace: 'nowrap',
                fontFamily: T.mono,
                fontSize: 10.5,
                letterSpacing: '0.4px',
                textTransform: 'uppercase',
              }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 1 ? 'rgba(12,22,40,0.3)' : 'transparent' }}>
              {cols.map(c => (
                <td key={c} style={{
                  border: `1px solid ${T.borderDim}`,
                  padding: '6px 12px',
                  verticalAlign: 'top',
                  color: T.fg,
                }}><CellValue value={row[c]} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// PlotContainer mounts an Observable Plot element into the DOM
function PlotContainer({ plotCode, data }: { plotCode: string; data: unknown[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    let cancelled = false;

    (async () => {
      try {
        const Plot = await import('@observablehq/plot');
        if (cancelled) return;
        // eslint-disable-next-line no-new-func
        const plotEl = new Function('Plot', 'data', `return ${plotCode}`)(Plot, data);
        if (cancelled || !containerRef.current) return;
        containerRef.current.replaceChildren(plotEl);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();

    return () => { cancelled = true; };
  }, [plotCode, data]);

  if (error) {
    return (
      <div style={{
        background: 'rgba(200,80,80,0.1)',
        color: '#e05555',
        padding: '12px 16px',
        borderRadius: 4,
        fontSize: 13,
      }}>
        <strong>Plot render error:</strong> {error}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        overflowX: 'auto',
        borderRadius: 4,
        background: '#0f1729',
        padding: 16,
        border: `1px solid ${T.borderDim}`,
      }}
    />
  );
}

export interface AnalysisRunnerProps {
  analysisId: string;
  title: string;
  description?: string;
  plotCode?: string;
  analysisType: string;
}

export function AnalysisRunner({
  analysisId,
  title,
  description,
  plotCode: initialPlotCode,
  analysisType,
}: AnalysisRunnerProps) {
  const typeNorm = analysisType?.toLowerCase() || 'plot';
  const typeColor = T.analysisTypeColor(analysisType);

  const descriptionData = useMemo(() => tryParseJsonArray(description), [description]);
  const isDescriptionJson = descriptionData !== null;

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [plotCode, setPlotCode] = useState<string | null>(initialPlotCode ?? null);
  const [data, setData] = useState<unknown[] | null>(() =>
    typeNorm !== 'prose' && descriptionData ? descriptionData : null
  );
  const [proseContent, setProseContent] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(() =>
    typeNorm !== 'prose' && descriptionData !== null
  );

  const handleRun = async () => {
    setRunning(true);
    setRunError(null);
    setPlotCode(null);
    setData(null);
    setProseContent(null);
    setHasRun(false);

    try {
      const res = await fetch(`/api/tech-recon/analysis/${analysisId}/run`);
      if (!res.ok) throw new Error(`Run failed: ${res.status}`);
      const json = await res.json();
      if (json.error) throw new Error(json.error);

      if (typeNorm === 'prose') {
        setProseContent(
          json.content ||
            (Array.isArray(json.data) && json.data.length > 0
              ? JSON.stringify(json.data, null, 2)
              : description || '')
        );
      } else {
        setPlotCode(json.plot_code || null);
        setData(json.data || []);
      }
      setHasRun(true);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  const iconName = typeNorm === 'prose' ? 'doc' : typeNorm === 'table' ? 'bar-chart' : 'bar-chart';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Icon name={iconName} size={16} color={typeColor} />
            <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: T.fg }}>{title}</h2>
            <span style={{
              fontFamily: T.mono,
              fontSize: 10,
              letterSpacing: '0.6px',
              textTransform: 'uppercase',
              padding: '2px 7px',
              borderRadius: 2,
              color: typeColor,
              border: `1px solid ${typeColor}66`,
            }}>{analysisType || 'plot'}</span>
          </div>
          {description && !isDescriptionJson && (
            <p style={{ fontSize: 13, color: T.fgDim, maxWidth: 640, margin: 0, lineHeight: 1.5 }}>{description}</p>
          )}
        </div>

        <button
          onClick={handleRun}
          disabled={running}
          style={{
            fontFamily: T.mono,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.6px',
            padding: '6px 14px',
            borderRadius: 3,
            cursor: running ? 'not-allowed' : 'pointer',
            background: running ? 'transparent' : `${T.teal}33`,
            color: running ? T.fgFaint : T.teal,
            border: `1px solid ${running ? T.borderDim : `${T.teal}4d`}`,
            textTransform: 'uppercase',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            flexShrink: 0,
          }}
        >
          <Icon name={running ? 'refresh' : 'play'} size={14} />
          {running ? 'Running...' : 'Run Analysis'}
        </button>
      </div>

      {/* Error */}
      {runError && (
        <div style={{
          background: 'rgba(200,80,80,0.1)',
          color: '#e05555',
          padding: '12px 16px',
          borderRadius: 4,
          fontSize: 13,
        }}>
          <strong>Run failed:</strong> {runError}
        </div>
      )}

      {/* Loading */}
      {running && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 10,
          padding: '32px 0',
          color: T.fgDim,
          fontSize: 13,
        }}>
          <Icon name="refresh" size={18} />
          Running analysis...
        </div>
      )}

      {/* Results */}
      {!running && hasRun && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {typeNorm === 'prose' && proseContent && (
            <div style={{
              background: T.panel,
              border: `1px solid ${T.borderDim}`,
              borderRadius: 4,
              padding: '16px 20px',
            }}>
              <MarkdownContent content={proseContent} />
            </div>
          )}

          {typeNorm !== 'prose' && plotCode && data !== null && (
            <PlotContainer plotCode={plotCode} data={data} />
          )}

          {typeNorm !== 'prose' && !plotCode && data !== null && data.length > 0 &&
           typeof data[0] === 'object' && data[0] !== null && (
            <TableRenderer data={data as Record<string, unknown>[]} />
          )}

          {typeNorm !== 'prose' && !plotCode && data !== null && data.length > 0 &&
           (typeof data[0] !== 'object' || data[0] === null) && (
            <div>
              <h3 style={{
                fontFamily: T.mono,
                fontSize: 10.5,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '1px',
                color: T.fgDim,
                marginBottom: 8,
              }}>Data ({data.length} records)</h3>
              <pre style={{
                fontFamily: T.mono,
                fontSize: 12,
                background: T.bgSunken,
                border: `1px solid ${T.borderDim}`,
                borderRadius: 4,
                padding: 16,
                overflowX: 'auto',
                maxHeight: 256,
                color: T.fg,
              }}>
                <code>{JSON.stringify(data, null, 2)}</code>
              </pre>
            </div>
          )}

          {typeNorm !== 'prose' && !plotCode && (!data || data.length === 0) && (
            <div style={{ fontSize: 13, color: T.fgDim, textAlign: 'center', padding: '24px 0' }}>
              Analysis returned no data.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
